"""
    仿真环境
    模拟机器人物理运动、传感器数据生成，并订阅执行指令。
    新增：发布 SIMULATION_STATE 消息（真实位姿、速度），作为系统中机器人位姿的唯一来源。
"""

import time
import asyncio
import math
import copy
import random

from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.agents.schemas.agent_messages import (
    RawSensorData, SimulationStateMessage, ExecutionCommand, Velocity, MapMetadata
)
from backend.models.physics.robot_state import Pose
from backend.models.physics.environment import Obstacle, ObstacleType
from backend.utils.logger_handler import logger
from backend.agents.simulation.scenario_loader import load_scenario


class SimulationEnvironment:
    def __init__(self, bus: MessageBus, robot_id: str = "robot_001", scenario_name: str = "standard"):
        self.bus = bus
        self.robot_id = robot_id
        # 加载场景（深拷贝）
        self.scenario = copy.deepcopy(load_scenario(scenario_name))
        # 保存原始预定义障碍物（用于切换场景后重建）
        self._predefined_obstacles = self.scenario.get("obstacles", [])

        # 仿真参数
        self.sensor_update_interval = 0.1
        self.state_publish_interval = 0.1
        self.wheel_distance = 0.3
        self._running = False
        self.robot_radius = 0.2

        # 调用初始化函数（根据场景设置障碍物、边界、机器人状态）
        self._init_from_scenario()

        logger.info(f"Load simulation scenario: {scenario_name} with {len(self.scenario['obstacles'])} obstacles")
        logger.info(f"Robot starts at ({self.pose.x}, {self.pose.y}) in a 16.0x16.0m room")
        logger.info(f"Boundary range set to ±{self.max_range:.1f}m")

    def _init_from_scenario(self):
        """根据 self.scenario 重新初始化环境（障碍物、边界、机器人位置等）"""
        # 清空障碍物（墙体随后会重新添加）
        self.scenario["obstacles"] = []

        room_width = 24.0
        room_height = 24.0
        wall_thickness = 0.5
        start_x, start_y = self.scenario["start"]

        self.max_range = max(room_width, room_height)

        # 添加四面墙体（使用字典格式）
        self.scenario["obstacles"].append(Obstacle(
            type=ObstacleType.RECTANGLE,
            center=(start_x, start_y + room_height / 2),
            width=room_width,
            height=wall_thickness
        ).model_dump())
        self.scenario["obstacles"].append(Obstacle(
            type=ObstacleType.RECTANGLE,
            center=(start_x, start_y - room_height / 2),
            width=room_width,
            height=wall_thickness
        ).model_dump())
        self.scenario["obstacles"].append(Obstacle(
            type=ObstacleType.RECTANGLE,
            center=(start_x - room_width / 2, start_y),
            width=wall_thickness,
            height=room_height
        ).model_dump())
        self.scenario["obstacles"].append(Obstacle(
            type=ObstacleType.RECTANGLE,
            center=(start_x + room_width / 2, start_y),
            width=wall_thickness,
            height=room_height
        ).model_dump())

        # 添加场景预定义的障碍物（必须转换为字典格式）
        predefined_obstacles = self.scenario.get("obstacles", [])
        # 注意：这里不能直接使用 self.scenario["obstacles"]，因为上面已经清空了，需要从原始场景配置读取
        # 由于 self.scenario 是深拷贝的，我们需要保存一份原始预定义障碍物副本
        # 简单做法：从 __init__ 时传进来的场景中保存一份原始配置，或者每次从 load_scenario 重新获取
        # 为简化，我们假设原始预定义障碍物保存在 self._predefined_obstacles 中
        if not hasattr(self, '_predefined_obstacles'):
            # 在 __init__ 中调用 _init_from_scenario 之前，先保存原始场景中的障碍物
            self._predefined_obstacles = self.scenario.get("obstacles", [])

        for obs in self._predefined_obstacles:
            if isinstance(obs, (list, tuple)) and len(obs) == 2:
                # 坐标列表 -> 圆形障碍物（半径0.2）
                x, y = obs
                self.scenario["obstacles"].append(Obstacle(
                    type=ObstacleType.CIRCLE,
                    center=(x, y),
                    radius=0.2
                ).model_dump())
            elif isinstance(obs, dict):
                # 已经是字典格式，直接添加（假设包含 type, center, radius 等）
                self.scenario["obstacles"].append(obs)
            else:
                logger.warning(f"Unknown obstacle format: {obs}, skipping")

        # 随机添加家具（带超时保护）
        random.seed(23)
        num_furniture = 9
        max_attempts_per_furniture = 100
        for _ in range(num_furniture):
            for attempt in range(max_attempts_per_furniture):
                x = random.uniform(start_x - 3.0, start_x + 3.0)
                y = random.uniform(start_y - 3.0, start_y + 3.0)
                dist_from_start = math.hypot(x - start_x, y - start_y)
                if dist_from_start > 2.0:
                    break
            else:
                # 超过尝试次数，使用后备位置
                x = start_x + random.uniform(2.5, 3.0)
                y = start_y + random.uniform(2.5, 3.0)
                logger.warning(
                    f"Could not find valid furniture position after {max_attempts_per_furniture} attempts, using fallback")
            r = random.uniform(0.15, 0.3)
            self.scenario["obstacles"].append(Obstacle(
                type=ObstacleType.CIRCLE,
                center=(x, y),
                radius=r
            ).model_dump())

        # 重置机器人状态
        self.pose = Pose(x=start_x, y=start_y, theta=0.0)
        self.battery_voltage = 12.0
        self.cleaned_area = 0.0
        self.collision_detected = False
        self._current_linear_vel = 0.0
        self._current_angular_vel = 0.0
        self.last_laser = [2.0] * 360

        logger.info(
            f"Environment initialized with start ({start_x},{start_y}) and {len(self.scenario['obstacles'])} obstacles")

    async def reset(self):
        """重置环境状态（使用场景初始位置）"""
        start_x, start_y = self.scenario["start"]
        self.pose = Pose(x=start_x, y=start_y, theta=0.0)
        self.battery_voltage = 12.0
        self.cleaned_area = 0.0
        self.collision_detected = False
        self.last_laser = [2.0] * 360
        self._current_linear_vel = 0.0
        self._current_angular_vel = 0.0
        logger.info("SimulationEnvironment 已重置（使用场景起点）")

    async def start(self):
        self._running = True
        await self.bus.subscribe(MessageType.EXECUTION, self.handle_exec_command)

        # 从已加载的场景中提取 rooms 数据（self.scenario 已在 __init__ 中通过 load_scenario 获得）
        rooms_data = self.scenario.get("rooms", [])
        if rooms_data:
            metadata = MapMetadata(rooms=rooms_data)
            msg = Message(
                type=MessageType.MAP_METADATA,
                source="simulation",
                payload=metadata.model_dump(),
                priority=Priority.NORMAL
            )
            await self.bus.publish(msg)
            logger.info(f"Published MAP_METADATA with {len(rooms_data)} rooms")
        else:
            logger.info("No rooms defined in scenario, skipping MAP_METADATA")
        asyncio.create_task(self._sensor_loop())
        logger.info("SimulationEnvironment 启动完成（发布 SENSOR 和 SIMULATION_STATE）")

    async def stop(self):
        """停止仿真"""
        self._running = False
        await self.bus.unsubscribe(MessageType.EXECUTION, self.handle_exec_command)
        logger.info("SimulationEnvironment 已停止")

    async def handle_exec_command(self, msg: Message):
        """
        接收执行指令（速度控制），更新机器人物理位姿（差速驱动模型）。
        同时记录当前速度，用于 SIMULATION_STATE 消息。
        """
        try:
            # 解析 ExecutionCommand 消息
            payload = msg.payload.copy()
            if "target_velocity" not in payload:
                payload["target_velocity"] = {"linear": 0.0, "angular": 0.0}
            exec_cmd = ExecutionCommand(**payload)

            v = exec_cmd.target_velocity.linear
            w = exec_cmd.target_velocity.angular
            dt = min(exec_cmd.duration, 0.1)

            # 保存当前速度（用于 SIMULATION_STATE）
            self._current_linear_vel = v
            self._current_angular_vel = w

            # 保存旧位置用于验证
            old_pose = Pose(x=self.pose.x, y=self.pose.y, theta=self.pose.theta)

            # 增加步数，确保不会穿墙
            steps = 20
            step_dt = dt / steps

            collision_occurred = False

            for step in range(steps):
                step_start_pose = Pose(x=self.pose.x, y=self.pose.y, theta=self.pose.theta)

                # 执行一步运动（使用线性与角速度）
                self.pose.theta += w * step_dt
                self.pose.x += v * math.cos(self.pose.theta) * step_dt
                self.pose.y += v * math.sin(self.pose.theta) * step_dt

                # 边界检查
                self.pose.x = max(-self.max_range, min(self.max_range, self.pose.x))
                self.pose.y = max(-self.max_range, min(self.max_range, self.pose.y))

                # 每一步都检测碰撞
                if self._check_collision():
                    max_bounce_attempts = 3
                    bounce_success = False

                    for attempt in range(max_bounce_attempts):
                        colliding_obs = self._find_colliding_obstacle()
                        if colliding_obs:
                            bounce_theta = self._calculate_bounce_angle(step_start_pose, colliding_obs)

                            self.pose = Pose(
                                x=step_start_pose.x,
                                y=step_start_pose.y,
                                theta=bounce_theta
                            )

                            if not self._check_collision():
                                bounce_success = True
                                self.collision_detected = True
                                break
                            else:
                                if attempt < max_bounce_attempts - 1:
                                    import random
                                    self.pose.theta += random.uniform(-math.pi / 6, math.pi / 6)
                        else:
                            self.pose = step_start_pose
                            self.collision_detected = True
                            bounce_success = True
                            break

                    if not bounce_success:
                        self.pose = step_start_pose
                        self.collision_detected = True
                        logger.error("Collision! All bounce attempts failed, stopping.")
                    collision_occurred = True
                    break

            if not collision_occurred:
                self.collision_detected = False

            # 更新电池和清扫面积（使用线速度的绝对值）
            self.battery_voltage -= 0.0001
            self.cleaned_area += abs(v) * dt * 0.1

        except Exception as e:
            logger.error(f"执行指令异常: {e}", exc_info=True)

    # ----- 碰撞检测方法（保持不变）-----
    def _check_collision(self):
        """机器人（半径 self.robot_radius）与场景中障碍物的碰撞检测（支持圆形和矩形）"""
        robot_r = getattr(self, 'robot_radius', 0.2)
        x, y = self.pose.x, self.pose.y

        for obs in self.scenario["obstacles"]:
            if obs["type"] == "circle":
                cx, cy = obs["center"]
                r = obs["radius"]
                dist = math.hypot(x - cx, y - cy)
                if dist < robot_r + r:
                    return True
            elif obs["type"] == "rect":
                cx, cy = obs["center"]
                w = obs["width"]
                h = obs["height"]
                left = cx - w / 2
                right = cx + w / 2
                bottom = cy - h / 2
                top = cy + h / 2
                closest_x = max(left, min(x, right))
                closest_y = max(bottom, min(y, top))
                dist = math.hypot(x - closest_x, y - closest_y)
                if dist < robot_r:
                    return True
                if left <= x <= right and bottom <= y <= top:
                    return True
        return False

    def _calculate_bounce_angle(self, old_pose: Pose, colliding_obs: dict) -> float:
        """计算碰撞后的反弹角度"""
        robot_x = old_pose.x
        robot_y = old_pose.y
        robot_theta = old_pose.theta

        obs_type = colliding_obs["type"]

        if obs_type == "rect":
            cx, cy = colliding_obs["center"]
            w = colliding_obs["width"]
            h = colliding_obs["height"]
            left = cx - w / 2
            right = cx + w / 2
            bottom = cy - h / 2
            top = cy + h / 2
            closest_x = max(left, min(robot_x, right))
            closest_y = max(bottom, min(robot_y, top))
            normal_x = robot_x - closest_x
            normal_y = robot_y - closest_y
            normal_len = math.hypot(normal_x, normal_y)
            if normal_len < 1e-6:
                normal_x, normal_y = 1.0, 0.0
            else:
                normal_x /= normal_len
                normal_y /= normal_len
        else:  # circle
            cx, cy = colliding_obs["center"]
            normal_x = robot_x - cx
            normal_y = robot_y - cy
            normal_len = math.hypot(normal_x, normal_y)
            if normal_len < 1e-6:
                normal_x, normal_y = 1.0, 0.0
            else:
                normal_x /= normal_len
                normal_y /= normal_len

        motion_x = math.cos(robot_theta)
        motion_y = math.sin(robot_theta)
        dot = motion_x * normal_x + motion_y * normal_y
        reflect_x = motion_x - 2 * dot * normal_x
        reflect_y = motion_y - 2 * dot * normal_y
        reflect_theta = math.atan2(reflect_y, reflect_x)
        import random
        perturbation = random.uniform(-math.pi / 12, math.pi / 12)
        reflect_theta += perturbation
        return reflect_theta

    def _find_colliding_obstacle(self) -> dict:
        """找到当前碰撞的障碍物"""
        robot_r = getattr(self, 'robot_radius', 0.2)
        x, y = self.pose.x, self.pose.y
        for obs in self.scenario["obstacles"]:
            if obs["type"] == "circle":
                cx, cy = obs["center"]
                r = obs["radius"]
                dist = math.hypot(x - cx, y - cy)
                if dist < robot_r + r:
                    return obs
            elif obs["type"] == "rect":
                cx, cy = obs["center"]
                w = obs["width"]
                h = obs["height"]
                left = cx - w / 2
                right = cx + w / 2
                bottom = cy - h / 2
                top = cy + h / 2
                closest_x = max(left, min(x, right))
                closest_y = max(bottom, min(y, top))
                dist = math.hypot(x - closest_x, y - closest_y)
                if dist < robot_r or (left <= x <= right and bottom <= y <= top):
                    return obs
        raise RuntimeError("No colliding obstacle found despite collision detection")

    # ----- 传感器循环（同时发布 SENSOR 和 SIMULATION_STATE）-----
    async def _sensor_loop(self):
        """模拟360度全向激光雷达、碰撞传感器，并发布 SIMULATION_STATE 提供真实位姿。"""
        while self._running:
            try:
                await asyncio.sleep(self.sensor_update_interval)

                laser = [2.0] * 360
                for angle in range(360):
                    laser[angle] = self._get_laser_distance(self.pose.x, self.pose.y, angle)

                self.collision_detected = self._check_collision()
                bump_left = self.collision_detected
                bump_right = self.collision_detected

                sim_time = time.monotonic()

                # ----- 发布 SIMULATION_STATE 消息（真实世界状态，位姿唯一来源）-----
                sim_state = SimulationStateMessage(
                    robot_id=self.robot_id,
                    timestamp=sim_time,
                    pose=self.pose,
                    velocity=Velocity(linear=self._current_linear_vel, angular=self._current_angular_vel),
                    collision=self.collision_detected
                )

                # 增加障碍物
                payload = sim_state.model_dump()
                payload["obstacles"] = self.scenario["obstacles"]

                state_msg = Message(
                    type=MessageType.SIMULATION_STATE,
                    source="simulation",
                    payload=payload,
                    priority=Priority.NORMAL
                )
                await self.bus.publish(state_msg)

                # ----- 发布 SENSOR 消息（原始传感器数据）-----
                raw = RawSensorData(
                    robot_id=self.robot_id,
                    timestamp=sim_time,
                    laser=laser,
                    bump_left=bump_left,
                    bump_right=bump_right,
                    cliff_sensors=[False] * 4
                )
                sensor_msg = Message(
                    type=MessageType.SENSOR,
                    source="simulation",
                    payload=raw.model_dump(),
                    priority=Priority.NORMAL
                )
                await self.bus.publish(sensor_msg)

            except Exception as e:
                logger.error(f"Sensor loop error: {e}", exc_info=True)

    # ----- 激光雷达距离计算（保持不变）-----
    def _get_laser_distance(self, x, y, angle_deg):
        """返回从 (x,y) 沿 angle_deg 方向发射的激光与最近圆形障碍物的交点距离"""
        angle_rad = math.radians(angle_deg)
        max_dist = 5.0
        min_dist = max_dist
        vx = math.cos(angle_rad)
        vy = math.sin(angle_rad)

        for obs in self.scenario["obstacles"]:
            if obs["type"] == "circle":
                cx, cy = obs["center"]
                r = obs["radius"]
                dx = cx - x
                dy = cy - y
                a = 1.0
                b = -2.0 * (dx * vx + dy * vy)
                c = dx * dx + dy * dy - r * r
                disc = b * b - 4 * a * c
                if disc < 0:
                    continue
                sqrt_disc = math.sqrt(disc)
                t1 = (-b - sqrt_disc) / (2 * a)
                t2 = (-b + sqrt_disc) / (2 * a)
                t = None
                for ti in (t1, t2):
                    if ti > 0 and (t is None or ti < t):
                        t = ti
                if t is not None and t < min_dist:
                    min_dist = t
            elif obs["type"] == "rect":
                cx, cy = obs["center"]
                w = obs["width"]
                h = obs["height"]
                left = cx - w / 2
                right = cx + w / 2
                bottom = cy - h / 2
                top = cy + h / 2
                t_candidates = []
                if abs(vx) > 1e-6:
                    t_left = (left - x) / vx
                    if t_left > 0:
                        y_at_left = y + vy * t_left
                        if bottom <= y_at_left <= top:
                            t_candidates.append(t_left)
                    t_right = (right - x) / vx
                    if t_right > 0:
                        y_at_right = y + vy * t_right
                        if bottom <= y_at_right <= top:
                            t_candidates.append(t_right)
                if abs(vy) > 1e-6:
                    t_bottom = (bottom - y) / vy
                    if t_bottom > 0:
                        x_at_bottom = x + vx * t_bottom
                        if left <= x_at_bottom <= right:
                            t_candidates.append(t_bottom)
                    t_top = (top - y) / vy
                    if t_top > 0:
                        x_at_top = x + vx * t_top
                        if left <= x_at_top <= right:
                            t_candidates.append(t_top)
                if t_candidates:
                    t = min(t for t in t_candidates if t > 0)
                    if t < min_dist:
                        min_dist = t
        return min_dist

    # ----- 保留但不再主动启动（避免与 ExecutionAgent 冲突）-----
    async def _state_publish_loop(self):
        """定时发布机器人状态（已废弃，不再使用）"""
        while self._running:
            await asyncio.sleep(self.state_publish_interval)
            state_payload = {
                "pose": {
                    "x": round(self.pose.x, 3),
                    "y": round(self.pose.y, 3),
                    "theta": round(self.pose.theta, 3)
                },
                "sensor": {
                    "battery_voltage": round(self.battery_voltage, 2)
                },
                "cleaned_area": round(self.cleaned_area, 2),
                "collision": self.collision_detected
            }
            msg = Message(
                type=MessageType.ROBOT_STATE,
                source="simulation",
                payload=state_payload,
                priority=Priority.NORMAL
            )
            await self.bus.publish(msg)

    async def reload_scenario(self, name: str):
        """重新加载场景，重置环境"""
        self.scenario = copy.deepcopy(load_scenario(name))
        self._predefined_obstacles = self.scenario.get("obstacles", [])
        self._init_from_scenario()
        # 可选：调用 reset 方法（如果已有）
        await self.reset()
        # 重新发布地图元数据
        await self._publish_map_metadata()
        logger.info(f"Scenario reloaded to {name}")

    
    def add_obstacle(self, x: float, y: float, radius: float = 0.3):
        """添加一个动态障碍物（圆形）"""
        from backend.models.physics.environment import Obstacle, ObstacleType
        obs = Obstacle(type=ObstacleType.CIRCLE, center=(x, y), radius=radius, is_dynamic=True)
        self.scenario.setdefault("obstacles", []).append(obs.model_dump())

    def add_obstacles(self, positions: list, radius: float = 0.3):
        """批量添加障碍物: positions = [[x1,y1], [x2,y2], ...]"""
        for x, y in positions:
            self.add_obstacle(x, y, radius)

    def remove_obstacles(self, positions: list, tolerance: float = 0.5):
        """移除指定位置的障碍物"""
        remaining = []
        for obs_dict in self.scenario.get("obstacles", []):
            cx, cy = obs_dict.get("center", (0, 0))
            keep = True
            for px, py in positions:
                if abs(cx - px) < tolerance and abs(cy - py) < tolerance:
                    keep = False
                    break
            if keep:
                remaining.append(obs_dict)
        self.scenario["obstacles"] = remaining

    def clear_obstacles(self):
        """清除所有非墙体障碍物（保留四面墙壁）"""
        walls = []
        for obs in self.scenario.get("obstacles", []):
            if not obs.get("is_dynamic", False):
                walls.append(obs)
        self.scenario["obstacles"] = walls

    async def _publish_map_metadata(self):
            """发布 MAP_METADATA 消息（单独调用）"""
            rooms_data = self.scenario.get("rooms", [])
            if rooms_data:
                from backend.agents.schemas.agent_messages import MapMetadata
                metadata = MapMetadata(rooms=rooms_data)
                msg = Message(
                    type=MessageType.MAP_METADATA,
                    source="simulation",
                    payload=metadata.model_dump(),
                    priority=Priority.NORMAL
                )
                await self.bus.publish(msg)
                logger.info(f"Published MAP_METADATA with {len(rooms_data)} rooms")
