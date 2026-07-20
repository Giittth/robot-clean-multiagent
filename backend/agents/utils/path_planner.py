"""
    路径规划器
    提供 A* 算法和全覆盖路径生成
"""


import heapq
import math
from typing import List, Tuple, Optional
from backend.utils.logger_handler import logger


class PathPlanner:
    @staticmethod
    def a_star(
            start: Tuple[int, int],         # 起点网格坐标 (row, col)
            goal: Tuple[int, int],          # 终点网格坐标 (row, col)
            grid: List[List[int]],          # 地图网格（0=空闲, 1=障碍）
            allow_diagonal=False            # 是否允许对角线移动
    ) -> Optional[List[Tuple[int, int]]]:   # 返回路径点列表，失败返回 None
        """
        A* 算法，grid: 0=空闲, 1=障碍物。返回从起点到终点的路径点（网格坐标）。
        优化：
        1. 启发函数与移动代价一致
        2. 添加最大迭代次数限制
        3. 支持对角线移动的优化代价
        """

        def heuristic(a, b):
            """根据是否允许对角线，选择合适地启发函数"""
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])

            if allow_diagonal:
                # Octile Distance（对角线距离）
                return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)
            else:
                # Manhattan Distance（曼哈顿距离）
                return dx + dy

        neighbors = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        if allow_diagonal:
            neighbors += [(1, 1), (1, -1), (-1, 1), (-1, -1)]

        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        f_score = {start: heuristic(start, goal)}

        # 添加迭代次数限制，防止长时间搜索
        iterations = 0
        max_iterations = 10000

        while open_set:
            iterations += 1
            if iterations > max_iterations:
                logger.warning(f"A* exceeded max iterations ({max_iterations}), path finding aborted")
                return None

            current = heapq.heappop(open_set)[1]
            if current == goal:
                # 重建路径
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]

            for dx, dy in neighbors:
                neighbor = (current[0] + dx, current[1] + dy)
                if not (0 <= neighbor[0] < len(grid) and 0 <= neighbor[1] < len(grid[0])):
                    continue
                if grid[neighbor[0]][neighbor[1]] == 1:  # 障碍物
                    continue

                # 对角线移动代价为 √2，直线移动代价为 1
                move_cost = math.sqrt(2) if (dx != 0 and dy != 0) else 1.0
                tentative_g = g_score[current] + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = int(tentative_g)
                    f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
        return None


    @staticmethod
    def generate_lawnmower_path(
            rows: int,               # 地图行数
            cols: int,               # 地图列数
            start_row: int = 0,      # 起始行
            start_col: int = 0       # 起始列
    ) -> List[Tuple[int, int]]:      # 返回全覆盖路径点列表
        """
        生成割草机（弓字形）全覆盖路径，返回网格坐标列表。

        Args:
            rows: 地图行数
            cols: 地图列数
            start_row: 起始行
            start_col: 起始列

        Returns:
            路径点列表 [(row, col), ...]
        """
        path = []
        direction = 1  # 1: 向右遍历列, -1: 向左遍历列

        for r in range(start_row, rows):
            if direction == 1:
                # 从左到右
                for c in range(0 if r == start_row else 0, cols):
                    path.append((r, c))
            else:
                # 从右到左
                for c in range(cols - 1, -1, -1):
                    path.append((r, c))

            # 换行时切换方向
            direction *= -1

        return path

    @staticmethod
    def generate_lawnmower_path_obstacle_aware(
            rows: int,
            cols: int,
            obstacle_grid: List[List[int]],  # 障碍物地图
            start_row: int = 0,
            start_col: int = 0
    ) -> List[Tuple[int, int]]:
        """
        优化版本：生成避开障碍物的弓字形全覆盖路径
        预留边界缓冲区，避免贴墙行走
        """
        path = []
        direction = 1  # 1: 向右, -1: 向左

        # 设置边界缓冲区（距离墙壁至少3格 = 0.6米）
        buffer = 3

        for r in range(max(start_row, buffer), rows - buffer):
            if direction == 1:
                # 从左到右，跳过障碍物和边界
                for c in range(buffer, cols - buffer):
                    if obstacle_grid[r][c] == 0:  # 只访问空闲格子
                        path.append((r, c))
            else:
                # 从右到左，跳过障碍物和边界
                for c in range(cols - 1 - buffer, buffer - 1, -1):
                    if obstacle_grid[r][c] == 0:  # 只访问空闲格子
                        path.append((r, c))

            # 换行时切换方向
            direction *= -1

        return path
