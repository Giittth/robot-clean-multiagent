"""
    长期记忆（用户习惯、偏好、固定信息）
    支持异步、去重合并、更新、管理
"""


import os
import hashlib
from datetime import datetime
from typing import List, Optional, Tuple, Any

from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import PromptTemplate

from backend.config import settings, BASE_DIR
from backend.utils.logger_handler import logger
from backend.utils.file_handler import get_abs_path



# 默认配置
DEFAULT_SIMILARITY_THRESHOLD = 0.7   # 相似度高于此值才认为匹配
DEFAULT_MAX_MEMORIES = 200           # 每个用户最多保留的记忆条数
DEFAULT_K_RETRIEVAL = 3              # 检索时返回的候选记忆数量


class LongTermMemory:
    """长期记忆：用户偏好、习惯、关键信息（异步优先）"""

    def __init__(self, user_id: int):
        self.user_id: int = user_id

        self.llm = ChatOllama(
            model=settings.model_name,
            base_url=settings.base_url,
            temperature=settings.temperature
        )

        # 向量库（同步接口，但通过 asyncio.to_thread 包装异步调用）
        self._vector_store = Chroma(
            collection_name="long_term_memory",
            embedding_function=OllamaEmbeddings(
                model=settings.embedding_name,
                base_url=settings.base_url
            ),
            persist_directory=get_abs_path(settings.long_term_memory_dir)
        )

    # 公共异步接口

    async def aget_relevant_memory(
        self,
        user_input: str,
        max_items: int = 3,
        max_chars: int = 500,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> str:
        """
        异步获取与当前输入相关的长期记忆（过滤低相似度）
        返回格式化文本，每条记忆间用 \n\n 分隔
        """
        try:
            docs_with_scores = await self._asimilarity_search_with_score(
                user_input, k=DEFAULT_K_RETRIEVAL
            )
        except Exception as e:
            logger.error(f"记忆检索失败 user_id={self.user_id}: {e}")
            return ""

        # 过滤并格式化
        memories = []
        for doc, score in docs_with_scores:
            if score < similarity_threshold:
                continue
            content = doc.page_content.strip()
            if content:
                memories.append(content)
            if len(memories) >= max_items:
                break

        if not memories:
            return ""

        result_text = "\n\n".join(memories)
        if len(result_text) > max_chars:
            result_text = result_text[:max_chars] + "..."
        return result_text

    async def asave_long_memory(self, user_input: str, ai_output: str) -> None:
        """
        异步保存长期记忆（如果对话中包含值得记忆的信息）
        """
        if not self._should_save_memory(user_input):
            logger.debug(f"跳过保存：输入太短或为问候语 user_id={self.user_id}")
            return

        memories = await self._aextract_content(user_input, ai_output)
        if not memories:
            return

        for mem_text in memories:
            await self._aupdate_single_memory(mem_text)

    async def alist_memories(self, limit: int = 100) -> List[dict]:
        """
        列出用户的所有长期记忆（用于管理界面）
        返回: [{"id": str, "text": str, "timestamp": str, "score": float}, ...]
        """
        try:
            all_data = await self._aget_all_user_docs()
            all_data.sort(key=lambda x: x["timestamp"], reverse=True)
            return all_data[:limit]
        except Exception as e:
            logger.error(f"列出记忆失败 user_id={self.user_id}: {e}")
            return []

    async def adelete_memory(self, memory_id: str) -> bool:
        """删除指定 ID 的长期记忆"""
        try:
            await self._adelete_by_ids([memory_id])
            return True
        except Exception as e:
            logger.error(f"删除记忆失败 {memory_id}: {e}")
            return False

    async def aclear_all_memories(self) -> bool:
        """清空用户的所有长期记忆（慎用）"""
        try:
            docs = await self._aget_all_user_docs()
            ids = [doc["id"] for doc in docs]
            if ids:
                await self._adelete_by_ids(ids)
            return True
        except Exception as e:
            logger.error(f"清空记忆失败 user_id={self.user_id}: {e}")
            return False

    # ==================== 内部异步辅助方法 ====================

    async def _asimilarity_search_with_score(self, query: str, k: int) -> List[Tuple[Any, float]]:
        """
        异步执行相似度搜索（包装 Chroma 的同步方法）
        返回 [(Document, score), ...]
        """
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._vector_store.similarity_search_with_score(
                query, k=k, filter={"user_id": str(self.user_id)}
            )
        )

    async def _aget_all_user_docs(self) -> List[dict]:
        """获取该用户的所有文档（包含 id, page_content, metadata）"""
        import asyncio
        loop = asyncio.get_running_loop()

        def _get():
            all_data = self._vector_store.get()
            docs = []
            for idx, text in enumerate(all_data.get("documents", [])):
                meta = all_data["metadatas"][idx]
                if meta.get("user_id") == str(self.user_id):
                    docs.append({
                        "id": all_data["ids"][idx],
                        "text": text,
                        "timestamp": meta.get("timestamp", ""),
                        "metadata": meta
                    })
            return docs

        return await loop.run_in_executor(None, _get)

    async def _adelete_by_ids(self, ids: List[str]) -> None:
        """异步删除指定 ID 的文档"""
        import asyncio
        if not ids:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self._vector_store.delete(ids))

    async def _aadd_texts(self, texts: List[str], metadatas: List[dict], ids: List[str]) -> None:
        """异步添加文档"""
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._vector_store.add_texts(texts, metadatas=metadatas, ids=ids)
        )

    async def _aupdate_single_memory(self, new_memory: str) -> None:
        """
        更新或添加单条记忆：
        1. 检索最相似的现有记忆（相似度）
        2. 如果相似度 > 阈值，进行合并；否则作为新记忆添加
        3. 若合并后内容变化，删除旧记忆，添加新记忆；若无变化则跳过
        """
        similar = await self._asimilarity_search_with_score(new_memory, k=1)
        best_doc = None
        best_score = 0.0
        if similar:
            best_doc, best_score = similar[0]

        if best_doc and best_score >= DEFAULT_SIMILARITY_THRESHOLD:
            merged = await self._amerge_with_existing(new_memory, best_doc.page_content)
            if merged is None:
                return
            if merged == best_doc.page_content:
                return
            await self._adelete_by_ids([best_doc.metadata.get("id") or best_doc.metadata["_id"]])
            new_id = self._generate_memory_id(merged)
            await self._aadd_texts(
                texts=[merged],
                metadatas=[{
                    "user_id": str(self.user_id),
                    "memory_type": "long_term",
                    "timestamp": datetime.utcnow().isoformat(),
                    "id": new_id
                }],
                ids=[new_id]
            )
        else:
            new_id = self._generate_memory_id(new_memory)
            await self._aadd_texts(
                texts=[new_memory],
                metadatas=[{
                    "user_id": str(self.user_id),
                    "memory_type": "long_term",
                    "timestamp": datetime.utcnow().isoformat(),
                    "id": new_id
                }],
                ids=[new_id]
            )

        await self._atrim_memories_if_needed()

    async def _amerge_with_existing(self, new_memory: str, existing_memory: str) -> Optional[str]:
        """
        合并新记忆与现有记忆，返回合并后的字符串。
        返回 None 表示重复（无需存储）；
        返回空字符串表示出错；
        否则返回合并后的文本。
        """
        merge_prompt = PromptTemplate.from_template("""
现有记忆：{existing}
新信息：{new_info}
请根据以下规则输出结果（只输出文本，不要解释）：
- 如果新信息与现有记忆重复或矛盾（例如现有记忆是“用户喜欢苹果”，新信息是“用户喜欢苹果”），输出：__DUPLICATE__
- 如果新信息是补充或修正（例如现有“用户喜欢苹果”，新“用户也喜欢香蕉”），输出合并后的一句话，保留原有信息并补充新信息。
- 如果新信息是全新内容，直接输出新信息本身。

现有记忆：{existing}
新信息：{new_info}
输出：""")
        chain = merge_prompt | self.llm | StrOutputParser()
        try:
            result = await chain.ainvoke({
                "existing": existing_memory[:500],
                "new_info": new_memory
            })
        except Exception as e:
            logger.error(f"合并记忆 LLM 调用失败: {e}")
            return new_memory

        if "__DUPLICATE__" in result:
            return None
        result = result.strip()
        return result if result else None

    async def _aextract_content(self, user_input: str, ai_output: str) -> List[str]:
        """从对话中提取值得记忆的片段"""
        conversation_text = f"用户：{user_input}\n助手：{ai_output}"

        extract_prompt = PromptTemplate.from_template("""
你是记忆管理助手，负责从用户对话中提取【需要长期记住的关键事实】
要求：
1. 只保留跨会话有用的：用户偏好、习惯、个人信息、固定需求
2. 临时闲聊、一次性问题、无关内容 直接输出：无需记忆
3. 精简为 1~2 句短句
4. 不要冗余、不要对话原文
5. 如果有多个记忆点，用分号分隔

对话内容：
{conversation}
请输出结果（没有则输出空字符串）：
        """)

        chain = extract_prompt | self.llm | StrOutputParser()
        try:
            result = await chain.ainvoke({"conversation": conversation_text})
        except Exception as e:
            logger.error(f"提取记忆失败: {e}")
            return []

        if not result or "无需记忆" in result:
            return []
        memories = [m.strip() for m in result.split("；") if m.strip()]
        return memories

    async def _atrim_memories_if_needed(self, max_memories: int = DEFAULT_MAX_MEMORIES) -> None:
        """如果记忆数量超过限制，删除最旧的若干条"""
        all_memories = await self._aget_all_user_docs()
        if len(all_memories) <= max_memories:
            return
        all_memories.sort(key=lambda x: x["timestamp"])
        to_delete = all_memories[:len(all_memories) - max_memories]
        ids_to_delete = [m["id"] for m in to_delete]
        if ids_to_delete:
            await self._adelete_by_ids(ids_to_delete)
            logger.info(f"清理了 {len(ids_to_delete)} 条旧记忆，用户 {self.user_id}")

    # ==================== 同步兼容方法（供旧代码调用） ====================

    def get_relevant_memory(self, user_input: str, max_items: int = 3, max_chars: int = 500) -> str:
        """同步版本，内部调用异步（不推荐在事件循环中使用）"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self.aget_relevant_memory(user_input, max_items, max_chars)
                )
                return future.result()
        else:
            return asyncio.run(self.aget_relevant_memory(user_input, max_items, max_chars))

    def save_long_memory(self, user_input: str, ai_output: str) -> None:
        """同步版本（兼容旧调用）"""
        import asyncio
        try:
            asyncio.run(self.asave_long_memory(user_input, ai_output))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.asave_long_memory(user_input, ai_output))

    # ==================== 私有辅助方法 ====================

    @staticmethod
    def _should_save_memory(user_input: str) -> bool:
        """启发式判断是否值得保存记忆（保留原有逻辑）"""
        if len(user_input) < 5:
            return False

        greetings = ["你好", "您好", "hi", "hello"]
        cleaned = user_input
        for g in greetings:
            cleaned = cleaned.replace(g, "")
        if len(cleaned) < 4:
            return False

        stop_words = ["吗", "啊", "哦", "哦哦", "哦哦哦"]
        for w in stop_words:
            cleaned = cleaned.replace(w, "")
        return len(cleaned) >= 4

    def _generate_memory_id(self, memory_text: str) -> str:
        """生成稳定的记忆 ID（基于内容和 user_id 哈希）"""
        content = f"{self.user_id}:{memory_text}"
        return hashlib.md5(content.encode()).hexdigest()



if __name__ == "__main__":
    ...



