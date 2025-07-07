import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import select, Session
from sqlmodel.ext.asyncio.session import AsyncSession

from aistack.schemas.apps import (
    App, AppCreate, AppUpdate, AppPublic, AppStatusEnum, ImageSourceEnum,
    AppInstance, AppInstanceCreate, AppInstanceUpdate, AppInstancePublic
)
from aistack.utils.docker_manager import DockerManager

logger = logging.getLogger(__name__)


class AppService:
    """应用管理服务"""
    
    def __init__(self):
        self.docker_manager = DockerManager()
    
    async def create_app(self, session: AsyncSession, app_data: AppCreate) -> AppPublic:
        """创建应用"""
        try:
            # 检查应用名称是否已存在
            existing_app = await session.exec(
                select(App).where(App.name == app_data.name)
            ).first()
            
            if existing_app:
                raise ValueError(f"应用名称已存在: {app_data.name}")
            
            # 创建应用
            app = App.from_orm(app_data)
            session.add(app)
            await session.commit()
            await session.refresh(app)
            
            logger.info(f"应用创建成功: {app.name}")
            return AppPublic.from_orm(app)
            
        except Exception as e:
            await session.rollback()
            logger.error(f"创建应用失败: {e}")
            raise
    
    async def get_app(self, session: AsyncSession, app_id: int) -> Optional[AppPublic]:
        """获取应用详情"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return None
            
            return AppPublic.from_orm(app)
            
        except Exception as e:
            logger.error(f"获取应用失败: {e}")
            raise
    
    async def get_app_by_name(self, session: AsyncSession, app_name: str) -> Optional[AppPublic]:
        """根据名称获取应用"""
        try:
            app = await session.exec(
                select(App).where(App.name == app_name)
            ).first()
            
            if not app:
                return None
            
            return AppPublic.from_orm(app)
            
        except Exception as e:
            logger.error(f"根据名称获取应用失败: {e}")
            raise
    
    async def list_apps(self, session: AsyncSession, 
                       skip: int = 0, limit: int = 100,
                       category: Optional[str] = None,
                       is_active: Optional[bool] = None) -> List[AppPublic]:
        """列出应用"""
        try:
            query = select(App)
            
            if category:
                query = query.where(App.category == category)
            
            if is_active is not None:
                query = query.where(App.is_active == is_active)
            
            apps = await session.exec(query.offset(skip).limit(limit))
            return [AppPublic.from_orm(app) for app in apps.all()]
            
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
    
    async def delete_app(self, session: AsyncSession, app_id: int) -> bool:
        """删除应用"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return False
            
            # 检查是否有运行中的实例
            running_instances = await session.exec(
                select(AppInstance).where(
                    AppInstance.app_id == app_id,
                    AppInstance.status.in_([AppStatusEnum.RUNNING, AppStatusEnum.STARTING])
                )
            ).all()
            
            if running_instances:
                raise ValueError(f"应用 {app.name} 有运行中的实例，无法删除")
            
            await session.delete(app)
            await session.commit()
            
            logger.info(f"应用删除成功: {app.name}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"删除应用失败: {e}")
            raise
    
    async def start_build_image(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """启动镜像构建（异步）"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 检查是否已在构建中
            if app.status == AppStatusEnum.BUILDING:
                return {"success": False, "message": "应用正在构建中，请稍后再试"}
            
            # 更新应用状态为构建中
            app.status = AppStatusEnum.BUILDING
            app.build_started_at = datetime.utcnow()
            app.build_message = "构建任务已启动"
            await session.commit()
            
            # 启动异步构建任务
            asyncio.create_task(self._build_image_async(session, app_id))
            
            logger.info(f"应用 {app.name} 构建任务已启动")
            return {
                "success": True, 
                "message": "构建任务已启动，请通过状态接口查询进度",
                "build_id": f"build_{app_id}_{int(datetime.utcnow().timestamp())}"
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"启动构建失败: {e}")
            return {"success": False, "message": f"启动构建失败: {e}"}
    
    async def _build_image_async(self, session: AsyncSession, app_id: int):
        """异步获取镜像（构建或拉取）"""
        try:
            logger.info(f"开始异步获取镜像，应用ID: {app_id}")
            
            # 重新获取应用信息（因为可能在其他协程中被修改）
            async with session.begin():
                app = await session.get(App, app_id)
                if not app:
                    logger.error(f"应用不存在: {app_id}")
                    return
            
            # 根据镜像获取方式执行相应操作
            if app.image_source == ImageSourceEnum.BUILD:
                # 构建镜像
                if not app.dockerfile_path:
                    raise ValueError("构建模式需要指定Dockerfile路径")
                
                success, message = self.docker_manager.build_image(
                    dockerfile_path=app.dockerfile_path,
                    image_name=app.image_name,
                    image_tag=app.image_tag
                )
            elif app.image_source == ImageSourceEnum.PULL:
                # 拉取镜像
                image_name = app.image_url or app.image_name
                success, message = self.docker_manager.pull_image(
                    image_name=image_name,
                    image_tag=app.image_tag
                )
            else:
                raise ValueError(f"不支持的镜像获取方式: {app.image_source}")
            
            # 更新构建结果
            async with session.begin():
                app = await session.get(App, app_id)
                app.build_finished_at = datetime.utcnow()
                
                if success:
                    app.status = AppStatusEnum.STOPPED
                    app.build_status = "success"
                    app.build_message = message
                    logger.info(f"应用 {app.name} 镜像获取成功")
                else:
                    app.status = AppStatusEnum.BUILD_FAILED
                    app.build_status = "failed"
                    app.build_message = message
                    logger.error(f"应用 {app.name} 镜像获取失败: {message}")
            
        except Exception as e:
            logger.error(f"异步获取镜像过程中发生异常: {e}")
            try:
                async with session.begin():
                    app = await session.get(App, app_id)
                    if app:
                        app.status = AppStatusEnum.BUILD_FAILED
                        app.build_status = "failed"
                        app.build_message = f"获取镜像异常: {str(e)}"
                        app.build_finished_at = datetime.utcnow()
            except Exception as update_error:
                logger.error(f"更新构建状态失败: {update_error}")
    
    async def get_build_status(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """获取构建状态"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 计算构建时长
            duration = None
            if app.build_started_at:
                end_time = app.build_finished_at or datetime.utcnow()
                duration = (end_time - app.build_started_at).total_seconds()
            
            return {
                "success": True,
                "app_id": app_id,
                "app_name": app.name,
                "status": app.status,
                "build_status": getattr(app, 'build_status', None),
                "build_message": getattr(app, 'build_message', None),
                "build_started_at": app.build_started_at,
                "build_finished_at": app.build_finished_at,
                "duration_seconds": duration,
                "duration_formatted": self._format_duration(duration) if duration else None
            }
            
        except Exception as e:
            logger.error(f"获取构建状态失败: {e}")
            return {"success": False, "message": f"获取构建状态失败: {e}"}
    
    def _format_duration(self, seconds: float) -> str:
        """格式化构建时长"""
        if seconds is None:
            return None
        
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    
    async def start_pull_image(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """启动镜像拉取（异步）"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 检查是否已在构建中
            if app.status == AppStatusEnum.BUILDING:
                return {"success": False, "message": "应用正在获取镜像中，请稍后再试"}
            
            # 临时设置为拉取模式
            app.image_source = ImageSourceEnum.PULL
            app.status = AppStatusEnum.BUILDING
            app.build_started_at = datetime.utcnow()
            app.build_message = "镜像拉取任务已启动"
            await session.commit()
            
            # 启动异步拉取任务
            asyncio.create_task(self._pull_image_async(session, app_id))
            
            logger.info(f"应用 {app.name} 镜像拉取任务已启动")
            return {
                "success": True, 
                "message": "镜像拉取任务已启动，请通过状态接口查询进度",
                "build_id": f"pull_{app_id}_{int(datetime.utcnow().timestamp())}"
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"启动镜像拉取失败: {e}")
            return {"success": False, "message": f"启动镜像拉取失败: {e}"}
    
    async def _pull_image_async(self, session: AsyncSession, app_id: int):
        """异步拉取镜像"""
        try:
            logger.info(f"开始异步拉取镜像，应用ID: {app_id}")
            
            # 重新获取应用信息
            async with session.begin():
                app = await session.get(App, app_id)
                if not app:
                    logger.error(f"应用不存在: {app_id}")
                    return
            
            # 拉取镜像
            image_name = app.image_url or app.image_name
            success, message = self.docker_manager.pull_image(
                image_name=image_name,
                image_tag=app.image_tag
            )
            
            # 更新拉取结果
            async with session.begin():
                app = await session.get(App, app_id)
                app.build_finished_at = datetime.utcnow()
                
                if success:
                    app.status = AppStatusEnum.STOPPED
                    app.build_status = "success"
                    app.build_message = message
                    logger.info(f"应用 {app.name} 镜像拉取成功")
                else:
                    app.status = AppStatusEnum.BUILD_FAILED
                    app.build_status = "failed"
                    app.build_message = message
                    logger.error(f"应用 {app.name} 镜像拉取失败: {message}")
            
        except Exception as e:
            logger.error(f"异步拉取镜像过程中发生异常: {e}")
            try:
                async with session.begin():
                    app = await session.get(App, app_id)
                    if app:
                        app.status = AppStatusEnum.BUILD_FAILED
                        app.build_status = "failed"
                        app.build_message = f"拉取镜像异常: {str(e)}"
                        app.build_finished_at = datetime.utcnow()
            except Exception as update_error:
                logger.error(f"更新拉取状态失败: {update_error}")
    
    async def build_app_image(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """构建应用镜像（同步版本，保留用于兼容性）"""
        logger.warning("使用同步构建方法，建议使用异步方法 start_build_image")
        return await self.start_build_image(session, app_id)
    
    async def get_image_info(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """获取应用镜像信息"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 获取镜像信息
            success, message, image_info = self.docker_manager.get_image_info(
                image_name=app.image_name,
                image_tag=app.image_tag
            )
            
            if not success:
                return {"success": False, "message": message}
            
            return {
                "success": True,
                "message": "获取镜像信息成功",
                "data": {
                    "app_info": {
                        "id": app.id,
                        "name": app.name,
                        "image_source": app.image_source,
                        "image_name": app.image_name,
                        "image_tag": app.image_tag,
                        "image_url": app.image_url
                    },
                    "image_info": image_info
                }
            }
            
        except Exception as e:
            logger.error(f"获取镜像信息失败: {e}")
            return {"success": False, "message": f"获取镜像信息失败: {e}"}
    
    async def start_app(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """启动应用"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 检查是否已有运行中的实例
            running_instance = await session.exec(
                select(AppInstance).where(
                    AppInstance.app_id == app_id,
                    AppInstance.status.in_([AppStatusEnum.RUNNING, AppStatusEnum.STARTING])
                )
            ).first()
            
            if running_instance:
                return {"success": False, "message": "应用已在运行中"}
            
            # 创建新实例
            instance = AppInstance(
                app_id=app_id,
                status=AppStatusEnum.STARTING,
                started_at=datetime.utcnow()
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            
            # 启动容器
            success, message, container_id = self.docker_manager.start_container(
                app_name=app.name,
                image_name=app.image_name,
                image_tag=app.image_tag,
                container_name=app.container_name,
                ports=app.ports,
                environment=app.environment,
                volumes=app.volumes,
                memory_limit=app.memory_limit,
                cpu_limit=app.cpu_limit
            )
            
            # 更新实例状态
            if success:
                instance.container_id = container_id
                instance.status = AppStatusEnum.RUNNING
                instance.status_message = "容器启动成功"
            else:
                instance.status = AppStatusEnum.ERROR
                instance.status_message = message
                instance.stopped_at = datetime.utcnow()
            
            await session.commit()
            
            return {"success": success, "message": message, "instance_id": instance.id}
            
        except Exception as e:
            await session.rollback()
            logger.error(f"启动应用失败: {e}")
            return {"success": False, "message": f"启动失败: {e}"}
    
    async def stop_app(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """停止应用"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 查找运行中的实例
            running_instance = await session.exec(
                select(AppInstance).where(
                    AppInstance.app_id == app_id,
                    AppInstance.status.in_([AppStatusEnum.RUNNING, AppStatusEnum.STARTING])
                )
            ).first()
            
            if not running_instance:
                return {"success": False, "message": "应用未在运行"}
            
            # 停止容器
            success, message = self.docker_manager.stop_container(running_instance.container_id)
            
            # 更新实例状态
            if success:
                running_instance.status = AppStatusEnum.STOPPED
                running_instance.status_message = "容器已停止"
                running_instance.stopped_at = datetime.utcnow()
            else:
                running_instance.status = AppStatusEnum.ERROR
                running_instance.status_message = message
            
            await session.commit()
            
            return {"success": success, "message": message}
            
        except Exception as e:
            await session.rollback()
            logger.error(f"停止应用失败: {e}")
            return {"success": False, "message": f"停止失败: {e}"}
    
    async def get_app_status(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """获取应用状态"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 获取最新实例
            latest_instance = await session.exec(
                select(AppInstance).where(AppInstance.app_id == app_id)
                .order_by(AppInstance.created_at.desc())
            ).first()
            
            if not latest_instance:
                return {
                    "success": True,
                    "app_name": app.name,
                    "status": AppStatusEnum.STOPPED,
                    "message": "无运行实例"
                }
            
            # 如果实例正在运行，获取实时状态
            if latest_instance.container_id and latest_instance.status in [AppStatusEnum.RUNNING, AppStatusEnum.STARTING]:
                success, message, status_info = self.docker_manager.get_container_status(latest_instance.container_id)
                if success:
                    # 更新实例状态
                    latest_instance.status = AppStatusEnum.RUNNING if status_info['running'] else AppStatusEnum.STOPPED
                    latest_instance.ip_address = status_info['ip_address']
                    latest_instance.exposed_ports = status_info['ports']
                    await session.commit()
            
            return {
                "success": True,
                "app_name": app.name,
                "status": latest_instance.status,
                "message": latest_instance.status_message,
                "container_id": latest_instance.container_id,
                "started_at": latest_instance.started_at,
                "stopped_at": latest_instance.stopped_at,
                "ip_address": latest_instance.ip_address,
                "exposed_ports": latest_instance.exposed_ports
            }
            
        except Exception as e:
            logger.error(f"获取应用状态失败: {e}")
            return {"success": False, "message": f"获取状态失败: {e}"}
    
    async def get_app_stats(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """获取应用资源统计"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 获取运行中的实例
            running_instance = await session.exec(
                select(AppInstance).where(
                    AppInstance.app_id == app_id,
                    AppInstance.status == AppStatusEnum.RUNNING
                )
            ).first()
            
            if not running_instance or not running_instance.container_id:
                return {"success": False, "message": "应用未在运行"}
            
            # 获取容器统计信息
            success, message, stats_info = self.docker_manager.get_container_stats(running_instance.container_id)
            
            if success:
                # 更新实例统计信息
                running_instance.memory_usage = stats_info['memory_usage']
                running_instance.cpu_usage = stats_info['cpu_usage']
                await session.commit()
            
            return {
                "success": success,
                "message": message,
                "stats": stats_info if success else None
            }
            
        except Exception as e:
            logger.error(f"获取应用统计失败: {e}")
            return {"success": False, "message": f"获取统计失败: {e}"}
    
    async def list_app_instances(self, session: AsyncSession, app_id: int) -> List[AppInstancePublic]:
        """列出应用实例"""
        try:
            instances = await session.exec(
                select(AppInstance).where(AppInstance.app_id == app_id)
                .order_by(AppInstance.created_at.desc())
            ).all()
            
            return [AppInstancePublic.from_orm(instance) for instance in instances]
            
        except Exception as e:
            logger.error(f"列出应用实例失败: {e}")
            raise
    
    async def cleanup_app_instances(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """清理应用实例"""
        try:
            app = await session.get(App, app_id)
            if not app:
                return {"success": False, "message": "应用不存在"}
            
            # 获取所有实例
            instances = await session.exec(
                select(AppInstance).where(AppInstance.app_id == app_id)
            ).all()
            
            cleaned_count = 0
            for instance in instances:
                if instance.container_id:
                    # 删除容器
                    success, message = self.docker_manager.remove_container(instance.container_id)
                    if success:
                        cleaned_count += 1
                
                # 删除实例记录
                await session.delete(instance)
            
            await session.commit()
            
            return {
                "success": True,
                "message": f"清理了 {cleaned_count} 个实例",
                "cleaned_count": cleaned_count
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"清理应用实例失败: {e}")
            return {"success": False, "message": f"清理失败: {e}"}
    
    async def find_apps_by_host_path(self, session: AsyncSession, host_path: str) -> List[Dict[str, Any]]:
        """根据本地路径查找所有映射该路径的应用及卷信息"""
        try:
            # 查询所有应用
            apps = await session.exec(select(App))
            result = []
            for app in apps.all():
                if not app.volumes:
                    continue
                for volume in app.volumes:
                    # 兼容volume为dict或AppVolume对象
                    v_host_path = volume["host_path"] if isinstance(volume, dict) else getattr(volume, "host_path", None)
                    if v_host_path and v_host_path.rstrip("/\\") == host_path.rstrip("/\\"):
                        result.append({
                            "app_id": app.id,
                            "app_name": app.name,
                            "display_name": app.display_name,
                            "volume": volume
                        })
            return result
        except Exception as e:
            logger.error(f"查找host_path映射失败: {e}")
            raise 