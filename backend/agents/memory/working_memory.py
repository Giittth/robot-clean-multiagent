
"""短期工作记忆：当前会话上下文"""
import time
from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class TurnRecord:
    step: int = 0
    action: str = ""
    action_input: Dict[str, Any] = field(default_factory=dict)
    observation: str = ""
    timestamp: float = 0.0


class WorkingMemory:
    def __init__(self):
        self.reset()

    def reset(self):
        self.user_command: str = ""
        self.robot_state: Dict[str, Any] = {}
        self.world_state: Dict[str, Any] = {}
        self.rooms: List[str] = []
        self.history: List[TurnRecord] = []

    def set_task(self, command: str):
        self.user_command = command
        self.history = []

    def add_turn(self, record: TurnRecord):
        record.step = len(self.history)
        record.timestamp = time.time()
        self.history.append(record)

    def update_state(self, robot_state=None, world_state=None, rooms=None):
        if robot_state:
            self.robot_state.update(robot_state)
        if world_state:
            self.world_state.update(world_state)
        if rooms is not None:
            self.rooms = rooms

    def get_summary(self) -> str:
        lines = [f"用户指令: {self.user_command}"]
        if self.robot_state:
            bat = self.robot_state.get("battery", {})
            v = bat.get("voltage", "?")
            lines.append(f"机器人状态: 电量={v}V")
        if self.world_state:
            cov = self.world_state.get("coverage_percent", "?")
            lines.append(f"环境: 覆盖率={cov}%")
        if self.rooms:
            lines.append(f"已知房间: {', '.join(self.rooms)}")
        return "\n".join(lines)

    def get_recent_turns(self, n: int = 3) -> List[TurnRecord]:
        return self.history[-n:] if self.history else []

    def last_action(self) -> str:
        if self.history:
            return self.history[-1].action
        return ""
