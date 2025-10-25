from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
import asyncio
import tempfile
import os
import urllib.request
import logging
import json
import time

# 移除用户认证依赖
from aistack.utils.docker_manager import DockerManager
from aistack.utils.build_task_manager import build_task_manager, BuildStatus, BuildTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["镜像管理"])


class BuildImageRequest(BaseModel):
    """构建镜像请求"""
    dockerfile: HttpUrl  # HTTP形式的Dockerfile URL
    image_name: str
    image_tag: str = "latest"
    build_args: Optional[Dict[str, str]] = None


class PullImageRequest(BaseModel):
    """拉取镜像请求"""
    docker_img_url: str  # 镜像URL
    image_tag: str = "latest"


class ImageInfo(BaseModel):
    """镜像信息"""
    id: str
    tags: List[str]
    created: str
    size: int
    architecture: Optional[str] = None
    os: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None


class ImageListResponse(BaseModel):
    """镜像列表响应"""
    images: List[ImageInfo]
    total: int


class ImageOperationResponse(BaseModel):
    """镜像操作响应"""
    success: bool
    message: str
    image_id: Optional[str] = None
    image_name: Optional[str] = None
    task_id: Optional[str] = None


class BuildTaskResponse(BaseModel):
    """构建任务响应"""
    task_id: str
    image_name: str
    image_tag: str
    status: str
    progress: float
    logs: List[str]
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class BuildTaskListResponse(BaseModel):
    """构建任务列表响应"""
    tasks: List[BuildTaskResponse]
    total: int


class ImageManager:
    """镜像管理器"""
    
    def __init__(self):
        self.docker_manager = DockerManager()
    
    async def build_image_from_dockerfile_url(
        self, 
        dockerfile_url: str, 
        image_name: str, 
        image_tag: str = "latest",
        build_args: Optional[Dict[str, str]] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从HTTP URL下载Dockerfile并构建镜像
        
        Args:
            dockerfile_url: Dockerfile的HTTP URL
            image_name: 镜像名称
            image_tag: 镜像标签
            build_args: 构建参数
            task_id: 任务ID，如果提供则更新任务状态
            
        Returns:
            操作结果字典
        """
        temp_dir = None
        try:
            logger.info(f"开始从URL构建镜像: {dockerfile_url}")
            
            if task_id:
                build_task_manager.update_task_status(task_id, BuildStatus.DOWNLOADING, 10.0)
                build_task_manager.add_log(task_id, f"开始下载Dockerfile: {dockerfile_url}")
            
            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix="docker_build_")
            logger.info(f"创建临时目录: {temp_dir}")
            
            # 下载Dockerfile
            dockerfile_path = os.path.join(temp_dir, "Dockerfile")
            try:
                logger.info(f"下载Dockerfile: {dockerfile_url}")
                urllib.request.urlretrieve(dockerfile_url, dockerfile_path)
                logger.info(f"Dockerfile下载完成: {dockerfile_path}")
                
                if task_id:
                    build_task_manager.update_task_status(task_id, BuildStatus.DOWNLOADING, 20.0)
                    build_task_manager.add_log(task_id, "Dockerfile下载完成")
                    
            except Exception as e:
                error_msg = f"下载Dockerfile失败: {e}"
                if task_id:
                    build_task_manager.update_task_status(task_id, BuildStatus.FAILED, error_message=error_msg)
                return {
                    "success": False,
                    "message": error_msg
                }
            
            # 验证Dockerfile内容（尝试多种编码）
            try:
                content = None
                encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']
                
                for encoding in encodings:
                    try:
                        with open(dockerfile_path, 'r', encoding=encoding) as f:
                            content = f.read().strip()
                            logger.info(f"Dockerfile读取成功，使用编码: {encoding}")
                            break
                    except UnicodeDecodeError:
                        continue
                
                if content is None:
                    error_msg = "无法读取Dockerfile内容，尝试了多种编码都失败"
                    if task_id:
                        build_task_manager.update_task_status(task_id, BuildStatus.FAILED, error_message=error_msg)
                    return {
                        "success": False,
                        "message": error_msg
                    }
                
                if not content:
                    error_msg = "Dockerfile内容为空"
                    if task_id:
                        build_task_manager.update_task_status(task_id, BuildStatus.FAILED, error_message=error_msg)
                    return {
                        "success": False,
                        "message": error_msg
                    }
                
                # 检查是否包含Dockerfile的基本指令
                if not any(keyword in content.upper() for keyword in ['FROM', 'RUN', 'CMD', 'ENTRYPOINT', 'COPY', 'ADD']):
                    logger.warning(f"Dockerfile可能不是有效的: {content[:100]}")
                    
                if task_id:
                    build_task_manager.update_task_status(task_id, BuildStatus.DOWNLOADING, 30.0)
                    build_task_manager.add_log(task_id, "Dockerfile验证通过")
                    
            except Exception as e:
                error_msg = f"无法读取Dockerfile内容: {e}"
                if task_id:
                    build_task_manager.update_task_status(task_id, BuildStatus.FAILED, error_message=error_msg)
                return {
                    "success": False,
                    "message": error_msg
                }
            
            # 构建镜像
            def progress_callback(step: int, total: int, message: str):
                if task_id:
                    progress = 30.0 + (step / total) * 60.0  # 30-90% 用于构建
                    build_task_manager.update_task_status(task_id, BuildStatus.BUILDING, progress)
                    build_task_manager.add_log(task_id, message)
            
            if task_id:
                build_task_manager.update_task_status(task_id, BuildStatus.BUILDING, 30.0)
                build_task_manager.add_log(task_id, "开始构建Docker镜像...")
            
            # 构建镜像（在线程池中运行同步操作）
            import asyncio
            success, message = await asyncio.to_thread(
                self.docker_manager.build_image,
                dockerfile_path=dockerfile_path,
                image_name=image_name,
                image_tag=image_tag,
                build_args=build_args,
                progress_callback=progress_callback
            )
            
            if success:
                if task_id:
                    build_task_manager.update_task_status(task_id, BuildStatus.SUCCESS, 100.0)
                    build_task_manager.add_log(task_id, f"镜像构建成功: {image_name}:{image_tag}")
                
                return {
                    "success": True,
                    "message": message,
                    "image_name": f"{image_name}:{image_tag}",
                    "task_id": task_id
                }
            else:
                if task_id:
                    build_task_manager.update_task_status(task_id, BuildStatus.FAILED, error_message=message)
                    build_task_manager.add_log(task_id, f"镜像构建失败: {message}")
                
                return {
                    "success": False,
                    "message": message,
                    "task_id": task_id
                }
                
        except Exception as e:
            logger.error(f"构建镜像异常: {e}")
            error_msg = f"构建镜像异常: {e}"
            if task_id:
                build_task_manager.update_task_status(task_id, BuildStatus.FAILED, error_message=error_msg)
                build_task_manager.add_log(task_id, error_msg)
            
            return {
                "success": False,
                "message": error_msg,
                "task_id": task_id
            }
        finally:
            # 清理临时目录
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.info(f"清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {e}")
    
    async def pull_image_from_url(
        self, 
        image_url: str, 
        image_tag: str = "latest",
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从镜像URL拉取镜像
        
        Args:
            image_url: 镜像URL
            image_tag: 镜像标签
            task_id: 任务ID，如果提供则更新任务状态
            
        Returns:
            操作结果字典
        """
        try:
            logger.info(f"开始拉取镜像: {image_url}:{image_tag}")
            
            if task_id:
                build_task_manager.update_task_status(task_id, BuildStatus.BUILDING, 10.0)
                build_task_manager.add_log(task_id, f"开始拉取镜像: {image_url}:{image_tag}")
            
            def progress_callback(step: int, total: int, message: str):
                if task_id:
                    progress = 10.0 + (step / total) * 80.0  # 10-90% 用于拉取
                    build_task_manager.update_task_status(task_id, BuildStatus.BUILDING, progress)
                    build_task_manager.add_log(task_id, message)
            
            # 拉取镜像（在线程池中运行同步操作）
            import asyncio
            success, message = await asyncio.to_thread(
                self.docker_manager.pull_image,
                image_name=image_url,
                image_tag=image_tag,
                progress_callback=progress_callback
            )
            
            if success:
                if task_id:
                    build_task_manager.update_task_status(task_id, BuildStatus.SUCCESS, 100.0)
                    build_task_manager.add_log(task_id, f"镜像拉取成功: {image_url}:{image_tag}")
                
                return {
                    "success": True,
                    "message": message,
                    "image_name": f"{image_url}:{image_tag}",
                    "task_id": task_id
                }
            else:
                if task_id:
                    build_task_manager.update_task_status(task_id, BuildStatus.FAILED, error_message=message)
                    build_task_manager.add_log(task_id, f"镜像拉取失败: {message}")
                
                return {
                    "success": False,
                    "message": message,
                    "task_id": task_id
                }
                
        except Exception as e:
            logger.error(f"拉取镜像异常: {e}")
            error_msg = f"拉取镜像异常: {e}"
            if task_id:
                build_task_manager.update_task_status(task_id, BuildStatus.FAILED, error_message=error_msg)
                build_task_manager.add_log(task_id, error_msg)
            
            return {
                "success": False,
                "message": error_msg,
                "task_id": task_id
            }
    
    async def list_images(self) -> Dict[str, Any]:
        """
        列出所有镜像
        
        Returns:
            镜像列表
        """
        try:
            images = self.docker_manager.list_images()
            
            # 转换为ImageInfo格式
            image_list = []
            for img in images:
                image_info = ImageInfo(
                    id=img['id'],
                    tags=img['tags'],
                    created=img['created'],
                    size=img['size']
                )
                image_list.append(image_info)
            
            return {
                "success": True,
                "images": image_list,
                "total": len(image_list)
            }
            
        except Exception as e:
            logger.error(f"列出镜像失败: {e}")
            return {
                "success": False,
                "message": f"列出镜像失败: {e}",
                "images": [],
                "total": 0
            }
    
    async def get_image_info(
        self, 
        image_name: str, 
        image_tag: str = "latest"
    ) -> Dict[str, Any]:
        """
        获取镜像详细信息
        
        Args:
            image_name: 镜像名称
            image_tag: 镜像标签
            
        Returns:
            镜像详细信息
        """
        try:
            success, message, image_info = self.docker_manager.get_image_info(
                image_name=image_name,
                image_tag=image_tag
            )
            
            if success:
                return {
                    "success": True,
                    "message": message,
                    "image_info": image_info
                }
            else:
                return {
                    "success": False,
                    "message": message,
                    "image_info": None
                }
                
        except Exception as e:
            logger.error(f"获取镜像信息失败: {e}")
            return {
                "success": False,
                "message": f"获取镜像信息失败: {e}",
                "image_info": None
            }
    
    async def remove_image(
        self, 
        image_name: str, 
        image_tag: str = "latest"
    ) -> Dict[str, Any]:
        """
        删除镜像
        
        Args:
            image_name: 镜像名称
            image_tag: 镜像标签
            
        Returns:
            操作结果
        """
        try:
            success, message = self.docker_manager.remove_image(
                image_name=image_name,
                image_tag=image_tag
            )
            
            return {
                "success": success,
                "message": message,
                "image_name": f"{image_name}:{image_tag}"
            }
            
        except Exception as e:
            logger.error(f"删除镜像失败: {e}")
            return {
                "success": False,
                "message": f"删除镜像失败: {e}"
            }


# 创建全局镜像管理器实例
image_manager = ImageManager()


@router.post("/build", response_model=ImageOperationResponse, summary="从Dockerfile URL构建镜像")
async def build_image_from_dockerfile(
    request: BuildImageRequest
):
    """
    从HTTP URL下载Dockerfile并构建镜像（同步）
    
    支持通过HTTP URL提供Dockerfile文件来构建Docker镜像
    注意：这是同步操作，会等待构建完成才返回结果
    """
    try:
        # 创建构建任务用于跟踪
        task_id = build_task_manager.create_task(
            image_name=request.image_name,
            image_tag=request.image_tag,
            dockerfile_url=str(request.dockerfile),
            build_args=request.build_args
        )
        
        result = await image_manager.build_image_from_dockerfile_url(
            dockerfile_url=str(request.dockerfile),
            image_name=request.image_name,
            image_tag=request.image_tag,
            build_args=request.build_args,
            task_id=task_id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return ImageOperationResponse(
            success=True,
            message=result["message"],
            image_name=result["image_name"],
            task_id=task_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"构建镜像失败: {e}")


@router.post("/pull", response_model=ImageOperationResponse, summary="拉取镜像")
async def pull_image(
    request: PullImageRequest
):
    """
    从镜像仓库拉取镜像（同步）
    
    支持从Docker Hub或其他镜像仓库拉取镜像
    注意：这是同步操作，会等待拉取完成才返回结果
    """
    try:
        # 创建拉取任务用于跟踪
        task_id = build_task_manager.create_task(
            image_name=request.docker_img_url,
            image_tag=request.image_tag,
            image_url=request.docker_img_url
        )
        
        result = await image_manager.pull_image_from_url(
            image_url=request.docker_img_url,
            image_tag=request.image_tag,
            task_id=task_id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return ImageOperationResponse(
            success=True,
            message=result["message"],
            image_name=result["image_name"],
            task_id=task_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拉取镜像失败: {e}")


@router.get("/", response_model=ImageListResponse, summary="列出所有镜像")
async def list_images():
    """
    列出当前系统中的所有Docker镜像
    
    返回镜像的基本信息，包括ID、标签、创建时间、大小等
    """
    try:
        result = await image_manager.list_images()
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])
        
        return ImageListResponse(
            images=result["images"],
            total=result["total"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出镜像失败: {e}")


@router.get("/info", summary="获取镜像详细信息")
async def get_image_info(
    image_name: str = Query(..., description="镜像名称"),
    tag: str = Query("latest", description="镜像标签")
):
    """
    获取指定镜像的详细信息
    
    包括镜像ID、标签、大小、创建时间、架构、操作系统等信息
    """
    try:
        result = await image_manager.get_image_info(
            image_name=image_name,
            image_tag=tag
        )
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "image_info": result["image_info"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取镜像信息失败: {e}")


@router.delete("/", summary="删除镜像")
async def remove_image(
    image_name: str = Query(..., description="镜像名称"),
    tag: str = Query("latest", description="镜像标签")
):
    """
    删除指定的Docker镜像
    
    注意：删除镜像前请确保没有容器正在使用该镜像
    """
    try:
        result = await image_manager.remove_image(
            image_name=image_name,
            image_tag=tag
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "image_name": result["image_name"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除镜像失败: {e}")


@router.post("/build-async", response_model=ImageOperationResponse, summary="异步构建镜像")
async def build_image_async(
    request: BuildImageRequest,
    background_tasks: BackgroundTasks
):
    """
    异步构建镜像（后台任务）
    
    立即返回任务ID，镜像构建在后台进行
    """
    try:
        # 创建构建任务
        task_id = build_task_manager.create_task(
            image_name=request.image_name,
            image_tag=request.image_tag,
            dockerfile_url=str(request.dockerfile),
            build_args=request.build_args
        )
        
        # 添加后台任务
        background_tasks.add_task(
            image_manager.build_image_from_dockerfile_url,
            str(request.dockerfile),
            request.image_name,
            request.image_tag,
            request.build_args,
            task_id
        )
        
        return ImageOperationResponse(
            success=True,
            message="镜像构建任务已提交",
            task_id=task_id,
            image_name=f"{request.image_name}:{request.image_tag}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交构建任务失败: {e}")


@router.post("/pull-async", response_model=ImageOperationResponse, summary="异步拉取镜像")
async def pull_image_async(
    request: PullImageRequest,
    background_tasks: BackgroundTasks
):
    """
    异步拉取镜像（后台任务）
    
    立即返回任务ID，镜像拉取在后台进行
    """
    try:
        # 创建拉取任务
        task_id = build_task_manager.create_task(
            image_name=request.docker_img_url,
            image_tag=request.image_tag,
            image_url=request.docker_img_url
        )
        
        # 添加后台任务
        background_tasks.add_task(
            image_manager.pull_image_from_url,
            request.docker_img_url,
            request.image_tag,
            task_id
        )
        
        return ImageOperationResponse(
            success=True,
            message="镜像拉取任务已提交",
            task_id=task_id,
            image_name=f"{request.docker_img_url}:{request.image_tag}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交拉取任务失败: {e}")


@router.get("/tasks", response_model=BuildTaskListResponse, summary="获取构建任务列表")
async def get_build_tasks(
    status: Optional[str] = Query(None, description="任务状态过滤")
):
    """
    获取构建任务列表
    
    支持按状态过滤任务
    """
    try:
        status_filter = None
        if status:
            try:
                status_filter = BuildStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的状态值: {status}")
        
        tasks = build_task_manager.list_tasks(status_filter)
        
        # 转换为响应格式
        task_responses = []
        for task in tasks:
            task_response = BuildTaskResponse(
                task_id=task.task_id,
                image_name=task.image_name,
                image_tag=task.image_tag,
                status=task.status.value,
                progress=task.progress,
                logs=task.logs,
                error_message=task.error_message,
                created_at=task.created_at.isoformat(),
                started_at=task.started_at.isoformat() if task.started_at else None,
                completed_at=task.completed_at.isoformat() if task.completed_at else None
            )
            task_responses.append(task_response)
        
        return BuildTaskListResponse(
            tasks=task_responses,
            total=len(task_responses)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {e}")


@router.get("/tasks/{task_id}", response_model=BuildTaskResponse, summary="获取构建任务详情")
async def get_build_task(
    task_id: str
):
    """
    获取指定构建任务的详细信息
    """
    try:
        task = build_task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return BuildTaskResponse(
            task_id=task.task_id,
            image_name=task.image_name,
            image_tag=task.image_tag,
            status=task.status.value,
            progress=task.progress,
            logs=task.logs,
            error_message=task.error_message,
            created_at=task.created_at.isoformat(),
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务详情失败: {e}")


@router.get("/tasks/{task_id}/stream", summary="实时获取构建任务状态")
async def stream_build_task(
    task_id: str
):
    """
    通过SSE实时获取构建任务状态和日志
    
    返回Server-Sent Events流，前端可以通过EventSource连接
    """
    try:
        task = build_task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        async def event_generator():
            # 发送初始状态
            data = {
                'task_id': task.task_id,
                'status': task.status.value,
                'progress': task.progress,
                'logs': task.logs,
                'error_message': task.error_message
            }
            yield f"data: {json.dumps(data)}\n\n"
            
            # 如果任务已完成，直接返回
            if task.status in [BuildStatus.SUCCESS, BuildStatus.FAILED, BuildStatus.CANCELLED]:
                return
            
            # 订阅任务更新
            def on_task_update(updated_task: BuildTask):
                if updated_task.task_id == task_id:
                    return {
                        'task_id': updated_task.task_id,
                        'status': updated_task.status.value,
                        'progress': updated_task.progress,
                        'logs': updated_task.logs,
                        'error_message': updated_task.error_message
                    }
                return None
            
            # 注册回调
            build_task_manager.subscribe(task_id, on_task_update)
            
            try:
                # 等待任务完成或超时
                timeout = 3600  # 1小时超时
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    current_task = build_task_manager.get_task(task_id)
                    if not current_task:
                        break
                    
                    if current_task.status in [BuildStatus.SUCCESS, BuildStatus.FAILED, BuildStatus.CANCELLED]:
                        # 发送最终状态
                        final_data = {
                            'task_id': current_task.task_id,
                            'status': current_task.status.value,
                            'progress': current_task.progress,
                            'logs': current_task.logs,
                            'error_message': current_task.error_message,
                            'completed': True
                        }
                        yield f"data: {json.dumps(final_data)}\n\n"
                        break
                    
                    await asyncio.sleep(1)  # 每秒检查一次
                    
            finally:
                # 取消订阅
                build_task_manager.unsubscribe(task_id, on_task_update)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建SSE流失败: {e}")


@router.delete("/tasks/{task_id}", summary="取消构建任务")
async def cancel_build_task(
    task_id: str
):
    """
    取消指定的构建任务
    
    注意：只能取消正在进行的任务
    """
    try:
        task = build_task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.status in [BuildStatus.SUCCESS, BuildStatus.FAILED, BuildStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="任务已完成，无法取消")
        
        # 更新任务状态为已取消
        build_task_manager.update_task_status(task_id, BuildStatus.CANCELLED, error_message="任务被用户取消")
        build_task_manager.add_log(task_id, "任务被用户取消")
        
        return {
            "success": True,
            "message": "任务已取消",
            "task_id": task_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务失败: {e}")
