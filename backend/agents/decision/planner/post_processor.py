"""
规划后处理器：对生成的 TaskGraph 进行统一增强（低电量注入、重试设置、安全策略等）
"""

import uuid
from typing import List, Optional

from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType
from backend.models.task.task import TaskType
from backend.agents.decision.planner.planner_context import PlannerContext
from backend.agents.decision.planner.utils.graph_helper import GraphHelper
from backend.utils.logger_handler import logger
from backend.models.task.task import Task, TaskState



class PlanningPostProcessor:
    def __init__(
        self,
        battery_threshold: float = 11.0,
        enable_low_battery_charge: bool = True,
        enable_retry_for_motion: bool = True,
        enable_safety_recovery: bool = True,
        default_max_retries: int = 2,
        default_retry_delay: float = 1.0,
    ):
        self.battery_threshold = battery_threshold
        self.enable_low_battery_charge = enable_low_battery_charge
        self.enable_retry_for_motion = enable_retry_for_motion
        self.enable_safety_recovery = enable_safety_recovery
        self.default_max_retries = default_max_retries
        self.default_retry_delay = default_retry_delay

    def process(self, graph: TaskGraph, context: PlannerContext) -> TaskGraph:
        """
        对图进行后处理，返回修改后的图（原地修改也可能，但为清晰返回副本）
        """
        # 1. 设置重试参数（关键任务）
        if self.enable_retry_for_motion:
            self._apply_retry_policy(graph)

        # 2. 低电量处理：添加低电量回充任务
        if self.enable_low_battery_charge and context.get_battery() < self.battery_threshold:
            graph = self._add_low_battery_charge(graph, context)

        # 3. 安全策略：添加默认恢复任务（如果图中没有 recovery 任务）
        if self.enable_safety_recovery and not self._has_recovery_task(graph):
            graph = self._add_default_recovery(graph)

        return graph

    # ---------- 私有方法 ----------
    def _apply_retry_policy(self, graph: TaskGraph):
        """为 motion 类任务设置重试次数和重试延迟"""
        motion_task_types = {TaskType.NAVIGATE_TO, TaskType.CLEANING, TaskType.RECOVER_STUCK}
        for task in graph.tasks.values():
            if task.type in motion_task_types:
                if task.max_retries == 0:
                    task.max_retries = self.default_max_retries
                if task.retry_delay == 0:
                    task.retry_delay = self.default_retry_delay

    def _has_recovery_task(self, graph: TaskGraph) -> bool:
        return any(t.type == TaskType.RECOVER_STUCK for t in graph.tasks.values())

    def _add_default_recovery(self, graph: TaskGraph) -> TaskGraph:
        """添加一个默认的恢复任务，连接所有出口任务"""
        # 注意：需要导入 BasePlanner 只是为了使用 _create_task，但这里应避免循环依赖。
        # 我们直接用 Task 构造函数（简化版）
        recovery = Task(
            task_id=f"recover_{uuid.uuid4().hex[:8]}",
            type=TaskType.RECOVER_STUCK,
            params={"method": "backup_and_turn"},
            status=TaskState.PENDING,
            robot_id=graph.tasks[next(iter(graph.tasks))].robot_id if graph.tasks else "robot_001",
            required_resources=["motion"],
            max_retries=2,
            retry_delay=1.0,
        )
        graph.add_task(recovery)
        # 让恢复任务成为新的出口（即原有出口任务可以执行 recovery）
        for exit_id in graph.exit_tasks.copy():
            graph.add_edge(exit_id, recovery.task_id, EdgeType.ALWAYS)
        # 重新计算出口任务
        GraphHelper.compute_entry_exit(graph)
        return graph

    def _add_low_battery_charge(self, graph: TaskGraph, context: PlannerContext) -> TaskGraph:
        """添加低电量回充任务，作为图中最后一个任务（依赖所有出口任务）"""
        charge = Task(
            task_id=f"low_battery_charge_{uuid.uuid4().hex[:8]}",
            type=TaskType.RETURN_TO_CHARGE,
            params={"reason": "low_battery"},
            status=TaskState.PENDING,
            robot_id=context.robot_id,
            required_resources=["motion"],
            max_retries=1,
        )
        graph.add_task(charge)
        # 将所有出口任务连接到 charge
        for exit_id in graph.exit_tasks:
            graph.add_edge(exit_id, charge.task_id, EdgeType.ALWAYS)
        # 重新计算入口/出口
        GraphHelper.compute_entry_exit(graph)
        return graph