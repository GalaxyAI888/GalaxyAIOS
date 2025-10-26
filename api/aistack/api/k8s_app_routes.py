from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession
import asyncio
import logging
import json
import time
from datetime import datetime

from aistack.server.deps import SessionDep, ListParamsDep, DefaultTestUserDep
from aistack.server.k8s_app_service import K8sAppService
from aistack.schemas.k8s_apps import (
    K8sAppCreate, K8sAppUpdate, K8sAppPublic, K8sAppInstancePublic
)
from aistack.schemas.common import PaginatedList
from aistack.schemas.users import User
from aistack.utils.deployment_task_manager import deploy_task_manager, DeployStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/k8s-apps", tags=["K8s应用管理"])


@router.post("/", response_model=K8sAppPublic, summary="创建K8s应用")
async def create_k8s_app(
    request: Request,
    app_data: K8sAppCreate,
    session: SessionDep,
    current_user: DefaultTestUserDep
):
    """创建新的K8s应用"""
    try:
        # 确保display_name有值（如果没有提供则使用name）
        if not hasattr(app_data, 'display_name') or not app_data.display_name or app_data.display_name == "":
            app_data.display_name = app_data.name
        
        # 处理字段别名问题 - 如果通过别名传入的值没有正确映射，需要手动处理
        # 注意：这些字段值应该在model_validator中已经被处理过了
        
        logger.info(f"创建K8s应用 - name: {app_data.name}, docker_img_url: {app_data.docker_img_url}, img_name: {app_data.img_name}, img_tag: {app_data.img_tag}")
        
        k8s_app_service = K8sAppService()
        app = await k8s_app_service.create_app(session, app_data, current_user.id)
        logger.info(f"K8s应用创建成功: {app.id}")
        return app
    except ValueError as e:
        logger.error(f"创建K8s应用失败(ValueError): {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建K8s应用失败(Exception): {e}", exc_info=True)
        import traceback
        logger.error(f"完整错误信息: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"创建K8s应用失败: {e}")


@router.get("/", response_model=List[K8sAppPublic], summary="列出K8s应用")
async def list_k8s_apps(
    session: SessionDep,
    current_user: DefaultTestUserDep,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    per_page: int = Query(100, ge=1, le=1000, description="每页记录数"),
    category: Optional[str] = Query(None, description="应用分类"),
    is_active: Optional[bool] = Query(None, description="是否激活")
):
    """列出当前用户的K8s应用"""
    try:
        k8s_app_service = K8sAppService()
        apps = await k8s_app_service.list_apps(
            session, current_user.id, page=page, per_page=per_page, 
            category=category, is_active=is_active
        )
        return apps
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取K8s应用列表失败: {e}")


@router.get("/{app_id}", response_model=K8sAppPublic, summary="获取K8s应用详情")
async def get_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: DefaultTestUserDep
):
    """获取K8s应用详情"""
    try:
        k8s_app_service = K8sAppService()
        app = await k8s_app_service.get_app(session, app_id, current_user.id)
        if not app:
            raise HTTPException(status_code=404, detail="K8s应用不存在")
        return app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取K8s应用详情失败: {e}")


@router.put("/{app_id}", response_model=K8sAppPublic, summary="更新K8s应用")
async def update_k8s_app(
    app_id: int,
    app_data: K8sAppUpdate,
    session: SessionDep,
    current_user: DefaultTestUserDep
):
    """更新K8s应用信息"""
    try:
        k8s_app_service = K8sAppService()
        app = await k8s_app_service.update_app(session, app_id, app_data)
        if not app:
            raise HTTPException(status_code=404, detail="K8s应用不存在")
        return app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新K8s应用失败: {e}")


@router.delete("/{app_id}", summary="删除K8s应用")
async def delete_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: DefaultTestUserDep,
    cleanup_resources: bool = Query(False, description="是否同时清理K8s资源")
):
    """删除K8s应用"""
    try:
        k8s_app_service = K8sAppService()
        result = await k8s_app_service.delete_app(session, app_id, cleanup_resources)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除K8s应用失败: {e}")


@router.post("/{app_id}/deploy", summary="部署K8s应用")
async def deploy_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: DefaultTestUserDep
):
    """部署K8s应用到集群"""
    try:
        # 获取应用信息
        k8s_app_service = K8sAppService()
        app = await k8s_app_service.get_app(session, app_id, current_user.id)
        if not app:
            raise HTTPException(status_code=404, detail="应用不存在")
        
        # 创建部署任务
        task_id = deploy_task_manager.create_task(
            app_id=app_id,
            app_name=app.name,
            namespace=app.namespace
        )
        
        # 在后台启动部署任务
        asyncio.create_task(k8s_app_service.deploy_app_with_progress(session, app_id, current_user.id, task_id))
        
        logger.info(f"K8s应用部署任务已启动，task_id: {task_id}")
        return {
            "success": True,
            "message": "应用部署任务已启动",
            "task_id": task_id,
            "deploy_id": f"deploy_{app_id}_{int(datetime.utcnow().timestamp())}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动应用部署失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动应用部署失败: {e}")


@router.get("/{app_id}/status", summary="获取K8s应用状态")
async def get_k8s_app_status(
    app_id: int,
    session: SessionDep,
    current_user: DefaultTestUserDep
):
    """获取K8s应用运行状态"""
    try:
        k8s_app_service = K8sAppService()
        result = await k8s_app_service.get_app_status(session, app_id, current_user.id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取K8s应用状态失败: {e}")


@router.get("/{app_id}/logs", summary="获取K8s应用日志")
async def get_k8s_app_logs(
    app_id: int,
    session: SessionDep,
    current_user: DefaultTestUserDep,
    tail_lines: int = Query(100, ge=1, le=10000, description="返回的日志行数"),
    container_name: Optional[str] = Query(None, description="容器名称（可选，仅当Pod中有多个容器时使用）")
):
    """获取K8s应用运行日志"""
    try:
        k8s_app_service = K8sAppService()
        result = await k8s_app_service.get_app_logs(session, app_id, current_user.id, container_name, tail_lines)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取K8s应用日志失败: {e}")


@router.get("/tasks/{task_id}/stream", summary="实时获取部署任务状态")
async def stream_deploy_task(task_id: str):
    """
    通过SSE实时获取部署任务状态和日志
    
    返回Server-Sent Events流，前端可以通过EventSource连接
    """
    try:
        task = deploy_task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        async def event_generator():
            # 发送初始状态
            data = {
                'task_id': task.task_id,
                'app_id': task.app_id,
                'app_name': task.app_name,
                'namespace': task.namespace,
                'status': task.status.value,
                'progress': task.progress,
                'logs': task.logs,
                'error_message': task.error_message,
                'deployment_result': task.deployment_result,
                'service_result': task.service_result
            }
            yield f"data: {json.dumps(data)}\n\n"
            
            # 如果任务已完成，直接返回
            if task.status in [DeployStatus.SUCCESS, DeployStatus.FAILED, DeployStatus.CANCELLED]:
                return
            
            # 订阅任务更新
            last_data = data
            
            def on_task_update(updated_task):
                if updated_task.task_id == task_id:
                    return {
                        'task_id': updated_task.task_id,
                        'app_id': updated_task.app_id,
                        'app_name': updated_task.app_name,
                        'namespace': updated_task.namespace,
                        'status': updated_task.status.value,
                        'progress': updated_task.progress,
                        'logs': updated_task.logs,
                        'error_message': updated_task.error_message,
                        'deployment_result': updated_task.deployment_result,
                        'service_result': updated_task.service_result
                    }
                return None
            
            # 注册回调
            deploy_task_manager.subscribe(task_id, on_task_update)
            
            try:
                # 等待任务完成或超时
                timeout = 3600  # 1小时超时
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    current_task = deploy_task_manager.get_task(task_id)
                    if not current_task:
                        break
                    
                    # 检查是否有新数据
                    current_data = {
                        'task_id': current_task.task_id,
                        'app_id': current_task.app_id,
                        'app_name': current_task.app_name,
                        'namespace': current_task.namespace,
                        'status': current_task.status.value,
                        'progress': current_task.progress,
                        'logs': current_task.logs,
                        'error_message': current_task.error_message,
                        'deployment_result': current_task.deployment_result,
                        'service_result': current_task.service_result
                    }
                    
                    # 如果数据有变化，发送更新
                    if current_data != last_data:
                        yield f"data: {json.dumps(current_data)}\n\n"
                        last_data = current_data
                    
                    if current_task.status in [DeployStatus.SUCCESS, DeployStatus.FAILED, DeployStatus.CANCELLED]:
                        # 发送最终状态
                        final_data = current_data.copy()
                        final_data['completed'] = True
                        yield f"data: {json.dumps(final_data)}\n\n"
                        break
                    
                    await asyncio.sleep(1)  # 每秒检查一次
                    
            finally:
                # 取消订阅
                deploy_task_manager.unsubscribe(task_id, on_task_update)
        
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
        logger.error(f"创建SSE流失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建SSE流失败: {e}")


@router.post("/{app_id}/scale", summary="扩缩容K8s应用")
async def scale_k8s_app(
    app_id: int,
    session: SessionDep,
    current_user: DefaultTestUserDep,
    replicas: int = Query(..., ge=0, description="目标副本数量")
):
    """扩缩容K8s应用"""
    try:
        k8s_app_service = K8sAppService()
        result = await k8s_app_service.scale_app(session, app_id, current_user.id, replicas)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扩缩容K8s应用失败: {e}")


@router.delete("/{app_id}/k8s", summary="从K8s集群删除应用")
async def delete_k8s_app_from_cluster(
    app_id: int,
    session: SessionDep,
    current_user: DefaultTestUserDep
):
    """从K8s集群中删除应用（保留数据库记录）"""
    try:
        k8s_app_service = K8sAppService()
        result = await k8s_app_service.delete_app_from_k8s(session, app_id, current_user.id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"从K8s集群删除应用失败: {e}")


# K8s集群相关操作
@router.get("/cluster/namespaces", summary="获取K8s命名空间列表")
async def get_k8s_namespaces():
    """获取K8s集群中的命名空间列表"""
    try:
        k8s_app_service = K8sAppService()
        namespaces = k8s_app_service.k8s_manager.client.get_namespaces()
        return {"namespaces": namespaces}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取命名空间列表失败: {e}")


@router.get("/cluster/apps", summary="获取K8s集群中的应用列表")
async def get_k8s_cluster_apps(
    namespace: str = Query("default", description="命名空间")
):
    """获取K8s集群中的应用列表"""
    try:
        k8s_app_service = K8sAppService()
        apps = k8s_app_service.k8s_manager.list_apps(namespace=namespace)
        return {"apps": apps}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取K8s集群应用列表失败: {e}")


@router.get("/cluster/apps/{app_name}/status", summary="获取K8s集群中应用状态")
async def get_k8s_cluster_app_status(
    app_name: str,
    namespace: str = Query("default", description="命名空间")
):
    """获取K8s集群中应用的状态"""
    try:
        k8s_app_service = K8sAppService()
        success, message, status = k8s_app_service.k8s_manager.get_app_status(
            app_name=app_name,
            namespace=namespace
        )
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return {"app_name": app_name, "namespace": namespace, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取K8s集群应用状态失败: {e}")


@router.post("/cluster/apps/{app_name}/scale", summary="扩缩容K8s集群中的应用")
async def scale_k8s_cluster_app(
    app_name: str,
    namespace: str = Query("default", description="命名空间"),
    replicas: int = Query(..., ge=0, description="目标副本数量")
):
    """扩缩容K8s集群中的应用"""
    try:
        k8s_app_service = K8sAppService()
        success, message = k8s_app_service.k8s_manager.scale_app(
            app_name=app_name,
            namespace=namespace,
            replicas=replicas
        )
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return {"message": message}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扩缩容K8s集群应用失败: {e}")


@router.delete("/cluster/apps/{app_name}", summary="删除K8s集群中的应用")
async def delete_k8s_cluster_app(
    app_name: str,
    namespace: str = Query("default", description="命名空间")
):
    """删除K8s集群中的应用"""
    try:
        k8s_app_service = K8sAppService()
        success, message, result = k8s_app_service.k8s_manager.delete_app(
            app_name=app_name,
            namespace=namespace
        )
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return {"message": message, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除K8s集群应用失败: {e}")


# 测试和验证相关
@router.get("/test/connection", summary="测试K8s连接")
async def test_k8s_connection():
    """测试K8s集群连接"""
    try:
        k8s_app_service = K8sAppService()
        success, message = k8s_app_service.k8s_manager.client.test_connection()
        return {"success": success, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试K8s连接失败: {e}")


@router.get("/test/yaml-parse", summary="测试YAML解析")
async def test_yaml_parse(
    yaml_content: str = Query(..., description="YAML内容")
):
    """测试YAML配置解析"""
    try:
        import yaml
        parsed_yaml = yaml.safe_load(yaml_content)
        return {"success": True, "parsed": parsed_yaml}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"YAML解析失败: {e}")


@router.post("/test/json-parse", summary="测试JSON解析")
async def test_json_parse(
    json_content: str = Query(..., description="JSON内容")
):
    """测试JSON配置解析"""
    try:
        import json
        parsed_json = json.loads(json_content)
        return {"success": True, "parsed": parsed_json}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON解析失败: {e}")
