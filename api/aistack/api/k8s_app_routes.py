from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
import asyncio
from datetime import datetime

from aistack.server.deps import SessionDep, ListParamsDep, OptionalUserDep
from aistack.server.k8s_app_service import K8sAppService
from aistack.schemas.apps import (
    AppCreate, AppUpdate, AppPublic, AppInstancePublic
)
from aistack.schemas.common import PaginatedList
from aistack.schemas.users import User

router = APIRouter(prefix="/k8s-apps", tags=["Kubernetes应用管理"])


@router.post("/", response_model=AppPublic, summary="创建Kubernetes应用")
async def create_k8s_app(
    app_data: AppCreate,
    session: SessionDep,
    current_user: OptionalUserDep
):
    """创建新的Kubernetes应用"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        app = await app_service.create_app(session, app_data, user_id)
        return app
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建应用失败: {e}")


@router.get("/", response_model=List[AppPublic], summary="列出Kubernetes应用")
async def list_k8s_apps(
    session: SessionDep,
    current_user: OptionalUserDep,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    per_page: int = Query(100, ge=1, le=1000, description="每页记录数"),
    category: Optional[str] = Query(None, description="应用分类"),
    is_active: Optional[bool] = Query(None, description="是否激活")
):
    """列出当前用户的Kubernetes应用"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        apps = await app_service.list_apps(
            session, user_id, page=page, per_page=per_page, 
            category=category, is_active=is_active
        )
        return apps
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用列表失败: {e}")


@router.get("/{app_id}", response_model=AppPublic, summary="获取Kubernetes应用详情")
async def get_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep
):
    """获取Kubernetes应用详情"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        app = await app_service.get_app(session, app_id, user_id)
        if not app:
            raise HTTPException(status_code=404, detail="应用不存在")
        return app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用详情失败: {e}")


@router.put("/{app_id}", response_model=AppPublic, summary="更新Kubernetes应用")
async def update_k8s_app(
    app_id: int,
    app_data: AppUpdate,
    session: SessionDep,
    current_user: OptionalUserDep
):
    """更新Kubernetes应用信息"""
    try:
        app_service = K8sAppService()
        app = await app_service.update_app(session, app_id, app_data)
        if not app:
            raise HTTPException(status_code=404, detail="应用不存在")
        return app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新应用失败: {e}")


@router.delete("/{app_id}", summary="删除Kubernetes应用")
async def delete_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep,
    cleanup_k8s: bool = Query(True, description="是否同时清理Kubernetes资源")
):
    """删除Kubernetes应用"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        result = await app_service.delete_app(session, app_id, user_id, cleanup_k8s)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除应用失败: {e}")


@router.post("/{app_id}/deploy", summary="部署Kubernetes应用")
async def deploy_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep
):
    """部署应用到Kubernetes集群"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        result = await app_service.deploy_app(session, app_id, user_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"部署应用失败: {e}")


@router.post("/{app_id}/start", summary="启动Kubernetes应用")
async def start_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep,
    replicas: int = Query(1, ge=1, description="副本数量")
):
    """启动Kubernetes应用（扩缩容到指定副本数）"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        result = await app_service.start_app(session, app_id, user_id, replicas)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动应用失败: {e}")


@router.post("/{app_id}/stop", summary="停止Kubernetes应用")
async def stop_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep
):
    """停止Kubernetes应用（扩缩容到0个副本）"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        result = await app_service.stop_app(session, app_id, user_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止应用失败: {e}")


@router.post("/{app_id}/scale", summary="扩缩容Kubernetes应用")
async def scale_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep,
    replicas: int = Query(1, ge=0, description="目标副本数量")
):
    """扩缩容Kubernetes应用"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        result = await app_service.scale_app(session, app_id, user_id, replicas)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扩缩容应用失败: {e}")


@router.get("/{app_id}/status", summary="获取Kubernetes应用状态")
async def get_k8s_app_status(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep
):
    """获取Kubernetes应用运行状态"""
    try:
        app_service = K8sAppService()
        user_id = current_user.id if current_user else 0
        result = await app_service.get_app_status(session, app_id, user_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用状态失败: {e}")


# Kubernetes集群相关操作
@router.get("/cluster/info", summary="获取Kubernetes集群信息")
async def get_k8s_cluster_info():
    """获取Kubernetes集群基本信息"""
    try:
        app_service = K8sAppService()
        success, message = app_service.k8s_manager.client.test_connection()
        if not success:
            raise HTTPException(status_code=500, detail=f"无法连接到Kubernetes集群: {message}")
        
        # 获取命名空间列表
        namespaces = app_service.k8s_manager.client.get_namespaces()
        
        return {
            "success": True,
            "cluster_status": "connected",
            "message": message,
            "namespaces_count": len(namespaces),
            "namespaces": [ns['name'] for ns in namespaces]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取集群信息失败: {e}")


@router.get("/cluster/namespaces", summary="获取Kubernetes命名空间列表")
async def get_k8s_namespaces():
    """获取Kubernetes集群中的所有命名空间"""
    try:
        app_service = K8sAppService()
        namespaces = app_service.k8s_manager.client.get_namespaces()
        return {
            "success": True,
            "namespaces": namespaces
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取命名空间列表失败: {e}")


@router.post("/cluster/namespaces", summary="创建Kubernetes命名空间")
async def create_k8s_namespace(
    name: str = Query(..., description="命名空间名称"),
    labels: Optional[str] = Query(None, description="标签（JSON格式）")
):
    """创建新的Kubernetes命名空间"""
    try:
        import json
        
        app_service = K8sAppService()
        
        # 解析标签
        labels_dict = {}
        if labels:
            try:
                labels_dict = json.loads(labels)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="标签格式不正确，应为JSON格式")
        
        success, message = app_service.k8s_manager.client.create_namespace(name, labels_dict)
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {
            "success": True,
            "message": message
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建命名空间失败: {e}")


# 应用实例相关操作（保留兼容性）
@router.get("/{app_id}/instances", response_model=List[AppInstancePublic], summary="列出Kubernetes应用实例")
async def list_k8s_app_instances(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep
):
    """列出Kubernetes应用的所有实例（Pod）"""
    try:
        # 这里可以扩展为获取Kubernetes Pod信息
        # 暂时返回空列表，保持API兼容性
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用实例失败: {e}")


# 日志相关操作
@router.get("/{app_id}/logs", summary="获取Kubernetes应用日志")
async def get_k8s_app_logs(
    app_id: int,
    session: SessionDep,
    current_user: OptionalUserDep,
    container_name: Optional[str] = Query(None, description="容器名称"),
    tail_lines: int = Query(100, ge=1, le=10000, description="日志行数")
):
    """获取Kubernetes应用日志"""
    try:
        app_service = K8sAppService()
        
        # 验证应用所有权
        user_id = current_user.id if current_user else 0
        has_permission, app, error_msg = await app_service._verify_app_ownership(session, app_id, user_id)
        if not has_permission:
            raise HTTPException(status_code=403, detail=error_msg)
        
        # 获取日志
        k8s_namespace = f"aistack-{user_id}" if user_id else "aistack-public"
        success, message, logs = app_service.k8s_manager.get_app_logs(
            app_name=app.name,
            namespace=k8s_namespace,
            container_name=container_name,
            tail_lines=tail_lines
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {
            "success": True,
            "logs": logs,
            "message": message
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取应用日志失败: {e}")


# 文件挂载相关操作
@router.get("/volumes/reverse-lookup", summary="根据本地路径查找映射的Kubernetes应用及卷信息")
async def reverse_lookup_k8s_volumes(
    session: SessionDep,
    current_user: OptionalUserDep,
    host_path: str = Query(..., description="要查询的本地路径")
):
    """根据本地路径查找所有映射该路径的Kubernetes应用及卷信息"""
    try:
        # 这里可以实现查找Kubernetes PersistentVolume和PersistentVolumeClaim的逻辑
        # 暂时返回空结果，保持API兼容性
        return {
            "host_path": host_path, 
            "mappings": [],
            "message": "Kubernetes卷映射查找功能待实现"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查找host_path映射失败: {e}")

