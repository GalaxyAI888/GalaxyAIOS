
import logging
import asyncio
import tempfile
import os
import shutil
import urllib.request
from typing import List, Optional, Dict, Any, Tuple
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

    def _download_dockerfile(self, url: str, temp_dir: str) -> Tuple[bool, str]:
        """
        从URL下载Dockerfile到临时目录
       
        Args:
            url: Dockerfile的URL地址
            temp_dir: 临时目录路径
           
        Returns:
            Tuple[bool, str]: (是否成功, 成功时返回Dockerfile路径/失败时返回错误信息)
        """
        dockerfile_path = os.path.join(temp_dir, "Dockerfile")
        try:
            urllib.request.urlretrieve(url, dockerfile_path)
            return True, dockerfile_path
        except Exception as e:
            return False, f"下载Dockerfile失败: {str(e)}"

    def _create_temp_dir(self) -> str:
        """
        创建临时目录
       
        Returns:
            str: 临时目录路径
        """
        return tempfile.mkdtemp()

    def _cleanup_temp_dir(self, temp_dir: Optional[str]) -> None:
        """
        清理临时目录
       
        Args:
            temp_dir: 临时目录路径
        """
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _update_build_status(
        self,
        session: AsyncSession,
        app_id: int,
        status: AppStatusEnum,
        build_status: str,
        message: str
    ) -> None:
        """
        更新应用构建状态
       
        Args:
            session: 数据库会话
            app_id: 应用ID
            status: 应用状态
            build_status: 构建状态
            message: 状态消息
        """
        async with session.begin():
            app = await session.get(App, app_id)
            if app:
                app.status = status
                app.build_status = build_status
                app.build_message = message
                app.build_finished_at = datetime.utcnow()
   
    async def create_app(self, session: AsyncSession, app_data: AppCreate) -> AppPublic:
        """创建应用"""
        try:
            # 检查应用名称是否已存在
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
            
            app = App(**app_data_dict)
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
            result = await session.exec(
                select(App).where(App.name == app_name)
            )
            app = result.first()
           
            if not app:
                return None
           
            return AppPublic.from_orm(app)
           
        except Exception as e:
            logger.error(f"根据名称获取应用失败: {e}")
            raise
   
    async def list_apps(self, session: AsyncSession,
                       page: int = 1, per_page: int = 100,
                       category: Optional[str] = None,
                       is_active: Optional[bool] = None) -> List[AppPublic]:
        """列出应用"""
        try:
            query = select(App)
           
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
   
    async def delete_app(self, session: AsyncSession, app_id: int, cleanup_resources: bool = False, cleanup_files: bool = False) -> Dict[str, Any]:
        """删除应用"""
        try:
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
                            AppInstance.status.in_([AppStatusEnum.RUNNING, AppStatusEnum.STARTING])
                        )
                    )
                    running_instances = result.all()
                   
                    if running_instances:
                        return {"success": False, "message": f"应用 {app.name} 有运行中的实例，无法删除"}
                   
                    # 删除所有相关的实例记录
                    all_instances = await new_session.exec(
                        select(AppInstance).where(AppInstance.app_id == app_id)
                    )
                    instances_to_delete = all_instances.all()
                    
                    for instance in instances_to_delete:
                        await new_session.delete(instance)
                    
                    # 如果需要清理资源，删除Docker镜像
                    if cleanup_resources:
                        try:
                            success, message = self.docker_manager.remove_image(app.image_name, app.image_tag)
                            if success:
                                logger.info(f"镜像删除成功: {app.image_name}:{app.image_tag}")
                            else:
                                logger.warning(f"镜像删除失败: {message}")
                        except Exception as e:
                            logger.warning(f"删除镜像时出错: {e}")
                    
                    # 如果需要清理文件，删除映射的目录
                    if cleanup_files and app.volumes:
                        try:
                            import shutil
                            from pathlib import Path
                            
                            for volume in app.volumes:
                                if isinstance(volume, dict):
                                    host_path = volume.get('host_path')
                                else:
                                    host_path = volume.host_path
                                
                                if host_path:
                                    path = Path(host_path)
                                    if path.exists():
                                        if path.is_dir():
                                            shutil.rmtree(path)
                                            logger.info(f"目录删除成功: {host_path}")
                                        elif path.is_file():
                                            path.unlink()
                                            logger.info(f"文件删除成功: {host_path}")
                        except Exception as e:
                            logger.warning(f"删除文件目录时出错: {e}")
                   
                    # 删除应用
                    await new_session.delete(app)
                    # 事务会自动提交
           
            logger.info(f"应用删除成功: {app.name}")
            return {"success": True, "message": f"应用 {app.name} 删除成功"}
           
        except Exception as e:
            logger.error(f"删除应用失败: {e}")
            return {"success": False, "message": f"删除应用失败: {e}"}
   
    async def start_build_image(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """启动镜像构建（异步）"""
        try:
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 检查是否已在构建中
                    if app.status == AppStatusEnum.BUILDING:
                        return {"success": False, "message": "应用正在构建中，请稍后再试"}
                   
                    # 更新应用状态为构建中
                    app.status = AppStatusEnum.BUILDING
                    app.build_started_at = datetime.utcnow()
                    app.build_message = "镜像获取任务已启动"
           
            # 启动异步构建任务
            asyncio.create_task(self._build_image_async(app_id))
           
            logger.info(f"应用镜像获取任务已启动")
            return {
                "success": True,
                "message": "镜像获取任务已启动，请通过状态接口查询进度",
                "build_id": f"image_{app_id}_{int(datetime.utcnow().timestamp())}"
            }
           
        except Exception as e:
            logger.error(f"启动镜像获取失败: {e}")
            # 用新的 session 更新状态
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if app:
                        app.status = AppStatusEnum.BUILD_FAILED
                        app.build_status = "failed"
                        app.build_message = f"启动镜像获取失败: {e}"
                        app.build_finished_at = datetime.utcnow()
            return {"success": False, "message": f"启动镜像获取失败: {e}"}
   
    async def _build_image_async(self, app_id: int):
        """异步获取镜像（构建或拉取）"""
        temp_dir = None
        try:
            logger.info(f"开始异步获取镜像，应用ID: {app_id}")
           
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
                        'image_source': app.image_source,
                        'dockerfile_path': app.dockerfile_path,
                        'image_name': app.image_name,
                        'image_tag': app.image_tag,
                        'image_url': app.image_url,
                        'name': app.name
                    }
           
            if app_info['image_source'] == ImageSourceEnum.BUILD:
                if not app_info['dockerfile_path']:
                    raise ValueError("构建模式需要指定Dockerfile路径")

                build_context_path = app_info['dockerfile_path']
                if app_info['dockerfile_path'].startswith(("http://", "https://")):
                    temp_dir = self._create_temp_dir()
                    success, result = self._download_dockerfile(app_info['dockerfile_path'], temp_dir)
                   
                    if not success:
                        # 创建新的会话来更新状态
                        engine = get_engine()
                        async with AsyncSession(engine) as new_session:
                            await self._update_build_status(
                                new_session, app_id,
                                AppStatusEnum.BUILD_FAILED,
                                "failed",
                                result
                            )
                        self._cleanup_temp_dir(temp_dir)
                        return
                   
                    build_context_path = temp_dir

                try:
                    success, message = self.docker_manager.build_image(
                        dockerfile_path=build_context_path,
                        image_name=app_info['image_name'],
                        image_tag=app_info['image_tag']
                    )
                finally:
                    self._cleanup_temp_dir(temp_dir)

            elif app_info['image_source'] == ImageSourceEnum.PULL:
                image_name = app_info['image_url'] or app_info['image_name']
                success, message = self.docker_manager.pull_image(
                    image_name=image_name,
                    image_tag=app_info['image_tag']
                )
            else:
                raise ValueError(f"不支持的镜像获取方式: {app_info['image_source']}")
           
            # 创建新的会话来更新状态
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                await self._update_build_status(
                    new_session, app_id,
                    AppStatusEnum.STOPPED if success else AppStatusEnum.BUILD_FAILED,
                    "success" if success else "failed",
                    message
                )
           
            if success:
                logger.info(f"应用 {app_info['name']} 镜像获取成功")
            else:
                logger.error(f"应用 {app_info['name']} 镜像获取失败: {message}")
           
        except Exception as e:
            logger.error(f"异步获取镜像过程中发生异常: {e}")
            try:
                # 创建新的数据库会话来处理异常
                engine = get_engine()
                async with AsyncSession(engine) as new_session:
                    async with new_session.begin():
                        app = await new_session.get(App, app_id)
                        if app:
                            app.status = AppStatusEnum.BUILD_FAILED
                            app.build_status = "failed"
                            app.build_message = f"获取镜像异常: {str(e)}"
                            app.build_finished_at = datetime.utcnow()
            except Exception as update_error:
                logger.error(f"更新构建状态失败: {update_error}")
            self._cleanup_temp_dir(temp_dir)
   
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
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 检查是否已在构建中
                    if app.status == AppStatusEnum.BUILDING:
                        return {"success": False, "message": "应用正在获取镜像中，请稍后再试"}
                   
                    # 更新应用状态（不修改 image_source，保持原有配置）
                    app.status = AppStatusEnum.BUILDING
                    app.build_started_at = datetime.utcnow()
                    app.build_message = "镜像拉取任务已启动"
           
            # 启动异步拉取任务
            asyncio.create_task(self._pull_image_async(app_id))
           
            logger.info(f"应用镜像拉取任务已启动")
            return {
                "success": True,
                "message": "镜像拉取任务已启动，请通过状态接口查询进度",
                "build_id": f"pull_{app_id}_{int(datetime.utcnow().timestamp())}"
            }
           
        except Exception as e:
            logger.error(f"启动镜像拉取失败: {e}")
            # 用新的 session 更新状态
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if app:
                        app.status = AppStatusEnum.BUILD_FAILED
                        app.build_status = "failed"
                        app.build_message = f"启动镜像拉取失败: {e}"
                        app.build_finished_at = datetime.utcnow()
            return {"success": False, "message": f"启动镜像拉取失败: {e}"}
    
    async def start_image_acquisition(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """启动镜像获取（自动判断build或pull）"""
        try:
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 检查是否已在构建中
                    if app.status == AppStatusEnum.BUILDING:
                        return {"success": False, "message": "应用正在获取镜像中，请稍后再试"}
                   
                    # 自动判断获取方式
                    if app.image_source == ImageSourceEnum.BUILD:
                        # 构建模式
                        if not app.dockerfile_path:
                            return {"success": False, "message": "构建模式需要指定Dockerfile路径"}
                        operation_type = "构建"
                        build_id_prefix = "build"
                    elif app.image_source == ImageSourceEnum.PULL:
                        # 拉取模式
                        operation_type = "拉取"
                        build_id_prefix = "pull"
                    else:
                        return {"success": False, "message": f"不支持的镜像获取方式: {app.image_source}"}
                   
                    # 更新应用状态
                    app.status = AppStatusEnum.BUILDING
                    app.build_started_at = datetime.utcnow()
                    app.build_message = f"镜像{operation_type}任务已启动"
           
            # 启动异步任务
            asyncio.create_task(self._build_image_async(app_id))
           
            logger.info(f"应用镜像{operation_type}任务已启动")
            return {
                "success": True,
                "message": f"镜像{operation_type}任务已启动，请通过状态接口查询进度",
                "operation_type": operation_type,
                "build_id": f"{build_id_prefix}_{app_id}_{int(datetime.utcnow().timestamp())}"
            }
           
        except Exception as e:
            logger.error(f"启动镜像获取失败: {e}")
            # 用新的 session 更新状态
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if app:
                        app.status = AppStatusEnum.BUILD_FAILED
                        app.build_status = "failed"
                        app.build_message = f"启动镜像获取失败: {e}"
                        app.build_finished_at = datetime.utcnow()
            return {"success": False, "message": f"启动镜像获取失败: {e}"}
   
    async def _pull_image_async(self, app_id: int):
        """异步拉取镜像"""
        try:
            logger.info(f"开始异步拉取镜像，应用ID: {app_id}")
           
            # 创建新的数据库会话
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as session:
                # 重新获取应用信息
                async with session.begin():
                    app = await session.get(App, app_id)
                    if not app:
                        logger.error(f"应用不存在: {app_id}")
                        return
                    
                    # 保存应用信息，因为session会在async with块结束后关闭
                    app_info = {
                        'image_url': app.image_url,
                        'image_name': app.image_name,
                        'image_tag': app.image_tag,
                        'name': app.name
                    }
           
            # 拉取镜像
            image_name = app_info['image_url'] or app_info['image_name']
            success, message = self.docker_manager.pull_image(
                image_name=image_name,
                image_tag=app_info['image_tag']
            )
           
            # 创建新的会话来更新状态
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                await self._update_build_status(
                    new_session, app_id,
                    AppStatusEnum.STOPPED if success else AppStatusEnum.BUILD_FAILED,
                    "success" if success else "failed",
                    message
                )
           
            if success:
                logger.info(f"应用 {app_info['name']} 镜像拉取成功")
            else:
                logger.error(f"应用 {app_info['name']} 镜像拉取失败: {message}")
           
        except Exception as e:
            logger.error(f"异步拉取镜像过程中发生异常: {e}")
            try:
                # 创建新的数据库会话来处理异常
                engine = get_engine()
                async with AsyncSession(engine) as new_session:
                    await self._update_build_status(
                        new_session, app_id,
                        AppStatusEnum.BUILD_FAILED,
                        "failed",
                        f"拉取镜像异常: {str(e)}"
                    )
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
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 检查是否已有任何实例（只允许一个实例）
                    result = await new_session.exec(
                        select(AppInstance).where(AppInstance.app_id == app_id)
                    )
                    existing_instance = result.first()
                   
                    if existing_instance:
                        return {"success": False, "message": "应用已有实例，请先停止现有实例"}
                   
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
                   
                                        # 只有容器启动成功才创建实例记录
                    if success:
                        # 获取容器的初始网络信息
                        ip_address = None
                        exposed_ports = {}
                        if container_id:
                            status_success, status_message, status_info = self.docker_manager.get_container_status(container_id)
                            if status_success:
                                ip_address = status_info['ip_address']
                                exposed_ports = status_info['ports']
                        
                        # 创建新实例
                        instance = AppInstance(
                            app_id=app_id,
                            status=AppStatusEnum.RUNNING,
                            status_message="容器启动成功",
                            container_id=container_id,
                            started_at=datetime.utcnow(),
                            ip_address=ip_address,
                            exposed_ports=exposed_ports
                        )
                        new_session.add(instance)
                        
                        # 更新应用状态为运行中
                        app.status = AppStatusEnum.RUNNING
                        
                        await new_session.flush()
                        await new_session.refresh(instance)
                        instance_id = instance.id
                    else:
                        # 容器启动失败，不创建实例记录
                        instance_id = None
                        logger.warning(f"容器启动失败，不创建实例记录: {message}")
                    
                    # 事务会自动提交
           
            return {"success": success, "message": message, "instance_id": instance_id}
           
        except Exception as e:
            logger.error(f"启动应用失败: {e}")
            return {"success": False, "message": f"启动失败: {e}"}
   
    async def stop_app(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """停止应用"""
        try:
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 查找实例
                    result = await new_session.exec(
                        select(AppInstance).where(AppInstance.app_id == app_id)
                    )
                    instance = result.first()
                   
                    if not instance:
                        return {"success": False, "message": "应用没有实例"}
                   
                    # 停止容器
                    success, message = self.docker_manager.stop_container(instance.container_id)
                    
                    # 尝试删除容器（清理资源）
                    if success:
                        try:
                            remove_success, remove_message = self.docker_manager.remove_container(instance.container_id)
                            if remove_success:
                                logger.info(f"已删除容器: {instance.container_id}")
                            else:
                                logger.warning(f"删除容器失败: {remove_message}")
                        except Exception as e:
                            logger.warning(f"删除容器时发生异常: {e}")
                   
                                        # 删除实例记录
                    await new_session.delete(instance)
                    logger.info(f"已删除应用实例记录: {instance.id}")
                    
                    # 更新应用状态为已停止
                    app.status = AppStatusEnum.STOPPED
                    
                    # 事务会自动提交
           
            return {"success": success, "message": message}
           
        except Exception as e:
            logger.error(f"停止应用失败: {e}")
            return {"success": False, "message": f"停止失败: {e}"}
   
    async def get_app_status(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """获取应用状态"""
        try:
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 获取实例
                    result = await new_session.exec(
                        select(AppInstance).where(AppInstance.app_id == app_id)
                    )
                    instance = result.first()
                   
                    # 如果没有实例，确保应用状态为已停止
                    if not instance:
                        # 如果应用状态不是已停止，更新它
                        if app.status != AppStatusEnum.STOPPED:
                            app.status = AppStatusEnum.STOPPED
                        
                        return {
                            "success": True,
                            "app_name": app.name,
                            "status": app.status,
                            "message": "无运行实例",
                            "container_id": None,
                            "started_at": None,
                            "stopped_at": None,
                            "ip_address": None,
                            "exposed_ports": {}
                        }
                    
                    # 获取实时状态
                    if instance.container_id:
                        success, message, status_info = self.docker_manager.get_container_status(instance.container_id)
                        if success:
                            # 更新实例状态
                            new_instance_status = AppStatusEnum.RUNNING if status_info['running'] else AppStatusEnum.STOPPED
                            instance.status = new_instance_status
                            instance.ip_address = status_info['ip_address']
                            instance.exposed_ports = status_info['ports']
                            
                            # 同步应用状态
                            app.status = new_instance_status
                            
                            # 事务会自动提交
                   
                    return {
                        "success": True,
                        "app_name": app.name,
                        "status": instance.status,
                        "message": instance.status_message,
                        "container_id": instance.container_id,
                        "started_at": instance.started_at,
                        "stopped_at": instance.stopped_at,
                        "ip_address": instance.ip_address,
                        "exposed_ports": instance.exposed_ports
                    }
           
        except Exception as e:
            logger.error(f"获取应用状态失败: {e}")
            return {"success": False, "message": f"获取状态失败: {e}"}
   
    async def get_app_stats(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """获取应用资源统计"""
        try:
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 获取实例
                    result = await new_session.exec(
                        select(AppInstance).where(AppInstance.app_id == app_id)
                    )
                    instance = result.first()
                   
                    if not instance or not instance.container_id:
                        return {"success": False, "message": "应用未在运行"}
                   
                    # 获取容器统计信息
                    success, message, stats_info = self.docker_manager.get_container_stats(instance.container_id)
                   
                    if success:
                        # 更新实例统计信息
                        instance.memory_usage = stats_info['memory_usage']
                        instance.cpu_usage = stats_info['cpu_usage']
                        # 事务会自动提交
                   
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
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    result = await new_session.exec(
                        select(AppInstance).where(AppInstance.app_id == app_id)
                        .order_by(AppInstance.created_at.desc())
                    )
                    instances = result.all()
                   
                    # 手动构建 AppInstancePublic 对象，避免异步关系字段访问
                    public_instances = []
                    for instance in instances:
                        # 获取关联的应用信息
                        app = await new_session.get(App, instance.app_id)
                        app_public = AppPublic.from_orm(app) if app else None
                        
                        # 如果有容器ID，实时获取容器状态和统计信息
                        if instance.container_id:
                            # 获取容器状态
                            status_success, status_message, status_info = self.docker_manager.get_container_status(instance.container_id)
                            if status_success:
                                # 更新实例状态信息
                                instance.status = AppStatusEnum.RUNNING if status_info['running'] else AppStatusEnum.STOPPED
                                instance.ip_address = status_info['ip_address']
                                instance.exposed_ports = status_info['ports']
                            else:
                                # 容器不存在或获取状态失败，标记为错误状态
                                instance.status = AppStatusEnum.ERROR
                                instance.status_message = status_message
                            
                            # 获取容器统计信息
                            stats_success, stats_message, stats_info = self.docker_manager.get_container_stats(instance.container_id)
                            if stats_success:
                                # 更新实例统计信息
                                instance.memory_usage = stats_info['memory_usage']
                                instance.cpu_usage = stats_info['cpu_usage']
                        
                        # 手动构建 AppInstancePublic 对象
                        instance_data = {
                            "id": instance.id,
                            "app_id": instance.app_id,
                            "container_id": instance.container_id,
                            "status": instance.status,
                            "status_message": instance.status_message,
                            "started_at": instance.started_at,
                            "stopped_at": instance.stopped_at,
                            "memory_usage": instance.memory_usage,
                            "cpu_usage": instance.cpu_usage,
                            "ip_address": instance.ip_address,
                            "exposed_ports": instance.exposed_ports,
                            "created_at": instance.created_at,
                            "updated_at": instance.updated_at,
                            "app": app_public
                        }
                        public_instances.append(AppInstancePublic(**instance_data))
                   
                    return public_instances
           
        except Exception as e:
            logger.error(f"列出应用实例失败: {e}")
            raise
   
    async def cleanup_app_instances(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """清理应用实例"""
        try:
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 获取所有实例
                    result = await new_session.exec(
                        select(AppInstance).where(AppInstance.app_id == app_id)
                    )
                    instances = result.all()
                   
                    cleaned_count = 0
                    for instance in instances:
                        if instance.container_id:
                            # 删除容器
                            success, message = self.docker_manager.remove_container(instance.container_id)
                            # 无论容器删除是否成功，都统计实例记录
                       
                        # 删除实例记录
                        await new_session.delete(instance)
                        cleaned_count += 1  # 统计删除的实例记录数量
                    
                    # 如果有实例被清理，确保应用状态为已停止
                    if cleaned_count > 0:
                        app.status = AppStatusEnum.STOPPED
                    
                    # 事务会自动提交
           
            return {
                "success": True,
                "message": f"清理了 {cleaned_count} 个实例",
                "cleaned_count": cleaned_count
            }
           
        except Exception as e:
            logger.error(f"清理应用实例失败: {e}")
            return {"success": False, "message": f"清理失败: {e}"}
    
    async def cleanup_error_instances(self, session: AsyncSession, app_id: int) -> Dict[str, Any]:
        """清理错误的应用实例"""
        try:
            # 使用新的数据库会话，避免依赖注入的 session 上下文问题
            from aistack.server.db import get_engine
            engine = get_engine()
            async with AsyncSession(engine) as new_session:
                async with new_session.begin():
                    app = await new_session.get(App, app_id)
                    if not app:
                        return {"success": False, "message": "应用不存在"}
                   
                    # 获取所有错误状态的实例
                    result = await new_session.exec(
                        select(AppInstance).where(
                            AppInstance.app_id == app_id,
                            AppInstance.status == AppStatusEnum.ERROR
                        )
                    )
                    error_instances = result.all()
                    
                    logger.info(f"找到 {len(error_instances)} 个错误状态的实例")
                   
                    cleaned_count = 0
                    for instance in error_instances:
                        logger.info(f"清理错误实例: ID={instance.id}, 状态={instance.status}, 容器ID={instance.container_id}")
                        
                        if instance.container_id:
                            # 删除容器
                            success, message = self.docker_manager.remove_container(instance.container_id)
                            logger.info(f"容器删除结果: {success}, {message}")
                            # 无论容器删除是否成功，都统计实例记录
                        
                        # 删除实例记录
                        await new_session.delete(instance)
                        cleaned_count += 1  # 统计删除的实例记录数量
                        logger.info(f"已删除实例记录: ID={instance.id}")
                    
                    # 如果有实例被清理，确保应用状态为已停止
                    if cleaned_count > 0:
                        app.status = AppStatusEnum.STOPPED
                    
                    # 事务会自动提交
           
            return {
                "success": True,
                "message": f"清理了 {cleaned_count} 个错误实例",
                "cleaned_count": cleaned_count
            }
           
        except Exception as e:
            logger.error(f"清理错误应用实例失败: {e}")
            return {"success": False, "message": f"清理失败: {e}"}
   
    async def find_apps_by_host_path(self, session: AsyncSession, host_path: str) -> List[Dict[str, Any]]:
        """根据本地路径查找所有映射该路径的应用及卷信息"""
        try:
            import os
            # 查询所有应用
            result = await session.exec(select(App))
            apps = result.all()
            result = []
            
            # 标准化查询路径
            query_path = os.path.abspath(host_path.rstrip("/\\"))
            
            for app in apps:
                if not app.volumes:
                    continue
                for volume in app.volumes:
                    # 兼容volume为dict或AppVolume对象
                    v_host_path = volume["host_path"] if isinstance(volume, dict) else getattr(volume, "host_path", None)
                    if v_host_path:
                        # 标准化卷路径
                        volume_path = os.path.abspath(v_host_path.rstrip("/\\"))
                        if volume_path == query_path:
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
