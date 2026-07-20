"""
RAG 服务（整合短期+长期记忆 + 知识库管理 + 混合检索 + 异步优化）
支持登录模式（user_id > 0）和游客模式（user_id = 0），查询路由、重写、多提示词链
现已解耦具体 LLM 实现，通过 BaseLLMClient 调用。
"""

import asyncio
from enum import Enum
from typing import List, Dict, Any, AsyncGenerator, Optional

from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from backend.config import settings
from backend.llm.factory import LLMClientFactory
from backend.rag.vector.vector_optimization import vector_opt
from backend.rag.long_term_memory import LongTermMemory
from backend.rag.chat_history import ChatHistory
from backend.utils.prompt_loader import (
    summarize_prompts, repair_prompts, maintain_prompts, report_prompts,
    guide_prompts, query_routing_prompts, query_rewriting_prompts
)
from backend.utils.logger_handler import logger
from backend.llm.base import BaseLLMClient

# 路由类型枚举
class RouteType(str, Enum):
    GENERAL = "general"
    REPAIR = "repair"
    MAINTAIN = "maintain"
    GUIDE = "guide"
    REPORT = "report"

# 路由到知识库ID的映射（使用枚举键）
DOMAIN_KB_MAP = {
    RouteType.GENERAL: 1,
    RouteType.REPAIR: 2,
    RouteType.MAINTAIN: 3,
    RouteType.GUIDE: 4,
}
PUBLIC_KB_ID = 1


class RagService:
    def __init__(
        self,
        user_id: int,
        llm_client: BaseLLMClient,
        kb_id: Optional[int] = None
    ):
        """
        初始化 RAG 服务
        :param user_id: 用户ID（游客为0）
        :param llm_client: 统一大模型客户端
        :param kb_id: 知识库ID，游客模式下会被覆盖为 PUBLIC_KB_ID
        """
        self.user_id = user_id
        self.is_guest = (user_id == 0)
        self.kb_id = PUBLIC_KB_ID if self.is_guest else kb_id
        self.llm = llm_client  # 注入统一客户端

        # 短期记忆（对话历史）和长期记忆（用户偏好）
        self.chat_memory = ChatHistory(max_turns=5)
        self.long_memory = LongTermMemory(user_id) if not self.is_guest else None

        # 提示词模板（保留原有 LangChain 格式）
        self.summarize_prompt = PromptTemplate.from_template(summarize_prompts)
        self.repair_prompt = PromptTemplate.from_template(repair_prompts)
        self.maintain_prompt = PromptTemplate.from_template(maintain_prompts)
        self.guide_prompt = PromptTemplate.from_template(guide_prompts)
        self.router_prompt = PromptTemplate.from_template(query_routing_prompts)
        self.rewriter_prompt = PromptTemplate.from_template(query_rewriting_prompts)
        self.report_prompt = PromptTemplate.from_template(report_prompts)

    # ---------- 辅助方法：调用 LLM ----------
    async def _call_llm(self, prompt: str, system: str = "") -> str:
        """统一调用 LLM 生成文本"""
        return await self.llm.generate(prompt, system=system)

    async def _call_llm_stream(self, prompt: str, system: str = "") -> AsyncGenerator[str, None]:
        """流式调用 LLM，返回异步生成器"""
        async for chunk in self.llm.stream_chat([{"role": "user", "content": prompt}], system=system):
            yield chunk

    # ---------- 检索 ----------
    async def _aretrieve_context(self, query: str, kb_id: Optional[int] = None) -> List[Document]:
        """异步执行混合检索（将同步调用放入线程池）"""
        loop = asyncio.get_running_loop()
        effective_kb_id = kb_id or self.kb_id
        if not effective_kb_id:
            return []
        return await loop.run_in_executor(
            None,
            lambda: vector_opt.hybrid_search(
                query=query,
                user_id=self.user_id,
                kb_id=effective_kb_id,
                top_k=5
            )
        )

    # ---------- 查询路由与重写（异步版本）----------
    async def query_router(self, query: str) -> RouteType:
        """路由：决定使用哪个领域知识库，返回枚举类型"""
        prompt = self.router_prompt.format(history="", input=query)
        result = await self._call_llm(prompt)
        result = result.strip().lower()
        try:
            route = RouteType(result)
        except ValueError:
            logger.warning(f"未知路由类型 '{result}'，使用 GENERAL")
            route = RouteType.GENERAL
        return route

    async def query_rewrite(self, query: str) -> str:
        """查询重写，提升检索效果"""
        prompt = self.rewriter_prompt.format(history="", input=query)
        rewritten = await self._call_llm(prompt)
        rewritten = rewritten.strip()
        if rewritten != query:
            logger.info(f"查询重写: {query} -> {rewritten}")
        return rewritten

    # ---------- 辅助方法：根据路由生成回答（接收枚举）----------
    async def _generate_by_route(self, route: RouteType, input_vars: dict) -> str:
        """根据路由选择不同的提示词模板生成回答"""
        if route == RouteType.REPAIR:
            prompt = self.repair_prompt.format(**input_vars)
        elif route == RouteType.MAINTAIN:
            prompt = self.maintain_prompt.format(**input_vars)
        elif route == RouteType.GUIDE:
            prompt = self.guide_prompt.format(**input_vars)
        else:  # GENERAL 或未知
            prompt = self.summarize_prompt.format(**input_vars)
        return await self._call_llm(prompt)

    async def _generate_stream_by_route(self, route: RouteType, input_vars: dict) -> AsyncGenerator[str, None]:
        """流式生成，根据路由选择提示词模板"""
        if route == RouteType.REPAIR:
            prompt = self.repair_prompt.format(**input_vars)
        elif route == RouteType.MAINTAIN:
            prompt = self.maintain_prompt.format(**input_vars)
        elif route == RouteType.GUIDE:
            prompt = self.guide_prompt.format(**input_vars)
        else:
            prompt = self.summarize_prompt.format(**input_vars)
        async for chunk in self._call_llm_stream(prompt):
            yield chunk

    @staticmethod
    def _format_context(docs: List[Document], max_length: int = 2000) -> str:
        if not docs:
            return "无相关文档"
        parts, total = [], 0
        for doc in docs:
            text = doc.page_content.strip()
            if total + len(text) > max_length:
                remain = max_length - total
                if remain > 50:
                    parts.append(text[:remain] + "...")
                break
            parts.append(text)
            total += len(text)
        return "\n\n".join(parts)

    @staticmethod
    def _build_reference(docs: List[Document]) -> List[Dict]:
        refs = []
        for doc in docs:
            refs.append({
                "file_name": doc.metadata.get("file_name", "未知文件"),
                "chunk_text": doc.page_content[:200],
                "score": doc.metadata.get("rrf_score", None)
            })
        return refs

    # ---------- 核心生成回答（异步）----------
    async def generate_answer(
        self,
        query: str,
        kb_id: Optional[int] = None,
        enable_long_memory: bool = True,
        enable_short_memory: bool = True
    ) -> Dict[str, Any]:
        """异步生成回答（完整版，返回回答、引用、路由）"""
        # 1. 确定知识库
        effective_kb_id = kb_id or self.kb_id
        if effective_kb_id is None:
            route = await self.query_router(query)
            effective_kb_id = DOMAIN_KB_MAP.get(route, PUBLIC_KB_ID)
        self.kb_id = effective_kb_id

        # 2. 查询重写
        rewritten = await self.query_rewrite(query)

        # 3. 检索上下文
        docs = await self._aretrieve_context(rewritten, effective_kb_id)
        context_str = self._format_context(docs)

        # 4. 短期记忆（仅登录用户）
        short_history = ""
        if enable_short_memory and not self.is_guest:
            short_history = self.chat_memory.get_history_str(
                user_id=self.user_id, kb_id=effective_kb_id, limit=5
            )

        # 5. 长期记忆（异步调用）
        long_memory_str = ""
        if enable_long_memory and not self.is_guest and self.long_memory:
            long_memory_str = await self.long_memory.aget_relevant_memory(query)

        # 6. 路由并生成（路由已经是枚举）
        route = await self.query_router(rewritten)
        answer = await self._generate_by_route(route, {
            "input": rewritten,
            "history": short_history,
            "memory": long_memory_str,
            "context": context_str
        })

        # 7. 保存短期记忆（仅登录用户）
        if not self.is_guest:
            self.chat_memory.save_message(
                user_id=self.user_id, kb_id=effective_kb_id,
                user_msg=query, ai_msg=answer
            )
            if self.long_memory:
                self.long_memory.save_long_memory(query, answer)

        return {
            "answer": answer,
            "reference": self._build_reference(docs),
            "route": route.value  # 返回字符串，便于前端或日志
        }

    async def generate_answer_stream(
        self,
        query: str,
        kb_id: Optional[int] = None,
        enable_long_memory: bool = True,
        enable_short_memory: bool = True
    ) -> AsyncGenerator[str, None]:
        """异步流式生成回答，逐步输出文本块"""
        # 1. 确定知识库
        effective_kb_id = kb_id or self.kb_id
        if effective_kb_id is None:
            route = await self.query_router(query)
            effective_kb_id = DOMAIN_KB_MAP.get(route, PUBLIC_KB_ID)
        self.kb_id = effective_kb_id

        # 2. 查询重写
        rewritten = await self.query_rewrite(query)

        # 3. 检索上下文
        docs = await self._aretrieve_context(rewritten, effective_kb_id)
        context_str = self._format_context(docs)

        # 4. 短期记忆
        short_history = ""
        if enable_short_memory and not self.is_guest:
            short_history = self.chat_memory.get_history_str(
                user_id=self.user_id, kb_id=effective_kb_id, limit=5
            )

        # 5. 长期记忆
        long_memory_str = ""
        if enable_long_memory and not self.is_guest and self.long_memory:
            long_memory_str = await self.long_memory.aget_relevant_memory(query)

        # 6. 路由（枚举）
        route = await self.query_router(rewritten)

        # 7. 流式生成
        full_answer = ""
        async for chunk in self._generate_stream_by_route(route, {
            "input": rewritten,
            "history": short_history,
            "memory": long_memory_str,
            "context": context_str
        }):
            full_answer += chunk
            yield chunk

        # 8. 流结束后保存记忆
        if not self.is_guest:
            await self.chat_memory.asave_message(
                user_id=self.user_id, kb_id=effective_kb_id,
                user_msg=query, ai_msg=full_answer
            )
            if self.long_memory:
                await self.long_memory.asave_long_memory(query, full_answer)


    async def generate_report(
        self,
        user_id: str,
        month: str,
        usage_data: dict,
    ):
        """生成个人使用报告（独立方法，不走常规 RAG 路由）"""
        import json
        short_history = ""
        if not self.is_guest:
            short_history = self.chat_memory.get_history_str(
                user_id=int(user_id), kb_id=self.kb_id, limit=5
            )
        long_memory_str = ""
        if not self.is_guest and self.long_memory:
            long_memory_str = await self.long_memory.aget_relevant_memory("report")
        data_str = json.dumps(usage_data, ensure_ascii=False, indent=2)
        prompt = self.report_prompt.format(
            history=short_history,
            memory=long_memory_str,
            input=f"请为用户 {user_id} 生成 {month} 月的使用报告",
        )
        prompt += f"\n\n### 用户使用数据\n```json\n{data_str}\n```"
        system = "你是一份专业的扫地/拖地机器人方面的报告写手。请根据提供的数据，生成一份完整的使用报告和保养建议。"
        answer = await self._call_llm(prompt, system=system)
        if not self.is_guest:
            self.chat_memory.save_message(
                user_id=int(user_id), kb_id=self.kb_id,
                user_msg=f"生成 {month} 月使用报告", ai_msg=answer
            )
        return {"answer": answer, "user_id": user_id, "month": month}

if __name__ == "__main__":
    async def test():
        config = {"provider": "openai", "api_url": "...", "api_key": "...", "model": "gpt-4"}
        factory = LLMClientFactory(config)
        llm = factory.get_client()
        rag = RagService(user_id=123, llm_client=llm, kb_id=1)

        # 非流式
        result = await rag.generate_answer("如何清洁沙发？")
        print(result["answer"])

        # 流式
        async for chunk in rag.generate_answer_stream("告诉我电池维护方法"):
            print(chunk, end="")

    asyncio.run(test())

