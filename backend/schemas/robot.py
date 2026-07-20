from pydantic import BaseModel
from typing import List, Dict, Any, Optional


# 用于 /api/robot/state 的响应模型
class PoseModel(BaseModel):
    x: float
    y: float
    theta: float

class RobotStateResponse(BaseModel):
    pose: PoseModel
    battery: float
    cleaned_area: float
    collision: bool

# 用于 /api/robot/task 和 /api/robot/control 的请求模型
class TaskRequest(BaseModel):
    text: str

class ControlRequest(BaseModel):
    command: str