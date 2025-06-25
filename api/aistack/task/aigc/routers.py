from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .core import AIGCProcessor
import multiprocessing
from typing import Dict
import logging
import os
from aistack.utils.process import ensure_tmp_directory

logger = logging.getLogger(__name__)
aigc_router = APIRouter()

# 请求体模型
class TaskRequest(BaseModel):
    task_type: str
    account_id: str

# 进程管理存储
_process_manager: Dict[str, multiprocessing.Process] = {}

def run_processor(account_id, task_type):
    # 确保临时目录存在
    ensure_tmp_directory()
    
    processor = AIGCProcessor(account_id)
    processor.run(task_type)

@aigc_router.post("/tasks/start")
async def start_task(request: TaskRequest):
    """
    启动指定类型任务处理器
    - task_type: 任务类型 (txt2img/img2img/txt2speech/speech2txt)
    - account_id: 账户标识
    """
    VALID_TYPES = ["txt2img", "img2img", "txt2speech", "speech2txt"]
    if request.task_type not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task type. Valid types: {VALID_TYPES}"
        )

    process_key = f"{request.task_type}::{request.account_id}"
    
    # 如果已存在的进程 直接返回
    if process_key in _process_manager:
        return JSONResponse(
        status_code=200,
        content={
            "status": "running",
            "process_key": process_key,
            "pid": _process_manager[process_key].pid
        }
        )
        # _process_manager[process_key].terminate()
        # del _process_manager[process_key]

    # 创建新进程
    process = multiprocessing.Process(
        target=run_processor,
        args=(request.account_id, request.task_type),
        daemon=True
    )
    process.start()
    
    _process_manager[process_key] = process
    logger.info(f"Started {request.task_type} processor for {request.account_id} (PID: {process.pid})")
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "running",
            "process_key": process_key,
            "pid": process.pid
        }
    )

@aigc_router.post("/tasks/stop")
async def stop_task(request: TaskRequest):
    """停止指定任务处理器
    - task_type: 任务类型 (txt2img/img2img/txt2speech/speech2txt)
    - account_id: 账户标识
    """
    process_key = f"{request.task_type}::{request.account_id}"
    if process_key not in _process_manager:
        raise HTTPException(
            status_code=404,
            detail="No running process found"
        )

    _process_manager[process_key].terminate()
    del _process_manager[process_key]
    
    return {"status": "stopped"}

@aigc_router.get("/tasks")
async def list_tasks():
    """获取所有运行中的任务"""
    return {
        "processes": [
            {
                "process_key": key,
                "pid": proc.pid,
                "alive": proc.is_alive()
            }
            for key, proc in _process_manager.items()
        ]
    }
