"""
    流水线执行器
"""

from typing import Optional
from backend.models.physics.robot_state import Pose
from backend.agents.schemas.agent_messages import RawSensorData, PerceptionResult, NavCommand
from backend.models.physics.action import MotorCommand
from backend.agents.pipeline.data_preprocessor import preprocess_sensor_data
from backend.agents.pipeline.feature_analyzer import extract_features
from backend.agents.pipeline.command_generator import generate_commands


# 简易路径规划
def plan_path(perception: PerceptionResult, current_pose: Pose) -> NavCommand:
    """简易路径规划：朝前方平稳移动"""
    return NavCommand(
        robot_id=perception.robot_id,
        timestamp=perception.timestamp,
        linear_speed=0.3,
        angular_speed=0.0,
        waypoints=[]
    )

# 流水线主函数
def run_pipeline(
    raw_data: RawSensorData,
    current_pose: Optional[Pose] = None
) -> MotorCommand:
    """
    运行完整流水线，输入原始传感器数据和当前位姿（可选），输出电机指令。
    """
    # L1: 预处理与归一化
    robot_state = preprocess_sensor_data(raw_data)
    if current_pose:
        robot_state.pose = current_pose

    # L2: 特征提取
    perception = extract_features(robot_state)

    # L3: 路径决策
    if not robot_state.pose:
        robot_state.pose = Pose(x=0.0, y=0.0, theta=0.0)

    nav_cmd = plan_path(perception, robot_state.pose)

    # L4: 指令生成
    motor_cmd = generate_commands(nav_cmd)

    return motor_cmd