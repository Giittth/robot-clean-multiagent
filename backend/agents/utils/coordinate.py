from typing import Tuple
from backend.models.physics.robot_state import Pose

class CoordinateTransformer:
    def __init__(self, resolution: float, origin_offset: int):
        self.resolution = resolution      # 米/格
        self.origin_offset = origin_offset  # 世界原点对应的网格索引

    def world_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        gx = int(x / self.resolution) + self.origin_offset
        gy = int(y / self.resolution) + self.origin_offset
        return (gx, gy)

    def grid_to_world(self, gx: int, gy: int) -> Tuple[float, float]:
        """栅格坐标 (col, row) 转世界坐标"""
        x = (gx - self.origin_offset) * self.resolution
        y = (gy - self.origin_offset) * self.resolution
        return x, y
