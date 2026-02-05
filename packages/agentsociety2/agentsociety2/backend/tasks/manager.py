"""后台任务管理器

管理实验运行等长时间运行的后台任务，支持：
- 启动、监控、停止任务
- 进度回调推送到SSE
- 任务状态持久化
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Awaitable

from agentsociety2.logger import get_logger

logger = get_logger()


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskProgress:
    """任务进度信息"""
    current_step: int = 0
    total_steps: int = 0
    message: str = ""
    percentage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "message": self.message,
            "percentage": self.percentage,
        }


@dataclass
class BackgroundTask:
    """后台任务信息"""
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    progress: TaskProgress = field(default_factory=TaskProgress)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 内部使用
    _task: Optional[asyncio.Task] = field(default=None, repr=False)
    _progress_callback: Optional[Callable] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


class TaskManager:
    """全局后台任务管理器（单例模式）"""

    _instance: Optional[TaskManager] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._tasks: Dict[str, BackgroundTask] = {}
        self._initialized = True
        logger.info("TaskManager initialized")

    def generate_task_id(self) -> str:
        """生成唯一任务ID"""
        return f"task_{uuid.uuid4().hex[:12]}"

    async def create_task(
        self,
        task_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, TaskProgress], Awaitable[None]]] = None,
    ) -> BackgroundTask:
        """创建新任务（不启动）"""
        task_id = self.generate_task_id()
        task = BackgroundTask(
            task_id=task_id,
            task_type=task_type,
            metadata=metadata or {},
            _progress_callback=progress_callback,
        )
        self._tasks[task_id] = task
        logger.info(f"Created task {task_id} of type {task_type}")
        return task

    async def start_experiment_task(
        self,
        experiment_path: str,
        config_path: str,
        steps_path: str,
        progress_callback: Optional[Callable[[str, TaskProgress], Awaitable[None]]] = None,
    ) -> BackgroundTask:
        """
        启动实验运行任务

        Args:
            experiment_path: 实验目录路径
            config_path: init_config.json 路径
            steps_path: steps.yaml 路径
            progress_callback: 进度回调函数 (task_id, progress) -> None

        Returns:
            BackgroundTask 实例
        """
        from agentsociety2.society.cli import ExperimentRunner

        # 创建任务
        task = await self.create_task(
            task_type="experiment_run",
            metadata={
                "experiment_path": experiment_path,
                "config_path": config_path,
                "steps_path": steps_path,
            },
            progress_callback=progress_callback,
        )

        # 定义执行函数
        async def run_experiment():
            try:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()

                # 更新进度
                await self._update_progress(task, TaskProgress(
                    current_step=0,
                    total_steps=100,
                    message="正在初始化实验...",
                    percentage=0.0,
                ))

                # 创建运行目录
                exp_path = Path(experiment_path)
                run_dir = exp_path / "run"
                run_dir.mkdir(parents=True, exist_ok=True)

                # 创建ExperimentRunner
                runner = ExperimentRunner(run_dir=run_dir)

                # 包装进度回调
                original_run = runner.run

                async def wrapped_run(*args, **kwargs):
                    # 更新进度为运行中
                    await self._update_progress(task, TaskProgress(
                        current_step=10,
                        total_steps=100,
                        message="实验正在运行...",
                        percentage=10.0,
                    ))

                    result = await original_run(*args, **kwargs)

                    return result

                runner.run = wrapped_run

                # 运行实验
                await runner.run(
                    config_path=Path(config_path),
                    steps_path=Path(steps_path),
                    experiment_id=task.task_id,
                )

                # 完成
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = {
                    "run_dir": str(run_dir),
                    "pid_file": str(run_dir / "pid.json"),
                    "db_file": str(run_dir / "sqlite.db"),
                }

                await self._update_progress(task, TaskProgress(
                    current_step=100,
                    total_steps=100,
                    message="实验运行完成！",
                    percentage=100.0,
                ))

                logger.info(f"Task {task.task_id} completed successfully")

            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                task.error = "Task was cancelled"
                logger.info(f"Task {task.task_id} was cancelled")
                raise

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.error = str(e)
                logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)

                await self._update_progress(task, TaskProgress(
                    current_step=task.progress.current_step,
                    total_steps=100,
                    message=f"实验运行失败: {str(e)}",
                    percentage=task.progress.percentage,
                ))

        # 启动异步任务
        task._task = asyncio.create_task(run_experiment())
        logger.info(f"Started experiment task {task.task_id}")

        return task

    async def _update_progress(self, task: BackgroundTask, progress: TaskProgress):
        """更新任务进度并触发回调"""
        task.progress = progress
        if task._progress_callback:
            try:
                await task._progress_callback(task.task_id, progress)
            except Exception as e:
                logger.warning(f"Progress callback failed for task {task.task_id}: {e}")

    async def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """获取任务信息"""
        return self._tasks.get(task_id)

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态（字典格式）"""
        task = self._tasks.get(task_id)
        if task:
            return task.to_dict()
        return None

    async def list_tasks(
        self,
        task_type: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[Dict[str, Any]]:
        """列出任务"""
        tasks = []
        for task in self._tasks.values():
            if task_type and task.task_type != task_type:
                continue
            if status and task.status != status:
                continue
            tasks.append(task.to_dict())
        return tasks

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task._task and not task._task.done():
            task._task.cancel()
            try:
                await task._task
            except asyncio.CancelledError:
                pass
            logger.info(f"Task {task_id} cancelled")
            return True

        return False

    async def cleanup_completed_tasks(self, max_age_seconds: int = 3600):
        """清理已完成的旧任务"""
        now = datetime.now()
        to_remove = []

        for task_id, task in self._tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if task.completed_at:
                    age = (now - task.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]
            logger.info(f"Cleaned up task {task_id}")

        return len(to_remove)


# 全局任务管理器实例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取全局任务管理器实例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
