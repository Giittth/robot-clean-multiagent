from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ScheduleDB(BaseModel):
    id: int
    user_id: int = 0
    command: str
    cron_expression: str
    enabled: bool = True
    description: Optional[str] = None
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    created_at: Optional[datetime] = None
