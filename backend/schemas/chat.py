from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict


class ChatHistoryResponse(BaseModel):
    """单条消息（供前端展示）"""
    role: str          # "user" 或 "assistant"
    content: str
    create_time: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """前端发送的聊天请求"""
    user_id: int
    kb_id: int          # 知识库ID
    message: str
    model: Optional[str] = None  # 选择的模型 ID，None 表示使用默认模型


class ChatResponse(BaseModel):
    """AI 返回的最终回答"""
    answer: str
    reference: List[Dict] = []          # 引用的切片来源
    history: List[ChatHistoryResponse]  # 完整对话历史（role/content 列表）


