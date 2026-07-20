"""通知工具：发送通知推送到前端 WebSocket"""
from typing import Optional, Callable, Any
from backend.agents.tools.base_tool import BaseTool, ToolResult


class NotifyTool(BaseTool):
    """发送通知消息到用户界面（通过 WebSocket 直接推送）。"""

    name = "notify"
    description = "发送通知到用户界面（任务完成提醒、异常警告等）"
    parameters = {
        "message": {
            "type": "string",
            "description": "通知内容",
            "required": True,
        },
        "level": {
            "type": "string",
            "enum": ["info", "success", "warning", "error"],
            "description": "通知级别，默认 info",
        },
    }

    def __init__(self, broadcast_fn: Optional[Callable[[dict], Any]] = None):
        """broadcast_fn: 发送数据到所有 WebSocket 客户端的函数"""
        self._broadcast = broadcast_fn

    async def execute(self, message: str = "", level: str = "info", **kw) -> ToolResult:
        try:
            data = {
                "type": "ui.notification",
                "payload": {"message": message, "level": level},
            }
            if self._broadcast:
                await self._broadcast(data)
            return ToolResult(success=True, data={
                "answer": f"通知已发送: {message}",
            })
        except Exception as e:
            return ToolResult(success=False, error=f"通知发送失败: {e}")