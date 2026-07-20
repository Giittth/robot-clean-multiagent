from fastapi import APIRouter

from .robot import router as robot_router


agent_router = APIRouter()

agent_router.include_router(robot_router, prefix="/robot", tags=["robot"])