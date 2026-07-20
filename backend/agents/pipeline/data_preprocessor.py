"""
    数据清洗与归一化
"""

from typing import List, Dict, Any
from backend.agents.schemas.agent_messages import RawSensorData


def preprocess_sensor_data(raw: RawSensorData, use_median_filter: bool = True) -> Dict[str, Any]:
    """
    原始传感器数据清洗，返回清洗后的真实距离和碰撞状态。
    清洗：激光雷达限幅、可选的中值滤波；碰撞/悬崖去抖动（简单转换）。
    注意：不进行归一化，因为后续需要真实距离（米）进行障碍物聚类。

    Args:
        raw: 原始传感器数据
        use_median_filter: 是否使用中值滤波（默认 True，可关闭以降低延迟）

    Returns:
        字典包含：
            timestamp: float
            laser_cleaned: List[float]  清洗后的激光距离（米），长度与 raw.laser 相同
            bump_left: bool
            bump_right: bool
            cliff_sensors: List[bool]
    """
    # 激光雷达数据清洗
    laser_raw = raw.laser
    # 限幅：将超出 [0.05, 5.0] 米的距离截断到边界
    laser_limited = [max(0.05, min(5.0, d)) for d in laser_raw]

    if use_median_filter:
        # 中值滤波（窗口大小3），去除椒盐噪声
        filtered_laser = []
        window = 3
        half = window // 2
        for i in range(len(laser_limited)):
            start = max(0, i - half)
            end = min(len(laser_limited), i + half + 1)
            window_vals = laser_limited[start:end]
            window_vals.sort()
            median = window_vals[len(window_vals) // 2]
            filtered_laser.append(median)
        laser_cleaned = filtered_laser
    else:
        laser_cleaned = laser_limited

    # 碰撞传感器（直接转换布尔值）
    bump_left = raw.bump_left
    bump_right = raw.bump_right

    # 悬崖传感器
    cliff_sensors = raw.cliff_sensors

    return {
        "timestamp": raw.timestamp,
        "laser_cleaned": laser_cleaned,
        "bump_left": bump_left,
        "bump_right": bump_right,
        "cliff_sensors": cliff_sensors,
    }