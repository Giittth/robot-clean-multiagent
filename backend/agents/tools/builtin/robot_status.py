"""机器人状态查询工具：电量、位置、运行状态、当前任务"""
from typing import Dict, Any, Callable
from backend.agents.tools.base_tool import BaseTool, ToolResult


class RobotStatusTool(BaseTool):
    """查询机器人实时状态：电量、位置、运行模式、当前任务等。"""

    name = "robot_status"
    description = (
        "查询机器人实时状态，包括电量、位置、运行模式、当前任务、电源状态。"
        "回答'现在电量多少''机器人在哪''正在做什么'等问题"
    )
    parameters = {
        "aspect": {
            "type": "string",
            "enum": ["all", "battery", "position", "task", "power"],
            "description": "要查询的方面：all=全部, battery=电量, position=位置, task=当前任务, power=电源状态",
        },
    }

    def __init__(self, get_robot_state: Callable[[], Dict[str, Any]],
                 get_power_state: Callable[[], str]):
        self._get_state = get_robot_state
        self._get_power = get_power_state

    async def execute(self, aspect: str = "all", **kwargs) -> ToolResult:
        state = self._get_state() or {}
        power = self._get_power() or "?"
        battery = state.get("battery", {})
        pose = state.get("pose", {})

        parts = []
        if aspect in ("all", "battery"):
            voltage = battery.get("voltage", "?")
            percent = battery.get("percent", "?")
            charging = "充电中" if battery.get("charging") else "未充电"
            parts.append(f"电量: {voltage}V ({percent}%) {charging}")

        if aspect in ("all", "position"):
            x = pose.get("x", 0.0)
            y = pose.get("y", 0.0)
            parts.append(f"位置: ({x:.2f}, {y:.2f})")

        if aspect in ("all", "power"):
            power_cn = {
                "OFF": "关机", "BOOTING": "启动中", "IDLE": "空闲",
                "WORKING": "工作中", "CHARGING": "充电中", "PAUSED": "已暂停",
                "EMERGENCY_STOP": "急停", "ERROR": "错误",
            }.get(power, power)
            parts.append(f"电源状态: {power_cn}")

        if aspect in ("all", "task"):
            collision = state.get("collision", False)
            action = state.get("action", {})
            if action.get("linear") or action.get("angular"):
                parts.append("当前动作: 移动中")
            elif collision:
                parts.append("状态: 检测到碰撞")
            else:
                parts.append("状态: 静止")

        return ToolResult(success=True, data={
            "answer": "\n".join(parts),
            "battery_voltage": battery.get("voltage"),
            "battery_percent": battery.get("percent"),
            "position": {"x": pose.get("x"), "y": pose.get("y")},
            "power_state": power,
        })
