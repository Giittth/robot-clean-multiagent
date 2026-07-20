"""
导航智能体：任务驱动的局部导航执行器

    - 订阅 WORLD_MODEL（地图、障碍物、覆盖率）和 NAVIGATION_REQUEST（高层任务）
    - 使用独立的算法模块：
        * CoverageManager：覆盖策略（寻找下一个未覆盖点 / 生成全覆盖路径）
        * GlobalPlanner：全局路径规划（A* + 动态重规划）
        * PurePursuit：路径跟踪（计算控制指令）
    - 发布 EXECUTION（运动控制）和 NAVIGATION（可视化）
    - 通过 EventRouter 发送 ui.task_progress / ui.task_result 事件
"""

import random
import asyncio
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any

from backend.agents.implementations.base_agent import BaseAgent
from backend.agents.schemas.agent_messages import (
    ExecutionCommand, NavigationStatusMessage, NavigationStatus,
    NavigationMode, AvoidanceMode, ControlMode, WorldModelPayload,
    NavigationProgressPayload, NavigationResultPayload, RoomsUpdate,
    NavigationTaskResult   # NEW: 从 agent_messages 导入
)
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.agents.utils.coordinate import CoordinateTransformer
from backend.models.physics.action import Velocity
from backend.models.physics.robot_state import Pose
from backend.models.physics.environment import ObstacleType
from backend.agents.utils.rag_tool import RAGTool
from backend.agents.core.event.event_router import EventRouter
from backend.agents.core.event.event_types import UIEventType, Event
from backend.utils.logger_handler import logger

from backend.agents.decision.navigation.coverage_manager import CoverageManager
from backend.agents.decision.navigation.global_planner import GlobalPlanner
from backend.agents.decision.navigation.pure_pursuit import PurePursuit

# 状态机定义
class NavMode(Enum):
    IDLE = 0
    NAVIGATE_TO_POINT = 1
    NAVIGATE_TO_AREA = 2
    COVERAGE = 3
    RECOVERY = 4
    GO_HOME = 5

@dataclass
class ControlToken:
    task_id: str
    version: int
    cancel_event: asyncio.Event
    created_at: float

class NavigationAgent(BaseAgent):
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        message_bus,
        registry,
        event_router: EventRouter,
        rag_tool: RAGTool,
        map_size: Tuple[int, int] = (100, 100),
        resolution: float = 0.2,
    ):
        super().__init__(agent_id, agent_type, message_bus, registry, event_router=event_router)

        # ================== 地图与坐标 ==================
        self.map_rows, self.map_cols = map_size
        self.resolution = resolution
        self.origin_offset = self.map_rows // 2
        self.coord_trans = CoordinateTransformer(
            resolution=self.resolution,
            origin_offset=self.origin_offset
        )

        # ================== 机器人状态 ==================
        self.current_pose = Pose(x=0.0, y=0.0, theta=0.0)
        self._stuck_counter = 0
        self.position_history = []      # 用于卡死检测
        self.recovery_mode = False
        self.recovery_steps = 0

        # ================== 导航参数 ==================
        self.MAX_LINEAR_SPEED = 0.5
        self.MAX_ANGULAR_SPEED = 0.8
        self.SAFE_DISTANCE = 0.35
        self.GOAL_REACH_THRESHOLD = 0.8
        self._feedback_interval = 0.5
        self.WAYPOINT_THRESHOLD = 0.35       # 中间路径点到达阈值
        self.FINAL_GOAL_THRESHOLD = 0.35     # 最终目标到达阈值

        # ================== 路径跟踪 ==================
        self.current_path: List[Pose] = []      # 世界坐标路径点
        self.current_path_index = 0
        self.external_task_id: Optional[str] = None
        self._path_following_task: Optional[asyncio.Task] = None

        # ================== 地图数据 ==================
        self.obstacle_grid = [[0 for _ in range(self.map_cols)] for _ in range(self.map_rows)]
        self.coverage_grid = [[0 for _ in range(self.map_cols)] for _ in range(self.map_rows)]  # 覆盖地图，由 WorldModelAgent 更新

        # ================== 算法模块实例化 ==================
        # 覆盖策略：负责决定[扫哪里]
        self.coverage_mgr = CoverageManager(self.coord_trans, sweep_width=0.6)
        # 全局规划：负责[怎么去]
        self.global_planner = GlobalPlanner(self.coord_trans)
        # 路径跟踪：负责[怎么走]
        self.tracker = PurePursuit(
            max_linear=self.MAX_LINEAR_SPEED,
            max_angular=self.MAX_ANGULAR_SPEED,
            lookahead_dist=0.8,
            goal_thresh=self.GOAL_REACH_THRESHOLD
        )

        # ================== 状态机 ==================
        self.mode = NavMode.IDLE
        self.coverage_path = []          # 预先生成的全覆盖路径点（可选）
        self.coverage_index = 0

        # RAG 工具
        self.rag = rag_tool

        # 控制权管理
        self._last_nav_publish = 0.0
        self.control_owner = "IDLE"   # 可选值: "IDLE", "TASK_GRAPH", "RECOVERY"

        self.rooms_cache = {}  # name -> room data dict
        self._last_replan_time = 0.0  # 动态重规划冷却时间戳
        self.current_linear_vel = 0.0   # 当前实际线速度
        self.current_angular_vel = 0.0  # 可选，也可用于动态前瞻

        # 控制相关属性（用于响应 Supervisor 的暂停/恢复指令）
        self._paused = False                     # 是否处于暂停状态
        self._pause_event = asyncio.Event()      # 暂停事件，用于阻塞路径跟踪循环
        self._pause_event.set()                  # 初始为运行状态

        self._emergency_stopped = False  # 急停标志
        self.current_graph_id: Optional[str] = None  # 当前执行的任务图 ID
        self.current_session_id: Optional[str] = None  # 当前执行的会话 ID

        self._nav_generation = 0                # 加入 nav_generation 机制

        self.power_state = "OFF"                 # 电源状态，从 ExecutionAgent 同步

        self._control_version = 0
        self._current_token = None
        self._path_following_task = None
        # NEW: 记录最后完成的任务版本，用于调试
        self._last_completed_version: Optional[int] = None

    # ================== 统一状态重置（同步部分） ==================
    def _reset_navigation_state(self):
        """
        重置所有导航状态（同步部分，不包含任务取消的异步等待）。
        用于会话重置和控制命令 reset。
        """
        self.external_task_id = None
        self.control_owner = "IDLE"
        self._paused = False
        self._pause_event.set()
        self._emergency_stopped = False
        self.current_graph_id = None
        self.current_session_id = None
        self.current_path = []
        self.current_path_index = 0
        self.coverage_path = []
        self.coverage_index = 0
        self.mode = NavMode.IDLE
        self._nav_generation += 1
        logger.debug(f"[NavigationAgent] Internal state reset, generation={self._nav_generation}")

    # ================== 生命周期 ==================
    async def on_start(self):
        """订阅世界模型、机器人状态和导航请求"""
        await self.subscribe(MessageType.WORLD_MODEL, self.handle_world_model)
        await self.subscribe(MessageType.ROBOT_STATE, self._on_robot_state)
        await self.subscribe(MessageType.NAVIGATION_REQUEST, self.handle_navigation_request)
        await self.subscribe(MessageType.ROOMS_UPDATE, self._on_rooms_update)
        # 订阅导航控制消息（暂停/恢复/停止/急停）
        await self.subscribe(MessageType.NAVIGATION_CONTROL, self._handle_control)
        # 新增订阅 system.graph_session_reset
        self.event_router.subscribe("system.graph_session_reset", self._on_graph_reset)

    async def on_stop(self):
        if self._path_following_task and not self._path_following_task.done():
            self._path_following_task.cancel()
        logger.info(f"NavigationAgent {self.agent_id} stopped")

    # ================== 控制权管理 ==================
    def _acquire_token(self, task_id: str) -> ControlToken:
        """
        创建并获取一个新的控制令牌（Token），用于表示当前导航任务对机器人的控制权。

        调用时机：在 handle_navigation_request 接收到新任务且准备执行时调用。
        作用：
            - 递增版本号 _control_version，确保每个任务的 token 版本唯一且单调递增。
            - 创建 ControlToken 对象，包含任务 ID、版本号、取消事件和创建时间。
            - 将 token 赋值给 self._current_token，并设置 control_owner 和 external_task_id。
        注意事项：
            - 该函数是唯一允许对 self._current_token 赋正值的地方。
            - 版本号用于后续抢占检查（新任务版本 > 旧任务版本时，旧任务失效）。
            - 调用后，任务应在包装器（如 _run_navigation_task）中确保 finally 释放 token。
        """
        self._control_version += 1
        token = ControlToken(
            task_id=task_id,
            version=self._control_version,
            cancel_event=asyncio.Event(),
            created_at=time.time()
        )
        self._current_token = token
        self.control_owner = "TASK_GRAPH"
        self.external_task_id = task_id
        logger.info(f"[Token] Acquired v{token.version} for task {task_id}")
        return token

    def _release_token(self, version: int):
        """
        正常释放一个控制令牌。仅当当前 token 的版本与传入版本一致时才会执行释放。

        调用时机：顶层导航任务（导航、覆盖清扫等）正常结束时，在 finally 块中调用。
        作用：
            - 清空 _current_token、control_owner、external_task_id。
            - 将 mode 重置为 NavMode.IDLE。
            - 记录最后完成的任务版本，便于调试。
        注意事项：
            - 版本检查可防止旧任务的 finally 误释放已被新任务抢占的 token。
            - 该函数是正常任务路径中唯一的 token 释放出口。
            - 不负责停止机器人运动（运动停止由路径跟踪自然结束或上层处理）。
        """
        if self._current_token and self._current_token.version == version:
            logger.info(f"[Token] Release v{version}")
            self._last_completed_version = version
            self._current_token = None
            self.control_owner = "IDLE"
            self.external_task_id = None
            self.mode = NavMode.IDLE

    def _force_clear_token(self):
        """
        强制清除当前控制令牌，不检查版本号。

        调用时机：
            - 任务异常失败（如规划无路径、参数错误）且无需正常释放时。
            - 收到 stop / emergency_stop / graph reset 等强制终止指令时。
        作用：
            - 无条件清空 _current_token、control_owner、external_task_id。
            - 强制将 mode 置为 IDLE，防止状态不一致。
        注意事项：
            - 该函数不依赖版本号，用于紧急清理。
            - 调用后，任何正在进行的路径跟踪任务应已被取消或已结束。
            - 不会主动取消任务（调用方需先取消 _path_following_task）。
        """
        if self._current_token:
            logger.info(f"[Token] Force clear v{self._current_token.version}")
        self._current_token = None
        self.control_owner = "IDLE"
        self.external_task_id = None
        self.mode = NavMode.IDLE

    # ================== 导航任务 ==================
    async def _run_navigation_task(self, token: ControlToken, path: List[Pose],
                                   final_goal: Pose) -> NavigationTaskResult:
        # 创建导航包装器
        my_version = token.version
        try:
            return await self._follow_path(token, path, final_goal=final_goal)
        finally:
            self._release_token(my_version)

    # ================== 消息处理 ==================
    async def handle_world_model(self, msg: Message):
        """更新障碍物地图，世界模型元数据仅作参考"""
        try:
            world = WorldModelPayload(**msg.payload)
            if world.obstacles:
                self._update_obstacle_map_from_world(world.obstacles)
            # NOTE: 不直接覆盖 self.coverage_grid，因为 WorldModelAgent 使用
            # 不同的分辨率（200x200 @ 0.1m vs 100x100 @ 0.2m）。
            # NavigationAgent 自己通过 coverage_mgr.update_coverage() 维护覆盖栅格，
            # 并通过 COVERAGE_UPDATE 消息广播给前端。
        except Exception as e:
            logger.error(f"handle_world_model error: {e}", exc_info=True)

    async def _on_robot_state(self, msg: Message):
        """获取最新机器人位姿、速度及电源状态"""
        try:
            # 1. 更新位姿
            pose_data = msg.payload.get("pose", {})
            raw_theta = pose_data.get("theta", self.current_pose.theta)
            self.current_pose = Pose(
                x=pose_data.get("x", self.current_pose.x),
                y=pose_data.get("y", self.current_pose.y),
                theta=math.atan2(math.sin(raw_theta), math.cos(raw_theta))
            )
            # 2. 更新速度
            velocity = msg.payload.get("velocity", {})
            self.current_linear_vel = velocity.get("linear", 0.0)
            self.current_angular_vel = velocity.get("angular", 0.0)
            # 3. 更新电源状态
            power_state = msg.payload.get("power_state")
            if power_state:
                self.power_state = power_state
            # 4. 清扫模式下更新覆盖栅格 + 定期发布到前端
            if self.mode == NavMode.COVERAGE:
                self.coverage_mgr.update_coverage(
                    self.current_pose, self.coverage_grid)
                # 节流发布（每秒最多一次）
                now = time.time()
                if not hasattr(self, '_last_coverage_publish'):
                    self._last_coverage_publish = 0
                if now - self._last_coverage_publish > 1.0:
                    self._last_coverage_publish = now
                    covered = sum(sum(r) for r in self.coverage_grid)
                    total = self.map_rows * self.map_cols
                    percent = (covered / total) * 100 if total > 0 else 0
                    await self.publish(
                        MessageType.COVERAGE_UPDATE,
                        payload={
                            "grid": self.coverage_grid,
                            "covered": covered,
                            "total": total,
                            "percent": round(percent, 1),
                        },
                        priority=Priority.NORMAL,
                    )
        except Exception as e:
            logger.error(f"_on_robot_state error: {e}")

    # ================== 任务处理 ==================
    async def handle_navigation_request(self, msg: Message):
        """
        处理导航请求，根据任务类型调用不同策略。

        升级点：
            - 使用 ControlToken 管理任务生命周期（版本号 + 独立取消事件）
            - 抢占旧任务时非阻塞（只设置取消事件，不等待）
            - 启动新任务时使用统一包装器（_run_navigation_task / _run_coverage_loop）
            - 失败分支统一调用 _force_clear_token() 清理状态
            - Token 创建与释放完全收敛到专用方法
        """
        # 0. 电源状态检查
        if hasattr(self, 'power_state') and self.power_state not in ('IDLE', 'WORKING'):
            task_id = msg.payload.get("task_id")
            logger.warning(f"Navigation request rejected: power_state={self.power_state}, task_id={task_id}")
            if task_id:
                # 注意：这里没有 token，直接发送失败结果
                await self._send_task_result(task_id, 0, False, False,
                                             {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                             failure_reason="POWER_STATE_REJECT")
            return

        # 1. 解析消息载荷
        payload = msg.payload
        task_id = payload.get("task_id")
        task_type = payload.get("type")
        params = payload.get("params", {})

        # 2. 记录图与会话 ID（用于重置事件校验）
        self.current_graph_id = payload.get("graph_id")
        self.current_session_id = payload.get("session_id")

        # 3. 强制复位运行状态（防御性）
        self._paused = False
        self._pause_event.set()
        self._emergency_stopped = False

        # ========== 4. 抢占旧任务（非阻塞） ==========
        old_task = self._path_following_task
        old_token = self._current_token

        if old_task and not old_task.done():
            logger.info(f"Interrupting previous task (version={old_token.version if old_token else '?'})")
            if old_token:
                old_token.cancel_event.set()  # 唤醒旧任务中的取消等待
            old_task.cancel()  # 取消协程
            asyncio.create_task(self._wait_task_cleanup(old_task, old_token))  # 后台清理
            # 注意：不立即置空 _path_following_task，避免竞态

        # 5. 创建新 token（使用统一获取方法）
        token = self._acquire_token(task_id)

        logger.info(f"Received NAVIGATION_REQUEST: task_id={task_id}, type={task_type}, version={token.version}")
        logger.debug(f"[NavRequest] graph={self.current_graph_id}, session={self.current_session_id}")

        # ========== 6. 根据任务类型分发 ==========
        try:
            if task_type == "navigate_to":
                target = params.get("target")
                if not target:
                    raise ValueError("Missing target in navigate_to")
                target_pose = Pose(
                    x=float(target.get("x", 0.0)),
                    y=float(target.get("y", 0.0)),
                    theta=float(target.get("theta", 0.0))
                )
                self.mode = NavMode.NAVIGATE_TO_POINT
                path = self.global_planner.plan(self.current_pose, target_pose, self.obstacle_grid)
                if not path:
                    logger.warning(f"No path to target {target_pose}")
                    await self._send_task_result(task_id, token.version, False, False,
                                                 {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                                 failure_reason="NO_PATH")
                    self._force_clear_token()
                    return

                # 使用导航包装器
                self._path_following_task = asyncio.create_task(
                    self._run_navigation_task(token, path, target_pose)
                )
                self._path_following_task.add_done_callback(self._on_navigation_task_done)

            elif task_type == "navigate_to_area":
                area_name = params.get("room_id") or params.get("area")
                if not area_name:
                    logger.error("Missing room_id/area in navigate_to_area")
                    await self._send_task_result(task_id, token.version, False, False,
                                                 {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                                 failure_reason="MISSING_AREA")
                    self._force_clear_token()
                    return

                room_data = self._get_room_data(area_name)
                if not room_data:
                    # fallback 坐标
                    fallback_points = {
                        "living_room": (3.0, 3.0),
                        "bedroom": (-3.0, 3.0),
                        "kitchen": (3.0, -3.0),
                        "bathroom": (-3.0, -3.0),
                    }
                    x, y = fallback_points.get(area_name, (0.0, 0.0))
                    target_pose = Pose(x=x, y=y, theta=0.0)
                else:
                    if room_data.get("entry_point"):
                        x, y = room_data["entry_point"]
                    elif room_data.get("center"):
                        x, y = room_data["center"]
                    else:
                        polygon = room_data["polygon"]
                        xs = [p[0] for p in polygon]
                        ys = [p[1] for p in polygon]
                        x, y = sum(xs) / len(xs), sum(ys) / len(ys)
                    target_pose = Pose(x=x, y=y, theta=0.0)

                path = self.global_planner.plan(self.current_pose, target_pose, self.obstacle_grid)
                if not path:
                    await self._send_task_result(task_id, token.version, False, False,
                                                 {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                                 failure_reason="NO_PATH")
                    self._force_clear_token()
                    return

                # 使用导航包装器
                self._path_following_task = asyncio.create_task(
                    self._run_navigation_task(token, path, target_pose)
                )
                self._path_following_task.add_done_callback(self._on_navigation_task_done)

            elif task_type == "clean_area":
                area = params.get("room_id") or params.get("area")
                if not area:
                    logger.error("Missing room_id/area in clean_area")
                    await self._send_task_result(task_id, token.version, False, False,
                                                 {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                                 failure_reason="MISSING_AREA")
                    self._force_clear_token()
                    return

                room_data = self._get_room_data(area)
                if not room_data:
                    logger.warning(f"Room {area} not in cache, fallback to full map coverage")
                    coverage_path = await self._generate_coverage_path(area)
                else:
                    polygon = room_data["polygon"]
                    coverage_path = self.coverage_mgr.generate_lawnmower_path(polygon)

                if not coverage_path:
                    logger.error(f"No coverage path generated for {area}")
                    await self._send_task_result(task_id, token.version, False, False,
                                                 {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                                 failure_reason="NO_COVERAGE_PATH")
                    self._force_clear_token()
                    return

                # 覆盖清扫已使用包装器 _run_coverage_loop
                self.mode = NavMode.COVERAGE
                self._path_following_task = asyncio.create_task(
                    self._run_coverage_loop(token, coverage_path)
                )
                self._path_following_task.add_done_callback(self._on_navigation_task_done)

            elif task_type == "return_to_charge":
                target_pose = Pose(x=0.0, y=0.0, theta=0.0)
                self.mode = NavMode.GO_HOME
                path = self.global_planner.plan(self.current_pose, target_pose, self.obstacle_grid)
                if not path:
                    await self._send_task_result(task_id, token.version, False, False,
                                                 {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                                 failure_reason="NO_PATH")
                    self._force_clear_token()
                    return

                # 使用导航包装器
                self._path_following_task = asyncio.create_task(
                    self._run_navigation_task(token, path, target_pose)
                )
                self._path_following_task.add_done_callback(self._on_navigation_task_done)

            elif task_type == "recover_stuck":
                self.mode = NavMode.RECOVERY
                self._path_following_task = asyncio.create_task(
                    self._run_recovery(token)
                )
                self._path_following_task.add_done_callback(self._on_navigation_task_done)

            else:
                logger.warning(f"Unsupported task type: {task_type}")
                await self._send_task_result(task_id, token.version, False, False,
                                             {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                             failure_reason="UNSUPPORTED_TYPE")
                self._force_clear_token()
                return

        except Exception as e:
            logger.error(f"handle_navigation_request error: {e}", exc_info=True)
            # 如果已经有 token，则强制清理
            if self._current_token and self._current_token.task_id == task_id:
                self._force_clear_token()
            # 发送失败结果
            await self._send_task_result(task_id, 0, False, False,
                                         {"x": self.current_pose.x, "y": self.current_pose.y}, 0.0,
                                         failure_reason=str(e))

    async def _on_rooms_update(self, msg: Message):
        """接收并缓存所有房间的数据"""
        try:
            data = RoomsUpdate(**msg.payload)
            self.rooms_cache = data.rooms
            logger.info(f"NavigationAgent: Cached {len(self.rooms_cache)} rooms: {list(self.rooms_cache.keys())}")
        except Exception as e:
            logger.error(f"Failed to process ROOMS_UPDATE: {e}")

    async def _handle_control(self, msg: Message):
        """
        处理来自 Supervisor 的导航控制指令。
        支持命令: pause, resume, stop, emergency_stop, reset

        升级点：
            - stop / emergency_stop 分支使用 _force_clear_token() 统一清理 token 状态
            - 保留运动停止、任务取消等核心逻辑
        """
        command = msg.payload.get("command")

        if command == "pause":
            if self._emergency_stopped:
                logger.warning("Already in emergency stop, cannot pause")
                return
            if self._paused:
                logger.warning("Already paused")
                return
            self._paused = True
            self._pause_event.clear()
            await self._publish_zero_velocity()
            logger.info("NavigationAgent paused")

        elif command == "resume":
            if self._emergency_stopped:
                logger.warning("In emergency stop, use 'reset' instead of 'resume'")
                return
            if not self._paused:
                logger.warning("Not paused, cannot resume")
                return
            self._paused = False
            self._pause_event.set()
            logger.info("NavigationAgent resumed")

        elif command == "stop":
            # 主动取消当前任务
            if self._current_token:
                self._current_token.cancel_event.set()
            if self._path_following_task and not self._path_following_task.done():
                self._path_following_task.cancel()
                asyncio.create_task(self._wait_task_cleanup(self._path_following_task, self._current_token))
            # 强制清理 token 和控制权状态
            self._force_clear_token()
            # 恢复暂停标志和事件（确保下次任务不被阻塞）
            self._paused = False
            self._pause_event.set()
            await self._publish_zero_velocity()
            logger.info("NavigationAgent stopped")

        elif command == "emergency_stop":
            self._emergency_stopped = True
            self._paused = True
            self._pause_event.clear()
            # 取消当前任务
            if self._current_token:
                self._current_token.cancel_event.set()
            if self._path_following_task and not self._path_following_task.done():
                self._path_following_task.cancel()
                asyncio.create_task(self._wait_task_cleanup(self._path_following_task, self._current_token))
            # 强制清理 token 和控制权状态
            self._force_clear_token()
            # 清空路径缓存
            self.current_path = []
            self.coverage_path = []
            # 发送零速度指令
            await self._publish_zero_velocity()
            logger.warning("NavigationAgent emergency stopped, task discarded")

        elif command == "reset":
            # 无条件重置所有导航状态（包括 token、控制权、路径等）
            # 无论是否处于急停状态，reset 都应执行完整清理
            self._reset_navigation_state()
            logger.info("NavigationAgent reset, system idle")

        else:
            logger.warning(f"Unknown navigation control command: {command}")

    async def _publish_zero_velocity(self):
        """发送零速度指令，使机器人立即停车"""
        exec_cmd = ExecutionCommand(
            timestamp=time.monotonic(),
            target_velocity=Velocity(linear=0.0, angular=0.0),
            duration=0.1,
            control_mode=ControlMode.STOP
        )
        await self.publish(MessageType.EXECUTION, payload=exec_cmd.model_dump(), priority=Priority.HIGH)

    def _get_room_data(self, name: str) -> Optional[Dict[str, Any]]:
        """从本地缓存获取房间的几何信息"""
        return self.rooms_cache.get(name)

    async def _on_graph_reset(self, event: Event):
        """
        收到图会话重置信号（由 GraphExecutor 在会话结束时发出）。
        重置 NavigationAgent 所有可能阻塞的状态，确保下一次任务干净执行。

        升级点：
            - 使用 _force_clear_token() 统一清理 token 及相关状态
            - 取消正在运行的任务并等待其结束（非阻塞等待）
        """
        payload = event.payload
        graph_id = payload.get("graph_id")
        session_id = payload.get("session_id")

        # 校验：如果不是当前活动的图，忽略此重置事件（防止多图干扰）
        if self.current_graph_id is not None and graph_id != self.current_graph_id:
            logger.debug(f"[NavigationAgent] Ignoring reset for graph {graph_id}, current is {self.current_graph_id}")
            return
        # 校验 session_id
        if self.current_session_id is not None and session_id != self.current_session_id:
            logger.debug(
                f"[NavigationAgent] Ignoring reset for session {session_id}, current is {self.current_session_id}")
            return

        logger.info("[NavigationAgent] Session reset received, resetting state")

        # 1. 使用 token 发送取消信号（主动唤醒等待中的协程）
        if self._current_token:
            self._current_token.cancel_event.set()

        # 2. 取消正在运行的路径跟踪任务（异步等待）
        if self._path_following_task and not self._path_following_task.done():
            self._path_following_task.cancel()
            try:
                await self._path_following_task
            except asyncio.CancelledError:
                pass
            self._path_following_task = None

        # 3. 强制清理 token 和控制权状态
        self._force_clear_token()
        # 注意：版本计数器 _control_version 不重置，保持单调递增，便于日志排查

        # 4. 调用统一重置方法（清空 external_task_id、控制权等，但 _force_clear_token 已做部分，_reset_navigation_state 会重置其余状态）
        self._reset_navigation_state()

        logger.debug("[NavigationAgent] Reset complete")

    # ================== 辅助方法 ==================
    async def _run_coverage_loop(self, token: ControlToken, coverage_path: List[Pose]) -> NavigationTaskResult:
        """
        覆盖清扫主循环：直接跟踪整条覆盖路径，无需逐点规划。
        支持暂停/恢复（通过 self._paused 和 self._pause_event）。
        改进：某个路径点失败不中断整个清扫，仅记录并跳过。
        增强：添加超时保护、定期日志，并在退出时释放控制权。
        返回 NavigationTaskResult 而非 bool。
        """
        task_id = token.task_id
        my_version = token.version
        cancel_event = token.cancel_event

        logger.info(f"[CoverageLoop] Start, total waypoints: {len(coverage_path)}")
        self.coverage_path = coverage_path
        overall_success = True
        failed_points = []
        failure_reason = None

        start_time = time.time()
        max_duration = 1800  # 30分钟超时
        last_log = 0

        # 计算总路径长度（可选）
        total_length = 0.0
        for i in range(len(coverage_path) - 1):
            total_length += math.hypot(
                coverage_path[i+1].x - coverage_path[i].x,
                coverage_path[i+1].y - coverage_path[i].y
            )

        try:
            for idx, goal in enumerate(coverage_path):
                # 1. 版本检查
                if self._current_token is None or self._current_token.version != my_version:
                    logger.warning(
                        f"[CoverageLoop] Version changed (current={self._current_token.version if self._current_token else 'None'}, my={my_version}), aborting")
                    overall_success = False
                    failure_reason = "VERSION_CHANGED"
                    break

                # 2. 取消事件检查
                if cancel_event.is_set():
                    logger.warning("[CoverageLoop] Cancel event set, aborting")
                    overall_success = False
                    failure_reason = "CANCELLED"
                    break

                # 3. 超时保护
                if time.time() - start_time > max_duration:
                    logger.error(f"[CoverageLoop] Timeout after {max_duration}s, aborting")
                    overall_success = False
                    failure_reason = "TIMEOUT"
                    break

                # 4. 定期日志
                now = time.time()
                if now - last_log > 5:
                    logger.info(f"[CoverageLoop] Alive: task={task_id}, idx={idx}/{len(coverage_path)}")
                    last_log = now

                self.coverage_index = idx

                # 5. 暂停处理
                if self._paused:
                    logger.debug(f"[CoverageLoop] Paused at waypoint {idx}, waiting...")
                    await self._pause_event.wait()
                    # 恢复后重新检查版本和取消事件
                    if self._current_token is None or self._current_token.version != my_version:
                        logger.warning(f"[CoverageLoop] Version changed during pause, aborting")
                        overall_success = False
                        failure_reason = "VERSION_CHANGED"
                        break
                    if cancel_event.is_set():
                        logger.warning("[CoverageLoop] Cancel event set during pause, aborting")
                        overall_success = False
                        failure_reason = "CANCELLED"
                        break
                    logger.debug(f"[CoverageLoop] Resumed at waypoint {idx}")

                # 6. 距离检查
                dist_to_goal = math.hypot(goal.x - self.current_pose.x, goal.y - self.current_pose.y)
                if dist_to_goal < 0.2:
                    logger.debug(f"[CoverageLoop] Waypoint {idx} already within 0.2m, skip")
                    continue

                # 7. 路径规划
                path = self.global_planner.plan(self.current_pose, goal, self.obstacle_grid)
                if not path:
                    logger.warning(f"[CoverageLoop] Cannot plan to waypoint {idx} ({goal.x:.2f},{goal.y:.2f}), skip")
                    failed_points.append(idx)
                    overall_success = False
                    failure_reason = "NO_PATH_TO_WAYPOINT"
                    continue

                # 8. 执行路径跟踪（传递 token，而不是 task_id）
                step_result = await self._follow_path(token, path, final_goal=goal)
                if not step_result.success:
                    # 如果因版本变化或取消事件导致失败，立即终止
                    if self._current_token is None or self._current_token.version != my_version:
                        logger.warning(f"[CoverageLoop] Version changed during path following, aborting")
                        overall_success = False
                        failure_reason = "VERSION_CHANGED"
                        break
                    if cancel_event.is_set():
                        logger.warning("[CoverageLoop] Cancel event set during path following, aborting")
                        overall_success = False
                        failure_reason = "CANCELLED"
                        break
                    # 其他原因（如路径受阻但任务仍在）视为该点失败，继续下一个点
                    logger.warning(f"[CoverageLoop] Failed to reach waypoint {idx}, continue to next")
                    overall_success = False
                    failure_reason = step_result.failure_reason or "WAYPOINT_FAILED"
                    failed_points.append(idx)
                    continue

            # 循环结束后的结果
            if overall_success and not failure_reason:
                success = True
                goal_reached = True
            else:
                success = False
                goal_reached = False

        except Exception as e:
            logger.error(f"[CoverageLoop] Unexpected error: {e}", exc_info=True)
            success = False
            goal_reached = False
            failure_reason = str(e)

        finally:
            self._release_token(my_version)

        # 10. 返回结果对象
        return NavigationTaskResult(
            task_id=task_id,
            version=my_version,
            success=success,
            goal_reached=goal_reached,
            session_id=self.current_session_id,
            graph_id=self.current_graph_id,
            final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
            path_length=total_length,
            failure_reason=failure_reason
        )

    async def _resume_coverage_loop(self, token: ControlToken, coverage_path: List[Pose], start_idx: int) -> NavigationTaskResult:
        """
        从指定索引恢复覆盖清扫。
        同样包含超时保护、定期日志，并在退出时释放控制权。
        返回 NavigationTaskResult。
        """
        task_id = token.task_id
        my_version = token.version
        cancel_event = token.cancel_event

        logger.info(f"[CoverageLoop] Resume from index {start_idx}, total {len(coverage_path)}")

        start_time = time.time()
        max_duration = 1800
        last_log = 0
        overall_success = True
        failure_reason = None

        # 计算总路径长度（可选）
        total_length = 0.0
        for i in range(len(coverage_path) - 1):
            total_length += math.hypot(
                coverage_path[i+1].x - coverage_path[i].x,
                coverage_path[i+1].y - coverage_path[i].y
            )

        try:
            for idx in range(start_idx, len(coverage_path)):
                # 版本检查
                if self._current_token is None or self._current_token.version != my_version:
                    logger.warning(f"[CoverageLoop] Resume: version changed, aborting")
                    overall_success = False
                    failure_reason = "VERSION_CHANGED"
                    break

                if cancel_event.is_set():
                    logger.warning("[CoverageLoop] Resume: cancel event set, aborting")
                    overall_success = False
                    failure_reason = "CANCELLED"
                    break

                if time.time() - start_time > max_duration:
                    logger.error(f"[CoverageLoop] Resume timeout, aborting")
                    overall_success = False
                    failure_reason = "TIMEOUT"
                    break

                now = time.time()
                if now - last_log > 5:
                    logger.info(f"[CoverageLoop] Resume alive: task={task_id}, idx={idx}/{len(coverage_path)}")
                    last_log = now

                self.coverage_index = idx

                if self._paused:
                    await self._pause_event.wait()
                    if self._current_token is None or self._current_token.version != my_version:
                        overall_success = False
                        failure_reason = "VERSION_CHANGED"
                        break
                    if cancel_event.is_set():
                        overall_success = False
                        failure_reason = "CANCELLED"
                        break
                    continue

                goal = coverage_path[idx]
                dist_to_goal = math.hypot(goal.x - self.current_pose.x, goal.y - self.current_pose.y)
                if dist_to_goal < 0.2:
                    continue

                path = self.global_planner.plan(self.current_pose, goal, self.obstacle_grid)
                if not path:
                    logger.warning(f"[CoverageLoop] Cannot plan to waypoint {idx}, skip")
                    overall_success = False
                    failure_reason = "NO_PATH_TO_WAYPOINT"
                    continue

                step_result = await self._follow_path(token, path, final_goal=goal)
                if not step_result.success:
                    if self._current_token is None or self._current_token.version != my_version:
                        overall_success = False
                        failure_reason = "VERSION_CHANGED"
                        break
                    if cancel_event.is_set():
                        overall_success = False
                        failure_reason = "CANCELLED"
                        break
                    overall_success = False
                    failure_reason = step_result.failure_reason or "WAYPOINT_FAILED"
                    break

        except Exception as e:
            logger.error(f"[CoverageLoop] Resume error: {e}", exc_info=True)
            overall_success = False
            failure_reason = str(e)

        finally:
            self._release_token(my_version)

        return NavigationTaskResult(
            task_id=task_id,
            version=my_version,
            success=overall_success,
            goal_reached=overall_success,
            session_id=self.current_session_id,
            graph_id=self.current_graph_id,
            final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
            path_length=total_length,
            failure_reason=failure_reason
        )

    async def _follow_path(self, token: ControlToken, path: List[Pose], final_goal: Optional[Pose] = None) -> NavigationTaskResult:
        """
        使用 PurePursuit 跟踪一段路径，支持动态重规划。
        返回 NavigationTaskResult 而不是 bool。
        支持响应 NAVIGATION_CONTROL 的 pause/resume/stop 指令以及会话重置。
        新增 token 机制，支持主动取消和版本校验。
        """
        task_id = token.task_id
        my_version = token.version
        cancel_event = token.cancel_event

        logger.info(
            f"[FollowPath START] task={task_id}, version={my_version}, path_len={len(path)}, "
            f"pose=({self.current_pose.x:.2f},{self.current_pose.y:.2f})"
        )
        logger.debug(
            f"[FollowPath] paused={self._paused}, control_owner={self.control_owner}"
        )

        self.final_goal = final_goal if final_goal else path[-1]  # 保存以便恢复
        if not path:
            return NavigationTaskResult(
                task_id=task_id,
                version=my_version,
                success=False,
                goal_reached=False,
                session_id=self.current_session_id,
                graph_id=self.current_graph_id,
                final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                path_length=0.0,
                failure_reason="EMPTY_PATH"
            )
        if final_goal is None:
            final_goal = path[-1]

        my_gen = self._nav_generation
        my_session_id = self.current_session_id

        idx = 0
        stuck_counter = 0
        replan_count = 0
        MAX_REPLAN = 3
        last_x = self.current_pose.x
        last_y = self.current_pose.y
        last_plan_time = time.time()
        last_log_time = time.time()

        start_time = time.time()
        max_duration = 600  # 10分钟
        last_log = 0

        # 计算实际路径总长度（累积欧氏距离）
        total_path_length = 0.0
        for i in range(len(path) - 1):
            total_path_length += math.hypot(
                path[i+1].x - path[i].x,
                path[i+1].y - path[i].y
            )

        failure_reason = None

        try:
            while True:
                # 索引越界保护
                if idx >= len(path):
                    logger.info(f"[FollowPath] All waypoints processed, navigation completed")
                    break

                # 1. 版本校验（是否被新任务抢占）
                if self._current_token is None or self._current_token.version != my_version:
                    logger.debug(
                        f"[FollowPath] Version mismatch, current={self._current_token.version if self._current_token else 'None'}, my={my_version}")
                    failure_reason = "VERSION_MISMATCH"
                    return NavigationTaskResult(
                        task_id=task_id,
                        version=my_version,
                        success=False,
                        goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=total_path_length,
                        failure_reason=failure_reason
                    )

                # 2. 检查取消事件（立即响应）
                if cancel_event.is_set():
                    logger.debug("[FollowPath] Cancel event set, aborting")
                    failure_reason = "CANCELLED"
                    return NavigationTaskResult(
                        task_id=task_id,
                        version=my_version,
                        success=False,
                        goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=total_path_length,
                        failure_reason=failure_reason
                    )

                # 3. 超时保护
                if time.time() - start_time > max_duration:
                    logger.error(f"Follow path timeout for task {task_id}, aborting")
                    failure_reason = "TIMEOUT"
                    return NavigationTaskResult(
                        task_id=task_id,
                        version=my_version,
                        success=False,
                        goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=total_path_length,
                        failure_reason=failure_reason
                    )

                # 4. 定期日志（每5秒）
                now = time.time()
                if now - last_log > 5:
                    logger.debug(f"_follow_path alive: task={task_id}, idx={idx}/{len(path)}")
                    last_log = now

                # 5. generation / session 检查
                if my_gen != self._nav_generation or my_session_id != self.current_session_id:
                    logger.debug("[FollowPath] Generation/Session mismatch, aborting")
                    failure_reason = "SESSION_RESET"
                    return NavigationTaskResult(
                        task_id=task_id,
                        version=my_version,
                        success=False,
                        goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=total_path_length,
                        failure_reason=failure_reason
                    )

                if self._emergency_stopped:
                    logger.warning("[FollowPath] Emergency stopped, exiting")
                    failure_reason = "EMERGENCY_STOP"
                    return NavigationTaskResult(
                        task_id=task_id,
                        version=my_version,
                        success=False,
                        goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=total_path_length,
                        failure_reason=failure_reason
                    )

                # 6. 暂停处理
                if self._paused:
                    await self._pause_event.wait()
                    # 恢复后立即检查 token 版本
                    if self._current_token is None or self._current_token.version != my_version:
                        failure_reason = "VERSION_MISMATCH_AFTER_PAUSE"
                        return NavigationTaskResult(
                            task_id=task_id,
                            version=my_version,
                            success=False,
                            goal_reached=False,
                            session_id=self.current_session_id,
                            graph_id=self.current_graph_id,
                            final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                            path_length=total_path_length,
                            failure_reason=failure_reason
                        )
                    if cancel_event.is_set():
                        failure_reason = "CANCELLED_AFTER_PAUSE"
                        return NavigationTaskResult(
                            task_id=task_id,
                            version=my_version,
                            success=False,
                            goal_reached=False,
                            session_id=self.current_session_id,
                            graph_id=self.current_graph_id,
                            final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                            path_length=total_path_length,
                            failure_reason=failure_reason
                        )
                    continue

                now = time.time()

                # 7. 到达判定
                if idx < len(path) - 1:
                    dist = math.hypot(path[idx].x - self.current_pose.x, path[idx].y - self.current_pose.y)
                    threshold = self.WAYPOINT_THRESHOLD
                else:
                    dist = math.hypot(final_goal.x - self.current_pose.x, final_goal.y - self.current_pose.y)
                    threshold = self.FINAL_GOAL_THRESHOLD

                if dist < threshold:
                    if idx == len(path) - 1:
                        logger.info(
                            f"[FollowPath] Final goal reached at ({self.current_pose.x:.2f},{self.current_pose.y:.2f})")
                        # 成功到达最终目标，跳出循环
                        break
                    else:
                        idx += 1
                        stuck_counter = 0
                        last_x = self.current_pose.x
                        last_y = self.current_pose.y
                        continue

                # 8. 计算控制指令
                front, _, _ = self._get_local_obstacle_distances()
                linear, angular = self.tracker.compute_command(
                    self.current_pose,
                    path[idx:],
                    front_obstacle_dist=front,
                    current_speed=self.current_linear_vel
                )

                if now - last_log_time > 5.0:
                    logger.debug(
                        f"[PurePursuit] linear={linear:.2f}, angular={angular:.2f}, front={front:.2f}, idx={idx}")
                    last_log_time = now

                # 9. publish 前再次校验 generation
                if my_gen != self._nav_generation:
                    logger.debug("[FollowPath] Generation changed before publish, aborting")
                    failure_reason = "SESSION_RESET_BEFORE_PUBLISH"
                    return NavigationTaskResult(
                        task_id=task_id,
                        version=my_version,
                        success=False,
                        goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=total_path_length,
                        failure_reason=failure_reason
                    )

                # 10. 发布执行指令
                exec_cmd = ExecutionCommand(
                    timestamp=time.monotonic(),
                    target_velocity=Velocity(linear=linear, angular=angular),
                    duration=0.2,
                    control_mode=ControlMode.TRACK_PATH
                )
                await self.publish(MessageType.EXECUTION, payload=exec_cmd.model_dump(), priority=Priority.HIGH)

                # 11. 卡死检测
                if abs(linear) < 0.05 and abs(angular) > 0.1:
                    stuck_counter = 0
                else:
                    movement = math.hypot(self.current_pose.x - last_x, self.current_pose.y - last_y)
                    if movement < 0.01:
                        stuck_counter += 1
                    else:
                        stuck_counter = 0
                    last_x = self.current_pose.x
                    last_y = self.current_pose.y

                # 12. 重规划（带次数上限，防止无限重规划循环）
                if stuck_counter > 30:
                    now_time = time.time()
                    if now_time - self._last_replan_time > 5.0:
                        replan_count += 1
                        if replan_count > MAX_REPLAN:
                            logger.error(f"Replan exceeded max ({MAX_REPLAN}), aborting")
                            failure_reason = "REPLAN_EXCEEDED"
                            return NavigationTaskResult(
                                task_id=task_id,
                                version=my_version,
                                success=False,
                                goal_reached=False,
                                session_id=self.current_session_id,
                                graph_id=self.current_graph_id,
                                final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                                path_length=total_path_length,
                                failure_reason=failure_reason
                            )
                        logger.info(f"Current pose: ({self.current_pose.x:.2f},{self.current_pose.y:.2f}), replan attempt {replan_count}/{MAX_REPLAN}")
                        new_path = self.global_planner.replan(self.current_pose, final_goal, self.obstacle_grid)
                        if new_path:
                            first = new_path[0]
                            dx = first.x - self.current_pose.x
                            dy = first.y - self.current_pose.y
                            cos_t = math.cos(self.current_pose.theta)
                            sin_t = math.sin(self.current_pose.theta)
                            local_x = dx * cos_t + dy * sin_t
                            if local_x < 0:
                                logger.warning(
                                    f"Replanned path starts behind robot! local_x={local_x:.2f}. Adjusting...")
                                new_path.insert(0, Pose(x=self.current_pose.x, y=self.current_pose.y,
                                                        theta=self.current_pose.theta))
                            logger.info(f"New path first 5 points: {[(p.x, p.y) for p in new_path[:5]]}")
                            goal_dist = math.hypot(new_path[-1].x - final_goal.x, new_path[-1].y - final_goal.y)
                            if goal_dist > self.FINAL_GOAL_THRESHOLD / 2:
                                new_path.append(final_goal)
                                logger.info("Appended final goal to replanned path")
                            # 重新计算新路径长度（可选）
                            new_total_length = 0.0
                            for i in range(len(new_path) - 1):
                                new_total_length += math.hypot(
                                    new_path[i+1].x - new_path[i].x,
                                    new_path[i+1].y - new_path[i].y
                                )
                            total_path_length = new_total_length
                            path = new_path
                            idx = 0
                            stuck_counter = 0
                            self._last_replan_time = now_time
                            logger.info(f"Replanned, new path length {len(path)}")
                        else:
                            logger.error("Replan failed, aborting")
                            failure_reason = "REPLAN_FAILED"
                            return NavigationTaskResult(
                                task_id=task_id,
                                version=my_version,
                                success=False,
                                goal_reached=False,
                                session_id=self.current_session_id,
                                graph_id=self.current_graph_id,
                                final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                                path_length=total_path_length,
                                failure_reason=failure_reason
                            )
                    else:
                        logger.debug(f"Replan throttled, last replan at {self._last_replan_time:.2f}s ago")

                # 13. 定期反馈进度
                if now - last_plan_time > self._feedback_interval:
                    progress = idx / len(path) if path else 0.0
                    remaining = math.hypot(final_goal.x - self.current_pose.x, final_goal.y - self.current_pose.y)
                    await self._send_task_progress(
                        task_id, "RUNNING", progress,
                        {"x": self.current_pose.x, "y": self.current_pose.y},
                        {"x": final_goal.x, "y": final_goal.y},
                        remaining,
                        f"Tracking path, progress {progress:.1%}"
                    )
                    last_plan_time = now

                # 14. 等待 0.05 秒，可被取消事件中断
                try:
                    await asyncio.wait_for(cancel_event.wait(), timeout=0.05)
                    # 如果取消事件被设置，立即退出
                    logger.debug("[FollowPath] Cancel event set during wait, aborting")
                    failure_reason = "CANCELLED_DURING_WAIT"
                    return NavigationTaskResult(
                        task_id=task_id,
                        version=my_version,
                        success=False,
                        goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=total_path_length,
                        failure_reason=failure_reason
                    )
                except asyncio.TimeoutError:
                    # 正常超时，继续循环
                    pass

                # 15. 循环末尾再次检查版本
                if self._current_token is None or self._current_token.version != my_version:
                    logger.debug("[FollowPath] Version changed after wait, aborting")
                    failure_reason = "VERSION_MISMATCH_AFTER_WAIT"
                    return NavigationTaskResult(
                        task_id=task_id,
                        version=my_version,
                        success=False,
                        goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=total_path_length,
                        failure_reason=failure_reason
                    )


        finally:
            # 子步骤不释放 token，仅记录退出
            logger.debug(f"[FollowPath EXIT] task={task_id}, version={my_version}")

        # 正常退出循环（成功到达目标或路径处理完毕）
        return NavigationTaskResult(
            task_id=task_id,
            version=my_version,
            success=True,
            goal_reached=True,
            session_id=self.current_session_id,
            graph_id=self.current_graph_id,
            final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
            path_length=total_path_length,
            failure_reason=None
        )

    async def _wait_task_cleanup(self, task: asyncio.Task, token: Optional[ControlToken]):
        """后台等待旧任务彻底退出，不阻塞新任务启动"""
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Old task did not exit in time, force cancelling")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass
        # 清理任务引用
        if self._path_following_task is task:
            self._path_following_task = None

    def _on_navigation_task_done(self, task: asyncio.Task):
        """导航任务完成时的回调，负责发送任务结果。"""
        try:
            result = task.result()
            if isinstance(result, NavigationTaskResult):
                # 调用通用的 send_task_result 方法（假设是异步且不需要额外 version 参数）
                asyncio.create_task(self.send_task_result(
                    task_id=result.task_id,
                    success=result.success,
                    result=result.model_dump()
                ))
            else:
                logger.warning(f"Unexpected task result type: {type(result)}")
        except asyncio.CancelledError:
            logger.debug("Navigation task cancelled")
        except Exception as e:
            logger.error(f"Navigation task failed: {e}")
        finally:
            if self._path_following_task is task:
                self._path_following_task = None

    # ================== 路径生成辅助 ==================
    async def _plan_path_to_target(self, target_pose: Pose) -> List[Pose]:
        return self.global_planner.plan(self.current_pose, target_pose, self.obstacle_grid)

    async def _generate_coverage_path(self, area: str) -> List[Pose]:
        rows = self.map_rows
        cols = self.map_cols
        buffer = 5
        path_grid = []
        direction = 1
        for r in range(buffer, rows - buffer):
            if direction == 1:
                for c in range(buffer, cols - buffer):
                    if self.obstacle_grid[r][c] == 0:
                        path_grid.append((r, c))
            else:
                for c in range(cols - buffer - 1, buffer - 1, -1):
                    if self.obstacle_grid[r][c] == 0:
                        path_grid.append((r, c))
            direction *= -1
        return [Pose(x=self.coord_trans.grid_to_world(g[0], g[1])[0],
                     y=self.coord_trans.grid_to_world(g[0], g[1])[1],
                     theta=0.0) for g in path_grid]

    # ================== 卡死恢复 ==================
    async def _run_recovery(self, token: ControlToken) -> NavigationTaskResult:
        """执行卡死恢复：后退 + 原地旋转，尝试脱困"""
        task_id = token.task_id
        my_version = token.version
        cancel_event = token.cancel_event

        logger.info(f"[Recovery] Start recovery for task {task_id}")
        self.recovery_mode = True
        self.recovery_steps = 0
        start_time = time.time()
        max_duration = 10.0  # 最多恢复 10 秒

        try:
            while self.recovery_mode and (time.time() - start_time < max_duration):
                if self._current_token is None or self._current_token.version != my_version:
                    logger.warning("[Recovery] Version changed, aborting")
                    return NavigationTaskResult(
                        task_id=task_id, version=my_version,
                        success=False, goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=0.0, failure_reason="VERSION_CHANGED"
                    )
                if cancel_event.is_set():
                    logger.warning("[Recovery] Cancelled")
                    return NavigationTaskResult(
                        task_id=task_id, version=my_version,
                        success=False, goal_reached=False,
                        session_id=self.current_session_id,
                        graph_id=self.current_graph_id,
                        final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                        path_length=0.0, failure_reason="CANCELLED"
                    )

                cmd = self._recovery_behavior()
                exec_cmd = ExecutionCommand(
                    timestamp=time.monotonic(),
                    target_velocity=Velocity(linear=cmd["linear"], angular=cmd["angular"]),
                    duration=0.2,
                    control_mode=ControlMode.RECOVERY
                )
                await self.publish(MessageType.EXECUTION, payload=exec_cmd.model_dump(), priority=Priority.HIGH)
                await asyncio.sleep(0.1)

            success = not self.recovery_mode
            logger.info(f"[Recovery] Completed: success={success}, steps={self.recovery_steps}")
            return NavigationTaskResult(
                task_id=task_id, version=my_version,
                success=success, goal_reached=success,
                session_id=self.current_session_id,
                graph_id=self.current_graph_id,
                final_pose={"x": self.current_pose.x, "y": self.current_pose.y},
                path_length=0.0,
                failure_reason=None if success else "RECOVERY_EXHAUSTED"
            )
        finally:
            self._release_token(my_version)

    # ================== 其他原方法 ==================
    def _is_stuck(self) -> bool:
        if len(self.position_history) < 30:
            return False
        sx, sy = self.position_history[0]
        ex, ey = self.position_history[-1]
        dist = math.hypot(ex - sx, ey - sy)
        return dist < 0.15

    def _recovery_behavior(self) -> Dict[str, float]:
        self.recovery_steps += 1
        if self.recovery_steps < 5:
            linear = -0.2
            angular = 0.0
        elif self.recovery_steps < 15:
            linear = 0.0
            angular = random.choice([-1.0, 1.0])
        else:
            self.recovery_mode = False
            self.recovery_steps = 0
            linear = 0.0
            angular = 0.0
        return {"linear": linear, "angular": angular}

    def _get_local_obstacle_distances(self) -> Tuple[float, float, float]:
        front = 2.0
        left = 2.0
        right = 2.0
        x, y, theta = self.current_pose.x, self.current_pose.y, self.current_pose.theta
        for delta, direction in [(0, "front"), (math.pi/2, "left"), (-math.pi/2, "right")]:
            angle = theta + delta
            for step_i in range(1, 30):
                nx = x + step_i * 0.1 * math.cos(angle)
                ny = y + step_i * 0.1 * math.sin(angle)
                gx = int(nx / self.resolution) + self.origin_offset
                gy = int(ny / self.resolution) + self.origin_offset
                if not (0 <= gy < self.map_rows and 0 <= gx < self.map_cols):
                    break
                if self.obstacle_grid[gy][gx] == 1:
                    dist = step_i * 0.1
                    if direction == "front":
                        front = min(front, dist)
                    elif direction == "left":
                        left = min(left, dist)
                    else:
                        right = min(right, dist)
                    break
        return front, left, right

    def _update_obstacle_map_from_world(self, obstacles: List[Any]):
        self.obstacle_grid = [[0 for _ in range(self.map_cols)] for _ in range(self.map_rows)]
        for obs in obstacles:
            if isinstance(obs, dict):
                obs_type = obs.get("type")
                center = obs.get("center")
                if not center:
                    continue
                cx, cy = center[0], center[1]
                if obs_type == "circle":
                    radius = obs.get("radius", 0.2)
                    self._mark_circle_obstacle(cx, cy, radius)
                elif obs_type == "rect":
                    width = obs.get("width", 0.2)
                    height = obs.get("height", 0.2)
                    self._mark_rect_obstacle(cx, cy, width, height)
            else:
                if hasattr(obs, "center"):
                    cx, cy = obs.center[0], obs.center[1]
                    if obs.type == ObstacleType.CIRCLE:
                        self._mark_circle_obstacle(cx, cy, obs.radius)
                    elif obs.type == ObstacleType.RECTANGLE:
                        self._mark_rect_obstacle(cx, cy, obs.width, obs.height)

    def _mark_circle_obstacle(self, cx, cy, radius):
        gx_center, gy_center = self.coord_trans.world_to_grid(cx, cy)
        r_grid = int(radius / self.resolution) + 2
        for dx in range(-r_grid, r_grid + 1):
            for dy in range(-r_grid, r_grid + 1):
                if dx*dx + dy*dy <= r_grid*r_grid:
                    gx, gy = gx_center + dx, gy_center + dy
                    if 0 <= gy < self.map_rows and 0 <= gx < self.map_cols:
                        self.obstacle_grid[gy][gx] = 1

    def _mark_rect_obstacle(self, cx, cy, width, height):
        gx_center, gy_center = self.coord_trans.world_to_grid(cx, cy)
        half_w = int((width / self.resolution) / 2) + 1
        half_h = int((height / self.resolution) / 2) + 1
        for dy in range(-half_h, half_h + 1):
            for dx in range(-half_w, half_w + 1):
                gx, gy = gx_center + dx, gy_center + dy
                if 0 <= gy < self.map_rows and 0 <= gx < self.map_cols:
                    self.obstacle_grid[gy][gx] = 1

    async def _publish_navigation_status(self):
        if not self.current_path:
            return
        goal = self.current_path[-1] if self.current_path else self.current_pose
        world_path = [[p.x, p.y] for p in self.current_path]
        nav_msg = NavigationStatusMessage(
            timestamp=time.monotonic(),
            target_pose={"x": goal.x, "y": goal.y, "theta": 0.0},
            path=world_path,
            navigation_mode=NavigationMode.SPOT,
            avoidance_mode=AvoidanceMode.DYNAMIC,
            navigation_status=NavigationStatus.TRACKING
        )
        await self.publish(MessageType.NAVIGATION, payload=nav_msg.model_dump(), priority=Priority.NORMAL)

    async def _send_task_progress(self, task_id: str, status: str, progress: float,
                                  current_pose: dict, target_pose: dict, remaining_distance: float, message: str):
        payload = NavigationProgressPayload(
            status=status,
            progress=progress,
            current_pose=current_pose,
            target_pose=target_pose,
            remaining_distance=remaining_distance,
            message=message
        )
        await self.emit_event(UIEventType.TASK_PROGRESS.value, task_id=task_id, payload=payload.model_dump())

    async def _send_task_result(self, task_id: str, version: int, success: bool, goal_reached: bool,
                                final_pose: dict, path_length: float, failure_reason: Optional[str] = None):
        """
        发送任务结果事件。
        使用版本号比较防止旧结果污染（只丢弃被更新的任务），不依赖 external_task_id。
        注意：任务完成后 _current_token 可能已被清空，此时只要没有更新的任务，就允许发送。
        """
        # 如果当前有活跃的任务，且其版本号大于当前结果版本，则丢弃（说明已被抢占）
        if task_id is None:
            # 防御：逐级兜底获取 task_id
            # 1. 尝试 external_task_id
            task_id = self.external_task_id
        if task_id is None and self._current_token is not None:
            # 2. 尝试从当前 token 获取
            task_id = self._current_token.task_id
        if task_id is None:
            logger.error("_send_task_result called with task_id=None and no fallback (external_task_id and token both None)")
            return

        payload = {
            "task_id": task_id,
            "session_id": self.current_session_id,  # 关键：必须带 session_id
            "success": success,
            "goal_reached": goal_reached,
            "final_pose": final_pose,
            "path_length": path_length,
            "failure_reason": failure_reason,
            "version": version
        }
        # 使用标准事件类型 UIEventType.TASK_RESULT
        await self.emit_event(UIEventType.TASK_RESULT.value, task_id=task_id, payload=payload)
