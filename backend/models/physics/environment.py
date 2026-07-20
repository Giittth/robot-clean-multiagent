from typing import List, Tuple, Optional, Union
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ObstacleType(str, Enum):
    """障碍物类型"""
    CIRCLE = "circle"
    RECTANGLE = "rect"


class Obstacle(BaseModel):
    """障碍物实体（支持圆形和矩形）"""
    type: ObstacleType
    center: Tuple[float, float]  # 中心点 (x, y) 世界坐标

    # 圆形专用
    radius: Optional[float] = Field(default=None, ge=0, description="圆形半径")

    # 矩形专用
    width: Optional[float] = Field(default=None, ge=0, description="矩形宽度")
    height: Optional[float] = Field(default=None, ge=0, description="矩形高度")

    is_dynamic: bool = Field(default=False, description="是否为动态障碍物")

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        if isinstance(v, str):
            return ObstacleType(v)
        return v

    @field_validator('radius', 'width', 'height')
    @classmethod
    def validate_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("尺寸不能为负数")
        return v

    def model_post_init(self, __context):
        """初始化后验证"""
        if self.type == ObstacleType.CIRCLE and self.radius is None:
            raise ValueError("圆形障碍物必须提供 radius")
        if self.type == ObstacleType.RECTANGLE and (self.width is None or self.height is None):
            raise ValueError("矩形障碍物必须提供 width 和 height")

    class Config:
        extra = "ignore"


class GridMap(BaseModel):
    """栅格地图（占用图）"""
    width: int  # 网格宽度（格数）
    height: int  # 网格高度
    resolution: float  # 每格代表真实米数
    occupancy: List[List[int]] = Field(default_factory=list)  # 0=未知, 1=空闲, 2=障碍物, 3=已清扫

    class Config:
        extra = "ignore"

    def to_compressed_dict(self):
        return {
            "width": self.width,
            "height": self.height,
            "resolution": self.resolution,
            "occupancy": self.occupancy,   # 直接使用，未来可改为 run-length 编码
        }


class EnvironmentState(BaseModel):
    """全局环境状态"""
    map_id: str
    obstacles: List[Obstacle] = Field(default_factory=list)
    grid: Optional[GridMap] = None
    clean_zone: List[Tuple[float, float, float, float]] = Field(default_factory=list)  # 清扫区域 (x1,y1,x2,y2)

    class Config:
        extra = "ignore"
