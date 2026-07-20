"""记忆工具：存储和查询用户偏好"""
from typing import Optional, Callable
from backend.agents.tools.base_tool import BaseTool, ToolResult


class MemoryTool(BaseTool):
    """存储或查询用户偏好/习惯，供未来任务参考。"""

    name = "memory"
    description = "存储用户偏好或习惯（比如记得先扫主卧），或查询已存储的偏好"
    parameters = {
        "action": {
            "type": "string",
            "enum": ["save", "query"],
            "description": "save=存储偏好, query=查询已有偏好",
            "required": True,
        },
        "content": {
            "type": "string",
            "description": "要存储或查询的偏好内容，如：先扫主卧再扫客厅",
        },
    }

    def __init__(self, save_fn: Optional[Callable] = None,
                 query_fn: Optional[Callable] = None):
        self._save = save_fn
        self._query = query_fn

    async def execute(self, action: str = "query", content: str = "",
                      **kwargs) -> ToolResult:
        if action == "save":
            if not self._save:
                return ToolResult(success=False, error="记忆存储未配置")
            try:
                await self._save(content)
                return ToolResult(data={"answer": f"已记录偏好: {content}"})
            except Exception as e:
                return ToolResult(success=False, error=f"存储失败: {e}")
        if not self._query:
            return ToolResult(data={"answer": "暂无存储的偏好记录"})
        try:
            result = await self._query("偏好 " + content)
            return ToolResult(data={"answer": result or "未找到相关偏好"})
        except Exception as e:
            return ToolResult(success=False, error=f"查询失败: {e}")