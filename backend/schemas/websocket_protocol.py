"""
定义 WebSocket 客户端发送的消息格式。
"""

from enum import Enum
from pydantic import BaseModel
from typing import Optional


class MessageType(str, Enum):
    PING = "ping"
    CONTROL = "control"
    SUBSCRIBE = "subscribe"

class ClientMessage(BaseModel):
    type: MessageType
    command: Optional[str] = None
    topic: Optional[str] = None