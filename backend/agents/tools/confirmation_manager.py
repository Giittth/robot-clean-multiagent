"""确认管理器：管理待处理的用户确认请求"""
import asyncio
import uuid
from typing import Dict, Optional


class ConfirmationManager:
    """管理待用户确认的请求"""

    def __init__(self):
        self._pending: Dict[str, asyncio.Event] = {}
        self._results: Dict[str, bool] = {}
        self._messages: Dict[str, str] = {}

    async def request(self, message: str, timeout: float = 30.0) -> bool:
        """发送确认请求，等待用户回复"""
        cid = uuid.uuid4().hex[:8]
        event = asyncio.Event()
        self._pending[cid] = event
        self._messages[cid] = message
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._results.get(cid, False)
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending.pop(cid, None)
            self._results.pop(cid, None)
            self._messages.pop(cid, None)

    def resolve(self, cid: str, approved: bool) -> bool:
        """用户回复确认结果"""
        if cid not in self._pending:
            return False
        self._results[cid] = approved
        self._pending[cid].set()
        return True

    def get_pending(self) -> list:
        """获取所有待确认请求（用于 WebSocket 推送）"""
        return [
            {"id": cid, "message": msg}
            for cid, msg in self._messages.items()
        ]


# 全局单例
confirm_manager = ConfirmationManager()