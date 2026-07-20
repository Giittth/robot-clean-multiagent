from typing import List, Tuple, Optional
from pydantic import BaseModel

class CoverageMap(BaseModel):
    """
    覆盖地图，记录机器人已清扫的栅格单元。
    data 采用行优先（y, x），与 occupancy_grid 保持一致。
    """
    width: int          # 栅格列数（x方向）
    height: int         # 栅格行数（y方向）
    resolution: float   # 米/栅格
    origin_x: float     # 世界坐标原点对应的栅格(0,0)的x坐标（通常为 -width/2 * resolution）
    origin_y: float     # 世界坐标原点对应的栅格(0,0)的y坐标（通常为 -height/2 * resolution）
    data: List[List[int]]  # 0=未覆盖, 1=已覆盖

    def mark_cell(self, gx: int, gy: int):
        """标记单个栅格为已覆盖"""
        if 0 <= gx < self.width and 0 <= gy < self.height:
            self.data[gy][gx] = 1

    def mark_circle(self, cx: float, cy: float, radius: float):
        """
        将世界坐标圆形区域内的栅格标记为已覆盖。
        cx, cy: 世界坐标中心点
        radius: 半径（米）
        """
        gx_center = int((cx - self.origin_x) / self.resolution)
        gy_center = int((cy - self.origin_y) / self.resolution)
        r_grid = int(radius / self.resolution) + 1
        for dy in range(-r_grid, r_grid + 1):
            for dx in range(-r_grid, r_grid + 1):
                if dx*dx + dy*dy <= r_grid*r_grid:
                    gx = gx_center + dx
                    gy = gy_center + dy
                    self.mark_cell(gx, gy)

    def get_coverage_percentage(self) -> float:
        total = self.width * self.height
        if total == 0:
            return 0.0
        covered = sum(sum(row) for row in self.data)
        return covered / total * 100.0

    def get_uncovered_cells_in_polygon(self, polygon: List[Tuple[float, float]]) -> List[Tuple[int, int]]:
        """返回多边形内部所有未覆盖的栅格坐标（栅格索引）"""
        # 简化：计算多边形包围盒，遍历内部栅格，判断点是否在多边形内且未覆盖
        # 这里省略具体实现，后续可补充
        pass