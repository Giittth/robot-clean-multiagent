
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.models.physics.robot_state import RobotState
from backend.models.physics.environment import EnvironmentState, Obstacle, GridMap


class GlobalWorldState(BaseModel):
    """
    全局世界模型
    统一状态中心
    """
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    # 当前机器人状态
    robot_state: Optional[RobotState] = None
    # 全局环境状态
    environment: EnvironmentState = Field(default_factory=lambda: EnvironmentState(map_id="default_map"))
    # 历史轨迹
    trajectory: List[tuple] = Field(default_factory=list)
    # 已清扫面积
    cleaned_area: float = 0.0
    # 风险区域
    risk_zones: List[tuple] = Field(default_factory=list)
    # 动态障碍物
    dynamic_obstacles: List[Obstacle] = Field(default_factory=list)

    class Config:
        extra = "ignore"