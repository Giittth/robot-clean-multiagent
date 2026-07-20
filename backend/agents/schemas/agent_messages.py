import uuid
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, time

from backend.models.physics.robot_state import Pose, RobotState, SensorData
from backend.models.physics.environment import Obstacle, GridMap
from backend.models.physics.action import Velocity
from backend.models.task.task import TaskType


class FrameId(str, Enum):
    """坐标系标识"""
    BASE_LASER = "base_laser"
    ODOM = "odom"
    WORLD = "world"
    BASE_LINK = "base_link"

class WorldModelStatus(str, Enum):
    """世界模型系统状态"""
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"

class NavigationMode(str, Enum):
    """导航模式"""
    COVERAGE = "COVERAGE"
    FAST = "FAST"
    EDGE = "EDGE"
    SPOT = "SPOT"
    RETURN_HOME = "RETURN_HOME"

class AvoidanceMode(str, Enum):
    """避障模式"""
    STATIC = "STATIC"
    DYNAMIC = "DYNAMIC"
    AGGRESSIVE = "AGGRESSIVE"
    SAFE = "SAFE"

class NavigationStatus(str, Enum):
    """导航状态"""
    PLANNING = "PLANNING"
    TRACKING = "TRACKING"
    BLOCKED = "BLOCKED"
    REPLANNING = "REPLANNING"
    GOAL_REACHED = "GOAL_REACHED"
    FAILED = "FAILED"

class ControlMode(str, Enum):
    """控制模式（用于 EXECUTION 消息）"""
    TRACK_PATH = "TRACK_PATH"
    VELOCITY_CONTROL = "VELOCITY_CONTROL"
    POSITION_CONTROL = "POSITION_CONTROL"
    STOP = "STOP"
    ESTOP = "ESTOP"
    MANUAL = "MANUAL"
    RECOVERY = "RECOVERY"
    BACKUP = "BACKUP"
    HOLD = "HOLD"
    FORCE_CONTROL = "FORCE_CONTROL"


class ControllerState(str, Enum):
    # 定义控制器状态
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"

class ExecutionResult(str, Enum):
    # 执行结果枚举
    IDLE = "IDLE"
    MOVING = "MOVING"
    BLOCKED = "BLOCKED"
    RECOVERING = "RECOVERING"


class TaskResultEvent(BaseModel):
    """统一的任务结果事件载荷"""
    task_id: str
    session_id: str
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None

class NavigationTaskResult(BaseModel):
    """导航任务结果，携带完整上下文信息"""
    task_id: str
    version: int
    success: bool
    goal_reached: bool
    session_id: Optional[str]
    graph_id: Optional[str]
    final_pose: dict          # {"x": float, "y": float}
    path_length: float
    failure_reason: Optional[str] = None   # 建议增加，如 "TIMEOUT", "CANCELLED", "NO_PATH" 等


class RawSensorData(BaseModel):
    """原始传感器数据（来自仿真/硬件）"""
    robot_id: str
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    laser: List[float] = []                          # 激光雷达原始数据
    bump_left: bool = False                          # 左碰撞
    bump_right: bool = False                         # 右碰撞
    cliff_sensors: List[bool] = Field(default_factory=list)  # 悬崖传感器

    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"


class SimulationStateMessage(BaseModel):
    """仿真世界真实状态（唯一位姿来源）"""
    robot_id: str = "robot_001"
    timestamp: float = Field(default_factory=time)
    pose: Pose = Pose(x=0.0, y=0.0, theta=0.0)
    velocity: Velocity = Velocity(linear=0.0, angular=0.0)
    collision: bool = False
    obstacles: List[dict] = []

    class Config:
        exclude_none = False
        extra = "ignore"
        arbitrary_types_allowed = True


class PerceptionResult(BaseModel):
    """
    感知输出结果
    坐标系由 frame_id 标识：当前默认 base_laser 激光局部坐标系
    局部坐标 → 世界坐标转换，统一由 WorldModelAgent 完成
    """
    # 数据时间戳
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    # 机器人标识
    robot_id: str
    # 障碍物列表（坐标系由 frame_id 决定）
    obstacles: List[Obstacle] = Field(default_factory=list)
    # 自由空间点集
    free_space: List[List[float]] = Field(default_factory=list)
    # 环境风险等级 0.0 ~ 1.0
    risk_level: float = 0.0
    # 局部占用栅格
    local_occupancy: List[List[float]] = Field(default_factory=list)
    # 坐标系标识：base_laser / odom / world
    frame_id: FrameId = FrameId.BASE_LASER
    # 地面类型（预留字段）
    ground_type: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"  # 忽略多余字段，兼容扩展


class WorldModelPayload(BaseModel):
    """世界模型广播消息"""
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    robot_state: Optional[RobotState] = None
    obstacles: List[Obstacle] = Field(default_factory=list)
    map: Optional[GridMap] = None          # GridMap 序列化后的字典
    coverage_percent: float = 0.0
    cleaned_area: float = 0.0
    trajectory_length: int = 0
    system_status: WorldModelStatus = WorldModelStatus.RUNNING         # 系统状态，如 RUNNING, STOPPED, ERROR
    coverage_grid: Optional[List[List[int]]] = None

    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"


class NavigationStatusMessage(BaseModel):
    """NAVIGATION 消息：用于前端监控/Supervisor"""
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    target_pose: Dict[str, float]  # {"x": float, "y": float, "theta": float}
    path: List[List[float]]
    navigation_mode: NavigationMode = NavigationMode.COVERAGE
    avoidance_mode: AvoidanceMode = AvoidanceMode.DYNAMIC
    navigation_status: NavigationStatus = NavigationStatus.TRACKING

    class Config:
        use_enum_values = True   # 序列化时输出字符串，而非枚举对象
        extra = "ignore"


class ExecutionCommand(BaseModel):
    """执行器命令（EXECUTION 消息）"""
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    target_velocity: Velocity
    duration: float = 0.2
    control_mode: ControlMode = ControlMode.TRACK_PATH

    class Config:
        use_enum_values = True
        extra = "ignore"


class RobotStateMessage(BaseModel):
    """ROBOT_STATE 消息：机器人状态反馈"""
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    pose: Pose   # {"x": float, "y": float, "theta": float}
    velocity: Velocity   # {"linear": float, "angular": float}
    target_velocity: Velocity  # {"linear": float, "angular": float}
    controller_state: ControllerState = ControllerState.RUNNING
    execution_result: ExecutionResult = ExecutionResult.IDLE
    battery: Dict[str, Any]   # {"voltage": float, "percent": float, "charging": bool}
    collision: bool = False

    class Config:
        use_enum_values = True   # 序列化枚举为字符串
        extra = "ignore"


class UserCommand(BaseModel):
    """用户输入的指令"""
    command_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    timestamp: float = Field(default_factory=time)


class TaskCommand(BaseModel):
    """Supervisor 下发给 NavigationAgent 的任务"""
    task_id: str
    type: TaskType
    params: Dict[str, Any] = Field(default_factory=dict)


# ========== 任务进度/结果事件 Payload 模型 ==========
class NavigationProgressPayload(BaseModel):
    phase: str = "navigation"
    status: str
    progress: float
    current_pose: Dict[str, float]   # {"x": ..., "y": ...}
    target_pose: Dict[str, float]
    remaining_distance: float
    message: str

class NavigationResultPayload(BaseModel):
    phase: str = "navigation"
    success: bool
    goal_reached: bool
    final_pose: Dict[str, float]
    path_length: float
    session_id: Optional[str] = None

class NavigationRequestPayload(BaseModel):
    """NAVIGATION_REQUEST 消息的载荷"""
    task_id: str
    type: str          # 例如 "navigate_to", "clean_area", "return_to_charge", "recover_stuck"
    params: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "ignore"

class ExecutionProgressPayload(BaseModel):
    phase: str = "execution"
    status: str
    progress: float
    brush_speed: int
    suction_power: float
    cleaned_area: float
    message: str

class ExecutionResultPayload(BaseModel):
    phase: str = "execution"
    success: bool
    cleaned_area: float
    coverage_percent: float
    duration: float


def robot_state_from_message(msg: RobotStateMessage, robot_id: str = "robot_001") -> RobotState:
    return RobotState(
        robot_id=robot_id,
        timestamp=msg.timestamp,
        pose=msg.pose,
        velocity_linear=msg.velocity.linear,
        velocity_angular=msg.velocity.angular,
        sensor=SensorData(),
        coverage_map=None
    )


class MapMetadata(BaseModel):
    """仿真环境发送的地图元数据，包含房间的定义等"""
    rooms: List[Dict[str, Any]]   # 每个房间字典包含 name, polygon, entry_point, center 等

class RoomsReady(BaseModel):
    rooms: List[str]

class RoomsUpdate(BaseModel):
    """房间的数据推送消息，包含所有房间的几何信息"""
    rooms: Dict[str, Dict[str, Any]]   # 例如 {"living_room": {"polygon": [...], "entry_point": [...], "center": [...]}}




class NavCommand(BaseModel):
    """导航指令（给执行器）"""
    robot_id: str
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    waypoints: List[Pose] = Field(default_factory=list)
    linear_speed: float = 0.0
    angular_speed: float = 0.0

    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"
