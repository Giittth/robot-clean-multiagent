"""提问工具：向用户提问并等待文字回复"""
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.agents.tools.question_manager import question_manager

class AskUserTool(BaseTool):
    """向用户提问，等待文字回复。用于需要用户输入信息的场景"""

    name = "ask_user"
    description = "向用户提问并等待文字回复，用于需要用户输入信息或澄清的场景"
    parameters = {
        "question": {"type": "string", "description": "向用户提出的问题", "required": True},
    }

    async def execute(self, question="", **kw):
        try:
            answer = await question_manager.ask(question, timeout=60.0)
            return ToolResult(data={"answer": answer, "question": question})
        except Exception as e:
            return ToolResult(success=False, error=f"提问失败: {e}")