import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlmodel import select, Session
from sqlmodel.ext.asyncio.session import AsyncSession

from aistack.schemas.apps import (
    App, AppCreate, AppUpdate, AppPublic, AppStatusEnum,
    AppInstance, AppInstanceCreate, AppInstanceUpdate, AppInstancePublic
)
from aistack.utils.k8s_manager import KubernetesManager

logger = logging.getLogger(__name__)


class K8sAppService:
    """Kubernetes应用管理服务"""
   
    def __init__(self):
        self.k8s_manager = KubernetesManager()
        self._check_k8s_permissions()

    def _check_k8s_permissions(self) -> None:
        """
        检查Kubernetes权限和配置
        """
        try:
            # 测试Kubernetes连接
            success, message = self.k8s_manager.client.test_connection()
            if success:
                logger.info(f"Kubernetes连接正常: {message}")
            else:
                logger.warning(f"Kubernetes连接失败: {message}")
                logger.warning("请确保Kubernetes集群可访问，并且有足够的权限")
            
        except Exception as e:
            logger.warning(f"Kubernetes权限检查失败: {e}")
            logger.warning("请确保Kubernetes集群正在运行，并且当前用户有权限访问")

    async def _verify_app_ownership(self, session: AsyncSession, app_id: int, user_id: int) -> Tuple[bool, Optional[App], str]:
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
            # user_id<=0 表示不启用用户隔离，放宽所有权校验
            if user_id and user_id > 0:
                result = await session.exec(
                    select(App).where(App.id == app_id, App.user_id == user_id)
                )
                app = result.first()
            else:
                result = await session.exec(
                    select(App).where(App.id == app_id)
                )
                app = result.first()
            
            if not app:
                # 检查应用是否存在
                result = await session.exec(
                    select(App).where(App.id == app_id)
                )
                existing_app = result.first()
                
                if existing_app and user_id and user_id > 0:
                    return False, None, "您没有权限操作此应用"
                else:
                    return False, None, "应用不存在"
            
            return True, app, ""
            
        except Exception as e:
            logger.error(f"验证应用所有权失败: {e}")
            return False, None, f"验证应用所有权失败: {e}"

    async def _update_app_status(
        self,
        session: AsyncSession,
        app_id: int,
        status: AppStatusEnum,
        status_message: str = ""
    ) -> None:
        """
        更新应用状态
       
        Args:
            session: 数据库会话
            app_id: 应用ID
            status: 应用状态
            status_message: 状态消息
        """
        async with session.begin():
            app = await session.get(App, app_id)
            if app:
                app.status = status
                if status_message:
                    app.build_message = status_message

    async def create_app(self, session: AsyncSession, app_data: AppCreate, user_id: int) -> AppPublic:
        """创建应用"""
        try:
            # 检查应用名称是否已存在（在同一用户下）
            if user_id and user_id > 0:
                result = await session.exec(
                    select(App).where(App.name == app_data.name, App.user_id == user_id)
                )
            else:
                result = await session.exec(
                    select(App).where(App.name == app_data.name)
                )
            existing_app = result.first()
           
            if existing_app:
                raise ValueError(f"应用名称已存在: {app_data.name}")
           
            # 创建应用
            app_data_dict = app_data.dict()
            
            # 将 AppVolume 和 AppURL 对象转换为字典
            if app_data_dict.get('volumes'):
                app_data_dict['volumes'] = [
                    volume.dict() if hasattr(volume, 'dict') else volume 
                    for volume in app_data_dict['volumes']
                ]
            
            if app_data_dict.get('urls'):
                app_data_dict['urls'] = [
                    url.dict() if hasattr(url, 'dict') else url 
                    for url in app_data_dict['urls']
                ]
            
            # 添加用户ID（无用户则为 None）
            app_data_dict['user_id'] = user_id if (user_id and user_id > 0) else None
            
            app = App(**app_data_dict)
            session.add(app)
            await session.commit()
            await session.refresh(app)
           
            logger.info(f"应用创建成功: {app.name} (User: {user_id})")
            return AppPublic.from_orm(app)
           
        except Exception as e:
            await session.rollback()
            logger.error(f"创建应用失败: {e}")
            raise

    async def get_app(self, session: AsyncSession, app_id: int, user_id: int) -> Optional[AppPublic]:
        """获取应用详情"""
        try:
            if user_id and user_id > 0:
                result = await session.exec(
                    select(App).where(App.id == app_id, App.user_id == user_id)
                )
            else:
                result = await session.exec(
                    select(App).where(App.id == app_id)
                )
            app = result.first()
            if not app:
                return None
           
            return AppPublic.from_orm(app)
           
        except Exception as e:
            logger.error(f"获取应用失败: {e}")
            raise

    async def list_apps(self, session: AsyncSession, user_id: int,
                       page: int = 1, per_page: int = 100,
                       category: Optional[str] = None,
                       is_active: Optional[bool] = None) -> List[AppPublic]:
        """列出应用"""
        try:
            # user_id<=0 表示列出全部应用（仅用于无鉴权测试）
            query = select(App)
            if user_id and user_id > 0:
                query = query.where(App.user_id == user_id)
           
            if category:
                query = query.where(App.category == category)
           
            if is_active is not None:
                query = query.where(App.is_active == is_active)
           
            # 计算偏移量
            skip = (page - 1) * per_page
            result = await session.exec(query.offset(skip).limit(per_page))
            return [AppPublic.from_orm(app) for app in result.all()]
           
        except Exception as e:
            logger.error(f"列出应用失败: {e}")
            raise

    async def update_app(self, session: AsyncSession, app_id: int, app_data: AppUpdate) -> Optional[AppPublic]:
        """更新应用"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return None
           
            # 更新字段
            update_data = app_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(app, field, value)
           
            await session.commit()
            await session.refresh(app)
           
            logger.info(f"应用更新成功: {app.name}")
            return AppPublic.from_orm(app)
           
        except Exception as e:
            await session.rollback()
            logger.error(f"更新应用失败: {e}")
            raise

    async def delete_app(self, session: AsyncSession, app_id: int, user_id: int, 
                        cleanup_k8s: bool = True) -> Dict[str, Any]:
        """删除应用"""
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
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 检查是否有运行中的实例
                    result = await new_session.exec(
                        select(AppInstance).where(
                            AppInstance.app_id == app_id,
                            AppInstance.status.in_([AppStatusEnum.RUNNING, AppStatusEnum.STARTING, AppStatusEnum.DEPLOYING])
                        )
                    )
                    running_instances = result.all()
                   
                    if running_instances:
                        return {"success": False, "message": f"应用 {app.name} 有运行中的实例，无法删除"}
                    
                    # 保存应用名称，避免会话关闭后无法访问
                    app_name = app.name
                    
                    # 如果需要清理K8s资源
                    if cleanup_k8s:
                        try:
                            # 使用与部署时相同的命名空间逻辑
                            k8s_namespace = f"aistack-{user_id}" if (user_id and user_id > 0) else "aistack-public"
                            success, message, delete_result = self.k8s_manager.delete_app(
                                app_name=app_name,
                                namespace=k8s_namespace
                            )
                            if success:
                                logger.info(f"K8s资源清理成功: {message}")
                            else:
                                logger.warning(f"K8s资源清理失败: {message}")
                        except Exception as e:
                            logger.warning(f"清理K8s资源时出错: {e}")
                   
                    # 删除所有相关的实例记录
                    all_instances = await new_session.exec(
                        select(AppInstance).where(AppInstance.app_id == app_id)
                    )
                    instances_to_delete = all_instances.all()
                    
                    for instance in instances_to_delete:
                        await new_session.delete(instance)
                    
                    # 删除应用
                    await new_session.delete(app)
                    # 事务会自动提交
           
            logger.info(f"应用删除成功: {app_name}")
            return {"success": True, "message": f"应用 {app_name} 删除成功"}
           
        except Exception as e:
            logger.error(f"删除应用失败: {e}")
            return {"success": False, "message": f"删除应用失败: {e}"}

    async def deploy_app(self, session: AsyncSession, app_id: int, user_id: int) -> Dict[str, Any]:
        """部署应用到Kubernetes"""
        try:
            # 验证应用所有权
            has_permission, app, error_msg = await self._verify_app_ownership(session, app_id, user_id)
            if not has_permission:
                return {"success": False, "message": error_msg}
            
            # 检查必要的YAML配置
            if not app.deployment_yaml_url:
                return {"success": False, "message": "缺少Deployment YAML配置"}
            
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    # 重新获取应用信息
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 检查是否已在部署中
                    if app.status in [AppStatusEnum.DEPLOYING, AppStatusEnum.STARTING]:
                        return {"success": False, "message": "应用正在部署中，请稍后再试"}
                   
                    # 更新应用状态为部署中
                    app.status = AppStatusEnum.DEPLOYING
                    app.build_started_at = datetime.utcnow()
                    app.build_message = "Kubernetes部署任务已启动"
           
            # 启动异步部署任务
            asyncio.create_task(self._deploy_app_async(app_id, user_id))
           
            logger.info(f"应用Kubernetes部署任务已启动")
            return {
                "success": True,
                "message": "Kubernetes部署任务已启动，请通过状态接口查询进度",
                "deploy_id": f"k8s_{app_id}_{int(datetime.utcnow().timestamp())}"
            }
           
        except Exception as e:
            logger.error(f"启动Kubernetes部署失败: {e}")
            # 用新的 session 更新状态
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if app:
                        app.status = AppStatusEnum.DEPLOY_FAILED
                        app.build_status = "failed"
                        app.build_message = f"启动Kubernetes部署失败: {e}"
                        app.build_finished_at = datetime.utcnow()
            return {"success": False, "message": f"启动Kubernetes部署失败: {e}"}

    async def _deploy_app_async(self, app_id: int, user_id: int):
        """异步部署应用到Kubernetes"""
        try:
            logger.info(f"开始异步部署应用到Kubernetes，应用ID: {app_id}")
           
            # 创建新的数据库会话
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as session:
                async with session.begin():
                    app = await session.get(App, app_id)
                    if not app:
                        logger.error(f"应用不存在: {app_id}")
                        return
                    
                    # 保存应用信息，因为session会在async with块结束后关闭
                    app_info = {
                        'name': app.name,
                        'deployment_yaml_url': app.deployment_yaml_url,
                        'service_yaml_url': app.service_yaml_url,
                        'config_yaml_url': app.config_yaml_url,
                        'ingress_yaml_url': app.ingress_yaml_url,
                        'user_id': user_id
                    }
           
            # 准备K8s命名空间和标签
            k8s_namespace = f"aistack-{user_id}" if (user_id and user_id > 0) else "aistack-public"
            # 仅添加跟踪标签，避免覆盖 YAML 中的 app 标签
            custom_labels = {
                "managed-by": "aistack",
                "user-id": str(user_id)
            }
            
            # 部署到Kubernetes
            success, message, deploy_result = self.k8s_manager.deploy_app(
                app_name=app_info['name'],
                namespace=k8s_namespace,
                deployment_yaml_url=app_info['deployment_yaml_url'],
                service_yaml_url=app_info['service_yaml_url'],
                config_yaml_url=app_info['config_yaml_url'],
                ingress_yaml_url=app_info['ingress_yaml_url'],
                custom_labels=custom_labels
            )
           
            # 创建新的会话来更新状态
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                await self._update_app_status(
                    new_session, app_id,
                    AppStatusEnum.RUNNING if success else AppStatusEnum.DEPLOY_FAILED,
                    message
                )
           
            if success:
                logger.info(f"应用 {app_info['name']} Kubernetes部署成功")
            else:
                logger.error(f"应用 {app_info['name']} Kubernetes部署失败: {message}")
           
        except Exception as e:
            logger.error(f"异步Kubernetes部署过程中发生异常: {e}")
            try:
                # 创建新的数据库会话来处理异常
                engine = get_engine()
                async with AsyncSession(engine) as new_session:
                    await self._update_app_status(
                        new_session, app_id,
                        AppStatusEnum.DEPLOY_FAILED,
                        f"Kubernetes部署异常: {str(e)}"
                    )
            except Exception as update_error:
                logger.error(f"更新部署状态失败: {update_error}")

    async def get_app_status(self, session: AsyncSession, app_id: int, user_id: int) -> Dict[str, Any]:
        """获取应用状态"""
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
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                    
                    # 获取K8s状态
                    k8s_namespace = f"aistack-{user_id}" if (user_id and user_id > 0) else "aistack-public"
                    k8s_success, k8s_message, k8s_status = self.k8s_manager.get_app_status(
                        app_name=app.name,
                        namespace=k8s_namespace
                    )
                    
                    if k8s_success:
                        # 同步K8s状态到数据库
                        if k8s_status.get("overall_status") == "Running":
                            app.status = AppStatusEnum.RUNNING
                        elif k8s_status.get("overall_status") == "Not Ready":
                            app.status = AppStatusEnum.ERROR
                        else:
                            app.status = AppStatusEnum.STOPPED
                    
                    # 提取数据，避免在session外访问
                    app_name = app.name
                    app_status = app.status
                    build_message = app.build_message
                    build_started_at = app.build_started_at
                    build_finished_at = app.build_finished_at
           
            return {
                "success": True,
                "app_name": app_name,
                "status": app_status,
                "message": build_message,
                "k8s_status": k8s_status if k8s_success else None,
                "k8s_message": k8s_message,
                "build_started_at": build_started_at,
                "build_finished_at": build_finished_at
            }
       
        except Exception as e:
            logger.error(f"获取应用状态失败: {e}")
            return {"success": False, "message": f"获取状态失败: {e}"}

    async def scale_app(self, session: AsyncSession, app_id: int, user_id: int, replicas: int) -> Dict[str, Any]:
        """扩缩容应用"""
        try:
            # 验证应用所有权
            has_permission, app, error_msg = await self._verify_app_ownership(session, app_id, user_id)
            if not has_permission:
                return {"success": False, "message": error_msg}
            
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            app_name = None
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    # 重新获取应用信息
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                    
                    # 保存应用名称，避免会话关闭后无法访问
                    app_name = app.name
                    
                    # 更新状态为扩缩容中
                    app.status = AppStatusEnum.SCALING
                    app.build_message = f"正在扩缩容到 {replicas} 个副本"
            
            # 执行K8s扩缩容
            k8s_namespace = f"aistack-{user_id}" if (user_id and user_id > 0) else "aistack-public"
            success, message = self.k8s_manager.scale_app(
                app_name=app_name,
                namespace=k8s_namespace,
                replicas=replicas
            )
            
            # 更新状态
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                await self._update_app_status(
                    new_session, app_id,
                    AppStatusEnum.RUNNING if success else AppStatusEnum.ERROR,
                    message
                )
            
            return {"success": success, "message": message}
           
        except Exception as e:
            logger.error(f"扩缩容应用失败: {e}")
            return {"success": False, "message": f"扩缩容失败: {e}"}

    async def stop_app(self, session: AsyncSession, app_id: int, user_id: int) -> Dict[str, Any]:
        """停止应用（扩缩容到0）"""
        return await self.scale_app(session, app_id, user_id, 0)

    async def start_app(self, session: AsyncSession, app_id: int, user_id: int, replicas: int = 1) -> Dict[str, Any]:
        """启动应用（扩缩容到指定副本数）"""
        return await self.scale_app(session, app_id, user_id, replicas)

