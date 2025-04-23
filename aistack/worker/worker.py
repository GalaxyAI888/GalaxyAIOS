# -*- coding: utf-8 -*-
import asyncio
import logging
import os

import setproctitle

from aistack.log import setup_logging
from aistack.utils.process import add_signal_handlers_in_loop

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, config):
        self.config = config

    def start(self):
        setup_logging(self.config.debug)
        logger.info("Starting Worker")
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
        add_signal_handlers_in_loop()
        # ge
        while True:
            await asyncio.sleep(2)
            logger.info("Worker is running")