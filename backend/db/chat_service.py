from typing import List
from pymysql import MySQLError
from backend.models.db_model.chat import ChatHistoryDB
from backend.schemas.chat import ChatHistoryResponse
from backend.utils.logger_handler import logger



def add_chat_record(db, user_id: int, kb_id: int, user_msg: str, ai_msg: str) -> bool:
    """保存一轮对话（用户消息 + AI回复）"""
    try:
        with db.cursor() as cur:
            sql = """
                INSERT INTO chat_history (user_id, kb_id, user_msg, ai_msg)
                VALUES (%s, %s, %s, %s)
            """
            cur.execute(sql, (user_id, kb_id, user_msg, ai_msg))
        db.commit()
        return True
    except MySQLError as e:
        logger.error(f"保存对话失败: {e}")
        db.rollback()
        return False


def get_user_chat_history(
    db,
    user_id: int,
    kb_id: int,
    limit: int = 15
) -> List[ChatHistoryDB]:
    """获取用户聊天历史（数据库模型列表），按时间正序"""
    try:
        with db.cursor() as cur:
            # 子查询：先取最新 limit 条（倒序），再外层正序
            sql = """
                SELECT id, user_id, kb_id, user_msg, ai_msg, create_time
                FROM (
                    SELECT id, user_id, kb_id, user_msg, ai_msg, create_time
                    FROM chat_history
                    WHERE user_id = %s AND kb_id = %s
                    ORDER BY create_time DESC
                    LIMIT %s
                ) AS t
                ORDER BY create_time ASC
            """
            cur.execute(sql, (user_id, kb_id, limit))
            rows = cur.fetchall()
        return [ChatHistoryDB(**row) for row in rows]
    except MySQLError as e:
        logger.error(f"获取历史失败: {e}")
        return []


def format_chat_history(history_rows: List[ChatHistoryDB]) -> List[ChatHistoryResponse]:
    """
    将成对存储的记录转换为前端所需的 role/content 列表
    """
    result = []
    for row in history_rows:
        result.append(
            ChatHistoryResponse(
                role="user",
                content=row.user_msg,
                create_time=row.create_time
            )
        )
        result.append(
            ChatHistoryResponse(
                role="assistant",
                content=row.ai_msg,
                create_time=row.create_time
            )
        )
    return result


def clear_user_chat_history(db, user_id: int, kb_id: int):
    """清空指定用户和知识库的所有聊天记录"""
    try:
        with db.cursor() as cur:
            sql = "DELETE FROM chat_history WHERE user_id = %s AND kb_id = %s"
            cur.execute(sql, (user_id, kb_id))
        db.commit()
        logger.warning(f"清空了用户 {user_id} 知识库 {kb_id} 的所有记录")
    except MySQLError as e:
        logger.error(f"清空失败: {e}")
        db.rollback()