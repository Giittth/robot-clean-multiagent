"""
    Server-Sent Events (SSE) 工具类
    用于统一格式化 SSE 响应数据
"""

import json
from typing import Optional, Any


class SSE:
    """SSE 格式化工具"""

    @staticmethod
    def headers() -> dict:
        """
        返回 SSE 响应所需的 HTTP 头
        """
        return {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }

    @staticmethod
    def format(
        data: Any,
        event: Optional[str] = None,
        id: Optional[str] = None,
        retry: Optional[int] = None
    ) -> str:
        """
        将数据格式化为 SSE 标准格式

        Args:
            data: 要发送的数据（会自动 JSON 序列化）
            event: 事件类型（可选）
            id: 消息 ID（可选）
            retry: 重连时间（毫秒，可选）

        Returns:
            SSE 格式的字符串
        """
        lines = []
        if id:
            lines.append(f"id: {id}")
        if event:
            lines.append(f"event: {event}")
        if retry:
            lines.append(f"retry: {retry}")

        # 如果 data 不是字符串，则转为 JSON 字符串
        if isinstance(data, str):
            data_str = data
        else:
            data_str = json.dumps(data, ensure_ascii=False)

        lines.append(f"data: {data_str}")
        return "\n".join(lines) + "\n\n"