import logging
import asyncio
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlmodel import select, Session
from sqlmodel.ext.asyncio.session import AsyncSession

from aistack.schemas.k8s_apps import (
    K8sApp, K8sAppCreate, K8sAppUpdate, K8sAppPublic, K8sAppStatusEnum,
    K8sAppInstance, K8sAppInstanceCreate, K8sAppInstanceUpdate, K8sAppInstancePublic
)
from aistack.utils.k8s_manager import KubernetesManager
from aistack.utils.deployment_task_manager import deploy_task_manager, DeployStatus

logger = logging.getLogger(__name__)


class K8sAppService:
    """K8s应用管理服务"""
   
    def __init__(self):
        self.k8s_manager = KubernetesManager()
        self._check_k8s_permissions()

    def _check_k8s_permissions(self) -> None:
        """
        检查K8s权限和配置
        """
        try:
            # 测试连接
            success, message = self.k8s_manager.client.test_connection()
            if success:
                logger.info(f"Kubernetes连接测试成功: {message}")
            else:
                logger.warning(f"Kubernetes连接测试失败: {message}")
                logger.warning("请确保kubectl配置正确，并且有足够的权限访问集群")
            
        except Exception as e:
            logger.warning(f"Kubernetes权限检查失败: {e}")
            logger.warning("请确保Kubernetes集群可访问，并且当前用户有足够权限")

    async def _verify_app_ownership(self, session: AsyncSession, app_id: int, user_id: int) -> Tuple[bool, Optional[K8sApp], str]:
        """
        验证应用所有权
        
        Args:
            session: 数据库会话
            app_id: 应用ID
            user_id: 用户ID
            
        Returns:
            (是否拥有权限, 应用对象, 错误消息)
        """
        try:
            # 查询应用并验证所有权
            result = await session.exec(
                select(K8sApp).where(K8sApp.id == app_id, K8sApp.user_id == user_id)
            )
            app = result.first()
            
            if not app:
                # 检查应用是否存在
                result = await session.exec(
                    select(K8sApp).where(K8sApp.id == app_id)
                )
                existing_app = result.first()
                
                if existing_app:
                    return False, None, "您没有权限操作此应用"
                else:
                    return False, None, "应用不存在"
            
            return True, app, ""
            
        except Exception as e:
            logger.error(f"验证应用所有权失败: {e}")
            return False, None, f"验证应用所有权失败: {e}"

    async def create_app(self, session: AsyncSession, app_data: K8sAppCreate, user_id: int) -> K8sAppPublic:
        """创建K8s应用"""
        try:
            # 检查应用名称是否已存在（在同一用户下）
            result = await session.exec(
                select(K8sApp).where(K8sApp.name == app_data.name, K8sApp.user_id == user_id)
            )
            existing_app = result.first()
           
            if existing_app:
                raise ValueError(f"应用名称已存在: {app_data.name}")
           
            # 创建应用
            app_data_dict = app_data.dict()
            
            # 将 tags 对象转换为列表
            if app_data_dict.get('tags'):
                if isinstance(app_data_dict['tags'], str):
                    try:
                        app_data_dict['tags'] = json.loads(app_data_dict['tags'])
                    except json.JSONDecodeError:
                        app_data_dict['tags'] = []
                elif not isinstance(app_data_dict['tags'], list):
                    app_data_dict['tags'] = []
            
            # 添加用户ID
            app_data_dict['user_id'] = user_id
            
            app = K8sApp(**app_data_dict)
            session.add(app)
            await session.commit()
            await session.refresh(app)
           
            logger.info(f"K8s应用创建成功: {app.name} (User: {user_id})")
            return K8sAppPublic.from_orm(app)
           
        except Exception as e:
            await session.rollback()
            logger.error(f"创建K8s应用失败: {e}")
            raise
   
    async def get_app(self, session: AsyncSession, app_id: int, user_id: int) -> Optional[K8sAppPublic]:
        """获取K8s应用详情"""
        try:
            result = await session.exec(
                select(K8sApp).where(K8sApp.id == app_id, K8sApp.user_id == user_id)
            )
            app = result.first()
            if not app:
                return None
           
            return K8sAppPublic.from_orm(app)
           
        except Exception as e:
            logger.error(f"获取K8s应用失败: {e}")
            raise
   
    async def get_app_by_name(self, session: AsyncSession, app_name: str, user_id: int) -> Optional[K8sAppPublic]:
        """根据名称获取K8s应用"""
        try:
            result = await session.exec(
                select(K8sApp).where(K8sApp.name == app_name, K8sApp.user_id == user_id)
            )
            app = result.first()
           
            if not app:
                return None
           
            return K8sAppPublic.from_orm(app)
           
        except Exception as e:
            logger.error(f"根据名称获取K8s应用失败: {e}")
            raise
   
    async def list_apps(self, session: AsyncSession, user_id: int,
                       page: int = 1, per_page: int = 100,
                       category: Optional[str] = None,
                       is_active: Optional[bool] = None) -> List[K8sAppPublic]:
        """列出K8s应用"""
        try:
            query = select(K8sApp).where(K8sApp.user_id == user_id)
           
            if category:
                query = query.where(K8sApp.category == category)
           
            if is_active is not None:
                query = query.where(K8sApp.is_active == is_active)
           
            # 计算偏移量
            skip = (page - 1) * per_page
            result = await session.exec(query.offset(skip).limit(per_page))
            return [K8sAppPublic.from_orm(app) for app in result.all()]
           
        except Exception as e:
            logger.error(f"列出K8s应用失败: {e}")
            raise
   
    async def update_app(self, session: AsyncSession, app_id: int, app_data: K8sAppUpdate) -> Optional[K8sAppPublic]:
        """更新K8s应用"""
        try:
            app = await session.get(K8sApp, app_id)
            if not app:
                return None
           
            # 更新字段
            update_data = app_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(app, field, value)
           
            await session.commit()
            await session.refresh(app)
           
            logger.info(f"K8s应用更新成功: {app.name}")
            return K8sAppPublic.from_orm(app)
           
        except Exception as e:
            await session.rollback()
            logger.error(f"更新K8s应用失败: {e}")
            raise
   
    async def delete_app(self, session: AsyncSession, app_id: int, cleanup_resources: bool = False) -> Dict[str, Any]:
        """删除K8s应用"""
        try:
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(K8sApp, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 检查是否有运行中的实例
                    result = await new_session.exec(
                        select(K8sAppInstance).where(
                            K8sAppInstance.k8s_app_id == app_id,
                            K8sAppInstance.status.in_([K8sAppStatusEnum.RUNNING, K8sAppStatusEnum.DEPLOYING])
                        )
                    )
                    running_instances = result.all()
                   
                    if running_instances:
                        return {"success": False, "message": f"应用 {app.name} 有运行中的实例，无法删除"}
                   
                    # 删除所有相关的实例记录
                    all_instances = await new_session.exec(
                        select(K8sAppInstance).where(K8sAppInstance.k8s_app_id == app_id)
                    )
                    instances_to_delete = all_instances.all()
                    
                    for instance in instances_to_delete:
                        await new_session.delete(instance)
                    
                    # 如果需要清理资源，删除K8s资源
                    if cleanup_resources:
                        try:
                            success, message, result = self.k8s_manager.delete_app(
                                app_name=app.name,
                                namespace=app.namespace
                            )
                            if success:
                                logger.info(f"K8s资源删除成功: {app.name}")
                            else:
                                logger.warning(f"K8s资源删除失败: {message}")
                        except Exception as e:
                            logger.warning(f"删除K8s资源时出错: {e}")
                   
                    # 删除应用
                    await new_session.delete(app)
                    # 事务会自动提交
           
            logger.info(f"K8s应用删除成功: {app.name}")
            return {"success": True, "message": f"应用 {app.name} 删除成功"}
           
        except Exception as e:
            logger.error(f"删除K8s应用失败: {e}")
            return {"success": False, "message": f"删除应用失败: {e}"}

    async def deploy_app(self, session: AsyncSession, app_id: int, user_id: int) -> Dict[str, Any]:
        """部署K8s应用"""
        try:
            # 验证应用所有权
            has_permission, app, error_msg = await self._verify_app_ownership(session, app_id, user_id)
            if not has_permission:
                return {"success": False, "message": error_msg}
            
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    # 重新获取应用信息
                    app = await new_session.get(K8sApp, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 检查是否已在部署中
                    if app.status == K8sAppStatusEnum.DEPLOYING:
                        return {"success": False, "message": "应用正在部署中，请稍后再试"}
                   
                    # 更新应用状态为部署中
                    app.status = K8sAppStatusEnum.DEPLOYING
                    app.status_message = "应用部署任务已启动"
                    app.last_updated_at = datetime.utcnow()
           
            # 启动异步部署任务
            asyncio.create_task(self._deploy_app_async(app_id))
           
            logger.info(f"K8s应用部署任务已启动")
            return {
                "success": True,
                "message": "应用部署任务已启动，请通过状态接口查询进度",
                "deploy_id": f"deploy_{app_id}_{int(datetime.utcnow().timestamp())}"
            }
           
        except Exception as e:
            logger.error(f"启动应用部署失败: {e}")
            # 用新的 session 更新状态
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(K8sApp, app_id)
                    if app:
                        app.status = K8sAppStatusEnum.ERROR
                        app.status_message = f"启动应用部署失败: {e}"
                        app.last_updated_at = datetime.utcnow()
            return {"success": False, "message": f"启动应用部署失败: {e}"}

    async def _deploy_app_async(self, app_id: int):
        """异步部署K8s应用"""
        try:
            logger.info(f"开始异步部署K8s应用，应用ID: {app_id}")
           
            # 创建新的数据库会话
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as session:
                async with session.begin():
                    app = await session.get(K8sApp, app_id)
                    if not app:
                        logger.error(f"应用不存在: {app_id}")
                        return
                    
                    # 保存应用信息，因为session会在async with块结束后关闭
                    app_info = {
                        'name': app.name,
                        'namespace': app.namespace,
                        'deployment': app.deployment,
                        'service': app.service,
                        'configmap': app.configmap,
                        'ingress': app.ingress
                    }
           
            # 解析JSON配置
            deployment_config = None
            service_config = None
            configmap_config = None
            ingress_config = None
            
            if app_info['deployment']:
                try:
                    deployment_config = json.loads(app_info['deployment'])
                except json.JSONDecodeError as e:
                    logger.error(f"解析Deployment配置失败: {e}")
                    raise ValueError(f"Deployment配置JSON格式错误: {e}")
            
            if app_info['service']:
                try:
                    service_config = json.loads(app_info['service'])
                except json.JSONDecodeError as e:
                    logger.error(f"解析Service配置失败: {e}")
                    raise ValueError(f"Service配置JSON格式错误: {e}")
            
            if app_info['configmap']:
                try:
                    configmap_config = json.loads(app_info['configmap'])
                except json.JSONDecodeError as e:
                    logger.error(f"解析ConfigMap配置失败: {e}")
                    raise ValueError(f"ConfigMap配置JSON格式错误: {e}")
            
            if app_info['ingress']:
                try:
                    ingress_config = json.loads(app_info['ingress'])
                except json.JSONDecodeError as e:
                    logger.error(f"解析Ingress配置失败: {e}")
                    raise ValueError(f"Ingress配置JSON格式错误: {e}")
            
            # 部署应用到K8s
            success, message, deploy_result = self.k8s_manager.deploy_app_from_json(
                app_name=app_info['name'],
                namespace=app_info['namespace'],
                deployment_config=deployment_config,
                service_config=service_config,
                configmap_config=configmap_config,
                ingress_config=ingress_config
            )
           
            # 创建新的会话来更新状态
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(K8sApp, app_id)
                    if app:
                        if success:
                            app.status = K8sAppStatusEnum.RUNNING
                            app.status_message = "应用部署成功"
                            app.deployed_at = datetime.utcnow()
                        else:
                            app.status = K8sAppStatusEnum.ERROR
                            app.status_message = f"应用部署失败: {message}"
                        app.last_updated_at = datetime.utcnow()
           
            if success:
                logger.info(f"应用 {app_info['name']} 部署成功")
            else:
                logger.error(f"应用 {app_info['name']} 部署失败: {message}")
           
        except Exception as e:
            logger.error(f"异步部署K8s应用过程中发生异常: {e}")
            try:
                # 创建新的数据库会话来处理异常
                engine = get_engine()
                async with AsyncSession(engine) as new_session:
                    async with new_session.begin():
                        app = await new_session.get(K8sApp, app_id)
                        if app:
                            app.status = K8sAppStatusEnum.ERROR
                            app.status_message = f"应用部署异常: {str(e)}"
                            app.last_updated_at = datetime.utcnow()
            except Exception as update_error:
                logger.error(f"更新部署状态失败: {update_error}")

    async def deploy_app_with_progress(self, session: AsyncSession, app_id: int, user_id: int, task_id: str):
        """带进度跟踪的部署K8s应用"""
        try:
            logger.info(f"开始带进度部署K8s应用，应用ID: {app_id}, task_id: {task_id}")
            
            # 更新任务状态为解析配置中
            deploy_task_manager.update_task_status(task_id, DeployStatus.PARSING, 10.0)
            deploy_task_manager.add_log(task_id, f"开始解析应用 {app_id} 的配置...")
            
            # 创建新的数据库会话
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(K8sApp, app_id)
                    if not app:
                        logger.error(f"应用不存在: {app_id}")
                        deploy_task_manager.update_task_status(task_id, DeployStatus.FAILED, error_message="应用不存在")
                        return
                    
                    # 保存应用信息
                    app_info = {
                        'name': app.name,
                        'namespace': app.namespace,
                        'deployment': app.deployment,
                        'service': app.service,
                        'configmap': app.configmap,
                        'ingress': app.ingress
                    }
            
            # 解析JSON配置
            deploy_task_manager.update_task_status(task_id, DeployStatus.PARSING, 20.0)
            deploy_task_manager.add_log(task_id, "解析Deployment配置...")
            
            deployment_config = None
            service_config = None
            configmap_config = None
            ingress_config = None
            
            if app_info['deployment']:
                try:
                    deployment_config = json.loads(app_info['deployment'])
                    deploy_task_manager.add_log(task_id, "Deployment配置解析成功")
                except json.JSONDecodeError as e:
                    error_msg = f"Deployment配置JSON格式错误: {e}"
                    logger.error(error_msg)
                    deploy_task_manager.update_task_status(task_id, DeployStatus.FAILED, error_message=error_msg)
                    raise ValueError(error_msg)
            
            if app_info['service']:
                try:
                    service_config = json.loads(app_info['service'])
                    deploy_task_manager.add_log(task_id, "Service配置解析成功")
                except json.JSONDecodeError as e:
                    error_msg = f"Service配置JSON格式错误: {e}"
                    logger.error(error_msg)
                    deploy_task_manager.update_task_status(task_id, DeployStatus.FAILED, error_message=error_msg)
                    raise ValueError(error_msg)
            
            if app_info['configmap']:
                try:
                    configmap_config = json.loads(app_info['configmap'])
                    deploy_task_manager.add_log(task_id, "ConfigMap配置解析成功")
                except json.JSONDecodeError as e:
                    logger.warning(f"ConfigMap配置解析失败: {e}")
            
            if app_info['ingress']:
                try:
                    ingress_config = json.loads(app_info['ingress'])
                    deploy_task_manager.add_log(task_id, "Ingress配置解析成功")
                except json.JSONDecodeError as e:
                    logger.warning(f"Ingress配置解析失败: {e}")
            
            # 开始部署
            deploy_task_manager.update_task_status(task_id, DeployStatus.DEPLOYING, 30.0)
            deploy_task_manager.add_log(task_id, "开始部署到Kubernetes集群...")
            
            # 部署Deployment
            if deployment_config:
                deploy_task_manager.add_log(task_id, "部署Deployment...")
                success, message = self.k8s_manager.deployment_manager.create_deployment_from_json(
                    namespace=app_info['namespace'],
                    deployment_config=deployment_config
                )
                if not success:
                    error_msg = f"Deployment部署失败: {message}"
                    deploy_task_manager.update_task_status(task_id, DeployStatus.FAILED, error_message=error_msg)
                    deploy_task_manager.set_deployment_result(task_id, {"success": False, "message": message})
                    return
                deploy_task_manager.set_deployment_result(task_id, {"success": True, "message": message})
                deploy_task_manager.add_log(task_id, f"Deployment部署成功: {message}")
                deploy_task_manager.update_task_status(task_id, DeployStatus.DEPLOYING, 60.0)
            
            # 部署Service
            if service_config:
                deploy_task_manager.add_log(task_id, "部署Service...")
                success, message = self.k8s_manager.service_manager.create_service_from_json(
                    namespace=app_info['namespace'],
                    service_config=service_config
                )
                if not success:
                    error_msg = f"Service部署失败: {message}"
                    deploy_task_manager.update_task_status(task_id, DeployStatus.FAILED, error_message=error_msg)
                    deploy_task_manager.set_service_result(task_id, {"success": False, "message": message})
                    return
                deploy_task_manager.set_service_result(task_id, {"success": True, "message": message})
                deploy_task_manager.add_log(task_id, f"Service部署成功: {message}")
                deploy_task_manager.update_task_status(task_id, DeployStatus.DEPLOYING, 80.0)
            
            # 更新应用状态
            engine = get_engine()
            async with AsyncSession(engine) as update_session:
                async with update_session.begin():
                    app = await update_session.get(K8sApp, app_id)
                    if app:
                        app.status = K8sAppStatusEnum.RUNNING
                        app.status_message = "应用部署成功"
                        app.deployed_at = datetime.utcnow()
                        app.last_updated_at = datetime.utcnow()
            
            # 任务完成
            deploy_task_manager.update_task_status(task_id, DeployStatus.SUCCESS, 100.0)
            deploy_task_manager.add_log(task_id, "部署完成！")
            logger.info(f"应用 {app_info['name']} 部署成功")
            
        except Exception as e:
            error_msg = f"部署过程中发生异常: {str(e)}"
            logger.error(f"部署K8s应用失败: {e}")
            deploy_task_manager.update_task_status(task_id, DeployStatus.FAILED, error_message=error_msg)
            deploy_task_manager.add_log(task_id, f"错误: {error_msg}")
            
            try:
                # 更新数据库状态
                from aistack.server.db import get_engine
                engine = get_engine()
                async with AsyncSession(engine) as update_session:
                    async with update_session.begin():
                        app = await update_session.get(K8sApp, app_id)
                        if app:
                            app.status = K8sAppStatusEnum.ERROR
                            app.status_message = error_msg
                            app.last_updated_at = datetime.utcnow()
            except Exception as update_error:
                logger.error(f"更新部署状态失败: {update_error}")

    async def get_app_status(self, session: AsyncSession, app_id: int, user_id: int) -> Dict[str, Any]:
        """获取K8s应用状态"""
        try:
            # 验证应用所有权
            has_permission, app, error_msg = await self._verify_app_ownership(session, app_id, user_id)
            if not has_permission:
                return {"success": False, "message": error_msg}
            
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    # 重新获取应用信息
                    app = await new_session.get(K8sApp, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 获取K8s集群中的实际状态
                    k8s_success, k8s_message, k8s_status = self.k8s_manager.get_app_status(
                        app_name=app.name,
                        namespace=app.namespace
                    )
                    
                    if k8s_success:
                        # 更新应用状态
                        app.status_message = k8s_message
                        app.last_updated_at = datetime.utcnow()
                    
                    # 提取数据，避免在session外访问
                    app_name = app.name
                    app_status = app.status
                    app_status_message = app.status_message
                    deployed_at = app.deployed_at
                    last_updated_at = app.last_updated_at
           
            return {
                "success": True,
                "app_name": app_name,
                "status": app_status,
                "status_message": app_status_message,
                "deployed_at": deployed_at,
                "last_updated_at": last_updated_at,
                "k8s_status": k8s_status if k8s_success else None
            }
       
        except Exception as e:
            logger.error(f"获取K8s应用状态失败: {e}")
            return {"success": False, "message": f"获取状态失败: {e}"}

    async def scale_app(self, session: AsyncSession, app_id: int, user_id: int, replicas: int) -> Dict[str, Any]:
        """扩缩容K8s应用"""
        try:
            # 验证应用所有权
            has_permission, app, error_msg = await self._verify_app_ownership(session, app_id, user_id)
            if not has_permission:
                return {"success": False, "message": error_msg}
            
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    # 重新获取应用信息
                    app = await new_session.get(K8sApp, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 更新应用状态为扩缩容中
                    app.status = K8sAppStatusEnum.SCALING
                    app.status_message = f"应用扩缩容到 {replicas} 个副本"
                    app.last_updated_at = datetime.utcnow()
           
            # 执行扩缩容
            success, message = self.k8s_manager.scale_app(
                app_name=app.name,
                namespace=app.namespace,
                replicas=replicas
            )
            
            # 更新应用状态
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(K8sApp, app_id)
                    if app:
                        if success:
                            app.status = K8sAppStatusEnum.RUNNING
                            app.status_message = f"应用扩缩容成功到 {replicas} 个副本"
                            app.replicas = replicas
                        else:
                            app.status = K8sAppStatusEnum.ERROR
                            app.status_message = f"应用扩缩容失败: {message}"
                        app.last_updated_at = datetime.utcnow()
            
            return {"success": success, "message": message}
           
        except Exception as e:
            logger.error(f"扩缩容K8s应用失败: {e}")
            return {"success": False, "message": f"扩缩容失败: {e}"}

    async def delete_app_from_k8s(self, session: AsyncSession, app_id: int, user_id: int) -> Dict[str, Any]:
        """从K8s集群中删除应用"""
        try:
            # 验证应用所有权
            has_permission, app, error_msg = await self._verify_app_ownership(session, app_id, user_id)
            if not has_permission:
                return {"success": False, "message": error_msg}
            
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            
            # 先获取应用名称和命名空间，用于后续删除操作
            app_name = None
            app_namespace = None
            
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    # 重新获取应用信息
                    app = await new_session.get(K8sApp, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                    
                    # 提取名称和命名空间，避免在session关闭后访问
                    app_name = app.name
                    app_namespace = app.namespace
                    
                    # 更新应用状态为删除中
                    app.status = K8sAppStatusEnum.DELETING
                    app.status_message = "应用删除任务已启动"
                    app.last_updated_at = datetime.utcnow()
           
            # 从K8s集群中删除应用
            success, message, delete_result = self.k8s_manager.delete_app(
                app_name=app_name,
                namespace=app_namespace
            )
            
            # 更新应用状态
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(K8sApp, app_id)
                    if app:
                        if success:
                            app.status = K8sAppStatusEnum.STOPPED
                            app.status_message = "应用已从K8s集群中删除"
                        else:
                            app.status = K8sAppStatusEnum.ERROR
                            app.status_message = f"应用删除失败: {message}"
                        app.last_updated_at = datetime.utcnow()
            
            return {"success": success, "message": message, "result": delete_result}
           
        except Exception as e:
            logger.error(f"从K8s集群删除应用失败: {e}")
            return {"success": False, "message": f"删除失败: {e}"}
