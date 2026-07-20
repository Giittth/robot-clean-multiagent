from datetime import datetime
from enum import Enum
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class Pose(BaseModel):
    """位姿：坐标 + 朝向"""
    x: float = 0.0          # 横坐标 (米)
    y: float = 0.0          # 纵坐标 (米)
    theta: float = 0.0      # 朝向角 (弧度)


class SensorData(BaseModel):
    """传感器融合数据"""
    laser_distances: List[float] = Field(default_factory=lambda: [2.0]*360)  # 360°激光雷达
    bump_left: bool = False                # 左侧碰撞传感器
    bump_right: bool = False               # 右侧碰撞传感器
    cliff_sensors: List[bool] = Field(default_factory=lambda: [False]*4)    # 悬崖传感器
    battery_voltage: float = 12.0          # 电池电压 (V)


class RobotState(BaseModel):
    """机器人全局状态"""
    robot_id: str
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    pose: Optional[Pose] = None
    velocity_linear: float = 0.0        # 线速度 (m/s)
    velocity_angular: float = 0.0       # 角速度 (rad/s)
    sensor: SensorData
    coverage_map: Optional[List[List[bool]]] = None  # 清扫覆盖网格

    class Config:
        extra = "ignore"  # 忽略多余字段，防止解析崩溃


class RobotPowerState(str, Enum):
    """机器人电源状态"""
    ON = "ON"
    OFF = "OFF"
    BOOTING = "BOOTING"
    IDLE = "IDLE"
    WORKING = "WORKING"
    CHARGING = "CHARGING"
    PAUSED = "PAUSED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    ERROR = "ERROR"
