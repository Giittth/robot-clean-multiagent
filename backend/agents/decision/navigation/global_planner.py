import math
from typing import List
from backend.models.physics.robot_state import Pose
from backend.agents.utils.coordinate import CoordinateTransformer
from backend.agents.utils.path_planner import PathPlanner
from backend.utils.logger_handler import logger


class GlobalPlanner:
    def __init__(self, coord_trans: CoordinateTransformer):
        self.coord_trans = coord_trans

    def plan(self, start: Pose, goal: Pose, obstacle_grid: List[List[int]]) -> List[Pose]:
        # 世界坐标 → 栅格坐标 (gx, gy)
        start_gx, start_gy = self.coord_trans.world_to_grid(start.x, start.y)
        goal_gx, goal_gy = self.coord_trans.world_to_grid(goal.x, goal.y)

        logger.debug(f"[GlobalPlanner] Plan from ({start.x:.2f},{start.y:.2f}) -> ({goal.x:.2f},{goal.y:.2f})")
        logger.debug(f"[GlobalPlanner] Start grid: ({start_gx},{start_gy}) Goal grid: ({goal_gx},{goal_gy})")

        # 诊断：检查起点终点是否在网格范围内，障碍物密度
        rows, cols = len(obstacle_grid), len(obstacle_grid[0]) if obstacle_grid else 0
        total_cells = rows * cols
        obstacle_count = sum(sum(row) for row in obstacle_grid)
        start_blocked = obstacle_grid[start_gy][start_gx] if (0 <= start_gy < rows and 0 <= start_gx < cols) else -1
        goal_blocked = obstacle_grid[goal_gy][goal_gx] if (0 <= goal_gy < rows and 0 <= goal_gx < cols) else -1
        logger.debug(
            f"[GlobalPlanner] Grid={rows}x{cols}, obstacles={obstacle_count}/{total_cells} "
            f"({100*obstacle_count/max(total_cells,1):.1f}%), "
            f"start({start_gx},{start_gy})={start_blocked}, goal({goal_gx},{goal_gy})={goal_blocked}"
        )

        # PathPlanner 使用 (row, col) 顺序，即 (y, x)
        start_grid = (start_gy, start_gx)
        goal_grid = (goal_gy, goal_gx)

        # 调用 A*
        path_grid = PathPlanner.a_star(start_grid, goal_grid, obstacle_grid)
        if not path_grid:
            logger.warning(f"[GlobalPlanner] A* failed to find path")
            return []
        logger.info(f"[GlobalPlanner] Found path with {len(path_grid)} grid points")

        # 将路径点转换回世界坐标
        world_path = []
        for row, col in path_grid:  # path_grid 中每个点是 (row, col)
            x, y = self.coord_trans.grid_to_world(col, row)
            world_path.append(Pose(x=x, y=y, theta=0.0))

        # ---------- 新增：路径后处理 ----------
        # 1. 抽稀：去除方向变化不大的冗余点
        world_path = self._simplify_path(world_path, angle_threshold=0.15)
        # 2. 平滑：Chaikin 迭代一次
        world_path = self._smooth_path(world_path, iterations=1)
        # --------------------------------

        # 打印前10个点用于调试
        logger.info(f"[GlobalPlanner] Path after processing (first 10): {[(p.x, p.y) for p in world_path[:10]]}")
        return world_path

    def _simplify_path(self, path: List[Pose], angle_threshold: float = 0.15) -> List[Pose]:
        """抽稀：只保留方向变化超过阈值的关键点"""
        if len(path) <= 2:
            return path
        result = [path[0]]
        for i in range(1, len(path) - 1):
            prev = result[-1]
            curr = path[i]
            nxt = path[i + 1]
            angle_in = math.atan2(curr.y - prev.y, curr.x - prev.x)
            angle_out = math.atan2(nxt.y - curr.y, nxt.x - curr.x)
            diff = abs(angle_out - angle_in)
            diff = math.atan2(math.sin(diff), math.cos(diff))
            if diff > angle_threshold:
                result.append(curr)
        result.append(path[-1])
        return result

    def _smooth_path(self, path: List[Pose], iterations: int = 1) -> List[Pose]:
        """Chaikin 平滑"""
        if len(path) < 3:
            return path
        for _ in range(iterations):
            new_path = [path[0]]
            for i in range(len(path) - 1):
                p0 = path[i]
                p1 = path[i + 1]
                q0 = Pose(x=0.75 * p0.x + 0.25 * p1.x, y=0.75 * p0.y + 0.25 * p1.y, theta=0.0)
                q1 = Pose(x=0.25 * p0.x + 0.75 * p1.x, y=0.25 * p0.y + 0.75 * p1.y, theta=0.0)
                new_path.append(q0)
                new_path.append(q1)
            new_path.append(path[-1])
            path = new_path
        return path

    def replan(self, current_pose: Pose, goal: Pose, obstacle_grid: List[List[int]]) -> List[Pose]:
        path = self.plan(current_pose, goal, obstacle_grid)
        if not path:
            return []
        # 强制路径起点为当前机器人位置（避免栅格转换误差导致起点在后方）
        first = path[0]
        if math.hypot(first.x - current_pose.x, first.y - current_pose.y) > 0.01:
            path.insert(0, current_pose)
        return path