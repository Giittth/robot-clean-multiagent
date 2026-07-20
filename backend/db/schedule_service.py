"""定时任务 DB 服务：创建、查询、删除"""

from datetime import datetime
from pymysql import MySQLError
from backend.utils.cron_utils import compute_next_run, matches_cron, validate_cron
from backend.utils.logger_handler import logger


def create_schedule(db, user_id: int, command: str, cron_expression: str,
                    description: str = "") -> dict:
    """创建定时任务，计算 next_run，返回 {id, error}"""
    error = validate_cron(cron_expression)
    if error:
        return {"id": -1, "error": error}

    next_run = compute_next_run(cron_expression)
    try:
        with db.cursor() as cur:
            sql = (
                "INSERT INTO schedules (user_id, command, cron_expression, "
                "description, next_run) VALUES (%s, %s, %s, %s, %s)"
            )
            cur.execute(sql, (user_id, command, cron_expression, description, next_run))
        db.commit()
        return {"id": cur.lastrowid, "error": None}
    except MySQLError as e:
        logger.error(f"Create schedule failed: {e}")
        db.rollback()
        return {"id": -1, "error": str(e)}


def get_due_schedules(db) -> list:
    """Get due schedules."""
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT * FROM schedules "
                "WHERE enabled=1 AND next_run IS NOT NULL AND next_run <= NOW()"
            )
            return cur.fetchall()
    except MySQLError as e:
        logger.error(f"Get due schedules failed: {e}")
        return []


def update_next_run(db, schedule_id: int, cron_expression: str):
    """更新 next_run 为 cron 表达式计算的下次触发时间"""
    next_run = compute_next_run(cron_expression)
    if next_run is None:
        logger.warning(f"Cannot compute next_run for schedule {schedule_id}: {cron_expression}")
        return
    try:
        with db.cursor() as cur:
            sql = "UPDATE schedules SET last_run=NOW(), next_run=%s WHERE id=%s"
            cur.execute(sql, (next_run, schedule_id))
        db.commit()
    except MySQLError as e:
        logger.error(f"Update next_run failed: {e}")
        db.rollback()


def get_schedules(db, user_id: int = 0) -> list:
    """Get user schedules."""
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT * FROM schedules WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,)
            )
            return cur.fetchall()
    except MySQLError as e:
        logger.error(f"Get schedules failed: {e}")
        return []


def delete_schedule(db, schedule_id: int) -> bool:
    """删除定时任务"""
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM schedules WHERE id=%s", (schedule_id,))
        db.commit()
        return True
    except MySQLError as e:
        logger.error(f"Delete schedule failed: {e}")
        db.rollback()
        return False


def toggle_schedule(db, schedule_id: int, enabled: bool) -> bool:
    """启用/禁用定时任务"""
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE schedules SET enabled=%s WHERE id=%s", (int(enabled), schedule_id))
        db.commit()
        return True
    except MySQLError as e:
        logger.error(f"Toggle schedule failed: {e}")
        db.rollback()
        return False
