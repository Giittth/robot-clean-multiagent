"""
任务分发器：负责任务的具体执行。
- 统一管理 session 生命周期（单一 owner）
- 处理导航、控制等任务的派发
- 等待结果事件并回调 future
- 支持 late result 和宽限期（FINISHING 状态）
- 使用锁保护共享状态，防止并发竞争
"""

import asyncio
import time
from typing import Dict, Callable, List, Awaitable, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from backend.models.task.task import Task
from backend.agents.core.runtime.resource_manager import ResourceManager
from backend.agents.schemas.messages import MessageType
from backend.agents.implementations.base_agent import BaseAgent
from backend.agents.core.event.event_router import EventRouter
from backend.agents.core.event.event_types import Event, UIEventType
from backend.agents.schemas.agent_messages import NavigationRequestPayload
from backend.utils.logger_handler import logger


class SessionState(Enum):
    ACTIVE = "active"
    FINISHING = "finishing"
    CLOSED = "closed"


@dataclass
class SessionInfo:
    state: SessionState
    grace_until: float = 0.0
    finish_task: Optional[asyncio.Task] = None


class TaskDispatcher:
    def __init__(self, agent: BaseAgent, resource_manager: ResourceManager, event_router: EventRouter):
        self.agent = agent
        self.resource_manager = resource_manager
        self.event_router = event_router

        # 处理器注册表
        self.handlers: Dict[str, Callable[[Task], Awaitable[None]]] = {
            "navigate_to": self._dispatch_navigation,
            "navigate_to_area": self._dispatch_navigation,
            "clean_area": self._dispatch_navigation,
            "cleaning": self._dispatch_navigation,
            "return_to_charge": self._dispatch_navigation,
            "recover_stuck": self._dispatch_navigation,
            "stop": self._dispatch_control,
        }

        # 待处理任务 future: key = (task_id, session_id)
        self._pending_futures: Dict[Tuple[str, str], asyncio.Future] = {}
        # 任务资源记录
        self._task_resources: Dict[str, List[str]] = {}
        # 当前活动任务 ID（仅用于紧急 fallback）
        self._active_task_id: Optional[str] = None

        # 会话管理
        self._sessions: Dict[str, SessionInfo] = {}
        # task_id -> session_id 映射（不可变绑定）
        self._task_to_session: Dict[str, str] = {}

        # 并发锁保护所有共享字典
        self._session_lock = asyncio.Lock()

    async def start(self):
        self.event_router.subscribe(UIEventType.TASK_RESULT, self._on_task_result_event)
        self.event_router.subscribe("graph.started", self._on_graph_started)
        self.event_router.subscribe("graph.finished", self._on_graph_finished)
        self.event_router.subscribe("system.graph_session_reset", self._on_session_reset)

    async def stop(self):
        """取消所有事件订阅，防止旧 dispatcher 泄露"""
        self.event_router.unsubscribe(UIEventType.TASK_RESULT, self._on_task_result_event)
        self.event_router.unsubscribe("graph.started", self._on_graph_started)
        self.event_router.unsubscribe("graph.finished", self._on_graph_finished)
        self.event_router.unsubscribe("system.graph_session_reset", self._on_session_reset)
        # 清理残留状态
        for future in self._pending_futures.values():
            if not future.done():
                future.set_result(False)
        self._pending_futures.clear()
        self._task_to_session.clear()
        self._sessions.clear()
        logger.info("[TaskDispatcher] stopped")

    # ==================== 会话生命周期管理 ====================
    async def _on_graph_started(self, event: Event):
        session_id = event.payload.get("session_id")
        if not session_id:
            logger.warning("GRAPH_STARTED missing session_id")
            return
        async with self._session_lock:
            if session_id in self._sessions:
                logger.warning(f"Session {session_id} already active")
                return
            self._sessions[session_id] = SessionInfo(state=SessionState.ACTIVE)
            logger.info(f"[TaskDispatcher] Session {session_id} activated")

    async def _on_graph_finished(self, event: Event):
        session_id = event.payload.get("session_id")
        if not session_id:
            return
        async with self._session_lock:
            session = self._sessions.get(session_id)
            if not session or session.state != SessionState.ACTIVE:
                return
            session.state = SessionState.FINISHING
            grace_seconds = 10.0
            session.grace_until = time.time() + grace_seconds
            logger.info(f"[TaskDispatcher] Session {session_id} entering FINISHING, grace until {session.grace_until}")

            async def _close_after_grace():
                await asyncio.sleep(grace_seconds)
                async with self._session_lock:
                    self._close_session(session_id)   # 内部不再加锁
            session.finish_task = asyncio.create_task(_close_after_grace())

    def _close_session(self, session_id: str):
        """调用者必须持有 _session_lock"""
        session = self._sessions.get(session_id)
        if not session or session.state == SessionState.CLOSED:
            return
        session.state = SessionState.CLOSED
        # 清理相关 future
        keys_to_remove = [k for k in self._pending_futures if k[1] == session_id]
        for key in keys_to_remove:
            fut = self._pending_futures.pop(key, None)
            if fut and not fut.done():
                fut.set_result(False)
                logger.warning(f"[TaskDispatcher] Session {session_id} closed, cancelling future for task {key[0]}")
        # 清理任务映射
        tasks_to_remove = [tid for tid, sid in self._task_to_session.items() if sid == session_id]
        for tid in tasks_to_remove:
            self._task_to_session.pop(tid, None)
        logger.info(f"[TaskDispatcher] Session {session_id} closed")

    async def _on_session_reset(self, event: Event):
        logger.warning("[TaskDispatcher] Received system.graph_session_reset, closing all sessions")
        async with self._session_lock:
            for sid in list(self._sessions.keys()):
                self._close_session(sid)

    # ==================== 任务分发 ====================
    async def dispatch(self, task: Task) -> bool:
        session_id = task.params.get("_session_id", "")
        if not session_id:
            logger.warning(f"Task {task.task_id}: missing session_id")
            session_id = ""

        async with self._session_lock:
            # 不可变绑定
            if task.task_id not in self._task_to_session:
                self._task_to_session[task.task_id] = session_id
            else:
                existing = self._task_to_session[task.task_id]
                if existing != session_id:
                    logger.error(f"Task {task.task_id} already bound to session {existing}, new session {session_id} ignored")
                    # 继续使用已绑定的 session_id
                    session_id = existing

            # 检查重复分发
            key = (task.task_id, session_id)
            if key in self._pending_futures:
                logger.error(f"Task {task.task_id} already pending, duplicate dispatch")
                return False

            # 检查会话状态（只允许 ACTIVE）
            session_info = self._sessions.get(session_id)
            if session_info and session_info.state != SessionState.ACTIVE:
                logger.error(f"Task {task.task_id}: session {session_id} is {session_info.state}, cannot dispatch")
                return False

        # 资源获取（不在锁内，避免长时间阻塞）
        if self.resource_manager and task.required_resources:
            try:
                acquired = await self.resource_manager.acquire(
                    task.required_resources, timeout=10.0, task_id=task.task_id
                )
            except ValueError as e:
                logger.error(f"Task {task.task_id}: resource acquisition error: {e}")
                return False
            if not acquired:
                logger.error(f"Task {task.task_id}: failed to acquire resources {task.required_resources}")
                return False
            self._task_resources[task.task_id] = task.required_resources.copy()
        else:
            self._task_resources[task.task_id] = []

        handler = self.handlers.get(task.type.value)
        if not handler:
            logger.warning(f"Task {task.task_id}: no handler for type {task.type.value}")
            self._release_resources(task.task_id)
            return False

        # 创建 future
        future = asyncio.get_event_loop().create_future()
        async with self._session_lock:
            self._pending_futures[key] = future
        self._active_task_id = task.task_id

        try:
            await handler(task)
            logger.info(f"WAITING RESULT: {task.task_id} (session={session_id})")
            success = await asyncio.wait_for(future, timeout=60.0)
            logger.info(f"RESULT RECEIVED: {task.task_id} success={success}")
            return bool(success)
        except asyncio.TimeoutError:
            logger.error(f"Task {task.task_id}: timeout")
            return False
        except Exception as e:
            logger.error(f"Task {task.task_id}: unexpected error: {e}", exc_info=True)
            return False
        finally:
            self._release_resources(task.task_id)
            async with self._session_lock:
                self._pending_futures.pop(key, None)
                self._task_to_session.pop(task.task_id, None)
            self._active_task_id = None

    # ---------- 内部执行 ----------
    async def _dispatch_navigation(self, task: Task):
        payload = NavigationRequestPayload(
            task_id=task.task_id,
            type=task.type.value,
            params=task.params
        ).model_dump()
        graph_id = task.params.pop("_graph_id", None)
        session_id = task.params.pop("_session_id", None)
        if graph_id:
            payload["graph_id"] = graph_id
        if session_id:
            payload["session_id"] = session_id
        await self.agent.send_command(
            target="navigation_agent",
            command_type=MessageType.NAVIGATION_REQUEST,
            payload=payload,
            expect_reply=False
        )
        logger.info(f"Task {task.task_id}: NAVIGATION_REQUEST sent (graph={graph_id}, session={session_id})")

    async def _dispatch_control(self, task: Task):
        session_id = task.params.get("_session_id", "")
        await self.agent.send_command(
            target="execution_agent",
            command_type=MessageType.EXECUTION_CONTROL,
            payload={"command": task.type.value, "task_id": task.task_id},
            expect_reply=False
        )
        logger.info(f"Task {task.task_id}: EXECUTION_CONTROL sent")
        await self._on_task_completed(task.task_id, session_id, success=True)

    # ---------- 结果处理 ----------
    async def _on_task_completed(self, task_id: str, session_id: str, success: bool):
        self._release_resources(task_id)
        key = (task_id, session_id)
        async with self._session_lock:
            future = self._pending_futures.get(key)
            if future and not future.done():
                future.set_result(bool(success))
                logger.debug(f"Task {task_id} (session={session_id}): future set to {success}")
            else:
                if future is None:
                    logger.warning(f"Task {task_id} (session={session_id}): no pending future found")
                elif future.done():
                    logger.warning(f"Task {task_id} (session={session_id}): future already done")

    def _release_resources(self, task_id: str):
        resources = self._task_resources.pop(task_id, [])
        if resources and self.resource_manager:
            self.resource_manager.release(resources, task_id=task_id)

    def _get_current_active_task_id(self) -> Optional[str]:
        return self._active_task_id

    async def _on_task_result_event(self, event: Event):
        task_id = event.task_id
        payload = event.payload or {}

        # 系统生命周期事件（非任务结果），Dispatcher 不处理
        _SYSTEM_EVENT_PREFIXES = ("system_", "recharge_complete")
        if task_id and any(task_id.startswith(p) for p in _SYSTEM_EVENT_PREFIXES):
            return

        # 解析 task_id
        if not task_id:
            task_id = payload.get("task_id")
            if not task_id:
                task_id = self._get_current_active_task_id()
                if not task_id:
                    logger.debug("Cannot infer task_id (likely system event), dropping")
                    return
                payload["task_id"] = task_id
                logger.info(f"Inferred task_id={task_id} from active task")

        session_id = payload.get("session_id")
        if not session_id:
            async with self._session_lock:
                session_id = self._task_to_session.get(task_id)
                if not session_id:
                    logger.warning(f"Task {task_id}: no session_id found, cannot match future")
                    return
                logger.warning(f"Task {task_id}: session_id missing in result, resolved to {session_id} from mapping")

        # 加锁处理会话检查与 future 获取
        async with self._session_lock:
            session_info = self._sessions.get(session_id)
            if session_info:
                if session_info.state == SessionState.CLOSED:
                    logger.warning(f"Task {task_id}: session {session_id} already closed, result dropped")
                    return
                if session_info.state == SessionState.FINISHING:
                    now = time.time()
                    if now > session_info.grace_until:
                        logger.warning(f"Task {task_id}: session {session_id} grace period expired, result dropped")
                        return
                    else:
                        logger.info(f"Task {task_id}: session {session_id} in FINISHING state, accepting late result")
            else:
                logger.warning(f"Task {task_id}: session {session_id} not active, but trying to match future")

            key = (task_id, session_id)
            future = self._pending_futures.get(key)
            if future is None:
                # 尝试用映射中的 session_id 再试一次（兜底）
                alt_sid = self._task_to_session.get(task_id)
                if alt_sid and alt_sid != session_id:
                    key = (task_id, alt_sid)
                    future = self._pending_futures.get(key)
                    if future:
                        logger.warning(f"Task {task_id}: matched future using mapped session {alt_sid}")
            if future is None:
                logger.warning(f"Task {task_id}: no pending future found, stale result")
                return
            if future.done():
                logger.warning(f"Task {task_id}: future already done")
                return

            success = payload.get("success", False)
            future.set_result(success)
            logger.info(f"Task {task_id} (session={session_id}): future set to {success}")
            self._release_resources(task_id)

    async def shutdown(self):
        """优雅关闭，取消所有等待中的任务"""
        for future in self._pending_futures.values():
            if not future.done():
                future.set_result(False)
        self._pending_futures.clear()
        self._task_to_session.clear()
        self._task_resources.clear()
        self._sessions.clear()
        self._active_task_id = None
        # 如果有其他资源，一并清理

    async def reset(self):
        """系统级重置（power_on专用，不重建对象）"""
        async with self._session_lock:
            # 1. 清 pending futures
            for fut in self._pending_futures.values():
                if not fut.done():
                    fut.set_result(False)
            self._pending_futures.clear()
            # 2. 清 session 映射
            self._task_to_session.clear()
            # 3. 清 session（但不保留旧 FINISHING 逻辑）
            self._sessions.clear()
            # 4. 清 active task
            self._active_task_id = None
        logger.info("[TaskDispatcher] reset completed")