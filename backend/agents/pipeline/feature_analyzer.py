"""
特征提取与障碍物检测
从激光数据中检测障碍物，输出 **激光局部坐标系(base_laser)** 结果
全局坐标转换、位姿融合交由 WorldModelAgent 处理
"""

import math
from typing import List
from backend.models.physics.environment import Obstacle, ObstacleType


def extract_features(
    laser_ranges: List[float],
    angle_min: float = -1.5708,   # -90 deg
    angle_max: float = 1.5708,    # +90 deg
    max_range: float = 5.0,
    cluster_threshold: float = 0.2,
    min_points_per_cluster: int = 3,
) -> List[Obstacle]:
    """
    从激光数据中检测障碍物（输出 base_laser 局部坐标系）。

    Args:
        laser_ranges: 清洗后的激光距离（米），长度 N，按角度递增顺序排列
        angle_min: 激光扫描起始角度（弧度）
        angle_max: 激光扫描结束角度（弧度）
        max_range: 有效最大距离（米），超过此值的点忽略
        cluster_threshold: 聚类距离阈值（米），同一障碍物内点之间的最大距离
        min_points_per_cluster: 形成障碍物的最小点数

    Returns:
        激光局部坐标系下的障碍物列表（圆形）
    """
    if not laser_ranges or len(laser_ranges) == 0:
        return []

    n = len(laser_ranges)
    angle_step = (angle_max - angle_min) / (n - 1) if n > 1 else 0.0

    # 1. 将激光点转换为 激光局部坐标系 (base_laser)
    local_points = []
    for i, r in enumerate(laser_ranges):
        # 忽略无效点（过近或过远）
        if r < 0.05 or r >= max_range - 0.1:
            continue

        # 激光点在机器人/激光坐标系中的角度
        angle_rad = angle_min + i * angle_step
        # 局部坐标系坐标（不再转换到世界坐标）
        local_x = r * math.cos(angle_rad)
        local_y = r * math.sin(angle_rad)

        # === 原有世界坐标转换逻辑（注释保留，不再使用）===
        # world_x = robot_pose.x + local_x * math.cos(robot_pose.theta) - local_y * math.sin(robot_pose.theta)
        # world_y = robot_pose.y + local_x * math.sin(robot_pose.theta) + local_y * math.cos(robot_pose.theta)
        # world_points.append((world_x, world_y))

        local_points.append((local_x, local_y))

    if not local_points:
        return []

    # 2. 简单欧氏距离聚类（基于局部坐标）
    clusters = []
    for p in local_points:
        found = False
        for cluster in clusters:
            # 计算聚类中心
            cx = sum(pt[0] for pt in cluster) / len(cluster)
            cy = sum(pt[1] for pt in cluster) / len(cluster)
            if math.hypot(p[0] - cx, p[1] - cy) < cluster_threshold:
                cluster.append(p)
                found = True
                break
        if not found:
            clusters.append([p])

    # 3. 为每个有效聚类生成圆形障碍物（局部坐标系）
    obstacles = []
    for cluster in clusters:
        if len(cluster) < min_points_per_cluster:
            continue

        # 聚类中心（局部坐标）
        cx = sum(pt[0] for pt in cluster) / len(cluster)
        cy = sum(pt[1] for pt in cluster) / len(cluster)

        # 半径 = 所有点到中心的最大距离 + 安全边距
        max_dist = max(math.hypot(p[0] - cx, p[1] - cy) for p in cluster)
        radius = max_dist + 0.05   # 增加5cm安全边距

        # 限制最小半径（避免过于细小的噪声被当作障碍物）
        radius = max(0.08, min(radius, 0.5))

        obstacles.append(Obstacle(
            type=ObstacleType.CIRCLE,
            center=(cx, cy),
            radius=radius,
            is_dynamic=False,
        ))
    return obstacles
