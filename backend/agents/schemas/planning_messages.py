from typing import List, Tuple, Optional
from pydantic import BaseModel


class Waypoint(BaseModel):
    x: float
    y: float


class PathPlan(BaseModel):
    """
    全局路径规划结果
    """
    path: List[Waypoint]
    cost: float = 0.0
    success: bool = True