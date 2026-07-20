"""call_planner 工具：在 ReAct 循环中调现有 PlannerManager"""
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.agents.decision.planner.planner_context import PlannerContext, PlanningPolicy
from backend.utils.logger_handler import logger

class CallPlannerTool(BaseTool):
    """将复杂任务交给现有的任务规划器（LLMPlanner / RulePlanner）"""

    name = "call_planner"
    description = "执行清扫、导航、回充等机器人操作。将多步任务交给规划器自动处理。"
    parameters = {
        "command": {
            "type": "string",
            "description": "用户的原始指令，如：清扫客厅、先扫卧室再去厨房",
            "required": True,
        }
    }

    def __init__(self, planner_manager, make_context_fn):
        self._planner = planner_manager
        self._make_ctx = make_context_fn

    async def execute(self, command: str = "", **kw) -> ToolResult:
        if not command:
            return ToolResult(success=False, error="缺少指令")
        try:
            ctx = self._make_ctx(command)
            result = await self._planner.select_and_plan(ctx)
            if not result.success:
                return ToolResult(success=False, error=f"规划失败: {result.warnings}")
            task_count = len(result.graph.tasks)
            logger.info(f"CallPlanner: {command} -> {task_count} tasks")
            return ToolResult(success=True, data={
                "graph": result.graph,
                "task_count": task_count,
                "planner": result.planner_name,
                "answer": f"已规划 {task_count} 个任务，将依次执行",
            })
        except Exception as e:
            logger.error(f"CallPlanner failed: {e}")
            return ToolResult(success=False, error=str(e))