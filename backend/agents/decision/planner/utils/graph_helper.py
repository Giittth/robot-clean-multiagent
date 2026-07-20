"""
自动计算任务图的入口任务和出口任务：
入口任务：没有任何边指向的任务（即没有前驱依赖），是任务图执行的起点。
出口任务：没有边从它们出发指向其他任务（即没有后继任务），是任务图执行的终点。
"""

from backend.agents.decision.runtime.task_graph import TaskGraph

class GraphHelper:
    @staticmethod
    def compute_entry_exit(graph: TaskGraph):
        all_tasks = set(graph.tasks.keys())
        has_incoming = set(e.target for e in graph.edges)
        graph.entry_tasks = all_tasks - has_incoming
        has_outgoing = set(e.source for e in graph.edges)
        graph.exit_tasks = all_tasks - has_outgoing