"""获取当前月份的工具"""
from datetime import datetime
from backend.agents.tools.base_tool import BaseTool, ToolResult


class GetCurrentMonthTool(BaseTool):
    """获取系统当前月份，格式为 YYYY-MM"""

    name = "get_current_month"
    description = "获取系统当前月份，格式固定为 YYYY-MM（如'2026-07'）"
    parameters = {}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            month = datetime.now().strftime("%Y-%m")
            return ToolResult(success=True, data={
                "answer": month,
                "month": month,
            })
        except Exception as e:
            return ToolResult(success=False, error=f"获取当前月份失败: {e}")
