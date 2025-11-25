# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, status
from fastapi.responses import StreamingResponse
import os
import asyncio
import subprocess
import logging
from typing import Dict, List, Optional, Any
import json
import time
from pathlib import Path

from aistack.security import get_current_active_user
from aistack.schemas.users import User
from aistack.config.config import get_config

router = APIRouter()
logger = logging.getLogger(__name__)

# 存储脚本执行进程
script_processes: Dict[str, subprocess.Popen] = {}
# 存储脚本日志
script_logs: Dict[str, List[str]] = {}
# 存储脚本错误信息
script_errors: Dict[str, List[str]] = {}


@router.post("/join")
async def join_cluster(
    token: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """加入集群"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以执行此操作")
    
    script_id = f"join_cluster_{int(time.time())}"
    script_logs[script_id] = []
    script_errors[script_id] = []
    
    # 获取脚本路径
    config = get_config()
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "joincluster.sh")
    
    # 确保脚本存在且可执行
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="集群加入脚本不存在")
    
    # 确保脚本可执行
    os.chmod(script_path, 0o755)
    
    # 在后台执行脚本
    def run_script():
        try:
            process = subprocess.Popen(
                [script_path, token],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            script_processes[script_id] = process
            
            # 读取输出
            for line in process.stdout:
                script_logs[script_id].append(line.strip())
                logger.info(f"[JOIN] {line.strip()}")
            
            # 读取错误
            for line in process.stderr:
                script_errors[script_id].append(line.strip())
                logger.error(f"[JOIN ERROR] {line.strip()}")
                
            # 等待进程完成
            return_code = process.wait()
            if return_code != 0:
                script_errors[script_id].append(f"脚本执行失败，返回码: {return_code}")
                logger.error(f"[JOIN] 脚本执行失败，返回码: {return_code}")
        except Exception as e:
            script_errors[script_id].append(f"执行脚本时出错: {str(e)}")
            logger.exception("[JOIN] 执行脚本时出错")
    
    background_tasks.add_task(run_script)
    return {"message": "正在加入集群", "script_id": script_id}


@router.post("/leave")
async def leave_cluster(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """退出集群"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以执行此操作")
    
    script_id = f"leave_cluster_{int(time.time())}"
    script_logs[script_id] = []
    script_errors[script_id] = []
    
    # 获取脚本路径
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "leavecluster.sh")
    
    # 确保脚本存在且可执行
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="集群退出脚本不存在")
    
    # 确保脚本可执行
    os.chmod(script_path, 0o755)
    
    # 在后台执行脚本
    def run_leave_script():
        try:
            process = subprocess.Popen(
                [script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            script_processes[script_id] = process
            
            # 读取输出
            for line in process.stdout:
                script_logs[script_id].append(line.strip())
                logger.info(f"[LEAVE] {line.strip()}")
            
            # 读取错误
            for line in process.stderr:
                script_errors[script_id].append(line.strip())
                logger.error(f"[LEAVE ERROR] {line.strip()}")
                
            # 等待进程完成
            return_code = process.wait()
            if return_code != 0:
                script_errors[script_id].append(f"脚本执行失败，返回码: {return_code}")
                logger.error(f"[LEAVE] 脚本执行失败，返回码: {return_code}")
        except Exception as e:
            script_errors[script_id].append(f"执行脚本时出错: {str(e)}")
            logger.exception("[LEAVE] 执行脚本时出错")
    
    background_tasks.add_task(run_leave_script)
    return {"message": "正在退出集群", "script_id": script_id}


@router.get("/logs/{script_id}")
async def get_script_logs(
    script_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """获取脚本日志"""
    if script_id not in script_logs:
        raise HTTPException(status_code=404, detail="找不到指定的脚本日志")
    
    return {"logs": script_logs[script_id]}


@router.get("/errors/{script_id}")
async def get_script_errors(
    script_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """获取脚本错误信息"""
    if script_id not in script_errors:
        raise HTTPException(status_code=404, detail="找不到指定的脚本错误信息")
    
    return {"errors": script_errors[script_id]}


@router.websocket("/ws/logs/{script_id}")
async def websocket_script_logs(websocket: WebSocket, script_id: str):
    """流式获取脚本日志"""
    await websocket.accept()
    
    if script_id not in script_logs:
        await websocket.send_json({"error": "找不到指定的脚本日志"})
        await websocket.close()
        return
    
    # 发送已有的日志
    for log in script_logs[script_id]:
        await websocket.send_json({"log": log})
    
    # 持续监控新的日志
    last_index = len(script_logs[script_id])
    try:
        while True:
            if script_id in script_processes and script_processes[script_id].poll() is not None:
                # 脚本已结束
                if last_index < len(script_logs[script_id]):
                    # 发送剩余日志
                    for log in script_logs[script_id][last_index:]:
                        await websocket.send_json({"log": log})
                await websocket.send_json({"status": "completed"})
                break
            
            # 检查是否有新日志
            if last_index < len(script_logs[script_id]):
                for log in script_logs[script_id][last_index:]:
                    await websocket.send_json({"log": log})
                last_index = len(script_logs[script_id])
            
            await asyncio.sleep(0.5)
    except Exception as e:
        logger.exception("WebSocket连接错误")
    finally:
        await websocket.close()


@router.websocket("/ws/errors/{script_id}")
async def websocket_script_errors(websocket: WebSocket, script_id: str):
    """流式获取脚本错误信息"""
    await websocket.accept()
    
    if script_id not in script_errors:
        await websocket.send_json({"error": "找不到指定的脚本错误信息"})
        await websocket.close()
        return
    
    # 发送已有的错误信息
    for error in script_errors[script_id]:
        await websocket.send_json({"error": error})
    
    # 持续监控新的错误信息
    last_index = len(script_errors[script_id])
    try:
        while True:
            if script_id in script_processes and script_processes[script_id].poll() is not None:
                # 脚本已结束
                if last_index < len(script_errors[script_id]):
                    # 发送剩余错误信息
                    for error in script_errors[script_id][last_index:]:
                        await websocket.send_json({"error": error})
                await websocket.send_json({"status": "completed"})
                break
            
            # 检查是否有新错误信息
            if last_index < len(script_errors[script_id]):
                for error in script_errors[script_id][last_index:]:
                    await websocket.send_json({"error": error})
                last_index = len(script_errors[script_id])
            
            await asyncio.sleep(0.5)
    except Exception as e:
        logger.exception("WebSocket连接错误")
    finally:
        await websocket.close()


@router.post("/reset/{script_id}")
async def reset_script(
    script_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """重置脚本"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以执行此操作")
    
    if script_id not in script_processes:
        raise HTTPException(status_code=404, detail="找不到指定的脚本")
    
    # 如果脚本正在运行，终止它
    if script_id in script_processes and script_processes[script_id].poll() is None:
        try:
            script_processes[script_id].terminate()
            # 给进程一些时间来终止
            await asyncio.sleep(2)
            # 如果进程仍在运行，强制终止
            if script_processes[script_id].poll() is None:
                script_processes[script_id].kill()
        except Exception as e:
            logger.exception(f"终止脚本时出错: {e}")
    
    # 清除日志和错误信息
    if script_id in script_logs:
        script_logs[script_id] = []
    if script_id in script_errors:
        script_errors[script_id] = []
    
    # 从进程字典中移除
    if script_id in script_processes:
        del script_processes[script_id]
    
    return {"message": "脚本已重置"} 