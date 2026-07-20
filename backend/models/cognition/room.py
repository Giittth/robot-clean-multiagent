"""
Room（区域）数据模型
定义区域的几何信息、入口点等，用于语义导航和区域清扫。
"""

from typing import List, Tuple, Optional
from pydantic import BaseModel


class Room(BaseModel):
    """表示一个语义区域（例如客厅、卧室）"""
    name: str                           # 区域名称，如 "living_room"
    polygon: List[Tuple[float, float]]  # 多边形顶点列表（世界坐标系，顺时针或逆时针）
    entry_point: Optional[Tuple[float, float]] = None  # 推荐入口点（如门的位置）
    center: Optional[Tuple[float, float]] = None       # 区域中心点（可选，自动计算或手动指定）

    def get_center(self) -> Tuple[float, float]:
        """计算多边形中心（质心）"""
        if self.center:
            return self.center
        if not self.polygon:
            return (0.0, 0.0)
        # 简单平均
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        return (sum(xs)/len(xs), sum(ys)/len(ys))

    def contains_point(self, x: float, y: float) -> bool:
        """判断点是否在多边形内（射线法）"""
        if len(self.polygon) < 3:
            return False
        inside = False
        n = len(self.polygon)
        for i in range(n):
            x1, y1 = self.polygon[i]
            x2, y2 = self.polygon[(i+1)%n]
            # 检查射线是否穿过边
            if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1):
                inside = not inside
        return inside