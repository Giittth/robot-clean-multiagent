"""
任务图运行时上下文：存储任务状态、结果、共享黑板、事件定义。
"""

from typing import Dict, Any, List
from enum import Enum

from backend.agents.decision.runtime.task_graph import TaskGraph
from backend.models.task.task import TaskState


class GraphStatus(str, Enum):
    """任务图整体的执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class GraphContext:
    """
    运行时上下文，独立于静态图。
    包含共享黑板(shared_state)，用于在不同任务间传递信息。
    """

    def __init__(self, graph_id: str = ""):
        self.graph_id = graph_id
        self.task_status: Dict[str, TaskState] = {}      # 每个任务的状态
        self.task_results: Dict[str, Any] = {}            # 任务执行结果（如输出数据）
        self.dispatch_count: Dict[str, int] = {}          # 任务分发的次数（可用于重试监控）
        self.shared_state: Dict[str, Any] = {}            # 共享黑板，任务间可读写
        self.status = GraphStatus.PENDING                 # 图整体状态
        self.task_version: Dict[str, int] = {}            # task_id -> version
        self._task_ids: List[str] = []                    # 存储任务ID列表，用于reset

    def init_for_graph(self, task_ids: list):
        """根据任务ID列表初始化所有任务状态为 PENDING，并保存任务列表副本"""
        self._task_ids = task_ids[:]  # 深拷贝任务ID列表
        for tid in task_ids:
            self.task_status[tid] = TaskState.PENDING
            self.dispatch_count[tid] = 0
            self.task_version[tid] = 0

    def reset(self):
        """
        重置所有任务状态到初始 PENDING，清空结果和版本号。
        注意：不清空 shared_state（黑板），因为可能保留一些全局信息（如电量阈值）。
        如需完全重置，可调用 clear_shared_state() 自行处理。
        """
        self.task_status.clear()
        self.task_results.clear()
        self.dispatch_count.clear()
        self.task_version.clear()
        # 重新初始化任务列表
        for tid in self._task_ids:
            self.task_status[tid] = TaskState.PENDING
            self.dispatch_count[tid] = 0
            self.task_version[tid] = 0
        self.status = GraphStatus.PENDING

    def update_task_status(self, task_id: str, status: TaskState, result: Any = None):
        """更新任务状态，并可选择保存结果"""
        self.task_status[task_id] = status
        # 递增版本号
        self.task_version[task_id] = self.task_version.get(task_id, 0) + 1
        if result is not None:
            self.task_results[task_id] = result

    def get_task_version(self, task_id: str) -> int:
        return self.task_version.get(task_id, 0)

    def increment_dispatch(self, task_id: str):
        """增加分发计数（用于调试/监控）"""
        self.dispatch_count[task_id] = self.dispatch_count.get(task_id, 0) + 1

    def update_shared_state(self, key: str, value: Any, expected_type: type):
        """写入黑板前校验类型"""
        if not isinstance(value, expected_type):
            raise TypeError(f"Shared state type mismatch for {key}: expected {expected_type}, got {type(value)}")
        self.shared_state[key] = value

    def get_shared_state(self, key: str, default=None):
        """读取共享黑板中的值"""
        return self.shared_state.get(key, default)

    def clear_shared_state(self):
        """完全清空共享黑板（通常只在系统硬重置时使用）"""
        self.shared_state.clear()

    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "task_status": {tid: s.value for tid, s in self.task_status.items()},
            "task_results": self.task_results,
            "dispatch_count": self.dispatch_count,
            "shared_state": self.shared_state,
            "status": self.status.value,
            "task_version": self.task_version,
        }

    @classmethod
    def from_dict(cls, data: dict, graph: "TaskGraph") -> "GraphContext":
        ctx = cls(data["graph_id"])
        ctx.task_status = {tid: TaskState(s) for tid, s in data["task_status"].items()}
        ctx.task_results = data["task_results"]
        ctx.dispatch_count = data["dispatch_count"]
        ctx.shared_state = data["shared_state"]
        ctx.status = GraphStatus(data["status"])
        ctx.task_version = data.get("task_version", {})
        # 注意：_task_ids 无法从 dict 恢复，但 reset 需要它，所以从 graph.tasks 重建
        if graph:
            ctx._task_ids = list(graph.tasks.keys())
        return ctx