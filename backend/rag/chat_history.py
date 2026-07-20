"""
    短期记忆：聊天历史管理（基于 MySQL）
    表结构：chat_history (id, user_id, kb_id, user_msg, ai_msg, create_time)
"""


import asyncio
from typing import List, Optional
from pymysql import MySQLError
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from backend.db.database import get_db_connection
from backend.utils.logger_handler import logger



class ChatHistory:
    def __init__(self, max_turns: int = 5):
        """
        初始化短期记忆管理器

        Args:
            max_turns: 默认获取的最大对话轮数（每轮包含 user_msg + ai_msg）
        """
        self.max_turns = max_turns


    # 核心方法
    @staticmethod
    def save_message(user_id: int, kb_id: int, user_msg: str, ai_msg: str) -> bool:
        """
        保存一轮对话（用户消息 + AI回复）

        Args:
            user_id: 用户ID
            kb_id: 知识库ID
            user_msg: 用户消息内容
            ai_msg: AI回复内容

        Returns:
            是否保存成功
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO chat_history (user_id, kb_id, user_msg, ai_msg)
                    VALUES (%s, %s, %s, %s)
                """
                cur.execute(sql, (user_id, kb_id, user_msg, ai_msg))
            conn.commit()
            return True
        except MySQLError as e:
            logger.error(f"保存短期记忆失败 (user={user_id}, kb={kb_id}): {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    async def asave_message(user_id: int, kb_id: int, user_msg: str, ai_msg: str) -> bool:
        """
        异步保存一轮对话（用户消息 + AI回复）

        Args:
            user_id: 用户ID
            kb_id: 知识库ID
            user_msg: 用户消息内容
            ai_msg: AI回复内容

        Returns:
            是否保存成功
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            ChatHistory.save_message,
            user_id, kb_id, user_msg, ai_msg
        )


    def get_recent_messages(
        self,
        user_id: int,
        kb_id: int,
        limit: Optional[int] = None
    ) -> List[BaseMessage]:
        """
        获取最近 N 轮对话，返回 LangChain 消息列表（时间正序）

        Args:
            user_id: 用户ID
            kb_id: 知识库ID
            limit: 要获取的对话轮数，默认为 self.max_turns

        Returns:
            消息列表，按时间正序排列。异常时返回空列表。
        """
        limit = limit if limit is not None else self.max_turns
        messages: List[BaseMessage] = []
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # 子查询：先取最新的 limit 条（按时间倒序），再外层按时间正序
                sql = """
                    SELECT user_msg, ai_msg
                    FROM (
                        SELECT user_msg, ai_msg, create_time
                        FROM chat_history
                        WHERE user_id = %s AND kb_id = %s
                        ORDER BY create_time DESC
                        LIMIT %s
                    ) AS t
                    ORDER BY create_time ASC
                """
                cur.execute(sql, (user_id, kb_id, limit))
                rows = cur.fetchall()
                for row in rows:
                    messages.append(HumanMessage(content=row["user_msg"]))
                    messages.append(AIMessage(content=row["ai_msg"]))
        except MySQLError as e:
            logger.error(f"获取短期记忆失败 (user={user_id}, kb={kb_id}): {e}")
            # 异常时返回空列表（已在函数末尾返回 messages）
        finally:
            conn.close()
        return messages

    def get_history_str(self, user_id: int, kb_id: int, limit: Optional[int] = None) -> str:
        """
        返回格式化的历史文本，用于 Prompt 构建

        Args:
            user_id: 用户ID
            kb_id: 知识库ID
            limit: 要获取的对话轮数，默认为 self.max_turns

        Returns:
            格式化的历史字符串，每行格式为 "用户: xxx" 或 "AI: xxx"
        """
        messages = self.get_recent_messages(user_id, kb_id, limit)
        lines = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                lines.append(f"用户: {msg.content}")
            elif isinstance(msg, AIMessage):
                lines.append(f"AI: {msg.content}")
        return "\n".join(lines)


    # 清理与维护方法
    @staticmethod
    def cleanup_old_by_days(user_id: int, kb_id: int, keep_days: int = 30) -> int:
        """
        删除超过 keep_days 天的记录

        Args:
            user_id: 用户ID
            kb_id: 知识库ID
            keep_days: 保留天数，默认30天

        Returns:
            删除的记录行数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                sql = """
                    DELETE FROM chat_history
                    WHERE user_id = %s AND kb_id = %s
                      AND create_time < DATE_SUB(NOW(), INTERVAL %s DAY)
                """
                cur.execute(sql, (user_id, kb_id, keep_days))
                deleted = cur.rowcount
            conn.commit()
            logger.info(f"清理了 {deleted} 条超过 {keep_days} 天的记录 (user={user_id}, kb={kb_id})")
            return deleted
        except MySQLError as e:
            logger.error(f"按天数清理失败: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    @staticmethod
    def cleanup_old_by_turns(user_id: int, kb_id: int, keep_turns: int = 50) -> int:
        """
        保留最近 keep_turns 轮对话，删除更早的记录

        Args:
            user_id: 用户ID
            kb_id: 知识库ID
            keep_turns: 保留的对话轮数，默认50轮

        Returns:
            删除的记录行数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # 获取第 keep_turns 轮（从0开始）的 create_time 阈值
                sql_select = """
                    SELECT create_time FROM chat_history
                    WHERE user_id = %s AND kb_id = %s
                    ORDER BY create_time DESC
                    LIMIT 1 OFFSET %s
                """
                cur.execute(sql_select, (user_id, kb_id, keep_turns - 1))
                row = cur.fetchone()
                if not row:
                    return 0
                threshold = row[0]

                sql_delete = """
                    DELETE FROM chat_history
                    WHERE user_id = %s AND kb_id = %s AND create_time < %s
                """
                cur.execute(sql_delete, (user_id, kb_id, threshold))
                deleted = cur.rowcount
            conn.commit()
            logger.info(f"保留最近 {keep_turns} 轮，删除了 {deleted} 条更早的记录 (user={user_id}, kb={kb_id})")
            return deleted
        except MySQLError as e:
            logger.error(f"按轮数清理失败: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    @staticmethod
    def clear_all(user_id: int, kb_id: int) -> int:
        """
        清空指定用户和知识库的所有聊天记录

        Args:
            user_id: 用户ID
            kb_id: 知识库ID

        Returns:
            删除的记录行数
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chat_history WHERE user_id = %s AND kb_id = %s",
                    (user_id, kb_id)
                )
                deleted = cur.rowcount
            conn.commit()
            logger.warning(f"清空了用户 {user_id} 知识库 {kb_id} 的 {deleted} 条记录")
            return deleted
        except MySQLError as e:
            logger.error(f"清空失败: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()




if __name__ == "__main__":
    ...
