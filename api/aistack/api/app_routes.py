from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
import asyncio
from datetime import datetime

from aistack.server.deps import SessionDep, ListParamsDep
from aistack.server.app_service import AppService
from aistack.schemas.apps import (
    AppCreate, AppUpdate, AppPublic, AppInstancePublic
)
from aistack.schemas.common import PaginatedList

router = APIRouter(prefix="/apps", tags=["应用管理"])


@router.post("/", response_model=AppPublic, summary="创建应用")
async def create_app(
    app_data: AppCreate,
    session: SessionDep
):
    """创建新应用"""
    try:
        app_service = AppService()
        app = await app_service.create_app(session, app_data)
        return app
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建应用失败: {e}")


@router.get("/", response_model=List[AppPublic], summary="列出应用")
async def list_apps(
    session: SessionDep,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    per_page: int = Query(100, ge=1, le=1000, description="每页记录数"),
    category: Optional[str] = Query(None, description="应用分类"),
    is_active: Optional[bool] = Query(None, description="是否激活")
):
    """列出所有应用"""
    try:
        app_service = AppService()
        apps = await app_service.list_apps(
            session, page=page, per_page=per_page, 
            category=category, is_active=is_active
        )
        return apps
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用列表失败: {e}")


@router.get("/{app_id}", response_model=AppPublic, summary="获取应用详情")
async def get_app(
    app_id: int,
    session: SessionDep
):
    """获取应用详情"""
    try:
        app_service = AppService()
        app = await app_service.get_app(session, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="应用不存在")
        return app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用详情失败: {e}")


@router.put("/{app_id}", response_model=AppPublic, summary="更新应用")
async def update_app(
    app_id: int,
    app_data: AppUpdate,
    session: SessionDep
):
    """更新应用信息"""
    try:
        app_service = AppService()
        app = await app_service.update_app(session, app_id, app_data)
        if not app:
            raise HTTPException(status_code=404, detail="应用不存在")
        return app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新应用失败: {e}")


@router.delete("/{app_id}", summary="删除应用")
async def delete_app(
    app_id: int,
    session: SessionDep,
    cleanup_resources: bool = Query(False, description="是否同时清理Docker镜像等资源"),
    cleanup_files: bool = Query(False, description="是否同时清理映射的文件目录")
):
    """删除应用"""
    try:
        app_service = AppService()
        result = await app_service.delete_app(session, app_id, cleanup_resources, cleanup_files)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除应用失败: {e}")


@router.post("/{app_id}/build", summary="构建应用镜像")
async def build_app_image(
    app_id: int,
    session: SessionDep
):
    """构建应用Docker镜像"""
    try:
        app_service = AppService()
        result = await app_service.start_build_image(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取镜像失败: {e}")


@router.post("/{app_id}/pull", summary="拉取应用镜像")
async def pull_app_image(
    app_id: int,
    session: SessionDep
):
    """拉取应用Docker镜像"""
    try:
        app_service = AppService()
        result = await app_service.start_pull_image(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拉取镜像失败: {e}")


@router.post("/{app_id}/image", summary="获取应用镜像（自动判断build或pull）")
async def acquire_app_image(
    app_id: int,
    session: SessionDep
):
    """获取应用Docker镜像（自动判断构建或拉取）"""
    try:
        app_service = AppService()
        result = await app_service.start_image_acquisition(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取镜像失败: {e}")


from pydantic import BaseModel

class StartAppRequest(BaseModel):
    gpu_devices: Optional[List[int]] = None
    device_type: Optional[str] = None  # 可选，仅当混合厂商或无法推断时才需要

@router.post("/{app_id}/start", summary="启动应用")
async def start_app(
    app_id: int,
    session: SessionDep,
    request: Optional[StartAppRequest] = None,
):
    """启动应用容器"""
    try:
        app_service = AppService()
        result = await app_service.start_app(
            session,
            app_id,
            request.gpu_devices if request else None,
            request.device_type if request else None,
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动应用失败: {e}")


@router.get("/{app_id}/available-gpus", summary="获取应用可用的GPU列表")
async def get_available_gpus(app_id: int, session: SessionDep):
    """获取应用可用的GPU列表"""
    try:
        from aistack.server.gpu_service import GPUService
        gpu_service = GPUService()
        available_gpus = gpu_service.get_available_gpus()
        available_indices = gpu_service.get_available_gpu_indices()
        
        return {
            "success": True,
            "available_gpus": available_gpus,
            "available_indices": available_indices
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取可用GPU失败: {e}")


@router.post("/{app_id}/stop", summary="停止应用")
async def stop_app(
    app_id: int,
    session: SessionDep
):
    """停止应用容器"""
    try:
        app_service = AppService()
        result = await app_service.stop_app(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止应用失败: {e}")


@router.get("/{app_id}/status", summary="获取应用状态")
async def get_app_status(
    app_id: int,
    session: SessionDep
):
    """获取应用运行状态"""
    try:
        app_service = AppService()
        result = await app_service.get_app_status(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用状态失败: {e}")


@router.get("/{app_id}/stats", summary="获取应用资源统计")
async def get_app_stats(
    app_id: int,
    session: SessionDep
):
    """获取应用资源使用统计"""
    try:
        app_service = AppService()
        result = await app_service.get_app_stats(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用统计失败: {e}")


@router.get("/{app_id}/instances", response_model=List[AppInstancePublic], summary="列出应用实例")
async def list_app_instances(
    app_id: int,
    session: SessionDep
):
    """列出应用的所有实例"""
    try:
        app_service = AppService()
        instances = await app_service.list_app_instances(session, app_id)
        return instances
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用实例失败: {e}")


@router.post("/{app_id}/cleanup", summary="清理应用实例")
async def cleanup_app_instances(
    app_id: int,
    session: SessionDep
):
    """清理应用的所有实例和容器"""
    try:
        app_service = AppService()
        result = await app_service.cleanup_app_instances(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理应用实例失败: {e}")


@router.post("/{app_id}/cleanup-errors", summary="清理错误的应用实例")
async def cleanup_error_instances(
    app_id: int,
    session: SessionDep
):
    """清理应用的错误实例和容器"""
    try:
        app_service = AppService()
        result = await app_service.cleanup_error_instances(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理错误应用实例失败: {e}")


# Docker相关操作
@router.get("/docker/containers", summary="列出所有Docker容器")
async def list_docker_containers():
    """列出所有Docker容器"""
    try:
        app_service = AppService()
        containers = app_service.docker_manager.list_containers()
        return {"containers": containers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取容器列表失败: {e}")


@router.get("/docker/images", summary="列出所有Docker镜像")
async def list_docker_images():
    """列出所有Docker镜像"""
    try:
        app_service = AppService()
        images = app_service.docker_manager.list_images()
        return {"images": images}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取镜像列表失败: {e}")


@router.delete("/docker/images/{image_name}", summary="删除Docker镜像")
async def remove_docker_image(
    image_name: str,
    tag: str = Query("latest", description="镜像标签")
):
    """删除指定的Docker镜像"""
    try:
        app_service = AppService()
        success, message = app_service.docker_manager.remove_image(image_name, tag)
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return {"message": message}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除镜像失败: {e}")


@router.get("/{app_id}/build/status", summary="获取构建状态")
async def get_build_status(
    app_id: int,
    session: SessionDep
):
    """获取构建状态"""
    try:
        app_service = AppService()
        result = await app_service.get_build_status(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取构建状态失败: {e}")


@router.get("/{app_id}/image/info", summary="查询镜像信息")
async def get_image_info(
    app_id: int,
    session: SessionDep
):
    """查询应用镜像详细信息"""
    try:
        app_service = AppService()
        result = await app_service.get_image_info(session, app_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询镜像信息失败: {e}")


@router.get("/volumes/reverse-lookup", summary="根据本地路径查找映射的应用及卷信息")
async def reverse_lookup_volumes(
    session: SessionDep,
    host_path: str = Query(..., description="要查询的本地路径")
    
):
    """根据本地路径查找所有映射该路径的应用及卷信息"""
    try:
        app_service = AppService()
        result = await app_service.find_apps_by_host_path(session, host_path)
        return {"host_path": host_path, "mappings": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查找host_path映射失败: {e}") 