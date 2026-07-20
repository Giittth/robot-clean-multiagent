"""
执行智能体

职责：
    - 接收 EXECUTION 指令（线速度+角速度），记录目标速度，不进行位姿积分
    - 接收 EXECUTION_CONTROL 指令（高层控制如暂停/恢复/停止），执行相应动作
    - 订阅 SIMULATION_STATE 获取真实位姿和实际速度（唯一来源）
    - 定期发布 ROBOT_STATE 消息（供 WorldModelAgent 和 UI）
    - 当任务完成时，通过 EventRouter 发送 ui.task_result 事件

会话管理：
    - 通过 system.graph_session_reset 事件响应图会话重置
    - 提供统一的内部重置方法 _reset_internal_state()，确保所有运行时状态被清空

电源管理：
    - 支持 RobotPowerState 状态机（OFF, BOOTING, IDLE, WORKING, CHARGING, PAUSED, EMERGENCY_STOP）
    - 根据电源状态自动调整电池充放电速率
    - 提供开机/关机控制命令
"""

import asyncio
import time
from typing import Optional

from backend.agents.implementations.base_agent import BaseAgent
from backend.agents.schemas.agent_messages import (
    ExecutionCommand, ControlMode, RobotStateMessage,
    ControllerState, ExecutionResult, ExecutionProgressPayload, ExecutionResultPayload,
    SimulationStateMessage, Velocity
)
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.models.physics.robot_state import Pose, RobotPowerState
from backend.agents.core.event.event_router import EventRouter
from backend.agents.core.event.event_types import UIEventType, Event
from backend.hardware.base import RobotDriver, RobotState as DriverState
from backend.utils.logger_handler import logger


class ExecutionAgent(BaseAgent):
    def __init__(self, agent_id: str, agent_type: str, message_bus, registry,
                 event_router: EventRouter, robot_driver: Optional[RobotDriver] = None):
        """
        初始化执行智能体。
        :param event_router: 统一事件路由器，用于发送任务进度/结果事件（UI 事件）
        """
        super().__init__(agent_id, agent_type, message_bus, registry, event_router=event_router)

        # ----- 状态变量（与发布的 ROBOT_STATE 对应）-----
        self.current_pose = Pose(x=0.0, y=0.0, theta=0.0)   # 当前位姿（来自 SIMULATION_STATE）
        self.current_linear_vel = 0.0      # 实际线速度 (m/s)（来自 SIMULATION_STATE）
        self.current_angular_vel = 0.0     # 实际角速度 (rad/s)（来自 SIMULATION_STATE）
        self.target_linear = 0.0           # 目标线速度（来自 EXECUTION 指令）
        self.target_angular = 0.0          # 目标角速度（来自 EXECUTION 指令）
        self.controller_state = ControllerState.RUNNING
        self.execution_result = ExecutionResult.IDLE
        self.battery_voltage = 12.0        # 电池电压 (V)
        self.battery_percent = 100         # 电池百分比 (%)
        self.battery_charging = False      # 是否充电中
        self.collision = False             # 碰撞标志（来自 SIMULATION_STATE）

        # ----- 物理参数（与仿真环境保持一致）-----
        self._wheel_base = 0.3             # 轮距 (米)（仅用于可能的转换，不再用于积分）

        # ----- 生命周期与任务控制 -----
        self._running = True
        self._state_report_task: Optional[asyncio.Task] = None
        self._idle_timeout = 1.0           # 无指令后多久切为 IDLE (秒)
        self._last_cmd_time = time.monotonic()   # 最后收到指令的时间

        # ----- 控制指令标志（用于暂停/恢复）-----
        self._paused = False               # 是否处于暂停状态
        self._pause_event = asyncio.Event()
        self._pause_event.set()            # 初始为运行状态
        self._emergency_stopped = False    # 急停标志，一旦设置，忽略所有后续指令（除非 reset）

        # ----- 当前任务标识（用于发送结果事件）-----
        self.current_task_id: Optional[str] = None
        self._static_obstacles: list = []
        self._charging_task: Optional[asyncio.Task] = None
        self._robot_driver = robot_driver
        self._driver_poll_task: Optional[asyncio.Task] = None      # 充电过程

        # ========== 电源管理 ==========
        self.power_state = RobotPowerState.OFF          # 初始状态为关机
        self.idle_discharge_rate = 0.0001              # 0.006 V/min （极慢）
        self.working_discharge_rate = 0.01             # 0.6 V/min
        self.charging_rate = 0.02                      # 1.2 V/min
        self._discharge_task: Optional[asyncio.Task] = None

    # ================== 内部状态重置（统一入口） ==================
    def _reset_internal_state(self):
        """
        重置所有运行时状态（保留生命周期标志如 _running）。
        供会话重置和 reset 控制指令调用。
        """
        if self._charging_task and not self._charging_task.done():
            self._charging_task.cancel()
            self._charging_task = None
        self._emergency_stopped = False
        self._paused = False
        self._pause_event.set()
        self.current_task_id = None
        self.execution_result = ExecutionResult.IDLE
        self.target_linear = 0.0
        self.target_angular = 0.0
        self._last_cmd_time = time.monotonic()
        # 注意：不重置 current_pose、current_linear_vel 等物理状态，它们由仿真持续更新

    def _update_power_state(self):
        """根据内部标志更新电源状态（不涉及 OFF/BOOTING）"""
        if self.power_state == RobotPowerState.OFF:
            return
        if self._emergency_stopped:
            self.power_state = RobotPowerState.EMERGENCY_STOP
        elif self._charging_task and not self._charging_task.done():
            self.power_state = RobotPowerState.CHARGING
        elif self._paused:
            self.power_state = RobotPowerState.PAUSED
        elif self.execution_result == ExecutionResult.MOVING:
            self.power_state = RobotPowerState.WORKING
        else:
            self.power_state = RobotPowerState.IDLE

    # ================== 生命周期 ==================
    async def on_start(self):
        """订阅运动命令、控制指令和仿真状态消息"""
        await self.subscribe(MessageType.EXECUTION, self.handle_execution)
        await self.subscribe(MessageType.EXECUTION_CONTROL, self.handle_control)
        await self.subscribe(MessageType.SIMULATION_STATE, self._on_simulation_state)
        self._state_report_task = asyncio.create_task(self._periodic_state_report())
        self._discharge_task = asyncio.create_task(self._battery_discharge_loop())
        # 统一使用 system.graph_session_reset 事件（由 GraphExecutor 发出）
        self.event_router.subscribe("system.graph_session_reset", self._on_reset)

    async def on_stop(self):
        """停止状态报告任务，清理资源"""
        self._running = False
        if self._state_report_task:
            self._state_report_task.cancel()
            try:
                await self._state_report_task
            except asyncio.CancelledError:
                pass
        if self._discharge_task:
            self._discharge_task.cancel()
            try:
                await self._discharge_task
            except asyncio.CancelledError:
                pass
        logger.info(f"ExecutionAgent {self.agent_id} stopped")

    # ================== 消息处理 ==================
    async def handle_execution(self, msg: Message):
        """
        处理运动命令（来自 NavigationAgent 或 TaskDispatcher）。
        仅记录目标速度，更新执行状态，不进行位姿积分。
        """
        try:
            # 如果电源状态为 OFF，忽略所有执行指令
            if self.power_state == RobotPowerState.OFF:
                logger.debug("ExecutionAgent is OFF, ignoring EXECUTION command")
                return

            # 如果处于急停状态，忽略所有指令
            if self._emergency_stopped:
                logger.debug("ExecutionAgent in emergency stop, ignoring EXECUTION command")
                return

            if self._paused:
                logger.debug("ExecutionAgent paused, ignoring EXECUTION command")
                return

            payload = msg.payload.copy()
            # 缺字段直接给默认空速度
            if "target_velocity" not in payload:
                payload["target_velocity"] = {"linear": 0.0, "angular": 0.0}
            cmd = ExecutionCommand(**payload)

            # 记录任务ID（如果存在）
            if hasattr(cmd, 'task_id') and cmd.task_id:
                self.current_task_id = cmd.task_id

            # 停止模式
            if cmd.control_mode == ControlMode.STOP:
                self.target_linear = 0.0
                self.target_angular = 0.0
                self.execution_result = ExecutionResult.IDLE
                self._update_power_state()
                if self.current_task_id:
                    await self._send_task_result(
                        self.current_task_id,
                        success=True,
                        cleaned_area=0.0,
                        coverage_percent=0.0,
                        duration=0.0
                    )
                    self.current_task_id = None
                logger.info("Stop command received, robot halted")
                return

            # 获取目标速度与持续时间
            target_linear = cmd.target_velocity.linear
            target_angular = cmd.target_velocity.angular
            duration = cmd.duration

            self.target_linear = target_linear
            self.target_angular = target_angular

            # 更新执行状态
            if abs(target_linear) > 0.01 or abs(target_angular) > 0.01:
                self.execution_result = ExecutionResult.MOVING
            else:
                self.execution_result = ExecutionResult.IDLE
            self._update_power_state()
            self._last_cmd_time = time.monotonic()
            # 如果存在 RobotDriver，将速度指令转发到驱动层
            if self._robot_driver and (abs(target_linear) > 0.01 or abs(target_angular) > 0.01):
                try:
                    await self._robot_driver.send_velocity(target_linear, target_angular, duration)
                except Exception as e:
                    logger.error(f"Driver send_velocity failed: {e}")

        except Exception as e:
            logger.error(f"Failed to process EXECUTION command: {str(e)}", exc_info=True)

    async def handle_control(self, msg: Message):
        """
        处理高层控制命令（来自 SupervisorAgent）
        支持命令: pause, resume, stop, emergency_stop, reset, power_on, power_off, charge_start
        """
        try:
            command = msg.payload.get("command")
            if command == "pause":
                self._paused = True
                self._pause_event.clear()
                await self._send_zero_velocity()
                self._update_power_state()
                # 添加日志：打印更新后的电源状态
                logger.info("ExecutionAgent paused")
                if self.current_task_id:
                    await self._send_task_progress(
                        self.current_task_id, status="PAUSED", progress=0.0,
                        brush_speed=0, suction_power=0.0, cleaned_area=0.0,
                        message="Execution paused"
                    )

            elif command == "resume":
                self._paused = False
                self._pause_event.set()
                self._update_power_state()
                logger.info("ExecutionAgent resumed")
                if self.current_task_id:
                    await self._send_task_progress(
                        self.current_task_id, status="RUNNING", progress=0.0,
                        brush_speed=0, suction_power=0.0, cleaned_area=0.0,
                        message="Execution resumed"
                    )

            elif command == "stop":
                self._paused = False
                self._pause_event.set()
                if self._robot_driver:
                    await self._robot_driver.stop()
                await self._send_zero_velocity()
                self.target_linear = 0.0
                self.target_angular = 0.0
                self.execution_result = ExecutionResult.IDLE
                self._update_power_state()
                if self.current_task_id:
                    await self._send_task_result(
                        self.current_task_id, success=False,
                        cleaned_area=0.0, coverage_percent=0.0, duration=0.0
                    )
                    self.current_task_id = None
                logger.info("ExecutionAgent stopped by control command")

            elif command == "emergency_stop":
                # 急停：设置永久标志，忽略所有后续执行指令，立即停车
                self._emergency_stopped = True
                self._paused = True
                self._pause_event.clear()
                await self._send_zero_velocity()
                self.target_linear = 0.0
                self.target_angular = 0.0
                self.execution_result = ExecutionResult.IDLE
                self._update_power_state()
                if self.current_task_id:
                    await self._send_task_result(
                        self.current_task_id, success=False,
                        cleaned_area=0.0, coverage_percent=0.0, duration=0.0
                    )
                    self.current_task_id = None
                logger.warning("ExecutionAgent emergency stopped")

            elif command == "reset":
                # 无条件清除所有阻塞标志，确保 Agent 回到正常运行状态
                # 清除急停标志、暂停标志、任务ID等
                self._reset_internal_state()
                # 关键：更新电源状态（从 EMERGENCY_STOP 变为 IDLE）
                self._update_power_state()
                logger.info("ExecutionAgent reset via control command")

            elif command == "charge_start":
                target_voltage = msg.payload.get("target_voltage", 12.0)
                duration = msg.payload.get("duration", 5.0)
                # 设置电源状态为充电
                self.power_state = RobotPowerState.CHARGING
                await self.start_charging(target_voltage, duration)

            elif command == "power_on":
                if self.power_state == RobotPowerState.OFF:
                    self.power_state = RobotPowerState.BOOTING
                    logger.info("Powering on...")
                    await asyncio.sleep(0.5)  # 模拟启动过程
                    self.power_state = RobotPowerState.IDLE
                    # 可选：发送开机完成事件，让 Supervisor 重置状态
                    await self.emit_event(UIEventType.TASK_RESULT.value, task_id="system_power_on", payload={"success": True})
                    logger.info("Robot powered on, state IDLE")
                else:
                    logger.warning("Robot already on or not in OFF state")

            elif command == "power_off":
                if self.power_state in (RobotPowerState.IDLE, RobotPowerState.PAUSED, RobotPowerState.EMERGENCY_STOP):
                    # 停车
                    await self._send_zero_velocity()
                    self.target_linear = 0.0
                    self.target_angular = 0.0
                    self.execution_result = ExecutionResult.IDLE
                    # 取消当前任务（如果有）
                    if self.current_task_id:
                        await self._send_task_result(self.current_task_id, success=False,
                                                     cleaned_area=0.0, coverage_percent=0.0, duration=0.0)
                        self.current_task_id = None
                    self.power_state = RobotPowerState.OFF
                    # 发送关机事件，让 Supervisor 清理任务状态
                    await self.emit_event(UIEventType.TASK_RESULT.value, task_id="system_shutdown",
                                          payload={"success": True})
                    logger.info("Robot powered off")
                else:
                    logger.warning("Cannot power off in current state")

            else:
                logger.warning(f"Unknown control command: {command}")

        except Exception as e:
            logger.error(f"Failed to process EXECUTION_CONTROL: {e}", exc_info=True)

    async def _send_zero_velocity(self):
        """发送零速度命令，使机器人停车"""
        exec_cmd = ExecutionCommand(
            timestamp=time.monotonic(),
            target_velocity=Velocity(linear=0.0, angular=0.0),
            duration=0.1,
            control_mode=ControlMode.STOP
        )
        await self.publish(MessageType.EXECUTION, payload=exec_cmd.model_dump(), priority=Priority.HIGH)

    async def _on_simulation_state(self, msg: Message):
        """
        接收仿真环境发布的真实世界状态，更新当前位姿、实际速度和碰撞标志。
        这是位姿的唯一来源，彻底消除双重积分。
        """
        if msg.source != "simulation":
            logger.debug(f"Ignoring SIMULATION_STATE from {msg.source}")
            return

        try:
            safe_msg = msg.model_copy(deep=True)
            raw = safe_msg.payload.copy()
            full_payload = {
                "robot_id": raw.get("robot_id", "robot_001"),
                "timestamp": raw.get("timestamp", 0.0),
                "pose": raw.get("pose", {"x": 0.0, "y": 0.0, "theta": 0.0}),
                "velocity": raw.get("velocity", {"linear": 0.0, "angular": 0.0}),
                "collision": raw.get("collision", False)
            }
            sim_state = SimulationStateMessage(**full_payload)

            self.current_pose = sim_state.pose
            self.current_linear_vel = sim_state.velocity.linear
            self.current_angular_vel = sim_state.velocity.angular
            self.collision = sim_state.collision
            self._static_obstacles = raw.get("obstacles", [])
        except Exception as e:
            logger.error(f"Failed to parse SIMULATION_STATE: {e}, payload: {msg.payload}")
            # 兜底处理
            try:
                self.current_pose = Pose(**msg.payload.get("pose", {"x": 0.0, "y": 0.0, "theta": 0.0}))
                self.current_linear_vel = msg.payload.get("velocity", {}).get("linear", 0.0)
                self.current_angular_vel = msg.payload.get("velocity", {}).get("angular", 0.0)
                self.collision = msg.payload.get("collision", False)
                self._static_obstacles = msg.payload.get("obstacles", [])
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")

    # ================== 电池模型（电源状态驱动） ==================
    async def _battery_discharge_loop(self):
        """后台电池放电/充电循环，根据 power_state 调整电压"""
        while self._running:
            if self.power_state == RobotPowerState.OFF:
                await asyncio.sleep(1)
                continue

            if self.power_state == RobotPowerState.CHARGING:
                # 充电由 _charging_loop 单独处理，此处不干预
                pass
            else:
                # 放电
                if self.power_state == RobotPowerState.WORKING:
                    rate = self.working_discharge_rate
                elif self.power_state in (RobotPowerState.IDLE, RobotPowerState.PAUSED, RobotPowerState.EMERGENCY_STOP):
                    rate = self.idle_discharge_rate
                else:
                    rate = 0.0

                if rate > 0:
                    self.battery_voltage = max(10.0, self.battery_voltage - rate)
                    self.battery_percent = max(0.0, min(100.0, (self.battery_voltage - 10.0) / 2.0 * 100.0))

            await asyncio.sleep(1)  # 每秒更新一次

    async def start_charging(self, target_voltage: float = 12.0, duration: float = 8.0):
        """
        开始模拟充电过程。
        :param target_voltage: 目标电压 (V)
        :param duration: 充电总时长 (秒)
        """
        if self._charging_task and not self._charging_task.done():
            logger.warning("Charging already in progress")
            return
        self.power_state = RobotPowerState.CHARGING
        self._charging_task = asyncio.create_task(self._charging_loop(target_voltage, duration))

    async def _charging_loop(self, target_voltage: float, duration: float):
        """充电循环，逐步增加电池电压（每 0.1 秒更新一次，平滑过渡）"""
        start_voltage = self.battery_voltage
        # 固定每 0.1 秒更新一次，计算步数
        step_time = 0.1
        step_count = max(50, int(duration / step_time))  # 至少 50 步
        step_voltage = (target_voltage - start_voltage) / step_count

        for i in range(step_count):
            if not self._running or self._emergency_stopped:
                logger.info("Charging interrupted")
                break
            # 更新电池（更精细的步进）
            new_voltage = self.battery_voltage + step_voltage
            self.battery_voltage = min(target_voltage, new_voltage)
            self.battery_percent = max(0.0, min(100.0, (self.battery_voltage - 10.0) / 2.0 * 100.0))

            # 发送进度事件（保留三位小数，前端可显示更细）
            await self.emit_event(
                UIEventType.TASK_PROGRESS.value,
                task_id="recharge",
                payload={
                    "phase": "charging",
                    "progress": (i + 1) / step_count,
                    "voltage": round(self.battery_voltage, 3),
                    "percent": round(self.battery_percent, 2)
                }
            )
            await asyncio.sleep(step_time)

        # 确保最终达到满电
        self.battery_voltage = target_voltage
        self.battery_percent = 100.0
        logger.info(f"Charging completed, battery at {self.battery_voltage:.2f}V")
        await self.emit_event(
            UIEventType.TASK_RESULT.value,
            task_id="recharge_complete",
            payload={"success": True, "phase": "charging", "final_voltage": self.battery_voltage}
        )
        self._charging_task = None
        # 充电完成后根据当前状态更新电源状态
        self._update_power_state()

    # ================== 周期性状态报告 ==================
    async def _driver_state_poll(self):
        """?????obotDriver ?????????????????????????        """
        try:
            while self._running and self._robot_driver:
                state = await self._robot_driver.get_state()
                self.current_pose = state.pose
                self.current_linear_vel = state.linear_velocity
                self.current_angular_vel = state.angular_velocity
                self.collision = state.collision
                self.battery_voltage = state.battery_voltage
                self.battery_percent = state.battery_percent
                self.battery_charging = state.battery_charging
                self._static_obstacles = state.obstacles
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Driver state poll error: {e}", exc_info=True)

    async def _periodic_state_report(self):
        """定期（10Hz）发布 ROBOT_STATE 消息，供 WorldModelAgent 和 UI 使用"""
        logger.info("State report task started")
        try:
            while self._running:
                await asyncio.sleep(0.1)
                try:
                    now = time.monotonic()
                    if self.execution_result == ExecutionResult.MOVING and (now - self._last_cmd_time) > self._idle_timeout:
                        self.execution_result = ExecutionResult.IDLE
                        self.target_linear = 0.0
                        self.target_angular = 0.0
                        self._update_power_state()

                    robot_state_msg = RobotStateMessage(
                        timestamp=time.monotonic(),
                        pose=self.current_pose,
                        velocity=Velocity(
                            linear=round(self.current_linear_vel, 3),
                            angular=round(self.current_angular_vel, 3)
                        ),
                        target_velocity=Velocity(
                            linear=round(self.target_linear, 3),
                            angular=round(self.target_angular, 3)
                        ),
                        controller_state=ControllerState.RUNNING,
                        execution_result=ExecutionResult(self.execution_result),
                        battery={
                            "voltage": round(self.battery_voltage, 1),
                            "percent": round(self.battery_percent, 1),
                            "charging": self.battery_charging
                        },
                        collision=self.collision
                    )
                    payload = robot_state_msg.model_dump()
                    payload["obstacles"] = self._static_obstacles
                    payload["power_state"] = self.power_state.value  # 新增电源状态

                    await self.publish(MessageType.ROBOT_STATE, payload=payload, priority=Priority.NORMAL)
                except Exception as e:
                    logger.warning(f"State report failed: {str(e)}")
        except asyncio.CancelledError:
            logger.info("State report task cancelled")
        except Exception as e:
            logger.error(f"State report task error: {e}")

    # ================== 会话重置事件处理 ==================
    async def _on_reset(self, event: Event):
        """
        响应 system.graph_session_reset 事件，重置所有运行时状态。
        由 GraphExecutor 在会话结束时发出。
        """
        logger.info("[ExecutionAgent] Received graph session reset signal, resetting state")
        self._reset_internal_state()
        self._update_power_state()
        logger.debug("[ExecutionAgent] Reset complete")

    # ================== 统一事件发送 ==================
    async def _send_task_progress(self, task_id: str, status: str, progress: float,
                                   brush_speed: int, suction_power: float, cleaned_area: float, message: str):
        """
        发送任务进度事件（类型: ui.task_progress）
        """
        payload = ExecutionProgressPayload(
            status=status,
            progress=progress,
            brush_speed=brush_speed,
            suction_power=suction_power,
            cleaned_area=cleaned_area,
            message=message
        )
        await self.emit_event(
            UIEventType.TASK_PROGRESS.value,
            task_id=task_id,
            payload=payload.model_dump()
        )

    async def _send_task_result(self, task_id: str, success: bool, cleaned_area: float,
                                coverage_percent: float, duration: float):
        """
        发送任务最终结果事件（类型: ui.task_result）
        通过校验 current_task_id 防止旧任务结果污染。
        """
        if self.current_task_id != task_id:
            logger.warning(f"Stale task result for {task_id}, current={self.current_task_id}, dropping")
            return
        payload = ExecutionResultPayload(
            success=success,
            cleaned_area=cleaned_area,
            coverage_percent=coverage_percent,
            duration=duration
        )
        await self.emit_event(
            UIEventType.TASK_RESULT.value,
            task_id=task_id,
            payload=payload.model_dump()
        )