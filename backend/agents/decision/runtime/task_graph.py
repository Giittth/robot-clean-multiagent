"""
    任务图数据结构：纯静态定义，只包含任务节点和显式边（依赖关系）。
"""

from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum
from backend.models.task.task import Task


class EdgeType(str, Enum):
    """边的类型，决定依赖任务的结果如何影响后续任务"""
    SUCCESS = "success"   # 只有依赖任务成功（或跳过）时才触发
    FAILURE = "failure"   # 只有依赖任务失败时才触发
    ALWAYS = "always"     # 无论依赖任务结果如何，只要它终结就触发


@dataclass
class GraphEdge:
    """显式边定义"""
    source: str      # 源任务ID
    target: str      # 目标任务ID
    type: EdgeType   # 触发类型


class TaskGraph:
    """
    纯静态任务图，不含运行时状态。
    所有依赖关系通过 GraphEdge 表示，不支持 deprecated 的 depends_on 参数。
    """
    def __init__(self, graph_id: str = ""):
        self.graph_id = graph_id
        self.tasks: Dict[str, Task] = {}      # task_id -> Task
        self.edges: List[GraphEdge] = []      # 所有边

        self.entry_tasks: Set[str] = set()   # 入口任务ID集合
        self.exit_tasks: Set[str] = set()    # 出口任务ID集合


    def add_task(self, task: Task, is_entry: bool = False, is_exit: bool = False):
        """添加任务节点"""
        self.tasks[task.task_id] = task
        if is_entry:
            self.entry_tasks.add(task.task_id)
        if is_exit:
            self.exit_tasks.add(task.task_id)

    def add_edge(self, source: str, target: str, edge_type: EdgeType = EdgeType.SUCCESS):
        """添加一条有向边，定义任务间的依赖关系和触发条件"""
        self.edges.append(GraphEdge(source=source, target=target, type=edge_type))
        # 自动维护入口/出口：入口任务是无入边的任务，出口任务是无出边的任务
        # 但为简化，仍保留显式标记

    def get_outgoing_edges(self, source: str) -> List[GraphEdge]:
        """获取指定任务的所有出边"""
        return [e for e in self.edges if e.source == source]

    def get_incoming_edges(self, target: str) -> List[GraphEdge]:
        """获取指向指定任务的所有入边（依赖关系）"""
        return [e for e in self.edges if e.target == target]

    def get_successors_by_type(self, source: str, edge_type: EdgeType) -> List[str]:
        """获取指定任务指定类型边的所有后继任务ID"""
        return [e.target for e in self.edges if e.source == source and e.type == edge_type]

    def get_all_dependencies(self, task_id: str) -> List[str]:
        """返回所有依赖当前任务的任务ID（即所有边指向 task_id 的源任务）"""
        return [e.source for e in self.edges if e.target == task_id]


    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "tasks": {tid: task.model_dump() for tid, task in self.tasks.items()},
            "edges": [{"source": e.source, "target": e.target, "type": e.type.value} for e in self.edges],
            "entry_tasks": list(self.entry_tasks),
            "exit_tasks": list(self.exit_tasks),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskGraph":
        from backend.models.task.task import Task
        graph = cls(data["graph_id"])
        for tid, task_data in data["tasks"].items():
            task = Task(**task_data)
            graph.add_task(task)
        for edge_data in data["edges"]:
            graph.add_edge(edge_data["source"], edge_data["target"], EdgeType(edge_data["type"]))
        graph.entry_tasks = set(data["entry_tasks"])
        graph.exit_tasks = set(data["exit_tasks"])
        return graph
