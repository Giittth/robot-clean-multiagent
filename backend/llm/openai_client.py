import aiohttp
import asyncio
import json
from typing import AsyncIterator, List, Dict, Any, Optional
from backend.llm.base import BaseLLMClient
from backend.utils.logger_handler import logger


class OpenAICompatibleClient(BaseLLMClient):
    def __init__(
        self,
        api_url: str,
        api_key: str = "",
        model: str = "gpt-4",
        timeout: int = 30,
        max_retries: int = 2,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_max_tokens = max_tokens
        self.default_temperature = temperature

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
        return await self._chat(messages, tools, tool_choice, **kwargs)

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式对话，每次返回一个文本片段"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", self.default_max_tokens),
            "temperature": kwargs.get("temperature", self.default_temperature),
        }
        if tools:
            payload["tools"] = tools
        if tool_choice != "auto":
            payload["tool_choice"] = tool_choice
        payload.update({k: v for k, v in kwargs.items() if k not in payload})

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        for attempt in range(self.max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self.api_url, json=payload, headers=headers) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            raise Exception(f"HTTP {resp.status}: {text}")
                        async for line in resp.content:
                            line = line.decode("utf-8").strip()
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    continue
                break
            except Exception as e:
                logger.warning(f"Stream LLM attempt {attempt+1} failed: {e}")
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(1 * (attempt + 1))

    async def embed(self, text: str, **kwargs) -> List[float]:
        """获取文本嵌入（需要端点支持）"""
        # 默认尝试调用 /embeddings 端点（OpenAI 兼容）
        embed_url = self.api_url.replace("/chat/completions", "/embeddings")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "input": text,
            **kwargs,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(embed_url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f"Embedding failed: {await resp.text()}")
                data = await resp.json()
                return data["data"][0]["embedding"]

    async def health_check(self) -> bool:
        """简单的健康检查：尝试一次轻量调用（快速失败）"""
        try:
            # 使用很小的超时和空消息测试
            result = await asyncio.wait_for(
                self.generate("ping", timeout=5.0),
                timeout=5.0
            )
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def set_model(self, model: str) -> None:
        """动态切换模型名称"""
        self.model = model

    async def _chat(self, messages, tools, tool_choice="auto", **kwargs):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.default_max_tokens),
            "temperature": kwargs.get("temperature", self.default_temperature),
        }
        if tools:
            payload["tools"] = tools
        if tool_choice != "auto":
            payload["tool_choice"] = tool_choice
        payload.update({k: v for k, v in kwargs.items() if k not in payload})

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        for attempt in range(self.max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self.api_url, json=payload, headers=headers) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            raise Exception(f"HTTP {resp.status}: {text}")
                        data = await resp.json()
                        choice = data["choices"][0]
                        message = choice.get("message", {})
                        return {
                            "role": message.get("role", "assistant"),
                            "content": message.get("content", ""),
                            "tool_calls": message.get("tool_calls"),
                        }
            except Exception as e:
                logger.warning(f"LLM attempt {attempt+1} failed: {e}")
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(1 * (attempt + 1))
        return {"error": "Max retries exceeded", "content": ""}