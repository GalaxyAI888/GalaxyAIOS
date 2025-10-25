import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import threading
from collections import defaultdict


class BuildStatus(Enum):
    """构建状态枚举"""
    PENDING = "pending"      # 等待中
    DOWNLOADING = "downloading"  # 下载Dockerfile中
    BUILDING = "building"    # 构建中
    SUCCESS = "success"      # 成功
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class BuildTask:
    """构建任务"""
    task_id: str
    image_name: str
    image_tag: str
    dockerfile_url: Optional[str] = None
    image_url: Optional[str] = None
    status: BuildStatus = BuildStatus.PENDING
    progress: float = 0.0  # 0-100
    logs: List[str] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    build_args: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.logs is None:
            self.logs = []
        if self.created_at is None:
            self.created_at = datetime.now()


class BuildTaskManager:
    """构建任务管理器"""
    
    def __init__(self):
        self.tasks: Dict[str, BuildTask] = {}
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def create_task(
        self, 
        image_name: str, 
        image_tag: str,
        dockerfile_url: Optional[str] = None,
        image_url: Optional[str] = None,
        build_args: Optional[Dict[str, str]] = None
    ) -> str:
        """创建构建任务"""
        task_id = str(uuid.uuid4())
        
        task = BuildTask(
            task_id=task_id,
            image_name=image_name,
            image_tag=image_tag,
            dockerfile_url=dockerfile_url,
            image_url=image_url,
            build_args=build_args
        )
        
        with self._lock:
            self.tasks[task_id] = task
        
        self._notify_subscribers(task_id, task)
        return task_id
    
    def get_task(self, task_id: str) -> Optional[BuildTask]:
        """获取任务"""
        with self._lock:
            return self.tasks.get(task_id)
    
    def update_task_status(self, task_id: str, status: BuildStatus, progress: float = None, error_message: str = None):
        """更新任务状态"""
        with self._lock:
            if task_id not in self.tasks:
                return
            
            task = self.tasks[task_id]
            task.status = status
            
            if progress is not None:
                task.progress = progress
            
            if error_message is not None:
                task.error_message = error_message
            
            if status == BuildStatus.BUILDING and task.started_at is None:
                task.started_at = datetime.now()
            elif status in [BuildStatus.SUCCESS, BuildStatus.FAILED, BuildStatus.CANCELLED]:
                task.completed_at = datetime.now()
        
        self._notify_subscribers(task_id, task)
    
    def add_log(self, task_id: str, log_message: str):
        """添加日志"""
        with self._lock:
            if task_id not in self.tasks:
                return
            
            task = self.tasks[task_id]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            task.logs.append(f"[{timestamp}] {log_message}")
            
            # 限制日志数量，避免内存过多占用
            if len(task.logs) > 1000:
                task.logs = task.logs[-500:]  # 保留最近500条
        
        self._notify_subscribers(task_id, task)
    
    def subscribe(self, task_id: str, callback: Callable):
        """订阅任务更新"""
        self.subscribers[task_id].append(callback)
    
    def unsubscribe(self, task_id: str, callback: Callable):
        """取消订阅"""
        if callback in self.subscribers[task_id]:
            self.subscribers[task_id].remove(callback)
    
    def _notify_subscribers(self, task_id: str, task: BuildTask):
        """通知订阅者"""
        for callback in self.subscribers[task_id]:
            try:
                callback(task)
            except Exception as e:
                print(f"通知订阅者失败: {e}")
    
    def list_tasks(self, status_filter: Optional[BuildStatus] = None) -> List[BuildTask]:
        """列出任务"""
        with self._lock:
            tasks = list(self.tasks.values())
            
            if status_filter:
                tasks = [task for task in tasks if task.status == status_filter]
            
            # 按创建时间倒序排列
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            return tasks
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        with self._lock:
            tasks_to_remove = []
            for task_id, task in self.tasks.items():
                if task.created_at.timestamp() < cutoff_time:
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
                if task_id in self.subscribers:
                    del self.subscribers[task_id]


# 全局任务管理器实例
build_task_manager = BuildTaskManager()
