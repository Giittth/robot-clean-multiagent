"""事件类型定义"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum


@dataclass
class Event:
    """通用事件对象"""
    type: str
    source: str
    task_id: Optional[str] = None
    payload: Dict[str, Any] = None


class RuntimeEventType(str, Enum):
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_STATE_CHANGED = "task.state_changed"
    GRAPH_COMPLETED = "graph.completed"


class UIEventType(str, Enum):
    TASK_PROGRESS = "ui.task_progress"
    TASK_RESULT = "ui.task_result"
    NOTIFICATION = "ui.notification"
    GRAPH_STRUCTURE = "ui.graph_structure"
    TASK_NODE_STATUS = "ui.task_node_status"
