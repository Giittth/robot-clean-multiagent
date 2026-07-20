"""知识库查询工具：包装现有 RAGTool"""
from typing import Optional, Callable
from backend.agents.tools.base_tool import BaseTool, ToolResult


class KnowledgeQueryTool(BaseTool):
    """查询机器人相关的知识库（使用说明、常见问题、维护知识）。"""

    name = "knowledge_query"
    description = "查询关于机器人的使用说明、常见问题、维护知识，比如怎么清理滚刷、如何连接WiFi"
    parameters = {
        "question": {
            "type": "string",
            "description": "用户关于机器人使用的问题",
            "required": True,
        }
    }

    def __init__(self, query_fn: Optional[Callable] = None):
        self._query = query_fn

    async def execute(self, question: str = "", **kwargs) -> ToolResult:
        if not self._query:
            return ToolResult(success=False, error="知识库未配置")
        try:
            if callable(self._query):
                result = await self._query(question)
            else:
                result = await self._query.query(question)
            return ToolResult(success=True, data={
                "answer": result or "未找到相关答案",
            })
        except Exception as e:
            return ToolResult(success=False, error=f"知识库查询失败: {e}")