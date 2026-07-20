"""
规划上下文：封装规划所需的输入数据
用于将规划所需的所有输入数据打包成一个统一对象，传递给规划器的 plan 方法
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List


class PlanningPolicy(str, Enum):
    """规划策略，影响规划器的选择"""
    DEFAULT = "default"
    FAST = "fast"
    PRECISE = "precise"


@dataclass
class PlannerContext:
    """
    规划上下文，包含用户指令、世界状态、机器人状态、内存数据等。
    """
    robot_id: str           # 机器人标识
    user_command: str       # 用户自然语言指令
    world_state: Dict[str, Any] = field(default_factory=dict)       # 世界模型状态
    robot_state: Dict[str, Any] = field(default_factory=dict)       # 机器人状态
    memory: Dict[str, Any] = field(default_factory=dict)            # 短期/长期记忆数据
    metadata: Dict[str, Any] = field(default_factory=dict)          # 额外元数据
    planning_policy: PlanningPolicy = PlanningPolicy.DEFAULT        # 规划策略（默认、快速、精确），影响规划器选择
    rooms: List[str] = field(default_factory=list)  # 房间的名称列表
    conversation_history: List[Dict[str, str]] = field(default_factory=list)  # 最近对话历史，用于规划上下文感知


    def get_battery(self) -> float:
        """获取电池电压，默认 12.0V"""
        robot = self.robot_state if self.robot_state else self.world_state.get("robot_state", {})
        if isinstance(robot, dict):
            battery = robot.get("battery_voltage", robot.get("battery", {}).get("voltage", 12.0))
        else:
            battery = 12.0
        return float(battery)

    def get_coverage(self) -> float:
        """获取清扫覆盖率"""
        return float(self.world_state.get("coverage_percent", 0.0))

    def get_pose(self) -> Dict[str, float]:
        """获取机器人位姿"""
        robot = self.robot_state if self.robot_state else self.world_state.get("robot_state", {})
        if isinstance(robot, dict):
            return robot.get("pose", {"x": 0.0, "y": 0.0, "theta": 0.0})
        return {"x": 0.0, "y": 0.0, "theta": 0.0}
