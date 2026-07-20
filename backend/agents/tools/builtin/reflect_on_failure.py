"""失败分析工具：分析任务失败原因，建议改进"""
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.logger_handler import logger

class ReflectOnFailureTool(BaseTool):
    """分析任务失败原因，给出改进建议"""

    name = "reflect_on_failure"
    description = "分析任务失败原因，给出改进建议"
    parameters = {
        "task_id": {"type": "string", "description": "失败的任务ID", "required": True},
        "error_info": {"type": "string", "description": "错误信息", "required": False},
    }

    def __init__(self, llm_client=None):
        self._llm = llm_client

    async def execute(self, task_id="", error_info="", **kw):
        if not self._llm:
            return ToolResult(data={"answer": f"任务 {task_id} 失败，请检查日志。LLM分析不可用。"})
        messages = [
            {"role": "system", "content": "你是一个机器人故障分析专家。请从导航、电量、障碍物、参数等方面分析失败原因并给出改进建议。"},
            {"role": "user", "content": (
                f"分析以下机器人任务失败原因：\n"
                f"任务ID: {task_id}\n"
                f"错误信息: {error_info or '未知'}\n\n"
                f"请从以下角度分析：\n"
                f"1. 可能的原因（导航卡住、电量不足、障碍物等）\n"
                f"2. 建议的改进方案\n"
                f"3. 是否应该重试"
            )},
        ]
        try:
            resp = await self._llm.chat(messages, temperature=0.3, max_tokens=1024)
            analysis = resp.get("content", "")
            return ToolResult(data={"answer": analysis or f"任务 {task_id} 失败: {error_info}"})
        except Exception as e:
            logger.error(f"ReflectOnFailure failed: {e}")
            return ToolResult(data={"answer": f"任务 {task_id} 失败: {error_info}"})