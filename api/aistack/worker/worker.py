# -*- coding: utf-8 -*-
import asyncio
import logging

import socket

import setproctitle

from aistack.log import setup_logging
from aistack.utils.process import add_signal_handlers_in_loop
from aistack.client import ClientSet
from aistack.worker.model_file_manager import ModelFileManager
from aistack.utils.network import get_first_non_loopback_ip

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, config):
        self.config = config
        self._async_tasks = []
        
        # 设置 worker IP
        self._worker_ip = config.worker_ip
        if self._worker_ip is None:
            self._worker_ip = get_first_non_loopback_ip()
            self.config.worker_ip = self._worker_ip
        
        # 设置 worker 名称
        self._worker_name = config.worker_name
        if self._worker_name is None:
            self._worker_name = socket.gethostname()
            self.config.worker_name = self._worker_name
        
        # 创建 ClientSet
        self._clientset = ClientSet(
            base_url=config.server_url or "http://127.0.0.1:9999",
            username=f"system/worker/{self._worker_ip}",
            password=config.token,
        )
        
        # 设置 worker ID（简化版本，使用固定 ID）
        self._worker_id = 1

    def _create_async_task(self, coro):
        """创建异步任务并添加到任务列表"""
        self._async_tasks.append(asyncio.create_task(coro))

    def start(self):
        setup_logging(self.config.debug)
        logger.info("Starting GalaxyAIOS Worker")
        setproctitle.setproctitle("aistack-worker")
        try:
            asyncio.run(self.start_async())
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.error(f"Error serving worker APIs: {e}")
        finally:
            logger.info("Worker has shut down.")

    async def start_async(self):
        """启动异步主循环"""
        add_signal_handlers_in_loop()
        
        logger.info(f"Starting GalaxyAIOS worker: {self._worker_name} ({self._worker_ip})")
        
        # 启动 ModelFileManager
        model_file_manager = ModelFileManager(
            worker_id=self._worker_id,
            clientset=self._clientset,
            cfg=self.config
        )
        self._create_async_task(model_file_manager.watch_model_files())
        
        logger.info("ModelFileManager started successfully")
        
        # 等待所有异步任务
        try:
            await asyncio.gather(*self._async_tasks)
        except asyncio.CancelledError:
            logger.info("Worker tasks cancelled")
        except Exception as e:
            logger.error(f"Error in worker tasks: {e}")
            raise