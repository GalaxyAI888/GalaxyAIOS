import time
import base64
import httpx
from .api_client import TaskAPIClient
from .minio_manager import MinIOManager
import logging
from aistack.config.config import Config
import multiprocessing
import os
import io
from aistack.utils.process import ensure_tmp_directory


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(process)d %(filename)s:%(lineno)d - %(message)s"
)

logger = logging.getLogger(__name__)

class AIGCProcessor:
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.api = TaskAPIClient()
        self.minio = MinIOManager()
        
        # 确保tmp目录存在
        ensure_tmp_directory()

    def process_task(self, task: dict):
        """处理单个任务（含状态同步更新）"""

        try:
            logger.info(f"开始处理任务: {task['objectId']} | 类型: {task['type']}")
            # 1. 处理任务
            if task["type"] == "txt2img":
                result = self._process_txt2img(task)
            elif task["type"] == "img2img":
                result = self._process_img2img(task)
            elif task["type"] == "txt2speech":
                result = self._process_txt2speech(task)
            elif task["type"] == "txt2music":
                result = self._process_txt2music(task)
            elif task["type"] == "speech2txt":
                result = self._process_speech2txt(task)
            else:
                raise ValueError(f"未知任务类型: {task['type']}")
            
            # 2. 同步更新状态
            logger.info(f"任务 {task['objectId']} 处理成功，正在更新状态...")
            self.api.update_task(
                task_id=task["objectId"],
                status=1,
                account_id=self.account_id,
                result=result
                
            )
            logger.info(f"任务 {task['objectId']} 状态更新成功，任务完成。")
            
        except Exception as e:
            logger.error(f"任务失败: {task['objectId']} - {e}")
            self.api.update_task(task["objectId"], status=-1, account_id=self.account_id)
            raise

    def _process_txt2img(self, task: dict) -> list:
        """文生图任务处理"""
        logger.info(f"开始处理txt2img任务: {task['objectId']} | 参数: {task['data'].get('prompt', 'N/A')[:50]}...")
        response = httpx.post(
            f"{Config().sd_api}/sdapi/v1/txt2img",
            json=task["data"],
            timeout=Config().model_api_timeout
        )
        response.raise_for_status()
        logger.info(f"txt2img任务 {task['objectId']} 处理成功，生成{len(response.json()['images'])}张图片。")
        
        urls = []
        for i, img_data in enumerate(response.json()["images"]):
            object_path = f"{self.account_id}/{task['objectId']}_{i}.png"
            logger.info(f"正在为任务 {task['objectId']} 上传图片 {i+1} 到MinIO: {object_path}")
            url = self.minio.upload_file(
                data=base64.b64decode(img_data),
                object_path=object_path
            )
            urls.append(url)
            logger.info(f"图片 {i+1} 上传成功，URL: {url}")
        logger.info(f"txt2img任务 {task['objectId']} 所有图片上传完成。")
        return urls

    def _process_img2img(self, task: dict) -> list:
        """图生图任务处理"""
        logger.info(f"开始处理img2img任务: {task['objectId']}")
        # 预处理 init_images
        init_images = task["data"].get("init_images", [])
        processed_images = []
        for img in init_images:
            if isinstance(img, str):
                if img.startswith("data:image"):
                    # 去掉前缀
                    base64_data = img.split(",", 1)[-1]
                    processed_images.append(base64_data)
                elif img.startswith("http://") or img.startswith("https://"):
                    # 下载图片并转base64
                    try:
                        resp = httpx.get(img, timeout=Config().model_api_timeout)
                        resp.raise_for_status()
                        b64_img = base64.b64encode(resp.content).decode("utf-8")
                        processed_images.append(b64_img)
                    except Exception as e:
                        logger.error(f"下载图片失败: {img} - {e}")
                        continue
                else:
                    # 假设已是base64
                    processed_images.append(img)
            else:
                logger.warning(f"init_images中存在非字符串类型: {type(img)}，已跳过。")
        task["data"]["init_images"] = processed_images
        response = httpx.post(
            f"{Config().sd_api}/sdapi/v1/img2img",
            json=task["data"],
            timeout=Config().model_api_timeout
        )
        response.raise_for_status()
        logger.info(f"img2img任务 {task['objectId']} 处理成功，生成{len(response.json()['images'])}张图片。")
        
        urls = []
        for i, img_data in enumerate(response.json()["images"]):
            object_path = f"{self.account_id}/{task['objectId']}_{i}.png"
            logger.info(f"正在为任务 {task['objectId']} 上传图片 {i+1} 到MinIO: {object_path}")
            url = self.minio.upload_file(
                data=base64.b64decode(img_data),
                object_path=object_path
            )
            urls.append(url)
            logger.info(f"图片 {i+1} 上传成功，URL: {url}")
        logger.info(f"img2img任务 {task['objectId']} 所有图片上传完成。")
        return urls

    def _process_txt2speech(self, task: dict) -> list:
        """文本转语音任务处理"""
        logger.info(f"开始处理txt2speech任务: {task['objectId']} | 文本长度: {len(task['data'].get('text', ''))}字符")
        response = httpx.post(
            Config().tts_api,
            json=task["data"],
            timeout=Config().model_api_timeout
        )
        response.raise_for_status()
        
        # 检查响应内容类型
        content_type = response.headers.get('content-type', '')
        logger.info(f"TTS API响应内容类型: {content_type}")
        
        if 'audio' in content_type:
            # 直接返回音频文件
            audio_data = response.content
            file_name = f"{task['objectId']}.mp3"
            object_path = f"{self.account_id}/{file_name}"
            logger.info(f"正在为任务 {task['objectId']} 上传音频文件到MinIO: {object_path}")
            url = self.minio.upload_file(
                data=audio_data,
                object_path=object_path
            )
            logger.info(f"音频文件上传成功，URL: {url}")
            return [url]
        else:
            # 尝试解析JSON响应（兼容旧格式）
            try:
                response_json = response.json()
                if 'audio' in response_json:
                    audio_list = response_json["audio"]
                    logger.info(f"txt2speech任务 {task['objectId']} 处理成功，生成{len(audio_list)}个音频片段。")
                    
                    urls = []
                    for i, audio_data_b64 in enumerate(audio_list):
                        audio_data = base64.b64decode(audio_data_b64)
                        file_name = f"{task['objectId']}_{i}.wav"
                        object_path = f"{self.account_id}/{file_name}"
                        logger.info(f"正在为任务 {task['objectId']} 上传音频 {i+1} 到MinIO: {object_path}")
                        url = self.minio.upload_file(
                            data=audio_data,
                            object_path=object_path
                        )
                        urls.append(url)
                        logger.info(f"音频 {i+1} 上传成功，URL: {url}")
                    logger.info(f"txt2speech任务 {task['objectId']} 所有音频上传完成。")
                    return urls
                else:
                    raise ValueError("响应中没有找到audio字段")
            except Exception as e:
                logger.error(f"解析TTS响应失败: {e}")
                raise ValueError(f"无法解析TTS API响应: {e}")

    def _process_txt2music(self, task: dict) -> list:
        """文本转音乐任务处理"""
        logger.info(f"开始处理txt2music任务: {task['objectId']} | 文本长度: {len(task['data'].get('text', ''))}字符")
        response = httpx.post(
            Config().music_api,
            json=task["data"],
            timeout=Config().model_api_timeout
        )
        response.raise_for_status()
        
        # 检查响应内容类型
        content_type = response.headers.get('content-type', '')
        logger.info(f"Music API响应内容类型: {content_type}")
        
        if 'audio' in content_type:
            # 直接返回音频文件
            audio_data = response.content
            file_name = f"{task['objectId']}.mp3"
            object_path = f"{self.account_id}/{file_name}"
            logger.info(f"正在为任务 {task['objectId']} 上传音乐文件到MinIO: {object_path}")
            url = self.minio.upload_file(
                data=audio_data,
                object_path=object_path
            )
            logger.info(f"音乐文件上传成功，URL: {url}")
            return [url]
        else:
            # 尝试解析JSON响应（兼容旧格式）
            try:
                response_json = response.json()
                if 'audio' in response_json:
                    audio_list = response_json["audio"]
                    logger.info(f"txt2music任务 {task['objectId']} 处理成功，生成{len(audio_list)}个音乐片段。")
                    
                    urls = []
                    for i, audio_data_b64 in enumerate(audio_list):
                        audio_data = base64.b64decode(audio_data_b64)
                        file_name = f"{task['objectId']}_{i}.mp3"
                        object_path = f"{self.account_id}/{file_name}"
                        logger.info(f"正在为任务 {task['objectId']} 上传音乐 {i+1} 到MinIO: {object_path}")
                        url = self.minio.upload_file(
                            data=audio_data,
                            object_path=object_path
                        )
                        urls.append(url)
                        logger.info(f"音乐 {i+1} 上传成功，URL: {url}")
                    logger.info(f"txt2music任务 {task['objectId']} 所有音乐上传完成。")
                    return urls
                else:
                    raise ValueError("响应中没有找到audio字段")
            except Exception as e:
                logger.error(f"解析Music API响应失败: {e}")
                raise ValueError(f"无法解析Music API响应: {e}")

    def _process_speech2txt(self, task: dict) -> list:
        """语音转文本任务处理"""
        logger.info(f"开始处理speech2txt任务: {task['objectId']} | 输入音频: {task['data'].get('input', 'N/A')}")
        audio_file_minio_path = task["data"]["input"]
        local_audio_path = f"tmp/{task['objectId']}_audio.wav"

        try:
            logger.info(f"正在从MinIO下载音频文件: {audio_file_minio_path} 到 {local_audio_path}")
            # 从MinIO下载音频文件到本地临时文件
            audio_data_bytes = self.minio.download_file(audio_file_minio_path)
            with open(local_audio_path, 'wb') as f:
                f.write(audio_data_bytes)
            logger.info(f"音频文件下载完成: {local_audio_path}")

            # 发送到语音识别API
            logger.info(f"正在将音频文件发送到语音识别API: {Config().stt_api}")
            with open(local_audio_path, 'rb') as audio_file_obj:
                files = {"file": (os.path.basename(local_audio_path), audio_file_obj, "audio/wav")}
                response = httpx.post(
                    Config().stt_api,
                    files=files,
                    timeout=Config().model_api_timeout
                )
                response.raise_for_status()
            logger.info(f"语音识别API调用成功，响应状态码: {response.status_code}")
        finally:
            # 清理临时音频文件
            if os.path.exists(local_audio_path):
                os.remove(local_audio_path)
                logger.info(f"临时音频文件已清理: {local_audio_path}")

        # 上传识别结果
        text_result = response.json()["text"]
        logger.info(f"语音识别结果获取成功，文本长度: {len(text_result)}字符")
        local_text_path = f"tmp/{task['objectId']}_stt_result.txt"
        file_name_for_minio = f"{task['objectId']}_stt_result.txt"

        try:
            logger.info(f"正在保存识别结果到本地临时文件: {local_text_path}")
            with open(local_text_path, 'w', encoding='utf-8') as f:
                f.write(text_result)
            logger.info(f"识别结果已保存到本地: {local_text_path}")

            # 读取临时文本文件内容为字节以供上传
            with open(local_text_path, 'rb') as f:
                text_bytes_to_upload = f.read()
            
            object_path_minio = f"{self.account_id}/{file_name_for_minio}"
            logger.info(f"正在上传识别结果文件到MinIO: {object_path_minio}")
            url = self.minio.upload_file(
                data=text_bytes_to_upload,
                object_path=object_path_minio
            )
            logger.info(f"识别结果文件上传成功，URL: {url}")
        finally:
            # 清理临时文本文件
            if os.path.exists(local_text_path):
                os.remove(local_text_path)
                logger.info(f"临时文本文件已清理: {local_text_path}")

        return [url]

    def run(self, task_type: str):
        """主循环"""
        logger.info(f"启动任务处理器 | 类型: {task_type} | 账户: {self.account_id}")
        
        while True:
            try:
                logger.info(f"正在获取待处理任务 | 类型: {task_type}")
                tasks = self.api.get_pending_tasks(task_type)
                logger.info(f"获取到 {len(tasks)} 个待处理 {task_type} 任务。")
                
                for task in tasks:
                    if 'data' not in task:
                        if 'inputdata' not in task:
                            logger.error(f"任务 {task['objectId']} 缺少data和inputdata字段，数据格式错误")
                            continue
                        else:
                            task['data'] = task['inputdata']
                    self.process_task(task)
                    
                time.sleep(Config().poll_interval)
                logger.info(f"等待 {Config().poll_interval} 秒后再次检查任务...")
                
            except Exception as e:
                logger.error(f"处理器异常: {e}", exc_info=True)
                time.sleep(60)
                logger.info(f"发生异常，等待60秒后重试...")
