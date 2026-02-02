"""Task queue implementation inspired by ComfyUI."""

import asyncio
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"  # Waiting in queue
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Execution failed
    CANCELLED = "cancelled"  # Cancelled by user


class TaskType(str, Enum):
    """Task type enumeration."""

    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"
    IMAGE_VARIATIONS = "image_variations"


@dataclass
class Task:
    """Represents a task in the queue."""

    id: str
    type: TaskType
    params: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    position: int = 0  # Position in queue

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "progress": self.progress,
            "position": self.position,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            # Don't include result in basic info, use separate endpoint
            "has_result": self.result is not None,
        }


class TaskQueue:
    """
    Thread-safe task queue with async support.

    Inspired by ComfyUI's queue implementation.
    """

    def __init__(self, max_queue_size: int = 100, max_history_size: int = 100):
        self._queue: deque[Task] = deque()
        self._history: deque[Task] = deque(maxlen=max_history_size)
        self._tasks: Dict[str, Task] = {}
        self._current_task: Optional[Task] = None
        self._lock = threading.Lock()
        self._task_handler: Optional[Callable[[Task], Any]] = None
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._max_queue_size = max_queue_size

    def set_task_handler(self, handler: Callable[[Task], Any]):
        """Set the function that processes tasks."""
        self._task_handler = handler

    def start(self):
        """Start the queue worker."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Task queue worker started")

    def stop(self):
        """Stop the queue worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("Task queue worker stopped")

    def _worker_loop(self):
        """Main worker loop that processes tasks."""
        while self._running:
            task = self._get_next_task()
            if task:
                self._execute_task(task)
            else:
                time.sleep(0.1)  # Small sleep to prevent busy waiting

    def _get_next_task(self) -> Optional[Task]:
        """Get the next pending task from queue."""
        with self._lock:
            if self._queue and self._current_task is None:
                task = self._queue.popleft()
                self._current_task = task
                self._update_queue_positions()
                return task
        return None

    def _execute_task(self, task: Task):
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.progress = 0

        logger.info(f"Executing task {task.id} of type {task.type.value}")

        try:
            if self._task_handler:
                result = self._task_handler(task)
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                logger.info(f"Task {task.id} completed successfully")
            else:
                raise RuntimeError("No task handler set")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Task {task.id} failed: {e}")

        finally:
            task.completed_at = datetime.now()
            with self._lock:
                self._current_task = None
                self._history.append(task)

    def _update_queue_positions(self):
        """Update position for all tasks in queue."""
        for i, task in enumerate(self._queue):
            task.position = i + 1

    def add_task(
        self,
        task_type: TaskType,
        params: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> Task:
        """
        Add a new task to the queue.

        Args:
            task_type: Type of task
            params: Task parameters
            task_id: Optional custom task ID

        Returns:
            The created task

        Raises:
            ValueError: If queue is full
        """
        with self._lock:
            if len(self._queue) >= self._max_queue_size:
                raise ValueError("Queue is full")

            task = Task(
                id=task_id or str(uuid.uuid4()),
                type=task_type,
                params=params,
                position=len(self._queue) + 1,
            )

            self._queue.append(task)
            self._tasks[task.id] = task

            logger.info(
                f"Task {task.id} added to queue at position {task.position}"
            )

            return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """Get task result by ID."""
        task = self.get_task(task_id)
        if task:
            return task.result
        return None

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending task.

        Returns:
            True if task was cancelled, False otherwise
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if task.status != TaskStatus.PENDING:
                return False

            # Remove from queue
            try:
                self._queue.remove(task)
            except ValueError:
                pass

            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            self._history.append(task)
            self._update_queue_positions()

            logger.info(f"Task {task_id} cancelled")
            return True

    def get_queue_status(self) -> dict:
        """Get current queue status."""
        with self._lock:
            pending_tasks = [t.to_dict() for t in self._queue]
            current = self._current_task.to_dict() if self._current_task else None
            history = [t.to_dict() for t in list(self._history)[-10:]]  # Last 10

            return {
                "queue_length": len(self._queue),
                "pending_tasks": pending_tasks,
                "current_task": current,
                "recent_history": history,
                "is_running": self._running,
            }

    def get_pending_count(self) -> int:
        """Get number of pending tasks."""
        with self._lock:
            return len(self._queue)

    def clear_queue(self) -> int:
        """
        Clear all pending tasks.

        Returns:
            Number of tasks cleared
        """
        with self._lock:
            count = len(self._queue)
            for task in self._queue:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                self._history.append(task)

            self._queue.clear()
            logger.info(f"Queue cleared, {count} tasks cancelled")
            return count

    def get_history(self, limit: int = 50) -> List[dict]:
        """Get task history."""
        with self._lock:
            return [t.to_dict() for t in list(self._history)[-limit:]]


# Global task queue instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> Optional[TaskQueue]:
    """Get the global task queue instance."""
    return _task_queue


def init_task_queue(
    max_queue_size: int = 100,
    max_history_size: int = 100,
) -> TaskQueue:
    """Initialize the global task queue."""
    global _task_queue
    _task_queue = TaskQueue(
        max_queue_size=max_queue_size,
        max_history_size=max_history_size,
    )
    return _task_queue
