"""情景记忆：存储和检索过往任务记录，包装 LongTermMemory"""
from typing import Optional
from backend.rag.long_term_memory import LongTermMemory
from backend.utils.logger_handler import logger


class EpisodicMemory:
    """情景记忆：记录过往任务，供 ReAct 循环参考"""

    def __init__(self, long_term_memory: Optional[LongTermMemory] = None):
        self._ltm = long_term_memory

    async def store_task(self, command: str, success: bool, summary: str = ""):
        """存储一次任务执行记录（直接写向量库，不经过 LLM 提取）"""
        if not self._ltm:
            return
        try:
            import uuid
            from datetime import datetime
            status = "成功" if success else "失败"
            content = f"[任务记录] 用户: {command} | 结果: {status}"
            if summary:
                content += f" | {summary[:200]}"
            mid = uuid.uuid4().hex
            await self._ltm._aadd_texts(
                texts=[content],
                metadatas=[{
                    "user_id": str(self._ltm.user_id),
                    "memory_type": "episodic",
                    "timestamp": datetime.utcnow().isoformat(),
                    "id": mid,
                }],
                ids=[mid],
            )
            logger.debug(f"EpisodicMemory stored: {content[:60]}")
        except Exception as e:
            logger.warning(f"EpisodicMemory store failed: {e}")

    async def query_similar(self, command: str) -> str:
        """检索相似历史任务的执行记录"""
        if not self._ltm:
            return ""
        try:
            return await self._ltm.aget_relevant_memory(
                command, max_items=3, max_chars=500
            )
        except Exception as e:
            logger.warning(f"EpisodicMemory query failed: {e}")
            return ""

    async def get_stats(self) -> str:
        """返回历史任务统计摘要"""
        if not self._ltm:
            return "记忆未配置"
        try:
            memories = await self._ltm.alist_memories(limit=100)
            if not memories:
                return "暂无任务记录"
            total = len(memories)
            successes = sum(1 for m in memories if "成功" in m.get("text", ""))
            return f"共 {total} 条任务记录，{successes} 条成功 (成功率 {successes/total*100:.0f}%)"
        except Exception as e:
            return f"查询失败: {e}"