"""Task & Mission database service."""

from datetime import datetime, timedelta
from typing import Optional
from pymysql import MySQLError
from backend.utils.logger_handler import logger


# ═══════════════════════════════════════════════
# Legacy task_history (keep for backward compat)
# ═══════════════════════════════════════════════

def save_task(db, user_id: int = 0, command: str = "", task_type: str = "",
              result: str = "", room: str = "", error_info: str = "",
              answer: str = "") -> bool:
    try:
        with db.cursor() as cur:
            sql = """INSERT INTO task_history (user_id, command, task_type, result, room, error_info, answer)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(sql, (user_id, command, task_type, result, room, error_info, answer))
        db.commit()
        return True
    except MySQLError as e:
        logger.error(f"Save task failed: {e}")
        db.rollback()
        return False


def get_task_stats(db, user_id: int = 0, days: int = 7) -> dict:
    try:
        with db.cursor() as cur:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                "SELECT result, COUNT(*) as cnt FROM task_history "
                "WHERE user_id=%s AND created_at>=%s GROUP BY result",
                (user_id, since)
            )
            rows = cur.fetchall()
            stats = {"total": 0, "success": 0, "failed": 0, "cancelled": 0}
            for r in rows:
                stats[r["result"]] = r["cnt"]
                stats["total"] += r["cnt"]
            return stats
    except MySQLError as e:
        logger.error(f"Get task stats failed: {e}")
        return {"total": 0, "success": 0, "failed": 0, "cancelled": 0}


def get_recent_tasks(db, user_id: int = 0, limit: int = 20) -> list:
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT * FROM task_history WHERE user_id=%s "
                "ORDER BY created_at DESC LIMIT %s",
                (user_id, limit)
            )
            return cur.fetchall()
    except MySQLError as e:
        logger.error(f"Get recent tasks failed: {e}")
        return []


# ═══════════════════════════════════════════════
# Mission History (P0)
# ═══════════════════════════════════════════════

def create_mission(db, user_id: int, command: str, graph_id: str,
                   session_id: str) -> int:
    """Start a mission record, returns mission_id."""
    try:
        with db.cursor() as cur:
            sql = (
                "INSERT INTO mission_history "
                "(user_id, command, graph_id, session_id, status, started_at) "
                "VALUES (%s, %s, %s, %s, 'running', NOW())"
            )
            cur.execute(sql, (user_id, command, graph_id, session_id))
        db.commit()
        return cur.lastrowid
    except MySQLError as e:
        logger.error(f"Create mission failed: {e}")
        db.rollback()
        return -1


def finish_mission(db, mission_id: int, status: str,
                   coverage: float = 0.0, error_info: str = ""):
    """Mark mission as completed/failed with duration and coverage."""
    try:
        with db.cursor() as cur:
            sql = (
                "UPDATE mission_history SET status=%s, finished_at=NOW(), "
                "duration=TIMESTAMPDIFF(SECOND, started_at, NOW()), "
                "coverage_percent=%s, error_info=%s "
                "WHERE id=%s"
            )
            cur.execute(sql, (status, coverage, error_info, mission_id))
        db.commit()
    except MySQLError as e:
        logger.error(f"Finish mission failed: {e}")
        db.rollback()


def get_missions(db, user_id: int = 0, limit: int = 30) -> list:
    """Get recent mission history."""
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT * FROM mission_history WHERE user_id=%s "
                "ORDER BY created_at DESC LIMIT %s",
                (user_id, limit)
            )
            return cur.fetchall()
    except MySQLError as e:
        logger.error(f"Get missions failed: {e}")
        return []


def get_mission(db, mission_id: int) -> Optional[dict]:
    """Get a single mission with its task nodes."""
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM mission_history WHERE id=%s", (mission_id,))
            mission = cur.fetchone()
            if not mission:
                return None
            cur.execute(
                "SELECT * FROM mission_task_nodes WHERE mission_id=%s ORDER BY id",
                (mission_id,)
            )
            mission["tasks"] = cur.fetchall()
            return mission
    except MySQLError as e:
        logger.error(f"Get mission failed: {e}")
        return None


# ═══════════════════════════════════════════════
# Mission Task Nodes (P1)
# ═══════════════════════════════════════════════

def add_task_node(db, mission_id: int, task_id: str, task_type: str,
                  status: str = "pending", error_info: str = ""):
    """Add or update a task execution node."""
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id FROM mission_task_nodes WHERE mission_id=%s AND task_id=%s",
                (mission_id, task_id)
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE mission_task_nodes SET status=%s, error_info=%s WHERE id=%s",
                    (status, error_info, existing["id"])
                )
            else:
                cur.execute(
                    "INSERT INTO mission_task_nodes "
                    "(mission_id, task_id, task_type, status, error_info) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (mission_id, task_id, task_type, status, error_info)
                )
        db.commit()
    except MySQLError as e:
        logger.error(f"Add task node failed: {e}")
        db.rollback()


# ═══════════════════════════════════════════════
# Mission Replay (P2)
# ═══════════════════════════════════════════════

def add_replay_point(db, mission_id: int, x: float, y: float, theta: float,
                     coverage_percent: float = 0.0):
    """Record a trajectory point for replay."""
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO mission_replay (mission_id, x, y, theta, coverage_percent, recorded_at) "
                "VALUES (%s, %s, %s, %s, %s, NOW())",
                (mission_id, x, y, theta, coverage_percent)
            )
        db.commit()
    except MySQLError as e:
        logger.error(f"Add replay point failed: {e}")
        db.rollback()


def get_replay(db, mission_id: int, limit: int = 2000) -> list:
    """Get trajectory replay data."""
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT x, y, theta, coverage_percent, recorded_at "
                "FROM mission_replay WHERE mission_id=%s "
                "ORDER BY recorded_at LIMIT %s",
                (mission_id, limit)
            )
            return cur.fetchall()
    except MySQLError as e:
        logger.error(f"Get replay failed: {e}")
        return []

def delete_task(db, task_id: int) -> bool:
    """Delete a single task_history record."""
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM task_history WHERE id=%s", (task_id,))
        db.commit()
        return True
    except MySQLError as e:
        logger.error(f"Delete task {task_id} failed: {e}")
        db.rollback()
        return False


def delete_mission(db, mission_id: int) -> bool:
    """Delete a single mission and its related nodes + replay points."""
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM mission_replay WHERE mission_id=%s", (mission_id,))
            cur.execute("DELETE FROM mission_task_nodes WHERE mission_id=%s", (mission_id,))
            cur.execute("DELETE FROM mission_history WHERE id=%s", (mission_id,))
        db.commit()
        return True
    except MySQLError as e:
        logger.error(f"Delete mission {mission_id} failed: {e}")
        db.rollback()
        return False


def clear_all_user_history(db, user_id: int = 0) -> bool:
    """Clear all task_history and mission_history for a user."""
    try:
        with db.cursor() as cur:
            cur.execute(
                "DELETE FROM mission_replay WHERE mission_id IN "
                "(SELECT id FROM mission_history WHERE user_id=%s)",
                (user_id,)
            )
            cur.execute(
                "DELETE FROM mission_task_nodes WHERE mission_id IN "
                "(SELECT id FROM mission_history WHERE user_id=%s)",
                (user_id,)
            )
            cur.execute("DELETE FROM mission_history WHERE user_id=%s", (user_id,))
            cur.execute("DELETE FROM task_history WHERE user_id=%s", (user_id,))
        db.commit()
        return True
    except MySQLError as e:
        logger.error(f"Clear history for user {user_id} failed: {e}")
        db.rollback()
        return False
