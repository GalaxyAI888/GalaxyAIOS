# -*- coding: utf-8 -*-
import psutil
import asyncio
import logging
import signal
import os
import threading


from aistack.utils import platform

logger = logging.getLogger(__name__)

threading_stop_event = threading.Event()

termination_signal_handled = False


def add_signal_handlers():
    signal.signal(signal.SIGTERM, handle_termination_signal)


def add_signal_handlers_in_loop():
    if platform.system() == "windows":
        # Windows does not support asyncio signal handlers.
        add_signal_handlers()
        return

    loop = asyncio.get_event_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        logger.debug(f"Adding signal handler for {sig}")
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(shutdown_event_loop(sig, loop))
        )


async def shutdown_event_loop(signal=None, loop=None):
    logger.debug(f"Received signal: {signal}. Shutting down gracefully...")

    threading_stop_event.set()

    try:
        tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass

    handle_termination_signal(signal=signal)


def handle_termination_signal(signal=None, frame=None):
    """
    Terminate the current process and all its children.
    """
    global termination_signal_handled
    if termination_signal_handled:
        return
    termination_signal_handled = True

    threading_stop_event.set()

    pid = os.getpid()
    terminate_process_tree(pid)


def terminate_process_tree(pid: int):
    try:
        process = psutil.Process(pid)
        children = process.children(recursive=True)

        # Terminate all child processes
        terminate_processes(children)

        # Terminate the parent process
        terminate_process(process)
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        logger.error(f"Error while terminating process tree: {e}")


def terminate_processes(processes):
    """
    Terminates a list of processes, attempting graceful termination first,
    then forcibly killing remaining ones if necessary.
    """
    for proc in processes:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            continue

    # Wait for processes to terminate and kill if still alive
    _, alive = psutil.wait_procs(processes, timeout=3)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            continue


def terminate_process(process):
    """
    Terminates a single process, attempting graceful termination first,
    then forcibly killing it if necessary.
    """
    if process.is_running():
        try:
            process.terminate()
            process.wait(timeout=3)
        except psutil.NoSuchProcess:
            pass
        except psutil.TimeoutExpired:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass


def ensure_tmp_directory():
    """确保临时目录存在"""
    tmp_dir = "tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
        logger.info(f"创建临时目录: {tmp_dir}")
    else:
        logger.debug(f"临时目录已存在: {tmp_dir}")

