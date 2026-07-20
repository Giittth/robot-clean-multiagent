"""
    资源管理器：避免死锁，支持超时、持有者跟踪、try_acquire、async context manager。
"""

import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any

from backend.models.task.task import TaskType
from backend.utils.logger_handler import logger


class ResourceManager:
    def __init__(self, enable_debug: bool = False):
        """
        初始化资源管理器
        :param enable_debug: 是否启用调试模式
        """
        self._locks: Dict[str, asyncio.Lock] = {}  # 存储资源名称到锁的映射
        self._resource_order: Dict[str, int] = {}  # 存储资源名称到固定顺序的映射
        self._owner: Dict[str, Optional[str]] = {}  # 当前持有任务的ID（每个资源只能被一个任务持有）
        self._enable_debug = enable_debug  # 是否启用调试模式标志
        self._next_order = 0  # 用于分配资源顺序的计数器

    def register(self, resource_name: str):
        """注册资源（若未注册则自动创建）"""
        if resource_name not in self._locks:
            self._locks[resource_name] = asyncio.Lock()
            self._resource_order[resource_name] = self._next_order
            self._owner[resource_name] = None
            self._next_order += 1
            if self._enable_debug:
                logger.debug(f"Registered resource: {resource_name} order={self._resource_order[resource_name]}")

    def _sort_resources(self, resources: List[str]) -> List[str]:
        """按全局固定顺序排序，避免死锁"""
        return sorted(resources, key=lambda r: self._resource_order.get(r, 0))

    async def acquire(
        self,
        resources: List[str],
        timeout: Optional[float] = None,
        task_id: Optional[str] = None,
    ) -> bool:
        """
        获取一组资源（按固定顺序）。
        :param resources: 资源名列表
        :param timeout: 整体超时秒数，None 表示无限等待
        :param task_id: 调用任务标识（用于调试和 owner 检查）
        :return: True 表示成功获取所有资源，False 表示超时失败
        """
        task_id = str(task_id) if task_id is not None else None
        if not resources:
            return True
        ordered = self._sort_resources(resources)
        acquired = []

        # 确保所有资源已注册
        for res in ordered:
            if res not in self._locks:
                self.register(res)

        try:
            if timeout is None:
                for res in ordered:
                    await self._locks[res].acquire()
                    self._owner[res] = task_id
                    acquired.append(res)
                return True
            else:
                # 整体超时：使用 asyncio.wait_for 包装一个协程
                async def _acquire_all():
                    for res in ordered:
                        await self._locks[res].acquire()
                        self._owner[res] = task_id
                        acquired.append(res)

                await asyncio.wait_for(_acquire_all(), timeout=timeout)
                return True
        except asyncio.TimeoutError:
            # 释放已获取的资源（逆序）
            for res in reversed(acquired):
                if self._locks[res].locked():
                    self._locks[res].release()
                    self._owner[res] = None
            return False
        except Exception as e:
            # 异常时释放已获取资源
            for res in reversed(acquired):
                if self._locks[res].locked():
                    self._locks[res].release()
                    self._owner[res] = None
            raise e

    def release(self, resources: List[str], task_id: Optional[str] = None):
        """
        释放一组资源（逆序释放）。
        :param resources: 资源名列表
        :param task_id: 调用任务标识，用于 owner 验证
        """
        if not resources:
            return
        ordered = self._sort_resources(resources)
        for res in reversed(ordered):
            if res not in self._locks:
                logger.warning(f"Release unregistered resource: {res}")
                continue
            # owner 检查
            if self._owner.get(res) != task_id:
                raise RuntimeError(f"Task {task_id} attempted to release resource {res} not held by it")
            lock = self._locks[res]
            if lock.locked():
                lock.release()
                self._owner[res] = None
                if self._enable_debug and task_id:
                    logger.debug(f"Task {task_id} released {res}")
            else:
                logger.warning(f"Resource {res} already unlocked (owner lost)")

    async def try_acquire(self, resources: List[str], task_id: Optional[str] = None) -> bool:
        """
        非阻塞尝试获取资源。
        :return: True 表示成功获取所有资源，False 表示至少一个资源被占用
        """
        if not resources:
            return True
        ordered = self._sort_resources(resources)
        acquired = []
        try:
            for res in ordered:
                if res not in self._locks:
                    self.register(res)
                lock = self._locks[res]
                # 尝试立即获取，不等待
                acquired_flag = await self._try_acquire_one(lock, res, task_id)
                if not acquired_flag:
                    # 失败：释放已获取的资源
                    for r in reversed(acquired):
                        self._locks[r].release()
                        self._owner[r] = None
                    return False
                acquired.append(res)
            return True
        except Exception:
            for r in reversed(acquired):
                if r in self._locks:
                    self._locks[r].release()
                    self._owner[r] = None
            raise

    async def _try_acquire_one(self, lock: asyncio.Lock, res: str, task_id: Optional[str]) -> bool:
        """尝试获取单个锁，非阻塞"""
        try:
            await asyncio.wait_for(lock.acquire(), timeout=0)
            self._owner[res] = task_id
            if self._enable_debug and task_id:
                logger.debug(f"Task {task_id} acquired {res}")
            return True
        except asyncio.TimeoutError:
            if self._enable_debug and task_id:
                logger.debug(f"Task {task_id} failed to acquire {res} (busy)")
            return False

    @asynccontextmanager
    async def locked(
        self,
        resources: List[str],
        timeout: Optional[float] = None,
        task_id: Optional[str] = None,
    ):
        """
        异步上下文管理器，自动获取和释放资源。
        用法: async with rm.locked(["motion"], timeout=5, task_id="nav"):
            # 执行任务
        """
        acquired = await self.acquire(resources, timeout=timeout, task_id=task_id)
        if not acquired:
            raise TimeoutError(f"Failed to acquire {resources} within {timeout}s")
        try:
            yield
        finally:
            self.release(resources, task_id=task_id)

    def get_status(self) -> Dict[str, Any]:
        """返回资源状态（调试用）"""
        status = {}
        for name in self._locks:
            status[name] = {
                "locked": self._locks[name].locked(),
                "order": self._resource_order.get(name),
                "owner": self._owner.get(name),
            }
        return status


    def get_resources_for_task(self, task_type: TaskType) -> List[str]:
        """根据任务类型返回所需资源列表（集中管理资源策略）"""
        if task_type in (TaskType.NAVIGATE_TO, TaskType.EXPLORE_AREA,
                         TaskType.CLEANING, TaskType.RETURN_TO_CHARGE,
                         TaskType.RECOVER_STUCK):
            return ["motion"]
        # 未知任务类型抛出明确异常，而非静默返回空列表导致下游类型断言崩溃
        raise ValueError(f"Unknown task type for resource mapping: {task_type}")