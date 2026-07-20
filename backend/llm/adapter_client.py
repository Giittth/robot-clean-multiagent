"""
通用适配器客户端：通过 request_adapter 和 response_adapter 转换请求/响应，
快速接入非标准 API。
"""
import asyncio
import aiohttp
from typing import Callable, Any, Dict, List, Optional, AsyncIterator
from backend.llm.base import BaseLLMClient
from backend.utils.logger_handler import logger


class AdapterLLMClient(BaseLLMClient):
    def __init__(
        self,
        api_url: str,
        api_key: str,
        request_adapter: Callable[[Dict], Dict],
        response_adapter: Callable[[Dict], Dict],
        timeout: int = 30,
        max_retries: int = 2,
        model: str = "",
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.request_adapter = request_adapter
        self.response_adapter = response_adapter
        self.timeout = timeout
        self.max_retries = max_retries
        self.model = model

    async def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await self.chat(messages, **kwargs)
        return resp.get("content", "")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> Dict[str, Any]:
        # 1. 构造标准内部请求（OpenAI 格式）
        standard_request = {
            "messages": messages,
            "tools": tools or [],
            "tool_choice": tool_choice,
            **kwargs,
        }
        # 2. 转换为目标 API 格式
        adapted_request = self.request_adapter(standard_request)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        for attempt in range(self.max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self.api_url, json=adapted_request, headers=headers) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            raise Exception(f"HTTP {resp.status}: {text}")
                        raw_response = await resp.json()
                        # 3. 将响应转换为标准格式
                        return self.response_adapter(raw_response)
            except Exception as e:
                logger.warning(f"Adapter attempt {attempt+1} failed: {e}")
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(1 * (attempt + 1))
        return {"error": "Max retries exceeded", "content": ""}

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> AsyncIterator[str]:
        # 对于流式，需要适配器也支持，但非标准 API 可能不支持流式，降级为非流式
        response = await self.chat(messages, tools, tool_choice, **kwargs)
        content = response.get("content", "")
        for chunk in content:
            yield chunk
            await asyncio.sleep(0.01)

    async def embed(self, text: str, **kwargs) -> List[float]:
        # 大部分非标准 API 可能不支持 embedding，抛出 NotImplementedError
        raise NotImplementedError("Embedding not implemented for adapter client")

    async def health_check(self) -> bool:
        try:
            # 轻量测试：发送一条极简消息
            await self.generate("ping", timeout=5.0)
            return True
        except Exception:
            return False

    def set_model(self, model: str) -> None:
        self.model = model