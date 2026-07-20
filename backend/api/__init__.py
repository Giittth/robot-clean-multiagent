from fastapi import APIRouter

from .db_api import db_router
from .agent_api import agent_router


api_router = APIRouter(prefix="/api")

api_router.include_router(db_router)
api_router.include_router(agent_router)