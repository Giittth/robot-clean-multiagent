"""
规划器抽象基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import uuid

from .planning_result import PlanningResult
from backend.models.task.task import Task, TaskType, TaskState
from backend.agents.decision.runtime.task_graph import TaskGraph
from backend.agents.decision.planner.planner_context import PlannerContext


class BasePlanner(ABC):
    """
    规划器抽象基类，定义元数据属性和规划接口。
    """

    # 元数据（子类必须覆盖）
    name: str = "base"
    supports_replan: bool = False   # 是否支持动态重规划
    supports_llm: bool = False      # 是否需要 LLM
    priority: int = 0               # 优先级，数值越大优先级越高

    def __init__(self, robot_id: str = "robot_001"):
        self.robot_id = robot_id

    def _default_resource_policy(self, task_type: TaskType) -> List[str]:
        """根据任务类型推断所需资源，子类可覆盖"""
        if task_type in (TaskType.NAVIGATE_TO, TaskType.EXPLORE_AREA,
                         TaskType.CLEANING, TaskType.RETURN_TO_CHARGE,
                         TaskType.RECOVER_STUCK):
            return ["motion"]
        return []

    def can_handle(self, context: PlannerContext) -> bool:
        """判断此规划器是否适用于当前上下文，子类可重写"""
        return True

    @abstractmethod
    async def plan(self, context: PlannerContext) -> PlanningResult:
        """
        生成初始任务图。
        :param context: 规划上下文（包含用户指令、世界状态、机器人状态等）
        :return: PlanningResult 规划结果
        """
        pass

    async def replan(
        self,
        current_graph: TaskGraph,
        failed_task_id: str,
        context: PlannerContext
    ) -> TaskGraph:
        """
        动态重规划（可选实现，默认抛出 NotImplementedError）。
        当 supports_replan 为 True 时子类应重写此方法。
        """
        raise NotImplementedError(f"{self.name} does not support replan")

    # ========== 辅助方法（子类可复用） ==========
    def _create_task(
        self,
        task_type: TaskType,
        params: Dict[str, Any],
        task_id: Optional[str] = None,
        required_resources: Optional[List[str]] = None,
        timeout: float = 30.0,
        max_retries: int = 1,
        priority: int = 1,
    ) -> Task:
        """
        创建任务对象，支持设置资源需求、超时、重试次数、优先级等。
        """
    # 保留 _create_task，但 required_resources 不再写死，而是调用资源策略
        if required_resources is None:
            required_resources = []  # 默认为空，由 ResourceManager 后续推断
        return Task(
            task_id=task_id or str(uuid.uuid4()),
            type=task_type,
            params=params,
            status=TaskState.PENDING,
            robot_id=self.robot_id,
            required_resources=required_resources,
            timeout=timeout,
            max_retries=max_retries,
            priority=priority,
        )