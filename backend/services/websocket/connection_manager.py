"""
管理所有活跃的 WebSocket 连接，提供广播功能。
"""

from typing import Set
from fastapi import WebSocket
from backend.utils.logger_handler import logger


class ConnectionManager:
    def __init__(self):
        self._active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        """接受连接并加入集合"""
        await ws.accept()
        self._active.add(ws)
        logger.info(f"WebSocket connected, total: {len(self._active)}")

    def disconnect(self, ws: WebSocket):
        """移除断开连接"""
        self._active.discard(ws)
        logger.info(f"WebSocket disconnected, remaining: {len(self._active)}")

    async def broadcast(self, data: dict):
        """向所有活跃客户端广播 JSON 数据，自动清理失效连接"""
        for ws in list(self._active):
            try:
                await ws.send_json(data)
            except Exception:
                self._active.discard(ws)