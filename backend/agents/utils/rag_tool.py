"""
RAG 工具：提供知识库查询功能，支持缓存、超时、降级。
通过外部注入 LLM 客户端，用于真实 RAG 服务。
"""

import asyncio
import time
from collections import OrderedDict
from typing import Optional

from backend.llm.base import BaseLLMClient
from backend.utils.logger_handler import logger


class RAGTool:
    """
    RAG 工具封装，要求外部注入 llm_client，用于创建 RagService。
    """
    MAX_CACHE_SIZE = 128

    def __init__(
        self,
        user_id: int = 0,
        kb_id: int = 1,
        llm_client: Optional[BaseLLMClient] = None,
        timeout: float = 5.0,
        cache_ttl: int = 60,
    ):
        """
        :param user_id: 用户ID
        :param kb_id: 知识库ID
        :param llm_client: 必须提供 BaseLLMClient 实例，用于创建 RagService
        :param timeout: 查询超时时间（秒）
        :param cache_ttl: 缓存有效期（秒）
        """
        if llm_client is None:
            raise ValueError("llm_client is required for RAGTool")

        self.user_id = user_id
        self.kb_id = kb_id
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

        # 动态导入 RagService，避免循环依赖
        from backend.rag.rag_service import RagService
        # 注意：RagService 的构造函数签名是 (user_id, llm_client, kb_id)
        self.rag = RagService(user_id=user_id, llm_client=llm_client, kb_id=kb_id)
        logger.info("RAGTool: Using real RagService with injected LLM client")

    async def query(self, prompt: str) -> str:
        """带 LRU 缓存、超时、降级的 RAG 查询"""
        # 读缓存
        if self.cache_ttl > 0:
            now = time.time()
            if prompt in self._cache:
                answer, expire = self._cache[prompt]
                if now < expire:
                    self._cache.move_to_end(prompt)
                    logger.debug(f"RAG cache hit: {prompt[:50]}...")
                    return answer
                else:
                    del self._cache[prompt]

        try:
            result = await asyncio.wait_for(
                self.rag.generate_answer(query=prompt),
                timeout=self.timeout
            )
            answer = result.get("answer", "")

            if self.cache_ttl > 0 and answer:
                if len(self._cache) >= self.MAX_CACHE_SIZE:
                    self._cache.popitem(last=False)
                self._cache[prompt] = (answer, time.time() + self.cache_ttl)

            return answer

        except asyncio.TimeoutError:
            logger.warning(f"RAG timeout: {prompt[:50]}...")
        except Exception as e:
            logger.error(f"RAG failed: {str(e)}")
        return ""