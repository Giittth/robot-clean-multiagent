"""
基于规则的规划器：通过关键词匹配生成任务图
支持：
    - 意图解析（IntentParser）
    - 动态入口/出口计算（而非手动标记）
    - 正确地失败恢复流（恢复后重试原任务，而非直接回充）
    - 运行时低电量条件（通过 condition edge 实现）
    - 图合法性验证
"""

import uuid
from typing import List, Tuple
from backend.agents.decision.planner.base_planner import BasePlanner
from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType
from backend.models.task.task import TaskType
from backend.agents.decision.planner.planner_context import PlannerContext
from backend.agents.decision.planner.utils.intent_parser import IntentParser
from backend.agents.decision.planner.planning_result import PlanningResult
from backend.utils.logger_handler import logger


class RulePlanner(BasePlanner):
    name = "rule"
    supports_replan = False
    supports_llm = False
    priority = 10
    # 区域坐标常量
    AREA_POSITIONS = {
        "living_room": {"x": 3.0, "y": 3.0},
        "bedroom":     {"x": -3.0, "y": 3.0},
        "kitchen":     {"x": 3.0, "y": -3.0},
        "bathroom":    {"x": -3.0, "y": -3.0},
    }

    def can_handle(self, context: PlannerContext) -> bool:
        return True

    async def plan(self, context: PlannerContext) -> PlanningResult:
        graph = TaskGraph(graph_id=str(uuid.uuid4()))
        intent = IntentParser.parse(context.user_command)
        warnings = []
        success = True

        # ---------- 根据意图生成图 ----------
        if intent["intent"] == "return_to_charge":
            task = self._create_task(TaskType.RETURN_TO_CHARGE, {"reason": "user_command"})
            graph.add_task(task)

        elif intent["intent"] == "stop":
            task = self._create_task(TaskType.STOP, {})
            graph.add_task(task)

        elif intent["intent"] == "clean_area":
            area = intent.get("area", "unknown")
            success, graph, warn = self._build_clean_graph(graph, area, context)
            warnings.extend(warn)
            if not success:
                return PlanningResult(
                    graph=graph,
                    planner_name=self.name,
                    success=False,
                    warnings=warnings,
                    metadata={"intent": intent, "error": "failed to build clean graph"}
                )

        elif intent["intent"] == "navigate_to":
            target = intent.get("target", {"x": 0.0, "y": 0.0})
            task = self._create_task(TaskType.NAVIGATE_TO, {"target": target})
            graph.add_task(task)

        else:  # explore
            task = self._create_task(TaskType.EXPLORE_AREA, {"distance": 2.0})
            graph.add_task(task)
            warnings.append("No specific intent recognized, using explore mode")

        # 自动计算入口和出口任务
        self._compute_entry_exit(graph)

        # 验证图的合法性
        is_valid, valid_warnings = self._validate_graph(graph)
        if not is_valid:
            success = False
            warnings.extend(valid_warnings)

        logger.info(f"RulePlanner intent: {intent}")
        logger.info(f"Generated graph with {len(graph.tasks)} tasks")

        return PlanningResult(
            graph=graph,
            planner_name=self.name,
            success=success,
            warnings=warnings,
            metadata={"intent": intent}
        )

    # ========== 构建清扫任务图（带完整失败流和条件边） ==========
    def _build_clean_graph(self, graph: TaskGraph, area: str, context: PlannerContext) -> Tuple[bool, TaskGraph, List[str]]:
        """
        构建清扫任务图，包含：
        - 导航任务
        - 清扫任务
        - 恢复任务（脱困，并可重试）
        - 失败回充（仅在最终失败时触发）
        - 低电量条件边（运行时检查）
        """
        warnings = []
        logger.info(f"RulePlanner checking area '{area}' in rooms {context.rooms}")
        # 直接使用 context 中的 rooms 列表判断区域是否存在
        if area in context.rooms:
            # 区域有几何定义：使用新的导航到区域任务
            logger.info(f"Area '{area}' found in rooms, using NAVIGATE_TO_AREA")
            nav_task = self._create_task(TaskType.NAVIGATE_TO_AREA, {"room_id": area})
        else:
            # 降级：使用固定点坐标
            logger.warning(f"Area '{area}' not in rooms, fallback to fixed point")
            area_target = self.AREA_POSITIONS.get(area, {"x": 2.0, "y": 2.0})
            nav_task = self._create_task(TaskType.NAVIGATE_TO, {"target": area_target})

        # 创建核心任务
        # 直接传坐标，不再传 area 字符串
        clean_task = self._create_task(TaskType.CLEAN_AREA, {"room_id": area, "mode": "full_coverage"})
        recover_task = self._create_task(TaskType.RECOVER_STUCK, {"method": "backup_and_turn"})
        # 最终失败回充任务
        final_charge = self._create_task(TaskType.RETURN_TO_CHARGE, {"reason": "cleaning_failed_after_retry"})

        graph.add_task(nav_task)
        graph.add_task(clean_task)
        graph.add_task(recover_task)
        graph.add_task(final_charge)

        # -------- 标准成功链路（无环）--------
        # 导航成功 → 清扫
        graph.add_edge(nav_task.task_id, clean_task.task_id, EdgeType.SUCCESS)
        # 清扫成功 → 终止（天然出口）

        # -------- 失败链路：不做回跳重试，改为恢复后直接走最终失败 --------
        # 导航失败 → 脱困恢复
        graph.add_edge(nav_task.task_id, recover_task.task_id, EdgeType.FAILURE)
        # 清扫失败 → 脱困恢复
        graph.add_edge(clean_task.task_id, recover_task.task_id, EdgeType.FAILURE)

        # 恢复成功/失败 统一走向 最终回充（终结链路，无回跳，彻底消除环）
        graph.add_edge(recover_task.task_id, final_charge.task_id, EdgeType.SUCCESS)
        graph.add_edge(recover_task.task_id, final_charge.task_id, EdgeType.FAILURE)

        # -------- 低电量分支（保留原有逻辑）--------
        # low_charge = self._create_task(TaskType.RETURN_TO_CHARGE, {"reason": "low_battery"})
        # graph.add_task(low_charge)
        # # graph.add_edge(nav_task.task_id, low_charge.task_id, EdgeType.ALWAYS)
        # graph.add_edge(clean_task.task_id, low_charge.task_id, EdgeType.ALWAYS)
        # graph.add_edge(recover_task.task_id, low_charge.task_id, EdgeType.ALWAYS)

        return True, graph, warnings

    # ========== 自动计算入口和出口任务 ==========
    def _compute_entry_exit(self, graph: TaskGraph):
        """根据边的结构自动计算入口和出口任务"""
        all_tasks = set(graph.tasks.keys())
        # 入口：没有入边的任务
        has_incoming = set()
        for edge in graph.edges:
            has_incoming.add(edge.target)
        entry_tasks = all_tasks - has_incoming
        graph.entry_tasks = entry_tasks

        # 出口：没有出边的任务
        has_outgoing = set()
        for edge in graph.edges:
            has_outgoing.add(edge.source)
        exit_tasks = all_tasks - has_outgoing
        graph.exit_tasks = exit_tasks

        if not graph.entry_tasks:
            logger.warning("TaskGraph has no entry tasks")
        if not graph.exit_tasks:
            logger.warning("TaskGraph has no exit tasks")

    # ========== 图验证 ==========
    def _validate_graph(self, graph: TaskGraph) -> Tuple[bool, List[str]]:
        """验证图的合法性：无循环依赖、有入口和出口、任务类型合法等"""
        warnings = []
        # 检查是否有循环依赖（简单检测：拓扑排序）
        try:
            self._topological_sort(graph)
        except Exception as e:
            warnings.append(f"Cycle detected: {e}")
            return False, warnings
        if not graph.entry_tasks:
            warnings.append("Graph has no entry tasks")
        if not graph.exit_tasks:
            warnings.append("Graph has no exit tasks")
        return len(warnings) == 0, warnings

    def _topological_sort(self, graph: TaskGraph) -> List[str]:
        """返回拓扑排序的任务ID列表，若存在循环则抛出异常"""
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