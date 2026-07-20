"""
验证 TaskGraph 结构（循环依赖、孤立节点、任务合法性等）
"""

from typing import List, Tuple, Set
from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType

class GraphValidator:
    @staticmethod
    def validate(graph: TaskGraph) -> Tuple[bool, List[str]]:
        errors = []
        # 1. 非空
        if not graph.tasks:
            errors.append("Graph is empty")
            return False, errors
        # 2. 检查任务 ID 唯一性（TaskGraph 本身保证）
        # 3. 检查所有边的源和目标存在
        task_ids = set(graph.tasks.keys())
        for edge in graph.edges:
            if edge.source not in task_ids:
                errors.append(f"Edge source '{edge.source}' not found")
            if edge.target not in task_ids:
                errors.append(f"Edge target '{edge.target}' not found")
        # 4. 检查循环依赖（拓扑排序）
        try:
            GraphValidator._topological_sort(graph)
        except Exception as e:
            errors.append(f"Cycle detected: {e}")
        # 5. 检查是否有入口任务（无入边）
        has_incoming = set()
        for edge in graph.edges:
            has_incoming.add(edge.target)
        entry_tasks = task_ids - has_incoming
        if not entry_tasks:
            errors.append("No entry tasks (all tasks have incoming edges)")
        return len(errors) == 0, errors

    @staticmethod
    def _topological_sort(graph: TaskGraph) -> List[str]:
        in_degree = {tid: 0 for tid in graph.tasks}
        for edge in graph.edges:
            in_degree[edge.target] += 1
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        result = []
        while queue:
            tid = queue.pop(0)
            result.append(tid)
            for edge in graph.edges:
                if edge.source == tid:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)
        if len(result) != len(graph.tasks):
            raise ValueError("Graph contains a cycle")
        return result