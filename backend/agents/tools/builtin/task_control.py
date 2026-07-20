"""任务控制工具：暂停、恢复、停止正在执行的任务"""
from typing import Callable, Any
from backend.agents.tools.base_tool import BaseTool, ToolResult


class TaskControlTool(BaseTool):
    """控制正在执行的任务：暂停、恢复、停止。"""

    name = "task_control"
    description = (
        "控制正在执行的任务：pause=暂停, resume=恢复, stop=停止。"
        "用户说'暂停清扫''停止'时使用此工具"
    )
    parameters = {
        "action": {
            "type": "string",
            "enum": ["pause", "resume", "stop"],
            "description": "控制动作：pause=暂停任务, resume=恢复任务, stop=停止任务",
            "required": True,
        },
    }

    def __init__(self, send_control: Callable[[str], Any]):
        """send_control: 发送控制指令到 Supervisor，如 send_control('pause')"""
        self._send = send_control

    async def execute(self, action: str = "", **kwargs) -> ToolResult:
        if not action:
            return ToolResult(success=False, error="缺少动作参数")
        actions_cn = {"pause": "暂停", "resume": "恢复", "stop": "停止"}
        try:
            result = self._send(action)
            if result is not None and hasattr(result, '__await__'):
                await result
            return ToolResult(success=True, data={
                "answer": f"已发送{actions_cn.get(action, action)}指令",
            })
        except Exception as e:
            return ToolResult(success=False, error=f"指令发送失败: {e}")
