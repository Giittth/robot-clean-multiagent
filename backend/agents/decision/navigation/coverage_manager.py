from typing import List, Optional, Tuple
from collections import deque
from backend.models.physics.robot_state import Pose
from backend.agents.utils.coordinate import CoordinateTransformer
from backend.utils.logger_handler import logger


class CoverageManager:
    def __init__(self, coord_trans: CoordinateTransformer, sweep_width: float = 0.4):
        self.coord_trans = coord_trans
        self.sweep_width = sweep_width

    def update_coverage(self, pose: Pose, coverage_grid, radius: float = 0.25):
        """将机器人当前位置标记为已覆盖（圆形区域）"""
        gx, gy = self.coord_trans.world_to_grid(pose.x, pose.y)
        cell_radius = int(radius / self.coord_trans.resolution) + 1
        rows = len(coverage_grid)
        cols = len(coverage_grid[0]) if rows > 0 else 0
        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                if dx * dx + dy * dy <= cell_radius * cell_radius:
                    nx, ny = gx + dx, gy + dy
                    if 0 <= ny < rows and 0 <= nx < cols:
                        if coverage_grid[ny][nx] == 0:
                            coverage_grid[ny][nx] = 1

    def generate_lawnmower_path(self, polygon: List[Tuple[float, float]]) -> List[Pose]:
        """
        基于房间的多边形生成弓字形全覆盖路径（世界坐标），返回 Pose 列表。
        每个路径点之间的距离为 sweep_width（米）。
        """
        if not polygon:
            logger.warning("Empty polygon, cannot generate coverage path")
            return []
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        sweep_width = self.sweep_width        # 例如 0.6
        y_start = min_y + sweep_width / 2
        y_end = max_y
        x_left = min_x
        x_right = max_x

        path = []
        direction = 1   # 1: left->right, -1: right->left
        y = y_start
        while y <= y_end:
            if direction == 1:
                # 从左到右：添加左端点和右端点
                path.append(Pose(x=x_left, y=y, theta=0.0))
                path.append(Pose(x=x_right, y=y, theta=0.0))
            else:
                # 从右到左：添加右端点和左端点
                path.append(Pose(x=x_right, y=y, theta=0.0))
                path.append(Pose(x=x_left, y=y, theta=0.0))
            y += sweep_width
            direction *= -1
        return path

    def get_next_target(
        self,
        current_pose: Pose,
        coverage_grid: List[List[int]],
        obstacle_grid: List[List[int]],
        task_region_polygon: Optional[List[Tuple[float, float]]] = None
    ) -> Optional[Pose]:
        gx, gy = self.coord_trans.world_to_grid(current_pose.x, current_pose.y)
        # 检查起点是否有效
        if not (0 <= gx < len(coverage_grid[0]) and 0 <= gy < len(coverage_grid)):
            return None
        if obstacle_grid[gy][gx] == 1:  # 起点在障碍物中，无法继续
            return None

        def is_uncovered(gx, gy):
            if not (0 <= gx < len(coverage_grid[0]) and 0 <= gy < len(coverage_grid)):
                return False
            # 未覆盖且不是障碍物（空闲）
            return coverage_grid[gy][gx] == 0 and obstacle_grid[gy][gx] == 0

        target_grid = self._bfs_find_nearest(obstacle_grid, gx, gy, is_uncovered)
        if target_grid:
            wx, wy = self.coord_trans.grid_to_world(target_grid[0], target_grid[1])
            return Pose(x=wx, y=wy, theta=0.0)
        return None

    @staticmethod
    def _bfs_find_nearest(grid: List[List[int]], start_gx: int, start_gy: int,
                          target_condition) -> Optional[Tuple[int, int]]:
        rows = len(grid)
        cols = len(grid[0]) if rows > 0 else 0
        visited = [[False] * cols for _ in range(rows)]
        q = deque()
        q.append((start_gx, start_gy))
        visited[start_gy][start_gx] = True

        while q:
            gx, gy = q.popleft()
            if target_condition(gx, gy):
                return (gx, gy)
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                nx, ny = gx + dx, gy + dy
                if 0 <= nx < cols and 0 <= ny < rows and not visited[ny][nx]:
                    # 只有空闲格子才能作为路径（障碍物不可通行）
                    if grid[ny][nx] == 0:
                        visited[ny][nx] = True
                        q.append((nx, ny))
        return None