"""获取当前用户 ID 的工具"""
from backend.agents.tools.base_tool import BaseTool, ToolResult
from typing import Callable, Optional


class GetUserIdTool(BaseTool):
    """获取当前用户的唯一标识（ID）"""

    name = "get_user_id"
    description = "获取当前用户的唯一标识（ID），ID格式为数字字符串（如'1001'）"
    parameters = {}

    def __init__(self, get_user_id_fn: Optional[Callable[[], str]] = None):
        self._get_user_id = get_user_id_fn or (lambda: "0")

    async def execute(self, **kwargs) -> ToolResult:
        try:
            user_id = self._get_user_id()
            return ToolResult(success=True, data={
                "answer": f"{user_id}",
                "user_id": str(user_id),
            })
        except Exception as e:
            return ToolResult(success=False, error=f"获取用户ID失败: {e}")
