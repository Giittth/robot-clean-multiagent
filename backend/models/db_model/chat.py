from datetime import datetime
from typing import Optional
from pydantic import BaseModel



# 数据库 chat_history 表对应的模型
class ChatHistoryDB(BaseModel):
    id: int
    user_id: int
    kb_id: int
    user_msg: str
    ai_msg: str
    create_time: Optional[datetime] = None

    class Config:
        from_attributes = True