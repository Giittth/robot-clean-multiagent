
"""Agent 记忆系统统一入口"""
from typing import Optional
from backend.agents.memory.working_memory import WorkingMemory
from backend.utils.logger_handler import logger


class AgentMemory:
    """工作记忆 + 情景记忆 + 语义记忆"""

    def __init__(self, user_id: int = 0, rag_tool=None, long_term_memory=None, episodic_memory=None):
        self.user_id = user_id
        self.working = WorkingMemory()
        self._rag = rag_tool
        self._ltm = long_term_memory
        self.episodic = episodic_memory

    async def build_context(self, user_command: str) -> str:
        """构建 LLM 上下文：状态 + 记忆 + 历史"""
        parts = ["[当前状态]", self.working.get_summary()]

        if self._ltm and user_command:
            try:
                memories = await self._ltm.aget_relevant_memory(
                    user_command, max_items=3, max_chars=300
                )
                if memories:
                    parts.extend(["[相关记忆]", memories])
            except Exception as e:
                logger.warning(f"Memory query failed: {e}")

        recent = self.working.get_recent_turns(3)
        if recent:
            parts.append("[最近步骤]")
            for t in recent:
                obs = t.observation[:80] if t.observation else ""
                parts.append(f"  Step {t.step}: {t.action} -> {obs}")

        return "\n\n".join(parts)

    async def save_preference(self, content: str):
        if self._ltm:
            try:
                await self._ltm.asave_long_memory(f"[偏好] {content}", "已记录")
            except Exception as e:
                logger.warning(f"Save memory failed: {e}")

    async def query_knowledge(self, query: str) -> str:
        if self._rag:
            try:
                return await self._rag.query(query)
            except Exception as e:
                logger.warning(f"Knowledge query failed: {e}")
        return ""
