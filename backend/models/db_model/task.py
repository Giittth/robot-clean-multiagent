from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TaskHistoryDB(BaseModel):
    id: int
    user_id: int = 0
    command: str
    task_type: Optional[str] = None
    result: Optional[str] = None
    room: Optional[str] = None
    error_info: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
