"""
定义 GraphPatch 数据类，动态修改正在执行的任务图
"""

from dataclasses import dataclass, field
from typing import List, Tuple
from backend.agents.decision.runtime.task_graph import Task, GraphEdge

@dataclass
class GraphPatch:
    add_tasks: List[Task] = field(default_factory=list)             # 需要新增的任务列表
    remove_tasks: List[str] = field(default_factory=list)           # 需要删除的任务 ID 列表
    add_edges: List[GraphEdge] = field(default_factory=list)        # 需要新增的边（依赖关系），用于连接新任务或修复依赖
    remove_edges: List[Tuple[str, str]] = field(default_factory=list)  # 需要删除的边，用 (source, target) 元组表示




