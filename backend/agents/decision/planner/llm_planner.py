"""
基于 LLM 的规划器（v2）。

- 改用 chat() 而非 generate()，支持重试 + 错误反馈循环
- graph_builder 解耦输出解析和构图
- 更丰富的 prompt：房间列表、机器人状态、运行约束
- 智能 replan：调用 LLM 分析失败原因并生成补救计划
- 与规则规划器解耦（由 PlannerManager 实现 fallback）
"""

import json
from typing import List, Dict, Any, Tuple

from backend.agents.decision.planner.base_planner import BasePlanner
from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType, GraphEdge
from backend.models.task.task import TaskType
from backend.agents.decision.planner.planner_context import PlannerContext
from backend.agents.decision.planner.planning_result import PlanningResult
from backend.agents.decision.planner.graph_builder import GraphBuilder, GraphBuildError
from backend.agents.decision.planner.utils.graph_patch import GraphPatch
from backend.agents.decision.planner.utils.graph_helper import GraphHelper
from backend.llm.base import BaseLLMClient
from backend.utils.logger_handler import logger


class LLMPlanner(BasePlanner):
    """基于大模型的任务规划器（v2）。"""
    name = "llm_v2"
    supports_replan = True
    supports_llm = True
    priority = 20  # 高于 RulePlanner 的 10

    def __init__(self, llm_client: BaseLLMClient, robot_id: str = "robot_001"):
        super().__init__(robot_id)
        self.llm = llm_client
        self.graph_builder = GraphBuilder(robot_id=robot_id)
        self._max_retries = 2

    def can_handle(self, context: PlannerContext) -> bool:
        return True

    # ==================== 主规划接口 ====================
    async def plan(self, context: PlannerContext) -> PlanningResult:
        prompt = self._build_plan_prompt(context)
        metadata: Dict[str, Any] = {"raw_output": ""}

        try:
            tasks_data, raw_output = await self._call_llm(prompt)
            metadata["raw_output"] = raw_output
        except Exception as e:
            logger.error(f"LLM call failed after retries: {e}")
            return PlanningResult(
                graph=TaskGraph(),
                planner_name=self.name,
                success=False,
                warnings=[f"LLM call failed: {str(e)}"],
                metadata=metadata,
            )

        try:
            graph = self.graph_builder.build(tasks_data, context)
            return PlanningResult(
                graph=graph,
                planner_name=self.name,
                success=True,
                warnings=[],
                metadata={**metadata, "task_count": len(graph.tasks)},
            )
        except GraphBuildError as e:
            logger.error(f"Graph building failed: {e.errors}")
            return PlanningResult(
                graph=TaskGraph(),
                planner_name=self.name,
                success=False,
                warnings=e.errors,
                metadata={**metadata, "build_errors": e.errors},
            )

    # ==================== LLM 调用（带重试 + 错误反馈） ====================
    async def _call_llm(self, prompt: str) -> Tuple[List[Dict], str]:
        system_prompt = (
            "你是一个机器人任务规划专家。你只输出合法 JSON，不包含任何其他文字。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        last_error = ""
        raw_text = ""
        for attempt in range(self._max_retries + 1):
            if last_error:
                messages.append({"role": "assistant", "content": raw_text})
                messages.append({
                    "role": "user",
                    "content": (
                        f"JSON 解析失败：{last_error}\n"
                        "请只输出一个合法的 JSON 数组，"
                        "不要包含任何额外文字、注释或格式标记。"
                    ),
                })

            try:
                resp = await self.llm.chat(
                    messages,
                    temperature=0.1,
                    max_tokens=4096,
                )
                raw_text = resp.get("content", "").strip()
            except Exception as e:
                last_error = str(e)
                logger.warning(f"LLM chat attempt {attempt + 1} failed: {last_error}")
                continue

            cleaned = self._clean_json(raw_text)
            try:
                data = json.loads(cleaned)
                if isinstance(data, list):
                    return data, raw_text
                if isinstance(data, dict) and "tasks" in data:
                    return data["tasks"], raw_text
                last_error = f"JSON is not a list or {{tasks: [...]}}: {type(data)}"
            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(
                    f"LLM JSON parse attempt {attempt + 1} failed: {last_error}"
                )
                continue

        raise ValueError(
            f"LLM failed to return valid JSON after {self._max_retries + 1} attempts. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _clean_json(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    # ==================== 智能重规划（LLM 驱动） ====================
    async def replan(
        self,
        current_graph: TaskGraph,
        failed_task_id: str,
        context: PlannerContext,
    ) -> GraphPatch:
        failed_task = current_graph.tasks.get(failed_task_id)
        if not failed_task:
            return self._fallback_patch(current_graph, failed_task_id)

        graph_summary = self._summarize_graph(current_graph, failed_task_id)
        replan_prompt = self._build_replan_prompt(
            context, failed_task, graph_summary
        )

        try:
            tasks_data, _ = await self._call_llm(replan_prompt)
            if not tasks_data:
                return self._fallback_patch(current_graph, failed_task_id)

            patch = GraphPatch()
            patch.remove_tasks.append(failed_task_id)
            for edge in current_graph.edges:
                if edge.source == failed_task_id:
                    patch.remove_edges.append((edge.source, edge.target))

            predecessor_ids = [
                e.source for e in current_graph.edges
                if e.target == failed_task_id
            ]

            for item in tasks_data:
                t_id = item.get("id")
                t_type_str = item.get("type")
                params = item.get("params", {})
                if not t_id or not t_type_str:
                    continue
                try:
                    t_type = TaskType(t_type_str)
                except ValueError:
                    continue

                new_task = self._create_task(t_type, params, task_id=t_id)
                patch.add_tasks.append(new_task)

                for pred_id in predecessor_ids:
                    if pred_id != t_id:
                        patch.add_edges.append(
                            GraphEdge(pred_id, t_id, EdgeType.SUCCESS)
                        )

            logger.info(
                f"LLM replan generated {len(patch.add_tasks)} new tasks"
            )
            return patch

        except Exception as e:
            logger.error(f"LLM replan failed: {e}, using fallback")
            return self._fallback_patch(current_graph, failed_task_id)

    def _fallback_patch(
        self, current_graph: TaskGraph, failed_task_id: str
    ) -> GraphPatch:
        patch = GraphPatch()
        patch.remove_tasks.append(failed_task_id)
        for edge in current_graph.edges:
            if edge.source == failed_task_id:
                patch.remove_edges.append((edge.source, edge.target))

        recover_id = f"recover_{failed_task_id}"
        recover_task = self._create_task(
            TaskType.RECOVER_STUCK,
            {"method": "backup_and_turn"},
            task_id=recover_id,
        )
        patch.add_tasks.append(recover_task)

        predecessors = [
            e.source for e in current_graph.edges
            if e.target == failed_task_id
        ]
        for pred_id in predecessors:
            patch.add_edges.append(
                GraphEdge(pred_id, recover_id, EdgeType.SUCCESS)
            )
        patch.add_edges.append(
            GraphEdge(recover_id, failed_task_id, EdgeType.SUCCESS)
        )
        return patch

    # ==================== Prompt 构建 ====================
    def _build_plan_prompt(self, context: PlannerContext) -> str:
        battery = context.get_battery()
        coverage = context.get_coverage()
        pose = context.get_pose()
        rooms = context.rooms or []
        rooms_str = ", ".join(rooms) if rooms else "（未知）"

        task_types_desc = (
            "可用任务类型：\n"
            "  - navigate_to        导航到指定坐标 {target: {x, y}}\n"
            "  - navigate_to_area   导航到指定房间 {room_id: str}\n"
            "  - clean_area         清扫指定房间 {room_id: str, mode: str}\n"
            "  - explore_area       探索未知区域 {distance: float}\n"
            "  - return_to_charge   返回充电座\n"
            "  - recover_stuck      脱困恢复\n"
            "  - wait               等待 {duration: float}\n"
            "  - stop               停止\n"
        )

        constraints = (
            "运行时约束（必须遵守）：\n"
            "1. 机器人同时只能执行一个 motion 类任务\n"
            "2. 任务之间通过 depends_on 指定顺序\n"
            "3. 电量低于 11V 时优先插入 return_to_charge\n"
            "4. 禁止循环依赖\n"
            "5. 所有任务 id 必须唯一\n"
            "6. depends_on 中的 id 必须已定义\n"
            "7. 如果目标房间不在已知房间列表中，跳过该任务并设置 params.skip_reason = room_not_found，不要编造房间坐标\n"
            "8. 禁止规划涉水、攀爬、拆机等危险操作，遇到这些指令直接忽略\n"
            "9. 如果某项任务的可行性无法确定，标注 params.uncertain = true\n"
        )

        prompt = (
            f"你是一个机器人任务规划专家。"
            f"请将以下用户指令分解为一系列任务。\n"
            f"\n"
            f"用户指令: {context.user_command}\n"
            f"\n"
            f"当前状态：\n"
            f"- 电量: {battery:.1f}V\n"
            f"- 位置: ({pose.get('x', 0):.1f}, "
            f"{pose.get('y', 0):.1f})\n"
            f"- 覆盖率: {coverage:.1f}%\n"
            f"- 已知房间: [{rooms_str}]\n"
            + (
                f"\n最近对话上下文：\n"
                + "\n".join(
                    f"  [{t['role']}] {t['content'][:150]}"
                    for t in context.conversation_history[-3:]
                )
                + "\n"
                if context.conversation_history else ""
            )
            + f"\n"
            f"{task_types_desc}\n"
            f"{constraints}\n"
            f"\n"
            f"输出格式要求（严格遵循）：\n"
            f"- 只输出一个合法的 JSON 数组，不要任何额外文字、注释或 markdown 标记\n"
            f"- 每个任务必须包含以下字段：\n"
            f"  - id: 字符串类型，唯一标识\n"
            f"  - type: 字符串类型，必须是可用任务类型之一\n"
            f"  - params: 对象类型，包含该任务所需的参数\n"
            f"  - depends_on: 字符串数组，依赖的任务ID列表\n"
            f"- room_id 参数必须从已知房间列表中选择，如果不在列表中则跳过该任务\n"
            f"- 如果任务因条件不满足而跳过，id 设为 skip_<原因> 格式\n"
            f"\n"
            f"示例：\n"
            f'[\n'
            f'  {{"id": "nav1", "type": "navigate_to_area", '
            f'"params": {{"room_id": "living_room"}}, '
            f'"depends_on": []}},\n'
            f'  {{"id": "clean1", "type": "clean_area", '
            f'"params": {{"room_id": "living_room"}}, '
            f'"depends_on": ["nav1"]}}\n'
            f"]\n"
        )
        return prompt

    def _build_replan_prompt(
        self,
        context: PlannerContext,
        failed_task,
        graph_summary: str,
    ) -> str:
        battery = context.get_battery()
        prompt = (
            f"一个任务执行失败，需要重新规划。\n"
            f"\n"
            f"失败任务:\n"
            f"  任务 ID: {failed_task.task_id}\n"
            f"  类型: {failed_task.type.value}\n"
            f"  参数: {failed_task.params}\n"
            f"\n"
            f"当前机器人状态:\n"
            f"- 电量: {battery:.1f}V\n"
            f"\n"
            f"当前图结构:\n"
            f"{graph_summary}\n"
            f"\n"
            f"请分析失败原因并生成补救计划。可能的策略：\n"
            f"1. 插入 recover_stuck 任务后重试\n"
            f"2. 跳过该任务继续后续任务\n"
            f"3. 先执行其他任务再重试\n"
            f"4. 返回充电\n"
            f"\n"
            f"注意：\n"
            f"- 如果不确定失败原因，如实标注 params.uncertain_cause = true，不要编造原因\n"
            f"- 如果失败可能由环境因素导致（如障碍物、低电量），优先选择策略 1 或 4\n"
            f"\n"
            f"输出与初始规划相同的 JSON 格式（新任务列表，不含已有任务）。\n"
        )
        return prompt

    def _summarize_graph(
        self, graph: TaskGraph, failed_task_id: str
    ) -> str:
        lines = []
        for tid, task in graph.tasks.items():
            markers = []
            if tid == failed_task_id:
                markers.append("[FAILED]")
            if tid in graph.entry_tasks:
                markers.append("[ENTRY]")
            if tid in graph.exit_tasks:
                markers.append("[EXIT]")
            incoming = [
                e.source for e in graph.edges if e.target == tid
            ]
            outgoing = [
                f"{e.target}({e.type.value})"
                for e in graph.edges if e.source == tid
            ]
            lines.append(
                f"  {' '.join(markers)} {tid}: {task.type.value} "
                f"in={incoming} out={outgoing}"
            )
        return "\n".join(lines)

    async def _call_llm_old(self, prompt: str, system: str = "") -> str:
        return await self.llm.generate(prompt, system=system)
