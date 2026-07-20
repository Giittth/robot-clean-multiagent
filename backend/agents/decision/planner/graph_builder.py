
"""
GraphBuilder: 将结构化 LLM 输出（JSON 任务列表）转换为合法的 TaskGraph。

职责：
- 校验任务类型、id 唯一性、依赖完整性
- 构造 TaskGraph（节点 + 边）
- 自动计算 entry/exit
- 闭环检测

与 LLMPlanner 解耦后，GraphBuilder 可独立测试，也支持手工构造图。
"""

import uuid
from typing import Dict, Any, List, Tuple

from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType, GraphEdge
from backend.agents.decision.planner.planner_context import PlannerContext
from backend.agents.decision.planner.utils.graph_helper import GraphHelper
from backend.models.task.task import Task, TaskType, TaskState
from backend.utils.logger_handler import logger


class GraphBuildError(Exception):
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class GraphBuilder:
    """
    将 LLM 返回的结构化任务数据转换为 TaskGraph。

    输入格式（task_data 列表的每项）:
    {
        "id": str,
        "type": str,
        "params": dict,
        "depends_on": [str],
    }
    """

    MOTION_TYPES = {
        TaskType.NAVIGATE_TO,
        TaskType.NAVIGATE_TO_AREA,
        TaskType.CLEAN_AREA,
        TaskType.CLEANING,
        TaskType.EXPLORE_AREA,
        TaskType.RETURN_TO_CHARGE,
        TaskType.RECOVER_STUCK,
    }

    def __init__(self, robot_id: str = "robot_001"):
        self.robot_id = robot_id

    def build(self, tasks_data: List[Dict[str, Any]], context: PlannerContext) -> TaskGraph:
        graph = TaskGraph(graph_id=f"graph_{uuid.uuid4().hex[:8]}")
        task_id_map: Dict[str, Task] = {}

        # 第一遍：创建任务节点
        for item in tasks_data:
            t_id = item.get("id")
            t_type_str = item.get("type")
            params = item.get("params", {})
            if not t_id or not isinstance(t_id, str):
                continue
            if not t_type_str or not isinstance(t_type_str, str):
                continue
            try:
                t_type = TaskType(t_type_str)
            except ValueError:
                continue
            if t_id in task_id_map:
                continue
            resources = self._infer_resources(t_type)
            params.setdefault("robot_id", self.robot_id)
            task = Task(
                task_id=t_id,
                type=t_type,
                params=params,
                status=TaskState.PENDING,
                robot_id=self.robot_id,
                required_resources=resources,
                timeout=params.get("timeout", 30.0),
                max_retries=params.get("max_retries", 1),
                priority=params.get("priority", 1),
            )
            graph.add_task(task)
            task_id_map[t_id] = task

        if not graph.tasks:
            raise GraphBuildError(["No valid tasks parsed from LLM output"])

        # 第二遍：添加依赖边
        for item in tasks_data:
            t_id = item.get("id")
            if t_id not in task_id_map:
                continue
            depends = item.get("depends_on", [])
            if not isinstance(depends, list):
                continue
            for dep_id in depends:
                if dep_id in task_id_map:
                    graph.add_edge(dep_id, t_id, EdgeType.SUCCESS)

        GraphHelper.compute_entry_exit(graph)

        # 闭环检测
        cycle_errors = self._check_cycles(graph)
        if cycle_errors:
            raise GraphBuildError(cycle_errors)

        return graph

    def _infer_resources(self, task_type: TaskType) -> List[str]:
        if task_type in self.MOTION_TYPES:
            return ["motion"]
        return []

    def _check_cycles(self, graph: TaskGraph) -> List[str]:
        in_degree = {tid: 0 for tid in graph.tasks}
        for edge in graph.edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            tid = queue.pop(0)
            visited += 1
            for edge in graph.edges:
                if edge.source == tid:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)
        if visited != len(graph.tasks):
            return ["Graph contains a cycle"]
        return []
