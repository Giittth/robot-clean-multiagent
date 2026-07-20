"""搜索记忆工具：检索过去相似任务的执行记录"""
from backend.agents.tools.base_tool import BaseTool, ToolResult

class SearchMemoryTool(BaseTool):
    """检索过去相似任务的执行记录，供参考"""

    name = "search_memory"
    description = "检索过去相似任务的执行记录，供当前决策参考"
    parameters = {
        "query": {"type": "string", "description": "搜索关键词，如清扫南室1、回充失败", "required": True},
    }

    def __init__(self, episodic_memory=None):
        self._memory = episodic_memory

    async def execute(self, query="", **kw):
        if not self._memory:
            return ToolResult(data={"answer": "记忆系统未配置"})
        try:
            result = await self._memory.query_similar(query)
            return ToolResult(data={"answer": result or "未找到相关历史记录"})
        except Exception as e:
            return ToolResult(success=False, error=f"记忆检索失败: {e}")