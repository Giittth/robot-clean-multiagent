"""
GraphSession - 任务图会话状态管理

统一管理一次任务图执行的完整生命周期状态，避免多个组件（GraphExecutor、NavigationAgent、ExecutionAgent）
各自维护分散状态导致不一致。
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GraphSession:
    """
    任务图会话（一次 run 的完整生命周期）
    - graph_id: 静态任务图 ID
    - session_id: 本次执行的唯一标识（每次 run 生成新 UUID）
    - running: 是否正在执行中
    - paused: 是否被用户暂停
    - control_owner: 当前控制权持有者（IDLE / TASK_GRAPH / RECOVERY）
    - external_task_id: 当前正在执行的外部任务 ID（来自 NavigationAgent 等）
    """
    graph_id: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    running: bool = False
    paused: bool = False
    control_owner: str = "IDLE"
    external_task_id: Optional[str] = None

    def reset(self):
        """重置会话状态（但保留 session_id 用于校验）"""
        self.running = False
        self.paused = False
        self.control_owner = "IDLE"
        self.external_task_id = None

    def can_accept_new_task(self) -> bool:
        """判断是否允许下发新任务（会话空闲且无外部任务）"""
        return not self.running and self.external_task_id is None

    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "session_id": self.session_id,
            "running": self.running,
            "paused": self.paused,
            "control_owner": self.control_owner,
            "external_task_id": self.external_task_id,
        }