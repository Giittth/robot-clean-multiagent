"""
    路径建议与最终决策
    基于世界模型（全局障碍物、占用栅格）和当前位姿进行局部路径规划。
"""

import math
from typing import List, Dict, Any, Optional
from backend.models.physics.robot_state import Pose
from backend.models.physics.environment import Obstacle
from backend.agents.schemas.agent_messages import NavCommand


def plan_path(
    world_model: Dict[str, Any],
    current_pose: Pose,
    goal_pose: Optional[Pose] = None,
    safe_distance: float = 0.5,
    max_linear_speed: float = 0.5,
    max_angular_speed: float = 1.0,
) -> NavCommand:
    """
    基于世界模型和当前位姿规划局部路径。

    Args:
        world_model: 世界模型数据，应包含：
            - obstacles: List[Obstacle]  全局障碍物列表（世界坐标）
            - occupancy_grid: 可选的占用栅格（暂未使用，保留扩展）
        current_pose: 当前机器人位姿
        goal_pose: 全局目标点（如果为 None，则沿当前方向前进 2 米）
        safe_distance: 安全距离阈值（米），小于此距离的障碍物将触发避障
        max_linear_speed: 最大线速度（m/s）
        max_angular_speed: 最大角速度（rad/s）

    Returns:
        NavCommand: 包含线速度、角速度和路径点序列
    """
    # 1. 确定局部目标点
    if goal_pose is None:
        # 简单策略：当前方向前方 2 米
        goal_x = current_pose.x + 2.0 * math.cos(current_pose.theta)
        goal_y = current_pose.y + 2.0 * math.sin(current_pose.theta)
        goal = Pose(x=goal_x, y=goal_y, theta=current_pose.theta)
    else:
        goal = goal_pose

    # 2. 检查周围障碍物距离（取最近的）
    obstacles: List[Obstacle] = world_model.get("obstacles", [])
    min_dist = safe_distance  # 初始安全距离
    closest_obs_angle = 0.0

    for obs in obstacles:
        # 获取障碍物中心（支持 circle 和 rectangle）
        if hasattr(obs, 'center'):
            ox, oy = obs.center
        elif isinstance(obs, dict):
            ox, oy = obs.get("center", (0, 0))
        else:
            continue

        dx = ox - current_pose.x
        dy = oy - current_pose.y
        dist = math.hypot(dx, dy)
        # 考虑障碍物半径（如果是圆形）或半宽半高（矩形），简化处理取半径/半宽
        if hasattr(obs, 'radius') and obs.radius:
            dist -= obs.radius
        elif hasattr(obs, 'width') and obs.width:
            dist -= max(obs.width, obs.height) / 2.0

        if dist < min_dist:
            min_dist = dist
            # 计算障碍物相对角度
            closest_obs_angle = math.atan2(dy, dx)

    # 3. 速度决策（简单的反应式避障）
    linear_speed = max_linear_speed
    angular_speed = 0.0

    if min_dist < safe_distance * 0.6:   # 非常近，快速转向
        linear_speed = 0.1
        # 根据障碍物方向决定转向：如果障碍物在右侧则向左转，反之向右
        if closest_obs_angle > 0:
            angular_speed = max_angular_speed   # 向左转
        else:
            angular_speed = -max_angular_speed  # 向右转
        # 调整目标朝向
        goal.theta = current_pose.theta + angular_speed * 0.5
    elif min_dist < safe_distance:         # 接近障碍物，减速轻微转向
        linear_speed = max_linear_speed * 0.5
        # 轻微避开
        if closest_obs_angle > 0:
            angular_speed = max_angular_speed * 0.5
        else:
            angular_speed = -max_angular_speed * 0.5
        goal.theta = current_pose.theta + angular_speed * 0.5

    # 4. 生成路径点（用于可视化）
    waypoints = []
    # 如果角速度不为0，先添加一个原地旋转点
    if abs(angular_speed) > 0.05:
        waypoints.append(Pose(x=current_pose.x, y=current_pose.y, theta=goal.theta))
    waypoints.append(goal)

    # 5. 极近距离情况下尝试后退
    if min_dist < 0.2:
        back_x = current_pose.x - 0.5 * math.cos(current_pose.theta)
        back_y = current_pose.y - 0.5 * math.sin(current_pose.theta)
        waypoints.insert(0, Pose(x=back_x, y=back_y, theta=current_pose.theta))

    # 6. 构建 NavCommand（注意 timestamp 和 robot_id 需要外部传入）
    return NavCommand(
        robot_id="",          # 由调用者填充
        timestamp=0.0,        # 由调用者填充
        waypoints=waypoints,
        linear_speed=linear_speed,
        angular_speed=angular_speed,
    )


# 保留旧接口标记为废弃（避免破坏现有调用）
def plan_path_legacy(perception, current_pose: Pose) -> NavCommand:
    """
    旧版本：基于 PerceptionResult 规划路径（已废弃，请使用 plan_path）
    """
    import warnings
    warnings.warn("plan_path_legacy is deprecated, use plan_path with world_model dict", DeprecationWarning)

    # 构建兼容的 world_model 字典（仅转换必要的 obstacles）
    obstacles = []
    for obs in perception.obstacles:
        # 兼容不同字段
        if hasattr(obs, 'position'):
            center = obs.position
        elif hasattr(obs, 'center'):
            center = obs.center
        else:
            continue
        obstacles.append({"center": center, "radius": getattr(obs, 'radius', 0.2)})
    world_model = {"obstacles": obstacles}
    return plan_path(world_model, current_pose)