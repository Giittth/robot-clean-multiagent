"""定时器工具：延时执行（单次定时，非 cron 周期性任务）"""
import asyncio
import uuid
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timezone
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.logger_handler import logger


class TimerTool(BaseTool):
    """单次延时定时器，在指定延迟后执行回调或发送通知。非周期性 cron 任务。"""

    name = "timer"
    description = "设置单次延时定时器，在指定时间后执行操作或发送提醒。支持秒级精度，非重复定时。"
    parameters = {
        "action": {
            "type": "string",
            "enum": ["start", "cancel", "list"],
            "description": "操作类型：start=启动定时器, cancel=取消定时器, list=查看活跃定时器列表",
            "required": True,
        },
        "delay_seconds": {
            "type": "integer",
            "description": "延时秒数（action=start 时必填），最少 5 秒",
        },
        "message": {
            "type": "string",
            "description": "定时器触发时要显示的提醒消息",
        },
        "timer_id": {
            "type": "string",
            "description": "定时器 ID（action=cancel 时必填，用于取消指定定时器）",
        },
    }

    def __init__(self, on_timer_fire: Optional[Callable[[str, str], Any]] = None):
        """
        Args:
            on_timer_fire: 定时器触发时的回调函数，接收 (timer_id, message) 参数（可选）
        """
        self._on_timer_fire = on_timer_fire
        self._active_timers: Dict[str, asyncio.Task] = {}
        self._timer_metadata: Dict[str, Dict[str, Any]] = {}

    async def execute(
        self,
        action: str = "",
        delay_seconds: Optional[int] = None,
        message: str = "",
        timer_id: str = "",
        **kwargs,
    ) -> ToolResult:
        try:
            if action == "start":
                return await self._start_timer(delay_seconds, message)
            elif action == "cancel":
                return await self._cancel_timer(timer_id)
            elif action == "list":
                return self._list_timers()
            else:
                return ToolResult(success=False, error=f"不支持的操作: {action}")
        except Exception as e:
            logger.error(f"Timer tool failed: {e}")
            return ToolResult(success=False, error=f"定时器操作失败: {e}")

    async def _start_timer(self, delay_seconds: Optional[int], message: str) -> ToolResult:
        if delay_seconds is None or delay_seconds < 5:
            return ToolResult(success=False, error="延时至少 5 秒，请提供 delay_seconds >= 5")

        timer_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        metadata = {
            "timer_id": timer_id,
            "delay_seconds": delay_seconds,
            "message": message or "定时器触发",
            "created_at": now.isoformat(),
        }
        self._timer_metadata[timer_id] = metadata
        task = asyncio.create_task(self._timer_loop(timer_id, delay_seconds, message))
        self._active_timers[timer_id] = task
        return ToolResult(success=True, data={
            "answer": f"定时器已启动（ID: {timer_id}），将在 {delay_seconds} 秒后触发",
            **metadata,
        })

    async def _cancel_timer(self, timer_id: str) -> ToolResult:
        if not timer_id:
            return ToolResult(success=False, error="取消定时器需要提供 timer_id 参数")
        task = self._active_timers.pop(timer_id, None)
        self._timer_metadata.pop(timer_id, None)
        if task is None:
            return ToolResult(success=False, error=f"未找到定时器: {timer_id}")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return ToolResult(success=True, data={
            "answer": f"定时器 {timer_id} 已取消",
            "timer_id": timer_id,
        })

    def _list_timers(self) -> ToolResult:
        if not self._active_timers:
            return ToolResult(success=True, data={
                "answer": "当前没有活跃的定时器",
                "timers": [], "count": 0,
            })
        lines = [f"当前有 {len(self._active_timers)} 个活跃定时器:"]
        timer_list = []
        for tid, meta in self._timer_metadata.items():
            if tid in self._active_timers:
                lines.append(f"  - [{tid}] 消息: {meta['message']}")
                timer_list.append({
                    "timer_id": tid,
                    "message": meta["message"],
                })
        return ToolResult(success=True, data={
            "answer": "\n".join(lines),
            "timers": timer_list,
            "count": len(timer_list),
        })

    async def _timer_loop(self, timer_id: str, delay: int, message: str):
        try:
            await asyncio.sleep(delay)
            logger.info(f"Timer {timer_id} fired: {message}")
            if self._on_timer_fire:
                try:
                    result = self._on_timer_fire(timer_id, message)
                    if hasattr(result, "__await__"):
                        await result
                except Exception as e:
                    logger.error(f"Timer callback failed: {e}")
        except asyncio.CancelledError:
            logger.info(f"Timer {timer_id} cancelled")
            raise
        finally:
            self._active_timers.pop(timer_id, None)
            self._timer_metadata.pop(timer_id, None)
