from minio import Minio
from minio.error import S3Error
from aistack.config.config import Config
import logging
import io
import os
from aistack.utils.process import ensure_tmp_directory

logger = logging.getLogger(__name__)

class MinIOManager:
    def __init__(self):
        self.client = Minio(
            Config().minio_endpoint,
            access_key=Config().minio_access_key,
            secret_key=Config().minio_secret_key,
            secure=False
        )
        
        # 确保tmp目录存在
        ensure_tmp_directory()
    
    def upload_file(self, data, object_path):
        # 保存一份到本地，便于调试
        local_filename = object_path.split('/')[-1]
        raw_bytes = data if isinstance(data, bytes) else data.getvalue()
        with open(local_filename, 'wb') as f:
            f.write(raw_bytes)
        try:
            if isinstance(data, bytes):
                data = io.BytesIO(data)
            self.client.put_object(
                Config().minio_bucket,
                object_path,
                data,
                length=data.getbuffer().nbytes
            )
            return f"{Config().minio_endpoint}/{Config().minio_bucket}/{object_path}"
        except S3Error as e:
            logger.error(f"MinIO上传失败: {e}")
            raise
            
    def download_file(self, object_path: str) -> bytes:
        try:
            # 从完整URL中提取对象路径
            if object_path.startswith(f"{Config().minio_endpoint}/{Config().minio_bucket}/"):
                object_path = object_path.replace(f"{Config().minio_endpoint}/{Config().minio_bucket}/", "")
                
            response = self.client.get_object(
                Config().minio_bucket,
                object_path
            )
            
            with response:
                return response.read()
                
        except S3Error as e:
            logger.error(f"MinIO下载失败: {e}")
            raise
