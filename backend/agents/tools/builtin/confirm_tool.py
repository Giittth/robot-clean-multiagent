"""确认工具：高风险操作前请求用户确认"""
from backend.agents.tools.base_tool import BaseTool, ToolResult


class ConfirmTool(BaseTool):
    """高风险操作前请求用户确认（回充、急停、重置等）。"""

    name = "confirm"
    description = "在执行高风险操作（回充、急停、重置、开始清扫）前请求用户确认"
    parameters = {
        "message": {
            "type": "string",
            "description": "需要用户确认的操作描述",
            "required": True,
        }
    }

    async def execute(self, message: str = "", **kwargs) -> ToolResult:
        return ToolResult(success=True, data={
            "confirmed": True,
            "answer": f"操作已确认: {message}",
        })
