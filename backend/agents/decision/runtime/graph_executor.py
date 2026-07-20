"""
任务图执行器：负责任务状态机、依赖解析、事件驱动调度。
重要：不管理 session 生命周期，只发送 graph.started / graph.finished 事件。
Session 生命周期由 TaskDispatcher 统一管理。

主要改进：
- 引入 ReadyState 分层判断（结构、逻辑、执行就绪）
- 增加 debug_force_ready 调试开关，可强制启动第一个任务
- 在 run() 中主动调用初始调度，解决[卡在 NOT_READY]问题
- 提供 soft_reset / hard_reset 区分运行级和系统级重置
- 移除对 self.session 的直接依赖，只使用固化的 self._session_id
"""

import asyncio
from enum import Enum
from typing import Callable, Awaitable, Optional, List

from backend.agents.core.event.event_router import EventRouter
from backend.agents.core.event.event_types import Event, RuntimeEventType, UIEventType
from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType
from backend.agents.decision.runtime.graph_context import GraphContext, GraphStatus
from backend.agents.decision.runtime.graph_session import GraphSession
from backend.models.task.task import Task, TaskState
from backend.utils.logger_handler import logger

# 成功状态集合
SUCCESS_STATES = {TaskState.SUCCESS, TaskState.SKIPPED}
# 终结状态集合
TERMINAL_STATES = {
    TaskState.SUCCESS,
    TaskState.FAILED,
    TaskState.SKIPPED,
    TaskState.CANCELLED,
    TaskState.STOPPED,
}


class ReadyState(Enum):
    """任务就绪层级，用于精确定位调度卡住的原因"""
    NOT_READY = 0
    STRUCTURAL_READY = 1      # 依赖满足，可进行条件检查
    LOGICAL_READY = 2         # 条件满足，可等待系统就绪
    EXECUTION_BLOCKED = 3     # 系统未就绪（例如 navigation 忙）
    READY = 4                 # 完全就绪，可立即调度


class GraphExecutor:
    """
    任务图执行器：无状态执行引擎，不管理 session 生命周期。
    - 维护任务状态机
    - 解析依赖图
    - 通过 execute_callback 交付就绪任务
    - 仅发送 graph.started / graph.finished 事件
    """

    def __init__(
        self,
        graph: TaskGraph,
        event_router: EventRouter,
        context: Optional[GraphContext] = None,
        condition_checker: Optional[Callable[[Task, GraphContext], bool]] = None,
        max_concurrent: int = 1,
        debug_force_ready: bool = False,
    ):
        """
        :param graph: 静态任务图
        :param event_router: 事件路由器
        :param context: 运行时上下文（若为 None 则自动创建）
        :param condition_checker: 可选条件函数，用于决定任务是否可执行
        :param max_concurrent: 最大并发数
        :param debug_force_ready: 调试开关，强制将第一个任务设为 READY（绕过所有依赖）
        """
        self.graph = graph
        self.event_router = event_router
        self.context = context or GraphContext(graph.graph_id)
        if not self.context.task_status:
            self.context.init_for_graph(list(graph.tasks.keys()))
        self.condition_checker = condition_checker

        self._running = False
        self._complete_event = asyncio.Event()

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._state_lock = asyncio.Lock()
        self._schedule_lock = asyncio.Lock()

        # 会话管理：仅在 run() 中创建临时对象，但只固化 session_id
        self.session = None
        self._session_id: Optional[str] = None
        self._finalized = False
        self._execute_callback = None

        # 调试开关
        self.debug_force_ready = debug_force_ready

        # 订阅外部事件（用于动态依赖）
        self._setup_event_subscriptions()

    # ==================== 外部事件订阅 ====================
    def _setup_event_subscriptions(self):
        """订阅世界模型和机器人状态更新，用于动态触发条件检查"""
        async def on_world_changed(event: Event):
            if self._running:
                try:
                    await self._promote_pending_to_ready()
                    await self._propagate_skipped()
                    await self._schedule_ready_tasks()
                except Exception as e:
                    logger.error(f"Error in on_world_changed: {e}", exc_info=True)

        async def on_robot_changed(event: Event):
            if self._running:
                try:
                    await self._promote_pending_to_ready()
                    await self._propagate_skipped()
                    await self._schedule_ready_tasks()
                except Exception as e:
                    logger.error(f"Error in on_robot_changed: {e}", exc_info=True)

        self.event_router.subscribe("system.world_model_update", on_world_changed)
        self.event_router.subscribe("system.robot_state_update", on_robot_changed)

    # ==================== 状态辅助方法 ====================
    async def _get_ready_level(self, task_id: str) -> ReadyState:
        """
        返回任务的就绪层级，用于定位调度卡住的原因。
        依次检查：结构依赖 → 条件检查 → 系统就绪。
        """
        current_status = self.context.task_status.get(task_id)
        incoming = self.graph.get_incoming_edges(task_id)

        if current_status != TaskState.PENDING:
            return ReadyState.NOT_READY

        # 1. 结构就绪：入边依赖
        #    OR 语义：任意一条入边满足即可触发（与 _propagate_skipped 一致）
        #    无入边的根任务直接视为结构就绪
        can_execute = not incoming  # 无入边 = 无依赖 = 结构就绪
        if not can_execute:
            for edge in incoming:
                pred_status = self.context.task_status[edge.source]
                if edge.type == EdgeType.SUCCESS and pred_status in SUCCESS_STATES:
                    can_execute = True
                    break
                if edge.type == EdgeType.FAILURE and pred_status in (
                    TaskState.FAILED,
                    TaskState.SKIPPED,
                ):
                    can_execute = True
                    break
                if edge.type == EdgeType.ALWAYS and pred_status in TERMINAL_STATES:
                    can_execute = True
                    break

        if not can_execute:
            return ReadyState.NOT_READY

        # 2. 逻辑就绪：条件检查
        if self.condition_checker is not None:
            task = self.graph.tasks[task_id]
            if not self.condition_checker(task, self.context):
                return ReadyState.LOGICAL_READY

        # 3. 执行就绪：底层系统（Navigation/Execution）空闲
        if not await self._is_system_ready():
            return ReadyState.EXECUTION_BLOCKED

        return ReadyState.READY
        return ReadyState.READY

    async def _is_system_ready(self) -> bool:
        """
        检查底层 Agent 是否空闲可接受新任务。
        可根据实际架构扩展，例如查询 TaskDispatcher 或 NavigationAgent 的 control_owner。
        当前简化返回 True，由外部保证 Agent 状态正确。
        """
        return True

    async def _is_task_ready(self, task_id: str) -> bool:
        """兼容旧版，直接返回是否完全就绪"""
        return await self._get_ready_level(task_id) == ReadyState.READY

    async def _promote_pending_to_ready(self):
        """将所有满足条件的 PENDING 任务提升为 READY"""
        async with self._state_lock:
            # 调试模式：强制将第一个任务设为 READY（绕过所有依赖，仅用于快速验证）
            if self.debug_force_ready:
                first_task_id = list(self.graph.tasks.keys())[0]
                if self.context.task_status[first_task_id] == TaskState.PENDING:
                    self.context.update_task_status(first_task_id, TaskState.READY)
                    logger.warning(f"[DEBUG] Force promoted {first_task_id} to READY")
                    return

            for task_id in self.graph.tasks:
                # 不跳过非 PENDING —— 调用 _get_ready_level 统一诊断
                level = await self._get_ready_level(task_id)
                if level == ReadyState.READY:
                    if self.context.task_status[task_id] == TaskState.PENDING:
                        self.context.update_task_status(task_id, TaskState.READY)
                        logger.info(f"Task {task_id} promoted to READY")

    async def _get_ready_tasks(self) -> List[Task]:
        """返回当前所有 READY 状态的任务"""
        async with self._state_lock:
            return [
                task for task_id, task in self.graph.tasks.items()
                if self.context.task_status[task_id] == TaskState.READY
            ]

    async def _all_tasks_terminal(self) -> bool:
        """检查所有任务是否都已终结"""
        async with self._state_lock:
            return all(self.context.task_status[tid] in TERMINAL_STATES for tid in self.graph.tasks)

    async def _propagate_skipped(self) -> bool:
        """传播跳过标记：当任务所有前驱终结且无可触发边时，标记为 SKIPPED"""
        any_skipped = False
        async with self._state_lock:
            changed = True
            while changed:
                changed = False
                for task_id in self.graph.tasks:
                    status = self.context.task_status[task_id]
                    if status != TaskState.PENDING:
                        continue
                    incoming = self.graph.get_incoming_edges(task_id)
                    if not incoming:
                        continue
                    pred_statuses = {e.source: self.context.task_status[e.source].value for e in incoming}
                    all_terminal = all(self.context.task_status[e.source] in TERMINAL_STATES for e in incoming)
                    if not all_terminal:
                        continue
                    can_execute = False
                    for edge in incoming:
                        src_status = self.context.task_status[edge.source]
                        if edge.type == EdgeType.SUCCESS and src_status in SUCCESS_STATES:
                            can_execute = True
                            break
                        if edge.type == EdgeType.FAILURE and src_status in (
                            TaskState.FAILED,
                            TaskState.SKIPPED,
                        ):
                            can_execute = True
                            break
                        if edge.type == EdgeType.ALWAYS:
                            can_execute = True
                            break
                    if not can_execute:
                        self.context.update_task_status(task_id, TaskState.SKIPPED)
                        logger.info(f"Task {task_id} skipped (pred_statuses={pred_statuses})")
                        any_skipped = True
                        changed = True
        return any_skipped

    async def _execute_task(self, task: Task, execute_callback: Callable[[Task], Awaitable[bool]]):
        """执行单个任务，发送运行时事件"""
        task_id = task.task_id
        self.context.update_task_status(task_id, TaskState.RUNNING)
        version = self.context.get_task_version(task_id)
        await self.event_router.emit(Event(
            type=RuntimeEventType.TASK_STARTED,
            source=self.graph.graph_id,
            task_id=task_id,
            payload={"version": version}
        ))
        success = False
        try:
            success = await execute_callback(task)
            if success:
                self.context.update_task_status(task_id, TaskState.SUCCESS)
                version = self.context.get_task_version(task_id)
                await self.event_router.emit(Event(
                    type=RuntimeEventType.TASK_COMPLETED,
                    source=self.graph.graph_id,
                    task_id=task_id,
                    payload={"version": version}
                ))
            else:
                self.context.update_task_status(task_id, TaskState.FAILED)
                version = self.context.get_task_version(task_id)
                await self.event_router.emit(Event(
                    type=RuntimeEventType.TASK_FAILED,
                    source=self.graph.graph_id,
                    task_id=task_id,
                    payload={"version": version, "error": "callback returned False"}
                ))
        except Exception as e:
            self.context.update_task_status(task_id, TaskState.FAILED)
            version = self.context.get_task_version(task_id)
            await self.event_router.emit(Event(
                type=RuntimeEventType.TASK_FAILED,
                source=self.graph.graph_id,
                task_id=task_id,
                payload={"version": version, "error": str(e)}
            ))
            success = False
        return success

    # ==================== 任务调度 ====================
    async def _schedule_ready_tasks(self):
        """调度所有就绪任务"""
        async with self._schedule_lock:
            if not self._running or self._execute_callback is None:
                return
            ready = await self._get_ready_tasks()
            for task in ready:
                if self.context.task_status[task.task_id] != TaskState.READY:
                    continue
                self.context.increment_dispatch(task.task_id)
                self.context.update_task_status(task.task_id, TaskState.DISPATCHED)
                asyncio.create_task(self._wrapped_execute(task))

    async def _wrapped_execute(self, task: Task):
        """带信号量和会话 ID 注入的执行包装器"""
        # 使用固化的 session ID（GraphExecutor 不再依赖 session 对象）
        captured_session_id = self._session_id
        async with self._semaphore:
            # 注入会话信息（供下层 Dispatcher 使用）
            task.params["_graph_id"] = self.graph.graph_id
            task.params["_session_id"] = captured_session_id

            success = await self._execute_task(task, self._execute_callback)

            # 清理临时字段
            task.params.pop("_graph_id", None)
            task.params.pop("_session_id", None)

            if not isinstance(success, bool):
                success = bool(success)

            logger.info(f"[GraphExecutor] Task {task.task_id} finished with success={success}")
            await self._finalize_task(task.task_id, success)

            # 推进后续任务
            await self._promote_pending_to_ready()
            await self._propagate_skipped()
            await self._schedule_ready_tasks()
            if await self._all_tasks_terminal():
                self._complete_event.set()

    async def _finalize_task(self, task_id: str, success: bool):
        """任务结束收口，发送 TASK_STATE_CHANGED 事件"""
        state = "completed" if success else "failed"
        await self.event_router.emit(Event(
            type=RuntimeEventType.TASK_STATE_CHANGED,
            source=self.graph.graph_id,
            task_id=task_id,
            payload={
                "task_state": "idle",
                "result": state,
                "progress": 1.0 if success else 0.0
            }
        ))
        logger.info(f"[GraphExecutor] Task {task_id} finalized with success={success}, state={state}")

    # ==================== 主流程与生命周期 ====================
    async def run(self, execute_callback: Callable[[Task], Awaitable[bool]], timeout: Optional[float] = None):
        """
        启动任务图执行。
        :param execute_callback: 实际执行任务的回调（由 TaskDispatcher 提供）
        :param timeout: 整体超时时间（秒）
        """
        if self._running is False and self.context.status == GraphStatus.STOPPED:
            self._running = True
        # 创建临时会话对象，只固化 session_id
        self.session = GraphSession(graph_id=self.graph.graph_id)
        self.session.running = True
        self._session_id = self.session.session_id
        self._running = True
        self._finalized = False
        self.context.status = GraphStatus.RUNNING
        self._execute_callback = execute_callback

        # 发送会话开始事件
        await self.event_router.emit(Event(
            type="graph.started",
            source=self.graph.graph_id,
            payload={
                "graph_id": self.graph.graph_id,
                "session_id": self._session_id
            }
        ))

        # ★★★ 关键修复：立即执行第一次调度，确保任务能够启动 ★★★
        await self._promote_pending_to_ready()
        await self._schedule_ready_tasks()

        # 如果所有任务已经终结，直接完成
        if await self._all_tasks_terminal():
            self._complete_event.set()
            return

        try:
            if timeout:
                await asyncio.wait_for(self._complete_event.wait(), timeout=timeout)
            else:
                await self._complete_event.wait()
        except asyncio.TimeoutError:
            logger.error(f"GraphExecutor {self.graph.graph_id} timed out after {timeout}s")
            await self._force_stop_on_timeout()
        finally:
            session_id = self._session_id
            await self._finalize_graph()
            if self.context.status == GraphStatus.RUNNING:
                self.context.status = GraphStatus.COMPLETED
                logger.info("GraphExecutor: all tasks completed")
            await self.event_router.emit(Event(
                type=RuntimeEventType.GRAPH_COMPLETED,
                source=self.graph.graph_id,
                payload={"status": self.context.status.value, "session_id": session_id}
            ))

    async def _force_stop_on_timeout(self):
        """超时后强制终止：标记所有未完成任务为 FAILED，并发送结果事件"""
        async with self._state_lock:
            for task_id, status in self.context.task_status.items():
                if status not in TERMINAL_STATES:
                    self.context.update_task_status(task_id, TaskState.FAILED)
                    logger.warning(f"Task {task_id} forced to FAILED due to graph timeout")
                    await self.event_router.emit(Event(
                        type=UIEventType.TASK_RESULT,
                        source=self.graph.graph_id,
                        task_id=task_id,
                        payload={
                            "task_id": task_id,
                            "session_id": self._session_id,
                            "success": False,
                            "result": {},
                            "error": "Graph timeout"
                        }
                    ))
        self.context.status = GraphStatus.FAILED
        self._complete_event.set()

    async def _finalize_graph(self):
        """发送 graph.finished 事件（不销毁任何 session 状态）"""
        if self._finalized:
            return
        self._finalized = True
        logger.info(f"[GraphExecutor] Finalizing graph execution: {self.graph.graph_id}, session={self._session_id}")
        self._running = False
        self.context.status = GraphStatus.COMPLETED
        self._execute_callback = None

        await self.event_router.emit(Event(
            type="graph.finished",
            source=self.graph.graph_id,
            payload={
                "graph_id": self.graph.graph_id,
                "session_id": self._session_id
            }
        ))

    # ==================== 外部控制接口 ====================
    async def wait_completion(self):
        """等待任务图执行完成"""
        await self._complete_event.wait()

    def stop(self):
        """停止调度新任务（不销毁状态）"""
        self._running = False
        self.context.status = GraphStatus.STOPPED

        # 不要 set 完成事件（否则 run 彻底结束）
        # self._complete_event.set()

        asyncio.create_task(self._emit_stop_results())
        logger.info(f"[GraphExecutor] Stopped (pause without session reset)")

    async def _emit_stop_results(self):
        """为所有尚未完成的任务发送 stop 结果"""
        async with self._state_lock:
            for task_id, status in self.context.task_status.items():
                if status not in TERMINAL_STATES:
                    await self.event_router.emit(Event(
                        type=UIEventType.TASK_RESULT,
                        source=self.graph.graph_id,
                        task_id=task_id,
                        payload={
                            "task_id": task_id,
                            "session_id": self._session_id,
                            "success": False,
                            "result": {},
                            "error": "Stopped by user"
                        }
                    ))
                    self.context.update_task_status(task_id, TaskState.STOPPED)

    def terminate(self):
        """彻底终止任务图（用户停止或系统重置时调用）"""
        self.stop()
        # 注意：不在此处发送 graph.finished，因为 run() 的 finally 已经会发送

    def soft_reset(self):
        """
        运行级重置：清空运行时事件和等待队列，但不改变任务图上下文和调度标志。
        可用于清除内部临时状态，恢复调度能力。
        """
        self._complete_event.clear()
        # 注意：不清空 _pending_futures 等，因为 soft_reset 仅用于恢复调度

    def hard_reset(self):
        """
        系统级重置：完全重置执行器，清空所有内部状态。
        仅在用户显式重置或系统致命错误时调用。
        """
        self.soft_reset()
        self._running = False
        self.context.reset()
        self._session_id = None
        self._execute_callback = None
        self._finalized = False

    async def notify_graph_updated(self):
        """外部调用：通知图结构已更新（如动态插入任务），重新评估就绪任务"""
        if self._running and self._execute_callback is not None:
            await self._propagate_skipped()
            await self._promote_pending_to_ready()
            asyncio.create_task(self._schedule_ready_tasks())

    async def resume(self):
        """从 STOPPED 恢复运行（power_on 必须调用）"""
        if self._running:
            return
        self._running = True
        self.context.status = GraphStatus.RUNNING
        # 关键：重新 kick 调度
        await self._promote_pending_to_ready()
        await self._schedule_ready_tasks()
        logger.info("[GraphExecutor] Resumed successfully")
