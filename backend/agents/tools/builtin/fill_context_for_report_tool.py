"""报告上下文注入工具（标记型工具，触发后端自动注入上下文）"""
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.prompt_loader import load_report_prompts
from typing import Optional, Callable


class FillContextForReportTool(BaseTool):
    """报告上下文注入工具：调用后触发中间件自动为报告生成场景动态注入上下文信息"""

    name = "fill_context_for_report"
    description = "调用后触发中间件自动为报告生成场景动态注入上下文信息，为后续提示词切换提供上下文支撑"
    parameters = {}

    def __init__(self):
        # 当前注入的上下文缓存，key 可以是 session_id 或 user_id
        self._injected_context: Optional[dict] = None

    async def execute(self, **kwargs) -> ToolResult:
        try:
            # 加载报告 prompt 模板
            report_template = load_report_prompts()
            # 存储上下文（后续 GenerateReportTool 会读取）
            self._injected_context = {
                "template": report_template,
                "injected": True,
            }
            return ToolResult(success=True, data={
                "answer": "上下文已注入，可以开始生成报告",
                "injected": True,
            })
        except Exception as e:
            return ToolResult(success=False, error=f"上下文注入失败: {e}")

    def get_context(self) -> Optional[dict]:
        """供 GenerateReportTool 读取注入的上下文"""
        return self._injected_context

    def clear_context(self):
        """完成报告后清除上下文"""
        self._injected_context = None
