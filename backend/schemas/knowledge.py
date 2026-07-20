from pydantic import BaseModel
from typing import Optional
from datetime import datetime



# 知识库 接口模型
class KnowledgeBaseBase(BaseModel):
    name: str
    description: Optional[str] = None


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBaseResponse(KnowledgeBaseBase):
    id: int
    user_id: int
    is_public: bool          # 公共/私有核心字段
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True


# 文档 接口模型
class KnowledgeDocBase(BaseModel):
    title: str
    content: str
    meta: Optional[str] = None


class KnowledgeDocCreate(KnowledgeDocBase):
    kb_id: int


class KnowledgeDocResponse(KnowledgeDocBase):
    id: int
    kb_id: int
    user_id: int
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True


# 切片 接口模型
class DocumentChunkResponse(BaseModel):
    id: int
    kb_id: int
    doc_id: int
    user_id: int
    content: str
    create_time: Optional[datetime] = None

    class Config:
        from_attributes = True