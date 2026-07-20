from pydantic import BaseModel
from datetime import datetime
from typing import Optional




# 数据库 users 表结构
class UserDB(BaseModel):
    id: int
    username: str
    password: str          # 数据库必须存密码
    create_time: Optional[datetime] = None

    class Config:
        from_attributes = True