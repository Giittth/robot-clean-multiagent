"""
    生成执行指令（已废弃，建议直接使用 Velocity 模型）
    将导航命令（线速度、角速度）转换为标准速度指令。
"""

from backend.models.physics.action import Velocity
from backend.agents.schemas.agent_messages import NavCommand


def generate_velocity(
    nav_cmd: NavCommand,
    max_linear: float = 0.8,
    max_angular: float = 1.2,
) -> Velocity:
    """
    将导航命令（线速度、角速度）转换为限幅后的速度指令。

    Args:
        nav_cmd: 导航命令（包含线速度和角速度）
        max_linear: 最大线速度绝对值（m/s）
        max_angular: 最大角速度绝对值（rad/s）

    Returns:
        Velocity: 限幅后的线速度和角速度
    """
    v = nav_cmd.linear_speed
    w = nav_cmd.angular_speed

    v = max(-max_linear, min(v, max_linear))
    w = max(-max_angular, min(w, max_angular))

    return Velocity(linear=v, angular=w)