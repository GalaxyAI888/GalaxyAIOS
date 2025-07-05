from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
import os

from aistack.utils.file_manager import FileManager

router = APIRouter(prefix="/files", tags=["文件管理"])

# 初始化文件管理器
file_manager = FileManager()


@router.get("/list/{app_name}", summary="列出应用文件")
async def list_app_files(
    app_name: str,
    volume_name: Optional[str] = Query(None, description="卷名称"),
    recursive: bool = Query(False, description="是否递归列出子目录")
):
    """列出应用的文件"""
    try:
        if volume_name:
            directory_path = file_manager.create_volume_directory(app_name, volume_name)
        else:
            directory_path = file_manager.create_app_directory(app_name)
        
        files = file_manager.list_files(str(directory_path), recursive=recursive)
        return {"files": files, "directory": str(directory_path)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出文件失败: {e}")


@router.post("/upload/{app_name}", summary="上传文件")
async def upload_file(
    app_name: str,
    volume_name: Optional[str] = Form(None, description="卷名称"),
    file: UploadFile = File(..., description="要上传的文件")
):
    """上传文件到应用目录"""
    try:
        # 确定目标目录
        if volume_name:
            directory_path = file_manager.create_volume_directory(app_name, volume_name)
        else:
            directory_path = file_manager.create_app_directory(app_name)
        
        # 读取文件内容
        file_content = await file.read()
        
        # 上传文件
        success, message = file_manager.upload_file(
            str(directory_path), file.filename, file_content
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"message": message, "filename": file.filename}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {e}")


@router.get("/download/{app_name}/{filename:path}", summary="下载文件")
async def download_file(
    app_name: str,
    filename: str,
    volume_name: Optional[str] = Query(None, description="卷名称")
):
    """下载应用文件"""
    try:
        # 确定文件路径
        if volume_name:
            directory_path = file_manager.create_volume_directory(app_name, volume_name)
        else:
            directory_path = file_manager.create_app_directory(app_name)
        
        file_path = directory_path / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="路径不是文件")
        
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件下载失败: {e}")


@router.delete("/delete/{app_name}/{filename:path}", summary="删除文件")
async def delete_file(
    app_name: str,
    filename: str,
    volume_name: Optional[str] = Query(None, description="卷名称")
):
    """删除应用文件"""
    try:
        # 确定文件路径
        if volume_name:
            directory_path = file_manager.create_volume_directory(app_name, volume_name)
        else:
            directory_path = file_manager.create_app_directory(app_name)
        
        file_path = directory_path / filename
        
        success, message = file_manager.delete_file(str(file_path))
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件删除失败: {e}")


@router.post("/mkdir/{app_name}", summary="创建目录")
async def create_directory(
    app_name: str,
    directory_name: str = Form(..., description="目录名称"),
    volume_name: Optional[str] = Form(None, description="卷名称")
):
    """在应用目录下创建新目录"""
    try:
        # 确定父目录
        if volume_name:
            parent_dir = file_manager.create_volume_directory(app_name, volume_name)
        else:
            parent_dir = file_manager.create_app_directory(app_name)
        
        # 创建新目录
        new_dir_path = parent_dir / directory_name
        success, message = file_manager.create_directory(str(new_dir_path))
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"message": message, "directory": str(new_dir_path)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建目录失败: {e}")


@router.post("/copy/{app_name}", summary="复制文件")
async def copy_file(
    app_name: str,
    source_path: str = Form(..., description="源文件路径"),
    target_path: str = Form(..., description="目标文件路径"),
    volume_name: Optional[str] = Form(None, description="卷名称")
):
    """复制应用文件"""
    try:
        # 确定基础目录
        if volume_name:
            base_dir = file_manager.create_volume_directory(app_name, volume_name)
        else:
            base_dir = file_manager.create_app_directory(app_name)
        
        # 构建完整路径
        full_source_path = base_dir / source_path
        full_target_path = base_dir / target_path
        
        success, message = file_manager.copy_file(
            str(full_source_path), str(full_target_path)
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"复制文件失败: {e}")


@router.post("/move/{app_name}", summary="移动文件")
async def move_file(
    app_name: str,
    source_path: str = Form(..., description="源文件路径"),
    target_path: str = Form(..., description="目标文件路径"),
    volume_name: Optional[str] = Form(None, description="卷名称")
):
    """移动应用文件"""
    try:
        # 确定基础目录
        if volume_name:
            base_dir = file_manager.create_volume_directory(app_name, volume_name)
        else:
            base_dir = file_manager.create_app_directory(app_name)
        
        # 构建完整路径
        full_source_path = base_dir / source_path
        full_target_path = base_dir / target_path
        
        success, message = file_manager.move_file(
            str(full_source_path), str(full_target_path)
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移动文件失败: {e}")


@router.post("/archive/{app_name}", summary="创建压缩文件")
async def create_archive(
    app_name: str,
    source_path: str = Form(..., description="源路径"),
    archive_name: str = Form(..., description="压缩文件名"),
    archive_type: str = Form("zip", description="压缩类型 (zip, tar, tar.gz)"),
    volume_name: Optional[str] = Form(None, description="卷名称")
):
    """创建压缩文件"""
    try:
        # 确定基础目录
        if volume_name:
            base_dir = file_manager.create_volume_directory(app_name, volume_name)
        else:
            base_dir = file_manager.create_app_directory(app_name)
        
        # 构建完整路径
        full_source_path = base_dir / source_path
        full_archive_path = base_dir / archive_name
        
        success, message = file_manager.create_archive(
            str(full_source_path), str(full_archive_path), archive_type
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建压缩文件失败: {e}")


@router.post("/extract/{app_name}", summary="解压文件")
async def extract_archive(
    app_name: str,
    archive_path: str = Form(..., description="压缩文件路径"),
    extract_path: str = Form(..., description="解压目标路径"),
    volume_name: Optional[str] = Form(None, description="卷名称")
):
    """解压文件"""
    try:
        # 确定基础目录
        if volume_name:
            base_dir = file_manager.create_volume_directory(app_name, volume_name)
        else:
            base_dir = file_manager.create_app_directory(app_name)
        
        # 构建完整路径
        full_archive_path = base_dir / archive_path
        full_extract_path = base_dir / extract_path
        
        success, message = file_manager.extract_archive(
            str(full_archive_path), str(full_extract_path)
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解压文件失败: {e}")


@router.get("/size/{app_name}", summary="获取目录大小")
async def get_directory_size(
    app_name: str,
    directory_path: str = Query("", description="目录路径"),
    volume_name: Optional[str] = Query(None, description="卷名称")
):
    """获取目录大小"""
    try:
        # 确定基础目录
        if volume_name:
            base_dir = file_manager.create_volume_directory(app_name, volume_name)
        else:
            base_dir = file_manager.create_app_directory(app_name)
        
        # 构建完整路径
        if directory_path:
            full_dir_path = base_dir / directory_path
        else:
            full_dir_path = base_dir
        
        success, message, size = file_manager.get_directory_size(str(full_dir_path))
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"message": message, "size": size, "size_mb": size / (1024 * 1024) if size else 0}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取目录大小失败: {e}")


@router.get("/search/{app_name}", summary="搜索文件")
async def search_files(
    app_name: str,
    pattern: str = Query(..., description="搜索模式"),
    recursive: bool = Query(True, description="是否递归搜索"),
    volume_name: Optional[str] = Query(None, description="卷名称")
):
    """搜索文件"""
    try:
        # 确定搜索目录
        if volume_name:
            search_dir = file_manager.create_volume_directory(app_name, volume_name)
        else:
            search_dir = file_manager.create_app_directory(app_name)
        
        files = file_manager.search_files(str(search_dir), pattern, recursive)
        return {"files": files, "count": len(files)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索文件失败: {e}") 