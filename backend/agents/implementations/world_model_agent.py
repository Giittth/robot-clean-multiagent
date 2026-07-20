"""
WorldModelAgent 世界模型智能体
核心职责：
1. 接收感知数据、机器人状态数据，融合构建全局环境模型
2. 维护占用栅格地图、障碍物记忆、机器人轨迹、清扫覆盖率
3. 定时对外发布统一 WORLD_MODEL 消息，供导航、决策模块使用
4. 架构约束：仅订阅 PERCEPTION / ROBOT_STATE，仅发布 WORLD_MODEL，禁止转发 SIMULATION_STATE
"""

import asyncio
import math
from datetime import datetime
from collections import deque
from typing import Dict, List, Optional

from backend.agents.implementations.base_agent import BaseAgent
from backend.agents.schemas.agent_messages import WorldModelPayload, RobotStateMessage, WorldModelStatus, \
    MapMetadata, RoomsReady, RoomsUpdate
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.agents.utils.coordinate import CoordinateTransformer
from backend.models.cognition.coverage_map import CoverageMap
from backend.models.cognition.room import Room
from backend.models.cognition.world_model import GlobalWorldState
from backend.models.physics.robot_state import RobotState, Pose, SensorData
from backend.models.physics.environment import EnvironmentState, GridMap, Obstacle, ObstacleType
from backend.utils.logger_handler import logger


class WorldModelAgent(BaseAgent):
    def __init__(self, agent_id: str, agent_type: str, message_bus, registry):
        super().__init__(agent_id, agent_type, message_bus, registry)
        # ====================== 全局世界状态 ======================
        # 顶层世界状态容器：环境信息 + 机器人轨迹
        self.world_state = GlobalWorldState(environment=EnvironmentState(map_id="global_map"), trajectory=[])
        # 障碍物记忆池：存放历史观测障碍物，做短期记忆与置信度衰减
        self.obstacle_memory = []
        # 当前最新机器人完整状态
        self.robot_state: Optional[RobotState] = None
        # 机器人历史轨迹队列，限制最大长度防止内存溢出
        self.pose_history = deque(maxlen=5000)

        # ====================== 栅格地图配置 ======================
        self.map_width = 200        # 地图宽度（格数）
        self.map_height = 200       # 地图高度（格数）
        self.resolution = 0.1       # 单格分辨率：0.1米/格

        # 初始化空占用栅格地图 0=未知 1=空闲 2=障碍物 3=已清扫
        self.world_state.environment.grid = GridMap(
            width=self.map_width,
            height=self.map_height,
            resolution=self.resolution,
            occupancy=[[0 for _ in range(self.map_width)] for _ in range(self.map_height)]
        )

        # 地图原点：世界坐标 -> 栅格坐标 偏移量（地图中心为原点）
        self.origin_x = self.map_width // 2
        self.origin_y = self.map_height // 2
        # 坐标转换器：统一世界坐标与栅格坐标互转
        self.coord_trans = CoordinateTransformer(
            resolution=self.resolution,
            origin_offset=self.origin_x
        )

        # ====================== 业务统计缓存 ======================
        self.cleaned_cells = set()          # 已清扫栅格集合，用于计算覆盖率
        self.dynamic_obstacles: Dict[str, Obstacle] = {}  # 预留：动态障碍物缓存

        # ====================== 消息发布配置 ======================
        self.publish_interval = 0.5         # 世界模型定时发布间隔(秒)

        # 增量更新标记：记录上一轮障碍物栅格，用于局部刷新（提升性能）
        self._last_obstacle_cells = set()

        # 区域名称 -> Room 对象
        self.rooms: Dict[str, Room] = {}

        self.coverage_map = CoverageMap(
            width=self.map_width,
            height=self.map_height,
            resolution=self.resolution,
            origin_x= -self.map_width//2 * self.resolution,
            origin_y= -self.map_height//2 * self.resolution,
            data=[[0 for _ in range(self.map_width)] for _ in range(self.map_height)]
        )

        self._last_coverage_update = None  # 记录上次更新时的位姿 (x, y)
        self._coverage_update_distance = 0.2  # 每移动 0.2 米更新一次

    # ====================== 生命周期方法 ======================
    async def on_start(self):
        """Agent 启动：注册订阅 + 启动定时发布任务"""
        # 订阅感知结果、机器人状态两类消息
        await self.subscribe(MessageType.PERCEPTION, self.handle_perception)
        await self.subscribe(MessageType.ROBOT_STATE, self.handle_robot_state)
        await self.subscribe(MessageType.MAP_METADATA, self.handle_map_metadata)

        asyncio.create_task(self._world_publish_loop())

    async def on_stop(self):
        """Agent 停止回调"""
        logger.info(f"WorldModelAgent [{self.agent_id}] stopped")

    def get_room(self, name: str):
        return self.rooms.get(name)

    # ====================== 感知数据处理 ======================
    async def handle_perception(self, msg: Message):
        """
        接收 PerceptionAgent 下发的感知障碍物数据
        :param msg: 总线消息，payload 包含 timestamp、obstacles 列表
        """
        try:
            payload = msg.payload
            sensor_time = payload.get("timestamp")
            # 校验时间戳，无时间戳直接丢弃
            if sensor_time is None:
                logger.warning("PERCEPTION message missing timestamp, skip")
                return

            # # 使用感知数据更新障碍物与栅格地图
            # self._update_from_perception(payload, sensor_time)

        except Exception as e:
            logger.error(f"WorldModelAgent handle_perception error: {e}", exc_info=True)

    def _update_from_perception(self, payload: dict, sensor_time: float):
        """
        解析感知障碍物，融合进世界模型并刷新栅格地图
        :param payload: 感知原始数据
        :param sensor_time: 感知数据时间戳
        """
        # 提取感知到的障碍物列表
        obstacles_data = payload.get("obstacles", [])
        new_obstacles = []

        # 获取当前机器人位姿
        if self.robot_state is None:
            return  # 没有位姿，无法转换，丢弃
        pose = self.robot_state.pose
        cos_t = math.cos(pose.theta)
        sin_t = math.sin(pose.theta)

        for obs in obstacles_data:
            if isinstance(obs, dict):
                o = Obstacle(**obs)
            else:
                o = obs

            # 局部坐标 → 世界坐标
            lx, ly = o.center[0], o.center[1]
            wx = pose.x + lx * cos_t - ly * sin_t
            wy = pose.y + lx * sin_t + ly * cos_t
            o.center = (wx, wy)
            new_obstacles.append(o)

        self._merge_obstacles(new_obstacles, current_time=sensor_time)
        self._rebuild_obstacle_layer()

        for o in new_obstacles:
            logger.debug(
                f"[WM] obstacle world pos: ({o.center[0]:.2f}, {o.center[1]:.2f}), robot=({pose.x:.2f},{pose.y:.2f})")

    # ====================== 机器人状态处理 ======================
    async def handle_robot_state(self, msg: Message):
        """接收机器人位姿、速度、电量，更新状态记录（覆盖更新已迁移至 NavigationAgent）。"""
        try:
            payload = {
                "robot_id": msg.payload.get("robot_id", "robot_001"),
                "timestamp": msg.payload.get("timestamp", 0),
                "pose": msg.payload.get("pose", {"x": 0.0, "y": 0.0, "theta": 0.0}),
                "velocity": msg.payload.get("velocity", {"linear": 0.0, "angular": 0.0}),
                "target_velocity": msg.payload.get("target_velocity", {"linear": 0.0, "angular": 0.0}),
                "battery": msg.payload.get("battery", {"percentage": 100.0}),
            }
            robot_state_msg = RobotStateMessage(**payload)
            pose = robot_state_msg.pose

            if self.robot_state is None:
                self.robot_state = RobotState(robot_id="robot_001", pose=pose, sensor=SensorData())
            else:
                self.robot_state.pose = pose

            self.pose_history.append(pose)

            # 静态障碍物
            static_obstacles = msg.payload.get("obstacles", [])
            if static_obstacles:
                self.world_state.environment.obstacles = [
                    Obstacle(**obs) for obs in static_obstacles
                ]
                self._rebuild_obstacle_layer()

        except Exception as e:
            logger.error(f"WorldModel handle_robot_state error: {e}", exc_info=True)

    async def handle_map_metadata(self, msg: Message):
        """接收仿真环境发送的区域定义，更新 self.rooms 并初始化 coverage_map 相关数据"""
        try:
            # 解析 MAP_METADATA 消息
            metadata = MapMetadata(**msg.payload)
            self.rooms.clear()
            for room_data in metadata.rooms:
                polygon = [(float(p[0]), float(p[1])) for p in room_data["polygon"]]
                entry = tuple(room_data["entry_point"]) if room_data.get("entry_point") else None
                center = tuple(room_data["center"]) if room_data.get("center") else None
                room = Room(
                    name=room_data["name"],
                    polygon=polygon,
                    entry_point=entry,
                    center=center
                )
                self.rooms[room.name] = room
            logger.info(f"WorldModelAgent: Loaded {len(self.rooms)} rooms from MAP_METADATA")

            # 如果需要，可以在这里根据房间的多边形初始化 coverage_map 的某些区域标记
            # 例如：将房间内的栅格初始化为未覆盖（默认已经是0），或者记录房间的边界供查询

            # 构造所有房间的序列化数据（用于推送）
            rooms_data = {}
            for name, room in self.rooms.items():
                rooms_data[name] = {
                    "polygon": room.polygon,
                    "entry_point": room.entry_point,
                    "center": room.center
                }

            # 发布 ROOMS_UPDATE 消息（完整房间数据）
            update_msg = RoomsUpdate(rooms=rooms_data)
            await self.publish(
                msg_type=MessageType.ROOMS_UPDATE,
                payload=update_msg.model_dump(),
                priority=Priority.NORMAL
            )
            logger.debug("Published ROOMS_UPDATE event")
            # 再发布 ROOMS_READY（房间名称列表）
            rooms_ready_msg = RoomsReady(rooms=list(self.rooms.keys()))
            await self.publish(
                msg_type=MessageType.ROOMS_READY,
                payload=rooms_ready_msg.model_dump(),
                priority=Priority.NORMAL
            )
            logger.debug("Published ROOMS_READY event")

        except Exception as e:
            logger.error(f"Failed to handle MAP_METADATA: {e}", exc_info=True)

    # ====================== 栅格地图操作 ======================
    def _update_obstacle_to_grid(self, obstacle: Obstacle):
        """将单个障碍物绘制到占用栅格地图中"""
        grid = self.world_state.environment.grid
        if grid is None:
            return

        # 圆形障碍物绘制
        if obstacle.type == ObstacleType.CIRCLE:
            cx, cy = obstacle.center
            radius = obstacle.radius or 0.2
            gx, gy = self.coord_trans.world_to_grid(cx, cy)
            r = int(radius / self.resolution) + 1

            for y in range(-r, r + 1):
                for x in range(-r, r + 1):
                    if x * x + y * y <= r * r:
                        nx = gx + x
                        ny = gy + y
                        if self._valid_grid(nx, ny):
                            grid.occupancy[ny][nx] = 2
                            self._last_obstacle_cells.add((nx, ny))

        # 矩形障碍物绘制
        elif obstacle.type == ObstacleType.RECTANGLE:
            cx, cy = obstacle.center
            w = obstacle.width or 0.2
            h = obstacle.height or 0.2
            gx, gy = self.coord_trans.world_to_grid(cx, cy)
            half_w = int((w / self.resolution) / 2) + 1
            half_h = int((h / self.resolution) / 2) + 1

            for y in range(-half_h, half_h + 1):
                for x in range(-half_w, half_w + 1):
                    nx = gx + x
                    ny = gy + y
                    if self._valid_grid(nx, ny):
                        grid.occupancy[ny][nx] = 2
                        self._last_obstacle_cells.add((nx, ny))

    def _valid_grid(self, x: int, y: int) -> bool:
        """栅格坐标边界校验，防止越界访问"""
        return 0 <= x < self.map_width and 0 <= y < self.map_height

    # ====================== 定时发布世界模型 ======================
    async def _world_publish_loop(self):
        """后台循环：定时组装并发布 WORLD_MODEL 消息（架构唯一出口）"""
        while self._running:
            try:
                await asyncio.sleep(self.publish_interval)

                # 计算清扫覆盖率、更新时间戳
                coverage = self._calculate_coverage()
                self.world_state.timestamp = datetime.utcnow().timestamp()
                self.world_state.cleaned_area = len(self.cleaned_cells) * (self.resolution ** 2)

                # 序列化栅格地图
                grid_dict = self.world_state.environment.grid.model_dump() if self.world_state.environment.grid else None
                # 将 coverage_map.data 深拷贝一份，避免后续修改影响已发布的消息
                coverage_grid_data = [row[:] for row in self.coverage_map.data] if hasattr(self, 'coverage_map') else None

                # 组装对外发布的世界模型报文
                payload_model = WorldModelPayload(
                    timestamp=self.world_state.timestamp,
                    robot_state=self.robot_state.model_dump() if self.robot_state else None,
                    obstacles=[obs.model_dump() for obs in self.world_state.environment.obstacles],
                    map=grid_dict,
                    coverage_percent=coverage,
                    cleaned_area=self.world_state.cleaned_area,
                    trajectory_length=len(self.pose_history),
                    system_status=WorldModelStatus.RUNNING,
                    coverage_grid=coverage_grid_data
                )

                # 严格只发布 WORLD_MODEL，禁止使用 SIMULATION_STATE，避免消息回环
                await self.publish(
                    msg_type=MessageType.WORLD_MODEL,
                    payload=payload_model.model_dump(),
                    priority=Priority.NORMAL
                )
            except Exception as e:
                logger.error(f"World publish loop error: {e}", exc_info=True)

    def _calculate_coverage(self) -> float:
        """计算全局清扫覆盖率（百分比）"""
        total_cells = self.map_width * self.map_height
        if total_cells == 0:
            return 0.0
        return (len(self.cleaned_cells) / total_cells) * 100.0

    # ====================== 障碍物记忆与融合逻辑 ======================
    def _merge_obstacles(self, new_obstacles: List[Obstacle], current_time: float):
        """
        障碍物融合：新感知 + 历史记忆 + 置信度衰减
        规则：
        1. 距离相近判定为同一障碍物，更新位置与置信度
        2. 长期未观测到的障碍物置信度逐步衰减，低于0则清除
        """
        # 匹配并更新已有障碍物
        for new_obs in new_obstacles:
            matched = False
            for memory in self.obstacle_memory:
                old_obs = memory["obstacle"]
                # 欧式距离判断是否为同一障碍物
                dist = math.hypot(
                    old_obs.center[0] - new_obs.center[0],
                    old_obs.center[1] - new_obs.center[1]
                )
                if dist < 1.5:
                    memory["obstacle"] = new_obs
                    memory["last_seen"] = current_time
                    memory["confidence"] = min(1.0, memory["confidence"] + 0.1)
                    matched = True
                    break
            # 全新障碍物，加入记忆池
            if not matched:
                self.obstacle_memory.append({
                    "obstacle": new_obs,
                    "last_seen": current_time,
                    "confidence": 0.5
                })

        # 置信度衰减 + 过滤失效障碍物
        filtered_memory = []
        for memory in self.obstacle_memory:
            time_age = current_time - memory["last_seen"]
            # 超过5秒未观测，置信度下降
            if time_age > 30.0:
                memory["confidence"] -= 0.01
            # 置信度大于0则保留
            if memory["confidence"] > 0:
                filtered_memory.append(memory)

        self.obstacle_memory = filtered_memory
        # 同步到顶层世界状态
        self.world_state.environment.obstacles = [m["obstacle"] for m in self.obstacle_memory]

    def _rebuild_obstacle_layer(self):
        """增量刷新障碍物栅格：只清除上一轮障碍物，再重新绘制"""
        grid = self.world_state.environment.grid
        if grid is None:
            return

        # 清空上一轮障碍物标记，还原为空闲格
        for (x, y) in self._last_obstacle_cells:
            if self._valid_grid(x, y) and grid.occupancy[y][x] == 2:
                grid.occupancy[y][x] = 1
        self._last_obstacle_cells.clear()

        # 绘制当前最新所有障碍物
        for obs in self.world_state.environment.obstacles:
            self._update_obstacle_to_grid(obs)

    def get_coverage_percent(self) -> float:
        """对外提供覆盖率查询接口"""
        return self._calculate_coverage()