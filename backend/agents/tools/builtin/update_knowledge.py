"""知识更新工具：将新信息存入长期知识库"""
from backend.agents.tools.base_tool import BaseTool, ToolResult

class UpdateKnowledgeTool(BaseTool):
    """将新知识存入长期知识库，供未来查询"""

    name = "update_knowledge"
    description = "将用户提供的新知识或发现存入长期知识库，如避障技巧、清扫偏好等"
    parameters = {
        "content": {"type": "string", "description": "要存储的知识内容", "required": True},
        "category": {"type": "string", "description": "知识类别，如避障、偏好、技巧", "required": False},
    }

    def __init__(self, long_term_memory=None):
        self._ltm = long_term_memory

    async def execute(self, content="", category="general", **kw):
        if not self._ltm:
            return ToolResult(success=False, error="知识库未配置")
        try:
            text = f"[知识-{category}] {content}"
            await self._ltm.asave_long_memory(text, "")
            return ToolResult(data={"answer": f"已保存知识: {content[:100]}"})
        except Exception as e:
            return ToolResult(success=False, error=f"保存失败: {e}")