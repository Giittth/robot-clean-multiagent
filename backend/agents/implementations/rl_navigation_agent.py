"""
RLNavigationAgent - 强化学习扫地机器人导航智能体
两种模式：
- pure纯模式：365维观测，端到端PPO强化学习局部导航避障
- hybrid混合模式：367维观测，上层全局路径规划 + PPO局部RL控制器，附带目标方向观测向量
观测格式必须和RobotGymEnv严格对齐，保证Sim2Real仿真迁移正确
"""
import math
import numpy as np
from datetime import datetime
from typing import Optional, Tuple, List
import time
import asyncio

from stable_baselines3 import PPO
from backend.agents.implementations.navigation_agent import NavigationAgent
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.agents.schemas.agent_messages import PerceptionResult, NavCommand, RawSensorData
from backend.models.physics.robot_state import Pose
from backend.utils.logger_handler import logger


class RLNavigationAgent(NavigationAgent):
    """RL-powered navigation agent.

    Two modes:
      - pure  (default):  end-to-end reactive RL, same obs as RobotGymEnv (365-dim)
      - hybrid:           RL as local controller + parent global planner for waypoints (367-dim obs)
    """

    def __init__(self, agent_id: str, agent_type: str, message_bus, registry,
                 event_router, rag_tool,
                 map_size: Tuple[int, int] = (20, 20),
                 resolution: float = 0.2,
                 model_path: Optional[str] = None,
                 hybrid_mode: bool = False):
        # 初始化基础导航智能体
        super().__init__(agent_id, agent_type, message_bus, registry,
                         event_router, rag_tool, map_size, resolution)
        self.model = None  # PPO强化学习模型
        self.battery_voltage = 12.0  # 当前电池电压，初始满电
        self.last_laser = np.full(360, 2.0, dtype=np.float32)  # 缓存360维激光雷达数据
        self.last_sensor_data = None  # 缓存原始传感器数据包
        self.hybrid_mode = hybrid_mode  # 标记是否启用混合导航模式

        # 混合模式全局路点相关变量
        self._active_goal: Optional[Pose] = None  # 全局导航目标位姿
        self._goal_path: List[Pose] = []  # 全局路径规划生成的路点列表
        self._goal_path_index = 0  # 当前追踪的路点索引

        # 加载PPO模型
        if model_path:
            try:
                self.model = PPO.load(model_path)
                logger.info(f"RL model loaded: {model_path}")
            except Exception as e:
                logger.error(f"RL model loading failed: {e}")

    async def on_start(self):
        # 智能体启动回调，订阅消息
        await super().on_start()
        await self.subscribe(MessageType.SENSOR, self.handle_sensor)
        # 混合模式额外订阅导航请求消息
        if self.hybrid_mode:
            await self.subscribe(MessageType.NAVIGATION_REQUEST, self._handle_nav_request_for_rl)

    async def handle_sensor(self, msg: Message):
        """缓存最新激光雷达和电池传感器数据"""
        try:
            raw = RawSensorData(**msg.payload)
            self.last_laser = np.array(raw.laser, dtype=np.float32)
            self.last_sensor_data = raw
            if hasattr(raw, 'battery_voltage'):
                self.battery_voltage = raw.battery_voltage
        except Exception as e:
            logger.error(f"Failed to process sensor data: {e}")

    async def _handle_nav_request_for_rl(self, msg: Message):
        """
        Hybrid模式：接收全局导航/清扫任务，调用全局规划器生成路点
        RL后续根据路点方向做局部控制
        """
        try:
            payload = msg.payload
            task_type = payload.get("type", "")
            params = payload.get("params", {})

            # 解析目标位姿
            if "target_pose" in params:
                tp = params["target_pose"]
                target = Pose(x=tp.get("x", 0.0), y=tp.get("y", 0.0), theta=tp.get("theta", 0.0))
            elif task_type == "cover_room" and "room" in params:
                room_name = params["room"]
                room_data = self.rooms_cache.get(room_name, {})
                entry = room_data.get("entry_point", None)
                if entry:
                    target = Pose(x=entry[0], y=entry[1], theta=0.0)
                else:
                    logger.warning(f"Room '{room_name}' entry point not found, aborting")
                    return
            else:
                logger.warning(f"Unknown navigation request type: {task_type}")
                return

            # 调用父类全局路径规划器生成全局路径
            path = self.global_planner.plan(self.current_pose, target, self.obstacle_grid)
            if not path:
                logger.warning(f"[RL-Hybrid] Global planner failed to find path")
                return

            self._goal_path = path
            self._goal_path_index = 0
            self._active_goal = target
            logger.info(f"[RL-Hybrid] Path planned: {len(path)} waypoints")
        except Exception as e:
            logger.error(f"[RL-Hybrid] Error handling nav request: {e}", exc_info=True)

    async def handle_perception(self, msg: Message):
        """
        感知消息回调：更新位姿/地图/清扫信息，调用RL模型生成导航指令
        """
        try:
            perception = PerceptionResult(**msg.payload)

            # 更新当前机器人真实位姿
            if hasattr(perception, 'current_pose') and perception.current_pose:
                self.current_pose = perception.current_pose

            # 更新障碍物地图和清扫覆盖栅格
            self._update_obstacle_map(perception)
            self._update_coverage(perception)

            # RL模型决策 / 默认导航
            if self.model:
                nav_cmd = await self._rl_decision(perception)
            else:
                nav_cmd = self._generate_nav_command()

            # 下发导航速度指令
            if nav_cmd:
                await self.publish(
                    msg_type=MessageType.NAVIGATION,
                    payload=nav_cmd.model_dump(),
                    priority=Priority.HIGH,
                )
        except Exception as e:
            logger.error(f"RL handle_perception error: {e}", exc_info=True)

    async def _rl_decision(self, perception: PerceptionResult) -> Optional[NavCommand]:
        """PPO模型推理，生成线速度+角速度指令"""
        if not self.model:
            return None

        try:
            obs = self._build_obs(perception)
            action, _ = self.model.predict(obs, deterministic=True)
            linear_speed, angular_speed = action

            # 限制动作范围，和仿真训练保持一致
            linear_speed = float(np.clip(linear_speed, -0.5, 1.0))
            angular_speed = float(np.clip(angular_speed, -1.0, 1.0))

            nav_cmd = NavCommand(
                robot_id=self.agent_id,
                timestamp=datetime.now().timestamp(),
                waypoints=[],
                linear_speed=linear_speed,
                angular_speed=angular_speed,
            )
            logger.debug(f"RL action: v={linear_speed:.2f}, w={angular_speed:.2f}")
            return nav_cmd

        except Exception as e:
            logger.error(f"RL decision error: {e}")
            return None

    def _build_obs(self, perception: PerceptionResult) -> np.ndarray:
        """
        构造观测向量，和RobotGymEnv格式保持对齐
        pure模式：365维 = 360激光 + 4位姿 + 1电池
        hybrid模式：367维 = 365维 + 2维目标方向向量
        """
        # 激光雷达归一化
        laser = self.last_laser.copy().astype(np.float32)
        laser = np.clip(laser / 5.0, 0.0, 1.0)

        # 位姿 + sin/cos朝向编码
        pose = self.current_pose or Pose(x=0.0, y=0.0, theta=0.0)
        pose_vec = np.array([
            pose.x / 10.0,
            pose.y / 10.0,
            math.sin(pose.theta),
            math.cos(pose.theta),
        ], dtype=np.float32)

        # 电池归一化
        battery_vec = np.array([self.battery_voltage / 12.0], dtype=np.float32)

        parts = [laser, pose_vec, battery_vec]

        # hybrid模式追加全局路点方向向量
        if self.hybrid_mode:
            goal_dx, goal_dy = self._get_goal_direction()
            parts.append(np.array([goal_dx, goal_dy], dtype=np.float32))

        return np.concatenate(parts).astype(np.float32)

    def _get_goal_direction(self) -> Tuple[float, float]:
        """计算朝向当前全局路点的归一化方向向量（hybrid模式专用）"""
        # 距离足够近则切换下一个路点
        if self._goal_path and self._goal_path_index < len(self._goal_path):
            wp = self._goal_path[self._goal_path_index]
            dist_to_wp = math.hypot(wp.x - self.current_pose.x, wp.y - self.current_pose.y)
            if dist_to_wp < 0.35:
                self._goal_path_index += 1

        # 计算方向向量并归一化
        if self._goal_path and self._goal_path_index < len(self._goal_path):
            wp = self._goal_path[self._goal_path_index]
            dx = wp.x - self.current_pose.x
            dy = wp.y - self.current_pose.y
            norm = math.hypot(dx, dy)
            if norm > 0.01:
                return (dx / norm, dy / norm)

        return (0.0, 0.0)

    def _update_obstacle_map(self, perception: PerceptionResult):
        """更新局部障碍物栅格地图"""
        try:
            if perception.obstacles:
                for obs in perception.obstacles:
                    if hasattr(obs, 'center'):
                        cx, cy = obs.center[0], obs.center[1]
                        r = getattr(obs, 'radius', 0.2)
                        self._mark_circle_obstacle(cx, cy, r)
        except Exception as e:
            logger.debug(f"_update_obstacle_map skipped: {e}")

    def _update_coverage(self, perception: PerceptionResult):
        """标记当前栅格为已清扫，统计全屋覆盖率"""
        pose = self.current_pose
        if pose is None:
            return
        gx = int(pose.x / self.resolution) + self.origin_offset
        gy = int(pose.y / self.resolution) + self.origin_offset
        if 0 <= gy < self.map_rows and 0 <= gx < self.map_cols:
            self.coverage_grid[gy][gx] = 1
