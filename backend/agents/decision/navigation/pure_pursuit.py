import math
from typing import List, Tuple
from backend.models.physics.robot_state import Pose
from backend.utils.logger_handler import logger


class PurePursuit:
    def __init__(self, max_linear: float, max_angular: float, lookahead_dist: float = 0.6, goal_thresh: float = 0.1):
        self.max_linear = max_linear
        self.max_angular = max_angular
        self.lookahead_dist = lookahead_dist  # 默认值，会被动态覆盖
        self.goal_thresh = goal_thresh

    def compute_command(self, current_pose: Pose, path: List[Pose],
                        front_obstacle_dist: float = 2.0, current_speed: float = 0.5) -> Tuple[float, float]:
        """
        返回 (linear_vel, angular_vel)
        :param current_speed: 当前线速度 (m/s)，用于动态调整前瞻距离
        """
        if not path:
            return 0.0, 0.0

        # 动态前瞻距离：低速时小，高速时大
        lookahead = max(0.4, min(1.2, current_speed * 1.5))
        # 找到前瞻点
        lookahead_point = self._get_lookahead_point(current_pose, path, lookahead)

        # 计算角度差
        dx = lookahead_point.x - current_pose.x
        dy = lookahead_point.y - current_pose.y
        target_angle = math.atan2(dy, dx)
        angle_diff = target_angle - current_pose.theta
        angle_diff = math.atan2(math.sin(angle_diff), math.cos(angle_diff))

        # 基础线速度（受前方障碍物距离影响）
        linear = self.max_linear
        if front_obstacle_dist < 0.3:
            linear = 0.1
        elif front_obstacle_dist < 0.6:
            linear = self.max_linear * (front_obstacle_dist / 0.6)

        # 到达目标附近减速
        dist_to_goal = math.hypot(path[-1].x - current_pose.x, path[-1].y - current_pose.y)
        if dist_to_goal < self.goal_thresh * 2:
            linear = min(linear, self.max_linear * (dist_to_goal / self.goal_thresh))

        # 角度偏差大时降低线速度（避免高速转弯）
        if abs(angle_diff) > 0.5:  # 约28度
            linear *= 0.3
        if abs(angle_diff) > 1.0:  # 约57度
            linear = min(linear, 0.1)

        # 角速度计算（P控制，可改为曲率公式）
        angular = max(-self.max_angular, min(self.max_angular, angle_diff * 1.5))
        return linear, angular

    def _get_lookahead_point(self, current_pose: Pose, path: List[Pose], lookahead_dist: float) -> Pose:
        """
        选择前瞻点：
        1. 优先选择在机器人前方且距离 >= lookahead_dist 的点
        2. 如果没有这样的点，选择前方最近的点（避免直接跳到最后）
        3. 如果前方没有任何点，返回路径最后一个点
        """
        cos_t = math.cos(current_pose.theta)
        sin_t = math.sin(current_pose.theta)
        best_front_point = None
        best_front_dist = float('inf')

        for wp in path:
            dx = wp.x - current_pose.x
            dy = wp.y - current_pose.y
            local_x = dx * cos_t + dy * sin_t
            if local_x < 0:
                continue
            dist = math.hypot(dx, dy)
            if dist >= lookahead_dist:
                return wp
            if dist < best_front_dist:
                best_front_dist = dist
                best_front_point = wp

        if best_front_point is not None:
            return best_front_point

        return path[-1]