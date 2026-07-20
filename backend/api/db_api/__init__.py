from fastapi import APIRouter

from .knowledge import router as knowledge_router
from .user import router as user_router
from .chat import router as chat_router
from .memory import router as memory_router
from .schedule import router as schedule_router
from .models import router as models_router


db_router = APIRouter()

db_router.include_router(knowledge_router, prefix="/knowledge", tags=["knowledge"])
db_router.include_router(user_router, prefix="/user", tags=["user"])
db_router.include_router(chat_router, prefix="/chat", tags=["chat"])
db_router.include_router(memory_router, prefix="/memory", tags=["memory"])
db_router.include_router(schedule_router, prefix="/schedules", tags=["schedules"])
db_router.include_router(models_router, prefix="/models", tags=["models"])
