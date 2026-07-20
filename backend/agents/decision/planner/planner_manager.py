"""
规划器管理器，负责统筹多个规划器实例，实现规划调度、失败回退（fallback）、结果后处理以及重规划
    规划调度：维护一个规划器列表（如 LLM 规划器、规则规划器），根据优先级和上下文选择合适的规划器执行 plan。
    失败回退：当一个规划器失败或返回无效结果时，自动尝试下一个规划器，确保系统总能得到任务图（例如 LLM 规划失败后降级到规则规划器）。
    后处理：规划成功后，调用可选的 PlanningPostProcessor 统一注入低电量回充、重试策略等，避免每个规划器重复实现。
    记录映射：缓存每个任务图对应的规划器，供后续重规划使用。
    重规划：当任务执行失败时，调用原规划器的 replan 方法生成补丁（GraphPatch），支持运行时动态修图。
"""

from typing import List, Dict, Optional
from backend.agents.decision.planner.base_planner import BasePlanner
from backend.agents.decision.planner.planner_context import PlannerContext
from backend.agents.decision.planner.planning_result import PlanningResult
from backend.agents.decision.planner.post_processor import PlanningPostProcessor
from backend.agents.decision.runtime.task_graph import TaskGraph
from backend.utils.logger_handler import logger


class PlannerManager:
    """
    管理多个规划器，按顺序尝试直到成功，并对成功的结果进行后处理。
    """

    def __init__(
        self,
        planners: List[BasePlanner],
        post_processor: Optional[PlanningPostProcessor] = None,
    ):
        """
        :param planners: 规划器列表，按优先级降序排列（列表顺序即为 fallback 顺序）
        :param post_processor: 可选的后处理器，用于统一注入低电量、重试等策略
        """
        self.planners = planners
        self.post_processor = post_processor
        self._graph_planner_map: Dict[str, BasePlanner] = {}  # graph_id -> 使用的规划器

    async def select_and_plan(self, context: PlannerContext) -> PlanningResult:
        """
        选择合适的规划器并生成 TaskGraph，失败则尝试下一个。
        成功后调用后处理器（如有）。
        :return: PlanningResult
        :raises: RuntimeError 如果所有规划器都无法生成合法图
        """
        errors = []
        for planner in self.planners:
            # 1. 检查规划器是否适用于当前上下文
            if not planner.can_handle(context):
                logger.debug(f"Planner {planner.name} cannot handle this context, skip")
                continue

            try:
                # 2. 执行规划
                result = await planner.plan(context)
                if not result.success:
                    logger.warning(f"Planner {planner.name} returned unsuccessful: {result.warnings}")
                    errors.append(f"{planner.name}: planning result not successful")
                    continue

                # 3. 后处理
                if self.post_processor:
                    processed_graph = self.post_processor.process(result.graph, context)
                    result.graph = processed_graph

                # 4. 记录使用的规划器，返回结果
                self._graph_planner_map[result.graph.graph_id] = planner
                logger.info(f"Planned with {planner.name}, graph_id={result.graph.graph_id}")
                return result

            except Exception as e:
                logger.error(f"Planner {planner.name} failed: {e}", exc_info=True)
                errors.append(f"{planner.name}: {str(e)}")
                continue

        # 所有规划器都失败
        raise RuntimeError(f"No planner could handle the request. Errors: {errors}")

    async def replan(
        self,
        current_graph: TaskGraph,
        failed_task_id: str,
        context: PlannerContext,
    ) -> Optional[TaskGraph]:
        """
        使用原规划器进行重规划，返回新图（或补丁）。
        若原规划器不支持重规划，则返回 None。
        """
        planner = self._graph_planner_map.get(current_graph.graph_id)
        if planner is None:
            logger.warning(f"No planner found for graph {current_graph.graph_id}, cannot replan")
            return None

        if not planner.supports_replan:
            logger.warning(f"Planner {planner.name} does not support replan")
            return None

        try:
            # 注意：replan 可能返回 GraphPatch，这里简化返回 TaskGraph
            # 实际可根据 planner 的实现调整
            new_graph = await planner.replan(current_graph, failed_task_id, context)
            if new_graph:
                self._graph_planner_map[new_graph.graph_id] = planner
                logger.info(f"Replanned with {planner.name}, new graph_id={new_graph.graph_id}")
                # 后处理
                if self.post_processor:
                    new_graph = self.post_processor.process(new_graph, context)
            return new_graph
        except Exception as e:
            logger.error(f"Replan failed: {e}", exc_info=True)
            return None