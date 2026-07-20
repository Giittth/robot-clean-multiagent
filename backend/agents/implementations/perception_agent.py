"""
感知智能体
负责接收原始传感器数据 → 预处理 → 特征分析 → 发布环境感知结果
功能：
1. 订阅 SENSOR 消息，获取激光雷达/碰撞/悬崖等原始传感器数据
2. 仅做局部坐标系(base_laser)特征提取，不依赖全局位姿
3. 发布 PERCEPTION 消息（局部坐标系障碍物/特征）
4. 局部坐标 → 世界坐标转换、位姿融合由 WorldModelAgent 负责
"""

from backend.agents.implementations.base_agent import BaseAgent
from backend.agents.schemas.agent_messages import RawSensorData, PerceptionResult, FrameId
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.utils.logger_handler import logger
from backend.agents.pipeline.data_preprocessor import preprocess_sensor_data
from backend.agents.pipeline.feature_analyzer import extract_features


class PerceptionAgent(BaseAgent):
    """感知智能体：原始传感器数据 → 局部坐标系环境特征"""

    def __init__(self, agent_id: str, agent_type: str, message_bus, registry):
        super().__init__(agent_id, agent_type, message_bus, registry)
        # 激光雷达配置（与仿真环境保持一致）
        self.laser_angle_min = -1.5708   # -90度
        self.laser_angle_max = 1.5708    # +90度
        self.laser_max_range = 5.0

    async def on_start(self):
        """仅订阅原始传感器消息"""
        await self.subscribe(MessageType.SENSOR, self.handle_sensor_data)

    async def on_stop(self):
        logger.info(f"PerceptionAgent {self.agent_id} stopped")

    async def handle_sensor_data(self, msg: Message):
        """处理原始传感器数据（激光 + 时间戳）"""
        try:
            # 解析原始传感器数据
            payload = msg.payload.copy()
            if "robot_id" not in payload:
                payload["robot_id"] = "robot_001"
            raw = RawSensorData(**payload)

            # 数据清洗：获取清洗后的激光距离（米）
            cleaned = preprocess_sensor_data(raw, use_median_filter=False)
            laser_ranges = cleaned["laser_cleaned"]
            sensor_time = cleaned["timestamp"]

            # 特征提取：输出激光局部坐标系障碍物
            obstacles = extract_features(
                laser_ranges=laser_ranges,
                angle_min=self.laser_angle_min,
                angle_max=self.laser_angle_max,
                max_range=self.laser_max_range,
                cluster_threshold=0.2,
                min_points_per_cluster=3
            )

            # 构造感知结果：标记为激光局部坐标系
            result = PerceptionResult(
                robot_id=self.agent_id,
                timestamp=sensor_time,
                obstacles=obstacles,
                free_space=[],
                risk_level=0.0,
                local_occupancy=[],
                frame_id=FrameId.BASE_LASER,  # 修正：局部激光坐标系
                ground_type=None
            )

            # 发布感知结果
            await self.publish(
                msg_type=MessageType.PERCEPTION,
                payload=result.model_dump(),
                priority=Priority.HIGH
            )

        except Exception as e:
            logger.error(f"PerceptionAgent failed to process sensor data: {str(e)}", exc_info=True)