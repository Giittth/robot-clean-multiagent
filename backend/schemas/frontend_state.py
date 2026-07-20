"""
前端状态数据传输对象（DTO）
定义推送给 WebSocket 客户端的数据结构，与业务模型解耦。
"""

from pydantic import BaseModel
from typing import List, Optional


class PoseDTO(BaseModel):
    """机器人位姿"""
    x: float
    y: float
    theta: float

class SensorDTO(BaseModel):
    """传感器数据"""
    battery_voltage: float
    collision: bool
    laser: List[float] = []       # 360个激光距离值

class ActionDTO(BaseModel):
    """当前执行的动作（目标速度）"""
    linear: float
    angular: float

class ObstacleDTO(BaseModel):
    """障碍物信息（简化版）"""
    type: str                     # "circle" 或 "rect"
    center: List[float]           # 中心坐标 [x, y]
    radius: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None

class FrontendRobotState(BaseModel):
    """推送给前端的完整机器人状态"""
    pose: PoseDTO
    sensor: SensorDTO
    cleaned_area: float
    action: ActionDTO
    rag_advice: str
    obstacles: List[ObstacleDTO] = []
    # 任务状态字段
    task_state: str = "idle"
    task_id: Optional[str] = None
    progress: float = 0.0
    # 新增：机器人电源状态
    power_state: str = "OFF"   # 可选值: off, starting, idle, working, charging, paused, emergency_stop
    # 覆盖地图（栅格数据，100x100）
    coverage_grid: list = []