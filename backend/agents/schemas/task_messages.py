from typing import Dict, Any, Optional
from pydantic import BaseModel
from backend.models.task.task import Task, TaskState


# Supervisor ↔ Navigation 通信模型
class TaskCommand(BaseModel):
    """Supervisor 下发给 NavigationAgent 的任务指令"""
    task_id: str
    type: str   # "navigate_to", "clean_area", "return_to_charge", "recover_stuck", "stop"
    params: Dict[str, Any] = {}


class TaskStatusReport(BaseModel):
    """NavigationAgent 向 Supervisor 反馈的任务状态"""
    task_id: str
    status: str   # "running", "success", "failed", "blocked"
    details: Optional[Dict[str, Any]] = None


# 用于外部 API 的模型
class TaskCreateRequest(BaseModel):
    type: str
    robot_id: str
    params: Dict[str, Any]


class TaskUpdateMessage(BaseModel):
    task_id: str
    status: TaskState
    metrics: Optional[Dict[str, float]] = None


class TaskResultMessage(BaseModel):
    task: Task
