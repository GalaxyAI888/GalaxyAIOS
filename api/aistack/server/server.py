# -*- coding: utf-8 -*-
import asyncio
import logging
from multiprocessing import Process
import os.path
from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
import uvicorn

from aistack import project_path
from aistack.config.config import Config
from aistack.server.app import app
from aistack.server.db import init_db, get_engine
from aistack.utils.process import add_signal_handlers_in_loop
from aistack.schemas.users import User
from aistack.security import generate_secure_password, get_secret_hash
from alembic import command
from alembic.config import Config as AlembicConfig
import importlib.util

logger = logging.getLogger(__name__)


class Server(object):

    def __init__(self, config: Config, sub_processes: List[Process] = None):
        self._config = config
        if sub_processes is None:
            sub_processes = []
        self._sub_processes = sub_processes

    @property
    def all_processes(self):
        return self._sub_processes

    async def start(self):
        logger.info("Starting server")
        add_signal_handlers_in_loop()

        self._run_migrations()
        await self._prepare_data()
        self._start_sub_processes()
        await self.start_server_api()

        # self._start_worker_syncer()

    async def start_server_api(self):
        port = 80
        if self._config.port:
            port = self._config.port
        elif self._config.ssl_certfile and self._config.ssl_keyfile:
            port = 443
        host = "0.0.0.0"
        if self._config.host:
            host = self._config.host

        app.state.server_config = self._config
        config = uvicorn.Config(app,
                                host=host,
                                port=port,
                                access_log=False,
                                log_level="error",
                                ssl_certfile=self._config.ssl_certfile,
                                ssl_keyfile=self._config.ssl_keyfile,
                                )
        logger.info(f"Serving on {config.host}:{config.port}.")
        server = uvicorn.Server(config)
        await server.serve()

    def _run_migrations(self):
        logger.info("Running database migration.")
        try:
            migrations_files_path = os.path.join(project_path, "migrations")
            alembic_cfg = AlembicConfig()
            alembic_cfg.set_main_option(
                "script_location", migrations_files_path)
            alembic_cfg.set_main_option("sqlalchemy.url", self._config.database_url)
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migration completed.")
        except Exception as e:
            logger.warning(f"Migration failed: {e}")
            logger.info("Trying to create tables directly...")
            try:
                from sqlmodel import SQLModel, create_engine
                # 导入所有模型以确保它们被注册到SQLModel.metadata
                import aistack.schemas.apps
                import aistack.schemas.users
                import aistack.schemas.model_files
                import aistack.schemas.preset_models
                import aistack.schemas.workers
                
                engine = create_engine(self._config.database_url)
                SQLModel.metadata.create_all(engine)
                logger.info("Tables created successfully.")
            except Exception as create_error:
                logger.error(f"Failed to create tables: {create_error}")
                raise

    async def _prepare_data(self):
        self._setup_data_dir(self._config.data_dir)

        await init_db(self._config.database_url)

        engine = get_engine()
        async with AsyncSession(engine) as session:
            await self._init_data(session)

        logger.debug("Data initialization completed.")

    # def _start_scheduler(self):
    #     scheduler = Scheduler(self._config)
    #     asyncio.create_task(scheduler.start())
    #
    #     logger.debug("Scheduler started.")
    #
    # def _start_controllers(self):
    #     model_controller = ModelController(self._config)
    #     asyncio.create_task(model_controller.start())
    #
    #     model_instance_controller = ModelInstanceController(self._config)
    #     asyncio.create_task(model_instance_controller.start())
    #
    #     worker_controller = WorkerController()
    #     asyncio.create_task(worker_controller.start())
    #
    #     logger.debug("Controllers started.")

    # def _start_system_load_collector(self):
    #     collector = SystemLoadCollector()
    #     asyncio.create_task(collector.start())
    #
    #     logger.debug("System load collector started.")

    # def _start_worker_syncer(self):
    #     worker_syncer = WorkerSyncer()
    #     asyncio.create_task(worker_syncer.start())
    #
    #     logger.debug("Worker syncer started.")

    # def _start_update_checker(self):
    #     if self._config.disable_update_check:
    #         return
    #
    #     update_checker = UpdateChecker(update_check_url=self._config.update_check_url)
    #     asyncio.create_task(update_checker.start())
    #
    #     logger.debug("Update checker started.")

    def _start_sub_processes(self):
        for process in self._sub_processes:
            process.start()

    @staticmethod
    def _setup_data_dir(data_dir: str):
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    async def _init_data(self, session: AsyncSession):
        init_data_funcs = [self._init_user]
        for init_data_func in init_data_funcs:
            await init_data_func(session)

    async def _init_user(self, session: AsyncSession):
        user = await User.first_by_field(
            session=session, field="username", value="admin"
        )
        if not user:
            bootstrap_password = self._config.bootstrap_password
            require_password_change = False
            if not bootstrap_password:
                require_password_change = True
                bootstrap_password = generate_secure_password()
                bootstrap_password_file = os.path.join(
                    self._config.data_dir, "initial_admin_password"
                )
                with open(bootstrap_password_file, "w") as file:
                    file.write(bootstrap_password + "\n")
                logger.info(
                    "Generated initial admin password. "
                    f"You can get it from {bootstrap_password_file}"
                )

            user = User(
                username="admin",
                full_name="Default System Admin",
                hashed_password=get_secret_hash(bootstrap_password),
                is_admin=True,
                require_password_change=require_password_change,
            )
            await User.create(session, user)

