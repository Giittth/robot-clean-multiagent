import asyncio
from datetime import datetime
from backend.utils.logger_handler import logger


class SchedulerService:
    def __init__(self, bus, get_db_fn):
        self._bus = bus
        self._get_db = get_db_fn
        self._running = False
        self._task = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("SchedulerService started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("SchedulerService stopped")

    async def _loop(self):
        from backend.agents.schemas.messages import Message, MessageType
        from backend.db.schedule_service import get_due_schedules, update_next_run
        while self._running:
            try:
                db = self._get_db()
                try:
                    due = get_due_schedules(db)
                    for s in due:
                        msg = Message(
                            type=MessageType.TASK, source="scheduler",
                            payload={"text": s["command"]}, priority=MessageType.TASK,
                        )
                        # Use correct priority value
                        from backend.agents.schemas.messages import Priority
                        msg.priority = Priority.HIGH
                        await self._bus.publish(msg)
                        logger.info(f"Scheduler triggered: {s['command']}")
                        update_next_run(db, s["id"], s["cron_expression"])
                    if due:
                        db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error(f"Scheduler loop error: {e}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Scheduler DB error: {e}")
            await asyncio.sleep(60)
