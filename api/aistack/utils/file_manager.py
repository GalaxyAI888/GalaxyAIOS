import os
import shutil
import zipfile
import tarfile
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class FileManager:
    """文件管理工具类"""
    
    def __init__(self, base_path: str = "./data"):
        """
        初始化文件管理器
        
        Args:
            base_path: 基础数据目录
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"文件管理器初始化，基础路径: {self.base_path}")
    
    def create_app_directory(self, app_name: str) -> Path:
        """
        为应用创建目录
        
        Args:
            app_name: 应用名称
            
        Returns:
            应用目录路径
        """
        app_dir = self.base_path / app_name
        app_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"创建应用目录: {app_dir}")
        return app_dir
    
    def create_volume_directory(self, app_name: str, volume_name: str) -> Path:
        """
        为应用卷创建目录
        
        Args:
            app_name: 应用名称
            volume_name: 卷名称
            
        Returns:
            卷目录路径
        """
        volume_dir = self.base_path / app_name / volume_name
        volume_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"创建卷目录: {volume_dir}")
        return volume_dir
    
    def list_files(self, directory_path: str, recursive: bool = False) -> List[Dict]:
        """
        列出目录中的文件
        
        Args:
            directory_path: 目录路径
            recursive: 是否递归列出子目录
            
        Returns:
            文件列表
        """
        try:
            directory = Path(directory_path)
            if not directory.exists():
                return []
            
            files = []
            if recursive:
                for file_path in directory.rglob("*"):
                    if file_path.is_file():
                        files.append(self._get_file_info(file_path, directory))
            else:
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        files.append(self._get_file_info(file_path, directory))
            
            return sorted(files, key=lambda x: x['name'])
            
        except Exception as e:
            logger.error(f"列出文件失败: {e}")
            return []
    
    def _get_file_info(self, file_path: Path, base_dir: Path) -> Dict:
        """获取文件信息"""
        stat = file_path.stat()
        return {
            'name': file_path.name,
            'path': str(file_path.relative_to(base_dir)),
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'is_directory': file_path.is_dir()
        }
    
    def upload_file(self, directory_path: str, file_name: str, file_content: bytes) -> Tuple[bool, str]:
        """
        上传文件到指定目录
        
        Args:
            directory_path: 目标目录路径
            file_name: 文件名
            file_content: 文件内容
            
        Returns:
            (成功标志, 消息)
        """
        try:
            directory = Path(directory_path)
            directory.mkdir(parents=True, exist_ok=True)
            
            file_path = directory / file_name
            
            # 检查文件是否已存在
            if file_path.exists():
                # 创建备份
                backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
                shutil.copy2(file_path, backup_path)
                logger.info(f"文件已存在，创建备份: {backup_path}")
            
            # 写入文件
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"文件上传成功: {file_path}")
            return True, f"文件上传成功: {file_name}"
            
        except Exception as e:
            error_msg = f"文件上传失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def download_file(self, file_path: str) -> Tuple[bool, str, Optional[bytes]]:
        """
        下载文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            (成功标志, 消息, 文件内容)
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False, f"文件不存在: {file_path}", None
            
            if not path.is_file():
                return False, f"路径不是文件: {file_path}", None
            
            with open(path, 'rb') as f:
                content = f.read()
            
            logger.info(f"文件下载成功: {file_path}")
            return True, f"文件下载成功: {path.name}", content
            
        except Exception as e:
            error_msg = f"文件下载失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def delete_file(self, file_path: str) -> Tuple[bool, str]:
        """
        删除文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            (成功标志, 消息)
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False, f"文件不存在: {file_path}"
            
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            else:
                return False, f"路径不是文件或目录: {file_path}"
            
            logger.info(f"文件删除成功: {file_path}")
            return True, f"文件删除成功: {path.name}"
            
        except Exception as e:
            error_msg = f"文件删除失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def create_directory(self, directory_path: str) -> Tuple[bool, str]:
        """
        创建目录
        
        Args:
            directory_path: 目录路径
            
        Returns:
            (成功标志, 消息)
        """
        try:
            directory = Path(directory_path)
            directory.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"目录创建成功: {directory_path}")
            return True, f"目录创建成功: {directory.name}"
            
        except Exception as e:
            error_msg = f"目录创建失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def copy_file(self, source_path: str, target_path: str) -> Tuple[bool, str]:
        """
        复制文件
        
        Args:
            source_path: 源文件路径
            target_path: 目标文件路径
            
        Returns:
            (成功标志, 消息)
        """
        try:
            source = Path(source_path)
            target = Path(target_path)
            
            if not source.exists():
                return False, f"源文件不存在: {source_path}"
            
            # 确保目标目录存在
            target.parent.mkdir(parents=True, exist_ok=True)
            
            if source.is_file():
                shutil.copy2(source, target)
            elif source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                return False, f"源路径不是文件或目录: {source_path}"
            
            logger.info(f"文件复制成功: {source_path} -> {target_path}")
            return True, f"文件复制成功: {source.name}"
            
        except Exception as e:
            error_msg = f"文件复制失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def move_file(self, source_path: str, target_path: str) -> Tuple[bool, str]:
        """
        移动文件
        
        Args:
            source_path: 源文件路径
            target_path: 目标文件路径
            
        Returns:
            (成功标志, 消息)
        """
        try:
            source = Path(source_path)
            target = Path(target_path)
            
            if not source.exists():
                return False, f"源文件不存在: {source_path}"
            
            # 确保目标目录存在
            target.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(source), str(target))
            
            logger.info(f"文件移动成功: {source_path} -> {target_path}")
            return True, f"文件移动成功: {source.name}"
            
        except Exception as e:
            error_msg = f"文件移动失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def create_archive(self, source_path: str, archive_path: str, archive_type: str = "zip") -> Tuple[bool, str]:
        """
        创建压缩文件
        
        Args:
            source_path: 源路径
            archive_path: 压缩文件路径
            archive_type: 压缩类型 (zip, tar, tar.gz)
            
        Returns:
            (成功标志, 消息)
        """
        try:
            source = Path(source_path)
            archive = Path(archive_path)
            
            if not source.exists():
                return False, f"源路径不存在: {source_path}"
            
            # 确保目标目录存在
            archive.parent.mkdir(parents=True, exist_ok=True)
            
            if archive_type == "zip":
                if source.is_file():
                    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        zipf.write(source, source.name)
                else:
                    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for file_path in source.rglob("*"):
                            if file_path.is_file():
                                zipf.write(file_path, file_path.relative_to(source))
            
            elif archive_type in ["tar", "tar.gz"]:
                mode = "w:gz" if archive_type == "tar.gz" else "w"
                with tarfile.open(archive, mode) as tar:
                    tar.add(source, arcname=source.name)
            
            else:
                return False, f"不支持的压缩类型: {archive_type}"
            
            logger.info(f"压缩文件创建成功: {archive_path}")
            return True, f"压缩文件创建成功: {archive.name}"
            
        except Exception as e:
            error_msg = f"压缩文件创建失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def extract_archive(self, archive_path: str, extract_path: str) -> Tuple[bool, str]:
        """
        解压文件
        
        Args:
            archive_path: 压缩文件路径
            extract_path: 解压目标路径
            
        Returns:
            (成功标志, 消息)
        """
        try:
            archive = Path(archive_path)
            extract = Path(extract_path)
            
            if not archive.exists():
                return False, f"压缩文件不存在: {archive_path}"
            
            # 确保目标目录存在
            extract.mkdir(parents=True, exist_ok=True)
            
            if archive.suffix == ".zip":
                with zipfile.ZipFile(archive, 'r') as zipf:
                    zipf.extractall(extract)
            
            elif archive.suffix in [".tar", ".gz"]:
                with tarfile.open(archive, 'r:*') as tar:
                    tar.extractall(extract)
            
            else:
                return False, f"不支持的压缩文件格式: {archive.suffix}"
            
            logger.info(f"文件解压成功: {archive_path} -> {extract_path}")
            return True, f"文件解压成功: {archive.name}"
            
        except Exception as e:
            error_msg = f"文件解压失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_directory_size(self, directory_path: str) -> Tuple[bool, str, Optional[int]]:
        """
        获取目录大小
        
        Args:
            directory_path: 目录路径
            
        Returns:
            (成功标志, 消息, 目录大小字节数)
        """
        try:
            directory = Path(directory_path)
            if not directory.exists():
                return False, f"目录不存在: {directory_path}", None
            
            if not directory.is_dir():
                return False, f"路径不是目录: {directory_path}", None
            
            total_size = 0
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            return True, f"目录大小: {total_size} 字节", total_size
            
        except Exception as e:
            error_msg = f"获取目录大小失败: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def search_files(self, directory_path: str, pattern: str, recursive: bool = True) -> List[Dict]:
        """
        搜索文件
        
        Args:
            directory_path: 搜索目录
            pattern: 搜索模式
            recursive: 是否递归搜索
            
        Returns:
            匹配的文件列表
        """
        try:
            directory = Path(directory_path)
            if not directory.exists():
                return []
            
            matches = []
            if recursive:
                search_path = directory.rglob(pattern)
            else:
                search_path = directory.glob(pattern)
            
            for file_path in search_path:
                if file_path.is_file():
                    matches.append(self._get_file_info(file_path, directory))
            
            return matches
            
        except Exception as e:
            logger.error(f"搜索文件失败: {e}")
            return [] 