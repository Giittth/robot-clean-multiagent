"""定时任务管理 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.db.database import get_db_connection
from backend.db.schedule_service import (
    create_schedule, get_schedules, delete_schedule,
    toggle_schedule, validate_cron,
)
from backend.utils.logger_handler import logger

router = APIRouter(tags=["定时任务"])


class ScheduleCreate(BaseModel):
    command: str
    cron_expression: str
    description: str = ""
    user_id: int = 0


class ScheduleToggle(BaseModel):
    enabled: bool = True


@router.get("")
async def list_schedules(user_id: int = 0):
    db = get_db_connection()
    try:
        return get_schedules(db, user_id=user_id)
    except Exception as e:
        logger.error(f"List schedules failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("")
async def add_schedule(body: ScheduleCreate):
    logger.info(f"Creating schedule: command={body.command}, cron={body.cron_expression}")
    if not body.command or not body.cron_expression:
        raise HTTPException(status_code=400, detail="command 和 cron_expression 必填")
    err = validate_cron(body.cron_expression)
    if err:
        raise HTTPException(status_code=400, detail=err)
    db = get_db_connection()
    try:
        result = create_schedule(db, body.user_id, body.command,
                                 body.cron_expression, body.description)
        if result.get("error"):
            logger.error(f"Schedule create failed: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
        logger.info(f"Schedule created: id={result.get('id')}")
        return {"id": result["id"], "status": "created"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Schedule create unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")
    finally:
        db.close()


@router.delete("/{schedule_id}")
async def remove_schedule(schedule_id: int):
    db = get_db_connection()
    try:
        if delete_schedule(db, schedule_id):
            return {"status": "deleted"}
        raise HTTPException(status_code=404, detail="不存在")
    finally:
        db.close()


@router.put("/{schedule_id}/toggle")
async def toggle(schedule_id: int, body: ScheduleToggle):
    db = get_db_connection()
    try:
        if toggle_schedule(db, schedule_id, body.enabled):
            return {"status": "updated", "enabled": body.enabled}
        raise HTTPException(status_code=404, detail="不存在")
    finally:
        db.close()