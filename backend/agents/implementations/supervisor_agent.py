"""
SupervisorAgent - 高层任务规划与调度中枢（事件驱动版）

职责：
    - 接收用户任务 (TASK 消息) 和控制指令 (TASK_CONTROL)
    - 调用 PlannerManager 生成 TaskGraph
    - 创建 GraphContext 和 GraphExecutor 执行任务图
    - 维护当前任务状态（唯一真相源）和恢复上下文
    - 通过 EventRouter 监听运行时事件，更新任务状态
    - 通过 MessageBus 下发点对点控制指令
    - 转发 UI 事件给前端
    - 持久化任务图状态，支持崩溃恢复
"""

import uuid
import time
import asyncio
from enum import Enum
from typing import Dict, Any, Optional

from backend.agents.implementations.base_agent import BaseAgent
from backend.agents.schemas.agent_messages import RoomsReady
from backend.agents.schemas.messages import MessageType, Message, Priority, HeartbeatPayload
from backend.agents.utils.task_storage import TaskStorage

from backend.agents.decision.planner import PlannerManager, PlannerContext, PlanningPolicy, PlanningResult
from backend.agents.runtime.agent_runtime import AgentRuntime
from backend.agents.runtime.task_router import is_simple_query, is_action_command
from backend.agents.decision.runtime.graph_context import GraphContext, GraphStatus
from backend.agents.decision.runtime.graph_executor import GraphExecutor
from backend.agents.decision.runtime.task_dispatcher import TaskDispatcher
from backend.agents.core.runtime.resource_manager import ResourceManager
from backend.agents.core.event.event_router import EventRouter
from backend.agents.core.event.event_types import Event, RuntimeEventType, UIEventType
from backend.models.task.task import TaskState, TaskContext, ResumeContext, TaskType, Task
from backend.models.physics.robot_state import Pose, RobotPowerState
from backend.utils.logger_handler import logger
from backend.agents.decision.runtime.task_graph import TaskGraph


class SupervisorState(str, Enum):
    """Supervisor 内部状态机状态（对应任务状态）"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    RECHARGING = "recharging"
    EMERGENCY_STOPPED = "emergency_stopped"
    SUCCESS = "success"
    FAILED = "failed"


class SupervisorAgent(BaseAgent):
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        message_bus,
        registry,
        planner_manager: PlannerManager,
        dispatcher: Optional[TaskDispatcher] = None,
        resource_manager: Optional[ResourceManager] = None,
        event_router: Optional[EventRouter] = None,
        agent_runtime: Optional[AgentRuntime] = None,
    ):
        super().__init__(agent_id, agent_type, message_bus, registry, event_router=event_router)
        self.planner_manager = planner_manager
        self.agent_runtime = agent_runtime
        self.resource_manager = resource_manager
        if dispatcher is None:
            self.dispatcher = TaskDispatcher(agent=self, resource_manager=resource_manager, event_router=event_router)
        else:
            self.dispatcher = dispatcher

        # 任务状态（唯一真相源）
        self._task_state = TaskState.IDLE                     # 当前任务状态（唯一真相源）
        self._task_context: Optional[TaskContext] = None      # 当前任务静态信息
        self._current_progress = 0.0                          # 当前任务进度
        self._resume_context: Optional[ResumeContext] = None  # 回充前保存的恢复上下文
        self._original_task_command: Optional[str] = None     # 保存原命令文本
        self._charge_complete_event = asyncio.Event()         # 等待充电完成的事件

        # 持久化相关
        self.storage = TaskStorage()
        self._task_versions: Dict[str, int] = {}

        # 控制队列与主循环
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._main_task: Optional[asyncio.Task] = None

        # 当前任务图执行上下文
        self.current_graph: Optional[TaskGraph] = None
        self.current_executor: Optional[GraphExecutor] = None
        self.current_context: Optional[GraphContext] = None
        self.current_planning_result: Optional[PlanningResult] = None

        # 缓存外部消息
        self.latest_world_model: Dict[str, Any] = {}
        self.latest_robot_state: Dict[str, Any] = {}

        # 心跳监控
        self._last_heartbeat: Dict[str, float] = {}
        self._heartbeat_timeout = 20
        self._heartbeat_monitor: Optional[asyncio.Task] = None
        self._last_heartbeat_log_time = 0.0

        self.room_names = []

        self._charge_complete_event = asyncio.Event()       # 充电任务
        self._power_state = "OFF"                           # 当前电源状态/关机
        self._mission_id: Optional[int] = None              # 当前任务 mission 记录 ID
        self._replay_task: Optional[asyncio.Task] = None    # 回放轨迹记录后台任务
        # 前端广播回调（由 container 注入，用于推流任务可视化数据到 WebSocket）
        self._broadcast_fn = None

    @property
    def power_state(self) -> str:
        """统一的外部电源状态访问接口（内部使用 _power_state 存储）"""
        return self._power_state

    # ================== 生命周期 ==================
    async def on_start(self):
        """启动 SupervisorAgent：订阅消息、启动命令队列主循环、恢复未完成任务"""
        # 订阅外部命令（用户任务、控制指令）
        await self.subscribe(MessageType.TASK, self._enqueue_command)
        # 订阅统一的任务控制消息
        await self.subscribe(MessageType.TASK_CONTROL, self._enqueue_command)
        # 为了兼容旧前端，保留 CONTROL 订阅（可转发到 TASK_CONTROL 或直接处理，这里直接处理）
        await self.subscribe(MessageType.CONTROL, self._enqueue_command)

        await self.subscribe(MessageType.WORLD_MODEL, self._on_world_model)
        await self.subscribe(MessageType.ROBOT_STATE, self._on_robot_state)
        await self.subscribe(MessageType.HEARTBEAT, self.on_heartbeat)
        await self.subscribe(MessageType.ROOMS_READY, self._on_rooms_ready)

        # 订阅 Runtime 事件
        self.event_router.subscribe(RuntimeEventType.TASK_STARTED, self._on_runtime_task_started)
        self.event_router.subscribe(RuntimeEventType.TASK_COMPLETED, self._on_runtime_task_completed)
        self.event_router.subscribe(RuntimeEventType.TASK_FAILED, self._on_runtime_task_failed)
        self.event_router.subscribe(RuntimeEventType.GRAPH_COMPLETED, self._on_runtime_graph_completed)
        self.event_router.subscribe(UIEventType.TASK_RESULT.value, self._on_charge_complete_event)
        # 订阅开机/关机事件（可选）
        self.event_router.subscribe(UIEventType.TASK_RESULT.value, self._on_system_event)

        await self.dispatcher.start()
        await self._restore_pending_graphs()

        self._main_task = asyncio.create_task(self._main_loop())
        self._heartbeat_monitor = asyncio.create_task(self._heartbeat_check_loop())

    async def on_stop(self):
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
        if self._heartbeat_monitor:
            self._heartbeat_monitor.cancel()
            try:
                await self._heartbeat_monitor
            except asyncio.CancelledError:
                pass
        logger.info("SupervisorAgent stopped")

    # ================== 消息队列 ==================
    async def _enqueue_command(self, msg: Message):
        logger.info(f"Supervisor enqueued command: {msg.type}")
        await self._command_queue.put(msg)

    # ================== 主事件循环 ==================
    async def _main_loop(self):
        """主循环：根据当前状态处理队列中的命令"""
        last_health_log = 0
        while True:
            now = time.time()
            if now - last_health_log > 10:
                bus = self.bus
                # 需要 MessageBus 提供 get_dropped_count() 等方法，可先简单记录日志
                logger.warning(
                    f"System health: bus_queue={bus.get_queue_size()}, "
                    f"bus_workers={bus.get_worker_count()}, "
                    f"task_state={self._task_state}, "
                    f"executor_running={self.current_executor is not None}, "
                    f"nav_mode={self.navigation_agent.mode if hasattr(self, 'navigation_agent') else '?'}, "
                    f"control_owner={self.navigation_agent.control_owner if hasattr(self, 'navigation_agent') else '?'}"
                )
                last_health_log = now

            # 关键修复：SUCCESS 等同于 IDLE（任务已完成，可以接受新任务）
            if self._task_state == TaskState.SUCCESS:
                self._task_state = TaskState.IDLE
                await self._publish_task_state()
                # 继续循环，让下一轮进入 IDLE 处理

            if self._task_state == TaskState.IDLE:
                cmd = await self._command_queue.get()
                if cmd.type == MessageType.TASK:
                    self._task_state = TaskState.RUNNING
                    await self._publish_task_state()
                    asyncio.create_task(self._handle_task(cmd))
                elif cmd.type in (MessageType.TASK_CONTROL, MessageType.CONTROL):
                    await self._handle_task_control(cmd)

            elif self._task_state == TaskState.RUNNING:
                try:
                    cmd = await asyncio.wait_for(self._command_queue.get(), timeout=0.5)
                    if cmd.type in (MessageType.TASK_CONTROL, MessageType.CONTROL):
                        await self._handle_task_control(cmd)
                except asyncio.TimeoutError:
                    pass

            elif self._task_state == TaskState.PAUSED:
                cmd = await self._command_queue.get()
                if cmd.type in (MessageType.TASK_CONTROL, MessageType.CONTROL):
                    await self._handle_task_control(cmd)

            elif self._task_state == TaskState.RECHARGING:
                cmd = await self._command_queue.get()
                if cmd.type in (MessageType.TASK_CONTROL, MessageType.CONTROL):
                    await self._handle_task_control(cmd)

            elif self._task_state == TaskState.EMERGENCY_STOP:
                cmd = await self._command_queue.get()
                if cmd.type in (MessageType.TASK_CONTROL, MessageType.CONTROL):
                    await self._handle_task_control(cmd)

            # FAILED / STOPPED / 未知状态 → 自动降级为 IDLE，确保控制指令可处理
            else:
                logger.warning(f"Supervisor recovered from {self._task_state} → IDLE")
                self._task_state = TaskState.IDLE
                await self._publish_task_state()

    # ================== 任务处理 ==================
    async def _handle_task(self, msg: Message):
        """处理用户任务（TASK消息）"""
        command = msg.payload.get("text") or msg.payload.get("command")
        if not command:
            return
        logger.info(f"Handling task: {command}")

        # 保存原始命令，用于回充后恢复
        self._original_task_command = command

        # 自动取消当前任务，确保系统处于空闲状态
        if self._task_state not in (TaskState.IDLE, TaskState.STOPPED):
            logger.warning(f"Task already running, cancelling current task (state={self._task_state})")
            await self._cancel_task()
            # 等待取消完成
            await asyncio.sleep(0.5)

        # 注意：不再发送 reset 命令，因为 GraphExecutor 会管理任务生命周期。
        # reset 只在用户显式停止/重置或系统错误时调用。
        # 如果需要确保机器人电源开启，可发送 power_on（可选）
        # await self._send_execution_control("power_on")

        # Fast path: pattern-matched actions -> RulePlanner direct
        if is_action_command(command):
            if self._power_state in ("OFF", "SHUTDOWN", "EMERGENCY_STOP"):
                await self.emit_event(UIEventType.TASK_RESULT.value, task_id=command, payload={"success": False, "error": f"机器人已关机，无法执行操作"})
                self._task_state = TaskState.IDLE
                await self._publish_task_state()
                return
            # Confirm removed - proceed directly
            ctx = PlannerContext(robot_id=self.agent_id, user_command=command, world_state=self.latest_world_model, robot_state=self.latest_robot_state, planning_policy=PlanningPolicy.DEFAULT, rooms=self.room_names)
            rule = [p for p in self.planner_manager.planners if p.name == "rule"][0]
            result = await rule.plan(ctx)
            if not result.success:
                logger.warning(f"RulePlanner failed, fallback: {result.warnings}")
            else:
                g = result.graph
                rc = GraphContext(g.graph_id)
                rc.init_for_graph(list(g.tasks.keys()))
                rc.update_shared_state("battery", self._get_battery(), float)
                ex = GraphExecutor(graph=g, event_router=self.event_router, context=rc, condition_checker=self._condition_checker)
                self.current_graph=g; self.current_context=rc; self.current_executor=ex; self.current_planning_result=None
                self._start_mission(command, g, ex)
                self._broadcast_graph_structure(g)
                asyncio.create_task(self._run_graph(ex, self.dispatcher.dispatch, g.graph_id))
                return

        # Try AgentRuntime for simple queries
        if self.agent_runtime is not None and is_simple_query(command):
            logger.info(f"Routing simple query to AgentRuntime: {command}")
            try:
                result = await self.agent_runtime.run(command)
                if result.action == "execute_graph":
                    logger.info("AgentRuntime: call_planner returned TaskGraph")
                    graph = result.graph
                    runtime_ctx = GraphContext(graph.graph_id)
                    runtime_ctx.init_for_graph(list(graph.tasks.keys()))
                    runtime_ctx.update_shared_state("battery", self._get_battery(), float)
                    runtime_ctx.update_shared_state("coverage", self.latest_world_model.get("coverage_percent", 0.0), float)
                    executor = GraphExecutor(
                        graph=graph, event_router=self.event_router,
                        context=runtime_ctx,
                        condition_checker=self._condition_checker,
                    )
                    self.current_graph = graph
                    self.current_context = runtime_ctx
                    self.current_executor = executor
                    self.current_planning_result = None
                    self._start_mission(command, graph, executor)
                    self._broadcast_graph_structure(graph)
                    asyncio.create_task(self._run_graph(executor, self.dispatcher.dispatch, graph.graph_id))
                    return
                await self.emit_event(UIEventType.TASK_RESULT.value, task_id=command,
                                    payload={"success": True, "answer": result.answer})
                self._task_state = TaskState.IDLE
                await self._publish_task_state()
                return
            except Exception as e:
                logger.warning(f"AgentRuntime failed, fallback to planner: {e}")

        # 动作类指令直接走 Planner（不经过 ReAct）
        await self._publish_task_state()
        await self.emit_event(UIEventType.TASK_PROGRESS.value, payload={"feedback": "Planning started"})

        try:
            ctx = PlannerContext(
                robot_id=self.agent_id,
                user_command=command,
                world_state=self.latest_world_model,
                robot_state=self.latest_robot_state,
                planning_policy=PlanningPolicy.DEFAULT,
                rooms=self.room_names,
            )
            planning_result = await self.planner_manager.select_and_plan(ctx)
            if not planning_result.success:
                logger.error(f"Planning failed: {planning_result.warnings}")
                await self.emit_event(
                    UIEventType.TASK_RESULT.value,
                    task_id=command,
                    payload={"success": False, "error": str(planning_result.warnings)}
                )
                self._task_state = TaskState.IDLE
                await self._publish_task_state()
                return

            graph = planning_result.graph
            logger.info(f"Planner {planning_result.planner_name} generated graph with {len(graph.tasks)} tasks")

            runtime_ctx = GraphContext(graph.graph_id)
            runtime_ctx.init_for_graph(list(graph.tasks.keys()))
            runtime_ctx.update_shared_state("battery", self._get_battery(), float)
            runtime_ctx.update_shared_state("coverage", self.latest_world_model.get("coverage_percent", 0.0), float)

            await self._save_graph_state(graph.graph_id, graph, runtime_ctx)

            executor = GraphExecutor(
                graph=graph,
                event_router=self.event_router,
                context=runtime_ctx,
                condition_checker=self._condition_checker,
                # 可选：调试模式临时开启
                # debug_force_ready=True,
            )

            self.current_graph = graph
            self.current_context = runtime_ctx
            self.current_executor = executor
            self.current_planning_result = planning_result

            self._start_mission(command, graph, executor)
            logger.info(f"[DEBUG] _start_mission returned, _mission_id={self._mission_id}")
            # 广播图结构（供前端 DAG 可视化渲染）
            self._broadcast_graph_structure(graph)

            # 保存任务上下文（静态信息）
            self._task_context = self._extract_task_context(graph, planning_result)
            self._resume_context = None
            self._current_progress = 0.0

            async def execute_callback(task):
                return await self.dispatcher.dispatch(task)

            await self.emit_event(UIEventType.TASK_PROGRESS.value, payload={"feedback": "Execution started"})
            asyncio.create_task(self._run_graph(executor, execute_callback, graph.graph_id))

        except Exception as e:
            logger.exception(f"Task handling failed: {e}")
            await self.emit_event(
                UIEventType.TASK_RESULT.value,
                task_id=command,
                payload={"success": False, "error": str(e)}
            )
            self._task_state = TaskState.IDLE
            await self._publish_task_state()

    def _extract_task_context(self, graph: TaskGraph, planning_result: PlanningResult) -> Optional[TaskContext]:
        """从任务图中提取静态上下文（用于恢复）"""
        # 简化：从第一个任务中提取信息，可根据实际扩展
        first_task_id = next(iter(graph.tasks.keys()))
        first_task = graph.tasks[first_task_id]
        room_id = first_task.params.get("room_id") or first_task.params.get("area", "")
        # 其他字段需从 planning_result 中获取，暂简略
        return TaskContext(
            task_id=first_task.task_id,
            graph_id=graph.graph_id,
            current_node=first_task_id,
            current_goal=Pose(x=0, y=0, theta=0),  # 暂缺
            current_path=[],
            path_index=0,
            room_id=room_id
        )

    # ================== 任务控制指令处理 ==================
    async def _handle_task_control(self, msg: Message):
        cmd = msg.payload.get("command")
        if not cmd:
            return
        if cmd == "pause":
            await self._pause_task()
        elif cmd == "resume":
            await self._resume_task()
        elif cmd == "recharge":
            await self._recharge()
        elif cmd == "stop":
            await self._cancel_task()
        elif cmd == "cancel":
            await self._cancel_task()
        elif cmd == "emergency_stop":
            await self._emergency_stop()
        elif cmd == "reset":
            await self._reset_emergency_stop()
        # 新增 power_on / power_off 处理
        elif cmd == "power_on":
            # 0. 先强制停止当前 executor（无论 task_state 是什么）
            #    解决 _cancel_task() 在 IDLE 状态下跳过 executor.stop() 的问题
            if self.current_executor:
                self.current_executor.stop()
                self.current_executor = None
            self.current_graph = None
            self.current_context = None
            # 然后走正常取消流程（处理充电任务等）
            await self._cancel_task()
            await self._send_execution_control("power_on")
            # 1. 停止旧 dispatcher（取消事件订阅），创建新的
            if self.dispatcher:
                await self.dispatcher.stop()
            self.dispatcher = TaskDispatcher(self, self.resource_manager, self.event_router)
            await self.dispatcher.start()
            # 2. reset navigation（清理残留 token / control_owner）
            await self._send_navigation_control("reset")
            # 3. 重置状态
            self._task_state = TaskState.IDLE
            self._power_state = RobotPowerState.IDLE
            self.control_owner = None
            # 关键修复：恢复 GraphExecutor（如果存在且需要恢复）
            if hasattr(self, "graph_executor") and self.graph_executor:
                await self.graph_executor.resume()
            logger.info("POWER_ON completed: system fully reinitialized")
        elif cmd == "power_off":
            await self._send_execution_control("power_off")
        else:
            logger.warning(f"Unknown task control command: {cmd}")

    async def _reset_emergency_stop(self):
        """从紧急停止状态恢复（即使状态不是 EMERGENCY_STOP 也允许强制复位）"""
        # 无论当前任务状态如何，都向底层发送 reset 命令
        await self._send_navigation_control("reset")
        await self._send_execution_control("reset")
        # 重置任务状态为 IDLE（如果当前是 EMERGENCY_STOP 或其他状态）
        if self._task_state == TaskState.EMERGENCY_STOP:
            self._task_state = TaskState.IDLE
            await self._publish_task_state()
            logger.info("Emergency stop reset, system idle")
        else:
            # 如果不是急停状态，也做一次清理，确保底层状态同步
            self._task_state = TaskState.IDLE
            await self._publish_task_state()
            logger.info("Reset command received, forced state sync to IDLE")

    async def _pause_task(self):
        """暂停任务：只要 executor 存在就发送暂停指令，不严格依赖状态"""
        if self.current_executor is None:
            logger.warning("No executor, cannot pause")
            return
        # 强制将状态设为 PAUSED（即使之前是其他状态）
        self._task_state = TaskState.PAUSED
        await self._publish_task_state()
        await self._send_navigation_control("pause")
        await self._send_execution_control("pause")
        await self.emit_event(UIEventType.TASK_PROGRESS.value, payload={"feedback": "Task paused"})
        logger.info("Task paused")

    async def _resume_task(self):
        """恢复任务：只要 executor 存在就发送恢复指令"""
        if self.current_executor is None:
            logger.warning("No executor, cannot resume")
            return
        self._task_state = TaskState.RUNNING
        await self._publish_task_state()
        await self._send_navigation_control("resume")
        await self._send_execution_control("resume")
        # ExecutionAgent 不需要额外指令
        await self.emit_event(UIEventType.TASK_PROGRESS.value, payload={"feedback": "Task resumed"})
        logger.info("Task resumed")

    async def _cancel_task(self):
        """取消当前任务：始终通知底层 Agent，不依赖 _task_state 判断"""
        # 1. 始终发送 stop 到 Navigation / Execution（状态可能因异步事件已不同步）
        await self._send_navigation_control("stop")
        await self._send_execution_control("stop")

        # 2. 停止 executor（如果存在）
        if self.current_executor:
            self.current_executor.stop()
            self.current_executor = None
        self.current_graph = None

        # 3. 取消充电任务（如果正在进行）
        if hasattr(self, '_recharge_task') and self._recharge_task and not self._recharge_task.done():
            self._recharge_task.cancel()
            try:
                await self._recharge_task
            except asyncio.CancelledError:
                pass
            self._recharge_task = None

        # 4. 更新 Supervisor 状态（仅当当前确实在运行任务时）
        if self._task_state not in (TaskState.IDLE, TaskState.STOPPED, TaskState.SUCCESS, TaskState.FAILED):
            self._task_state = TaskState.STOPPED
            await self._publish_task_state()
            self._task_context = None
            self._resume_context = None
            self._current_progress = 0.0
            await self.emit_event(UIEventType.TASK_RESULT.value,
                                payload={"success": False, "error": "Stopped by user"})

        logger.info("Task stopped")

    async def _recharge(self):
        """充电：仅在空闲状态执行回充任务，充电完成后回到空闲（不恢复原任务）"""
        if self._task_state != TaskState.IDLE:
            logger.warning(f"Cannot recharge in state {self._task_state}, only allowed in IDLE")
            return

        # 状态切换为回充中
        self._task_state = TaskState.RECHARGING
        await self._publish_task_state()

        # 创建回充图
        recharge_graph = self._create_recharge_graph()
        runtime_ctx = GraphContext(recharge_graph.graph_id)
        runtime_ctx.init_for_graph(list(recharge_graph.tasks.keys()))
        executor = GraphExecutor(
            graph=recharge_graph,
            event_router=self.event_router,
            context=runtime_ctx,
            condition_checker=self._condition_checker,
        )
        # 临时替换当前执行器（但没有正在执行的任务，所以 old_executor 为 None）
        old_executor = self.current_executor
        self.current_executor = executor
        # 异步执行回充图
        self._recharge_task = asyncio.create_task(
            self._run_recharge_graph(executor, recharge_graph.graph_id, old_executor)
        )

    async def _run_recharge_graph(self, executor: GraphExecutor, graph_id: str, old_executor):
        try:
            # 执行回充图（导航回充电桩）
            await self._run_graph(executor, self.dispatcher.dispatch, graph_id)

            # 检查导航是否成功
            recharge_task_id = list(executor.graph.tasks.keys())[0]
            recharge_success = (
                executor.context.task_status.get(recharge_task_id) == TaskState.SUCCESS
            )

            if recharge_success:
                logger.info("Recharge navigation succeeded, starting charging")
                await self._simulate_charging()
            else:
                logger.warning("Recharge navigation failed, skipping charging")
                await self.emit_event(
                    UIEventType.TASK_RESULT.value,
                    task_id="recharge",
                    payload={"success": False, "error": "Navigation to charging station failed"}
                )
        except asyncio.CancelledError:
            logger.info("Recharge cancelled")
        finally:
            self.current_executor = old_executor
            if self._task_state == TaskState.RECHARGING:
                self._task_state = TaskState.IDLE
                await self._publish_task_state()
            self._recharge_task = None

    async def _simulate_charging(self):
        """模拟充电过程，等待充电完成事件"""
        # 重置充电完成事件
        self._charge_complete_event.clear()
        # 向 ExecutionAgent 发送充电开始命令
        await self._send_execution_control("charge_start", target_voltage=12.0, duration=8.0)
        # 等待充电完成（最多等待 10 秒，足够充电完成）
        try:
            await asyncio.wait_for(self._charge_complete_event.wait(), timeout=10.0)
            logger.info("Battery charging completed")
        except asyncio.TimeoutError:
            logger.warning("Charging timeout, but continue")

    async def _emergency_stop(self):
        """紧急停止（不可恢复）"""
        self._task_state = TaskState.EMERGENCY_STOP
        # 停止所有执行器和任务
        if self.current_executor:
            self.current_executor.terminate()
        self.current_executor = None
        self.current_graph = None
        self._task_context = None
        self._resume_context = None
        # 通知 NavigationAgent 紧急停止
        await self._send_navigation_control("emergency_stop")
        # 通知 ExecutionAgent 紧急停车
        await self._send_execution_control("emergency_stop")
        await self._publish_task_state()
        await self.emit_event(
            UIEventType.TASK_RESULT.value,
            task_id=self._task_context.task_id if self._task_context else None,
            payload={"success": False, "error": "Emergency stop"}
        )
        logger.warning("Emergency stop activated")

    # ================== 辅助方法 ==================
    async def _send_navigation_control(self, command: str):
        """向 NavigationAgent 发送控制指令（HIGH 优先级，确保不被 EXECUTION 消息阻塞）"""
        try:
            logger.debug(f"Sending navigation control: {command}")
            msg = Message(type=MessageType.NAVIGATION_CONTROL, source=self.agent_id,
                        payload={"command": command}, priority=Priority.HIGH)
            await self.bus.publish(msg)
        except Exception as e:
            logger.error(f"Failed to send navigation control: {e}")

    async def _send_execution_control(self, command: str, **kwargs):
        """向 ExecutionAgent 发送控制指令（HIGH 优先级）"""
        payload = {"command": command}
        payload.update(kwargs)
        try:
            logger.debug(f"Sending execution control: {command}, {kwargs}")
            msg = Message(type=MessageType.EXECUTION_CONTROL, source=self.agent_id,
                        payload=payload, priority=Priority.HIGH)
            await self.bus.publish(msg)
        except Exception as e:
            logger.error(f"Failed to send execution control: {e}")

    async def _capture_resume_context(self) -> Optional[ResumeContext]:
        """从 NavigationAgent 获取当前导航状态，构建恢复上下文"""
        try:
            response = await self.request(
                target="navigation_agent",
                msg_type=MessageType.GET_NAVIGATION_STATE,
                payload={},
                timeout=2.0
            )
            waypoint_index = response.payload.get("waypoint_index", 0)
            progress = response.payload.get("progress", 0.0)
            return ResumeContext(
                task_context=self._task_context,
                waypoint_index=waypoint_index,
                progress=progress
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout getting navigation state, cannot capture resume context")
            return None
        except Exception as e:
            logger.error(f"Failed to capture resume context: {e}")
            return None

    def _create_recharge_graph(self) -> TaskGraph:
        """创建回充任务图"""
        graph = TaskGraph(graph_id=str(uuid.uuid4()))
        recharge_task = Task(
            task_id=f"recharge_{uuid.uuid4().hex[:8]}",
            type=TaskType.RETURN_TO_CHARGE,
            params={},
            robot_id=self.agent_id,
            required_resources=["motion"],
            max_retries=2,
            retry_delay=1.0,
        )
        graph.add_task(recharge_task)
        # 回充任务自动成功，无后继
        return graph

    async def _publish_task_state(self):
        """广播任务状态变化（供前端和 UI 使用）"""
        await self.publish(MessageType.TASK_STATE_CHANGED, payload={
            "task_id": self._task_context.task_id if self._task_context else None,
            "state": self._task_state.value,
            "progress": self._current_progress,
            "mission_id": self._mission_id
        })
        # Also broadcast via WebSocket for frontend
        if self._broadcast_fn:
            try:
                # Compute current_task_desc from first task in the graph
                current_task_desc = ''
                if self.current_graph and self.current_context:
                    task_ids = list(self.current_graph.tasks.keys())
                    if task_ids:
                        first_task = self.current_graph.tasks[task_ids[0]]
                        current_task_desc = first_task.params.get('name', first_task.task_id)

                # Compute graph stats from context
                graph_completed = 0
                graph_total = 0
                if self.current_context:
                    graph_completed = sum(1 for s in self.current_context.task_status.values() if s in [TaskState.SUCCESS, TaskState.FAILED])
                    graph_total = sum(1 for s in self.current_context.task_status.values() if s != TaskState.SKIPPED)

                await self._broadcast_fn({
                    "type": "task_state_changed",
                    "task_id": self._task_context.task_id if self._task_context else None,
                    "state": self._task_state.value,
                    "progress": self._current_progress,
                    "graph_id": self.current_graph.graph_id if self.current_graph else None,
                    "session_id": getattr(self.current_executor, "_session_id", None) if self.current_executor else None,
                    "current_task_desc": current_task_desc,
                    "graph_completed": graph_completed,
                    "graph_total": graph_total,
                    "mission_id": self._mission_id
                })
            except Exception:
                pass


    # ================== 任务可视化广播（WebSocket -> 前端 DAG） ==================
    def _broadcast_graph_structure(self, graph):
        """每当新图开始执行时，将图结构（节点+边）推送给前端"""
        if self._broadcast_fn is None:
            return
        try:
            tasks = [
                {"id": t.task_id, "type": t.type.value, "name": t.params.get("name", t.task_id)}
                for t in graph.tasks.values()
            ]
            edges = [
                {"source": e.source, "target": e.target, "type": e.type.value}
                for e in graph.edges
            ]
            data = {"type": "graph_structure", "payload": {
                "graph_id": graph.graph_id,
                "tasks": tasks,
                "edges": edges,
            }}
            try:
                asyncio.create_task(self._broadcast_fn(data))
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Broadcast graph structure failed: {e} (tasks_type={type(graph.tasks).__name__ if hasattr(graph, 'tasks') else 'N/A'}, graph_type={type(graph).__name__})")


    async def _publish_node_status(self):
        """广播每个任务节点的当前状态给前端"""
        if self._broadcast_fn is None or self.current_context is None:
            return
        try:
            status_map = {
                tid: s.value
                for tid, s in self.current_context.task_status.items()
            }
            data = {"type": "task_node_status", "payload": {
                "graph_id": self.current_graph.graph_id if self.current_graph else "",
                "task_status_map": status_map,
                "graph_completed": sum(1 for s in self.current_context.task_status.values() if s in [TaskState.SUCCESS, TaskState.FAILED]) if self.current_context else 0,
                "graph_total": sum(1 for s in self.current_context.task_status.values() if s != TaskState.SKIPPED) if self.current_context else 0,
            }}
            try:
                await self._broadcast_fn(data)
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Publish node status failed: {e}")

    # ================== 原有方法保持兼容（略作调整） ==================
    async def _save_graph_state(self, graph_id: str, graph: TaskGraph, context: GraphContext):
        data = {"graph": graph.to_dict(), "context": context.to_dict()}
        await self.storage.save(graph_id, data)

    async def _restore_graph(self, graph_id: str) -> Optional[tuple[TaskGraph, GraphContext]]:
        data = await self.storage.load(graph_id)
        if not data:
            return None
        graph = TaskGraph.from_dict(data["graph"])
        ctx = GraphContext.from_dict(data["context"], graph)
        return graph, ctx

    async def _restore_pending_graphs(self):
        pending = await self.storage.list_pending()
        for graph_id in pending:
            restored = await self._restore_graph(graph_id)
            if restored:
                graph, ctx = restored
                logger.info(f"Restoring graph {graph_id} with {len(graph.tasks)} tasks")
                executor = GraphExecutor(
                    graph=graph,
                    event_router=self.event_router,
                    context=ctx,
                    condition_checker=self._condition_checker,
                )
                # 追踪恢复的 executor 和 graph，确保后续 power_on / stop 能找到并停掉它
                self.current_graph = graph
                self.current_context = ctx
                self.current_executor = executor
                self._task_state = TaskState.RUNNING
                self._broadcast_graph_structure(graph)
                asyncio.create_task(self._run_graph(executor, self.dispatcher.dispatch, graph_id))

    async def _run_graph(self, executor: GraphExecutor, execute_callback, graph_id: str):
        self._task_versions.clear()
        try:
            await executor.run(execute_callback)
            await executor.wait_completion()
            await self.storage.delete(graph_id)
            logger.info(f"Graph {graph_id} finished and storage cleaned")
        except Exception as e:
            logger.exception(f"Graph execution failed: {e}")

    # Runtime 事件处理（更新进度 + 记录 mission task nodes）
    async def _on_runtime_task_started(self, event: Event):
        task_id = event.task_id
        if self._mission_id:
            task_type = event.payload.get("task_type", "")
            asyncio.create_task(self._add_mission_task(task_id, task_type, "running"))
        pass
        await self._publish_node_status()

    async def _on_runtime_task_completed(self, event: Event):
        task_id = event.task_id
        event_version = event.payload.get("version", 0)
        if self._mission_id:
            asyncio.create_task(self._add_mission_task(task_id, "", "success"))
        if self.current_context is None:
            return

        if event_version > self._task_versions.get(task_id, 0):
            self._task_versions[task_id] = event_version
            self.current_context.update_task_status(task_id, TaskState.SUCCESS)
            # 更新当前任务状态为 SUCCESS
            self._task_state = TaskState.SUCCESS
            self._current_progress = self._calculate_progress()
            # 发布任务状态变更消息（状态为 "success"）
            await self._publish_task_state()
            await self.emit_event(
                UIEventType.TASK_PROGRESS.value,
                payload={"feedback": f"Task {task_id} completed", "progress": self._current_progress},
                task_id=task_id
            )
            await self._publish_node_status()
        else:
            logger.debug(f"Ignored stale TASK_COMPLETED event for {task_id}, version {event_version}")

    async def _on_runtime_task_failed(self, event: Event):
        """处理任务失败事件，更新状态并发布 TASK_STATE_CHANGED 消息"""
        task_id = event.task_id
        event_version = event.payload.get("version", 0)
        if self._mission_id:
            error = event.payload.get("error", "")[:200]
            asyncio.create_task(self._add_mission_task(task_id, "", "failed", error))
        if self.current_context is None:
            return

        if event_version > self._task_versions.get(task_id, 0):
            self._task_versions[task_id] = event_version
            self.current_context.update_task_status(task_id, TaskState.FAILED)
            # 更新当前任务状态为 FAILED
            self._task_state = TaskState.FAILED
            # 重新计算整体进度
            self._current_progress = self._calculate_progress()
            # 发布任务状态变更消息（状态为 "failed"）
            await self._publish_task_state()
            # 发送 UI 事件（用于原有前端）
            await self.emit_event(
                UIEventType.TASK_RESULT.value,
                payload={"success": False, "error": event.payload.get("error")},
                task_id=task_id
            )
            await self._publish_node_status()
        else:
            logger.debug(f"Ignored stale TASK_FAILED event for {task_id}, version {event_version}")

    async def _on_runtime_task_started(self, event: Event):
        task_id = event.task_id
        if self._mission_id:
            task_type = event.payload.get("task_type", "")
            asyncio.create_task(self._add_mission_task(task_id, task_type, "running"))
        await self._publish_node_status()

    async def _on_runtime_graph_completed(self, event: Event):
        # 校验 graph_id：忽略不匹配当前图的陈旧事件
        event_graph_id = (event.payload or {}).get("graph_id")
        current_graph_id = self.current_graph.graph_id if self.current_graph else None
        if event_graph_id and current_graph_id and event_graph_id != current_graph_id:
            logger.debug(
                f"Ignoring stale GRAPH_COMPLETED for {event_graph_id}, "
                f"current is {current_graph_id}"
            )
            return
        await self._on_graph_finished()


    async def _on_graph_finished(self):
        # Save task to DB BEFORE clearing executor reference
        self._finish_mission()
        _save_fn = getattr(self, '_save_task_fn', None)
        if _save_fn:
            try:
                cmd = self._original_task_command or ""
                task_type = ""
                success = False
                if self.current_executor:
                    g = self.current_executor.graph
                    task_types = [t.type.value for t in g.tasks.values()]
                    task_type = task_types[0] if task_types else ""
                    success = self.current_executor.context.status == GraphStatus.COMPLETED
                _save_fn(cmd, task_type, 'completed' if success else 'failed')
            except Exception:
                pass

        # 钀涜摑盆蜊 Key (P3) — Fallback: create mission retroactively
        # 钀涜摑盆蜊 Key (P3) — Fallback: create mission retroactively
        if not getattr(self, "_mission_was_created", False) and self._original_task_command:
            try:
                from backend.db.database import get_db_connection
                from backend.db.task_service import create_mission, finish_mission
                fallback_db = get_db_connection()
                try:
                    mid = create_mission(
                        fallback_db, 0, self._original_task_command,
                        getattr(self.current_graph, "graph_id", None) or "fallback",
                        ""
                    )
                    if mid > 0:
                        self._mission_id = mid
                        status = "completed" if success else "failed"
                        coverage = 0.0
                        if self.current_context:
                            coverage = self.current_context.shared_state.get("coverage", 0.0)
                        finish_mission(fallback_db, mid, status, coverage, "")
                        logger.info(f"[MISSION] Fallback mission {mid} created & finished: {status}")
                finally:
                    fallback_db.close()
            except Exception as e:
                logger.warning(f"[MISSION] Fallback mission creation failed: {e}", exc_info=True)

        # Record final outcome BEFORE cleanup
        final_success = False
        if self.current_executor:
            final_success = self.current_executor.context.status == GraphStatus.COMPLETED
            await self.emit_event(UIEventType.TASK_RESULT.value, payload={"success": final_success})

        # Publish final node status while context is still valid
        await self._publish_node_status()

        # Clean up
        self.current_executor = None
        self.current_graph = None
        self.current_context = None
        self.current_planning_result = None
        # 不再手动发送 reset，由 GraphExecutor 的 system.graph_session_reset 事件统一处理
        if self._task_state != TaskState.RECHARGING:
            self._task_state = TaskState.SUCCESS if final_success else TaskState.FAILED
            await self._publish_task_state()
            self._task_state = TaskState.IDLE

    # ── Mission History Recording ──
    def _start_mission(self, command: str, graph, executor):
        """Create mission_history record with graph_id + session_id, and start replay recording."""
        # Reset flag first: _finish_mission clears _mission_id but not this flag
        self._mission_was_created = False
        logger.info(f"[MISSION] _start_mission: cmd={command[:60]}, graph={graph.graph_id}")
        try:
            from backend.db.database import get_db_connection
            from backend.db.task_service import create_mission as _create
            db = get_db_connection()
            try:
                mid = _create(db, 0, command, graph.graph_id,
                                getattr(executor, '_session_id', ''))
                if mid > 0:
                    self._mission_id = mid
                    self._mission_was_created = True
                    logger.info(f"[MISSION] Mission {mid} created: {command[:60]}")
                else:
                    logger.warning(f"[MISSION] create_mission returned {mid}, mission_id not set")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[MISSION] _start_mission failed: {e}", exc_info=True)

        # 启动回放轨迹记录（每秒记录一次位姿+覆盖率）
        if self._mission_id:
            if self._replay_task and not self._replay_task.done():
                self._replay_task.cancel()
            self._replay_task = asyncio.create_task(self._record_replay_loop())

    async def _add_mission_task(self, task_id: str, task_type: str,
                                status: str, error_info: str = ""):
        """Record a task node in the current mission."""
        if not self._mission_id:
            return
        try:
            from backend.db.database import get_db_connection
            from backend.db.task_service import add_task_node
            db = get_db_connection()
            try:
                add_task_node(db, self._mission_id, task_id, task_type,
                                status, error_info)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Add task node failed: {e}")

    def _finish_mission(self):
        """Mark the current mission as completed/failed and stop replay recording."""
        # Stop replay recording
        if self._replay_task and not self._replay_task.done():
            self._replay_task.cancel()
            self._replay_task = None

        if not self._mission_id:
            logger.warning("[MISSION] _finish_mission skipped: no mission_id")
            return
        try:
            from backend.db.database import get_db_connection
            from backend.db.task_service import finish_mission
            status = "completed"
            coverage = 0.0
            error = ""
            if hasattr(self, 'current_context') and self.current_context:
                if self.current_context.status.value == "completed":
                    status = "completed"
                elif self.current_context.status.value == "failed":
                    status = "failed"
                coverage = self.current_context.shared_state.get("coverage", 0.0)
            db = get_db_connection()
            try:
                finish_mission(db, self._mission_id, status, coverage, error)
                logger.info(f"[MISSION] Mission {self._mission_id} finished: status={status}, coverage={coverage:.1f}%")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[MISSION] _finish_mission failed: {e}")
        finally:
            self._mission_id = None

    async def _record_replay_loop(self):
        """后台循环：每秒记录一次当前位姿和覆盖率为回放轨迹点"""
        from backend.db.database import get_db_connection
        from backend.db.task_service import add_replay_point
        logger.info(f"[Replay] Starting recording for mission {self._mission_id}")
        try:
            while self._mission_id:
                await asyncio.sleep(1.0)
                if not self._mission_id:
                    break
                try:
                    pose = self.latest_robot_state.get("pose", {})
                    x = pose.get("x", 0.0)
                    y = pose.get("y", 0.0)
                    theta = pose.get("theta", 0.0)
                    coverage = self.latest_world_model.get("coverage_percent", 0.0)
                    db = get_db_connection()
                    try:
                        add_replay_point(db, self._mission_id, x, y, theta, coverage)
                    finally:
                        db.close()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"[Replay] Record point failed: {e}")
        except asyncio.CancelledError:
            pass
        logger.info(f"[Replay] Recording stopped for mission {self._mission_id}")

    async def _on_world_model(self, msg: Message):
        self.latest_world_model = msg.payload
        await self.emit_event("system.world_model_update", payload=msg.payload)

    async def _on_robot_state(self, msg: Message):
        self.latest_robot_state = msg.payload
        # 提取电源状态并更新内部变量
        power_state = msg.payload.get("power_state")
        if power_state:
            self._power_state = power_state
        if self._get_battery() < 10.5:
            logger.warning("Low battery detected")
            await self.emit_event(UIEventType.TASK_PROGRESS.value, payload={"feedback": "Low battery warning"})
        await self.emit_event("system.robot_state_update", payload=msg.payload)

    def _get_battery(self) -> float:
        return self.latest_robot_state.get("battery", {}).get("voltage", 12.0)

    def _condition_checker(self, task, context: GraphContext) -> bool:
        if task.type.value == "clean_area" and self._get_battery() < 10.8:
            logger.warning(f"Task {task.task_id} blocked: low battery")
            return False
        return True

    def _calculate_progress(self) -> float:
        if not self.current_context:
            return 0.0
        total = len(self.current_context.task_status)
        if total == 0:
            return 0.0
        completed = sum(1 for s in self.current_context.task_status.values() if s in (TaskState.SUCCESS, TaskState.SKIPPED))
        return completed / total

    async def on_heartbeat(self, msg: Message):
        try:
            hb_data = HeartbeatPayload(**msg.payload)
            agent_id = hb_data.agent_id
            self._last_heartbeat[agent_id] = time.time()
            now = time.time()
            # 每 60 秒打印一次心跳汇总
            if now - self._last_heartbeat_log_time > 60.0:
                alive_agents = [aid for aid, ts in self._last_heartbeat.items()
                                if now - ts < self._heartbeat_timeout]
                logger.info(f"Heartbeat status: {len(alive_agents)} agents alive: {alive_agents}")
                self._last_heartbeat_log_time = now
        except Exception as e:
            logger.error(f"Parse heartbeat failed: {e}")

    async def _on_rooms_ready(self, msg: Message):
        data = RoomsReady(**msg.payload)
        self.room_names = data.rooms
        logger.info(f"Received ROOMS_READY: {self.room_names}")

    async def _on_charge_complete_event(self, event: Event):
        """监听回充任务完成或充电模拟完成事件"""
        if event.task_id == "recharge_complete":
            self._charge_complete_event.set()
        elif event.task_id and event.task_id.startswith("recharge_"):
            # 原有的回充图任务完成（导航回充）
            success = event.payload.get("success", False)
            if success:
                self._charge_complete_event.set()

    async def _heartbeat_check_loop(self):
        while self._running:
            now = time.time()
            for agent_id, last_ts in list(self._last_heartbeat.items()):
                if agent_id == self.agent_id:
                    continue
                if now - last_ts > self._heartbeat_timeout:
                    logger.warning(f"Agent [{agent_id}] heartbeat timeout!")
                    del self._last_heartbeat[agent_id]
            await asyncio.sleep(10)

    async def _on_system_event(self, event: Event):
        if event.task_id == "system_power_on":
            logger.info("System powered on, resetting task state")
            self._task_state = TaskState.IDLE
            # 清空可能残留的任务上下文
            self.current_executor = None
            self.current_graph = None
            self._task_context = None
        elif event.task_id == "system_shutdown":
            logger.info("System powered off, cancelling any running task")
            await self._cancel_task()  # 强制取消任务

