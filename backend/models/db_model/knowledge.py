from pydantic import BaseModel
from datetime import datetime
from typing import Optional



# 知识库表
class KnowledgeBaseDB(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    user_id: int          # 0=系统公共
    is_public: int        # 0=私有，1=公共
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True



# 文档表
class KnowledgeDocDB(BaseModel):
    id: int
    kb_id: int
    title: str
    content: str
    user_id: int
    meta: Optional[str] = None
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True



# 3. 文档切片表
class DocumentChunkDB(BaseModel):
    id: int
    kb_id: int
    doc_id: int
    user_id: int
    content: str
    create_time: Optional[datetime] = None

    class Config:
        from_attributes = True