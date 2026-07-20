import aiohttp
import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncIterator
from backend.llm.base import BaseLLMClient
from backend.utils.logger_handler import logger


class ClaudeClient(BaseLLMClient):
    def __init__(
        self,
        api_url: str = "https://api.anthropic.com/v1/messages",
        api_key: str = "",
        model: str = "claude-3-sonnet-20240229",
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
        messages = [{"role": "user", "content": prompt}]
        resp = await self.chat(messages, system=system, **kwargs)
        return resp.get("content", "")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> Dict[str, Any]:
        # 提取 system 消息（Claude 要求顶层字段）
        system_prompt = None
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                filtered_messages.append(msg)
        # 确保消息以 user 开头，交替 user/assistant
        if filtered_messages and filtered_messages[0]["role"] != "user":
            # 添加一个空的 user 消息（如果第一条不是 user，Claude 可能报错）
            filtered_messages.insert(0, {"role": "user", "content": ""})
        # 转换工具定义到 Claude 格式
        claude_tools = None
        if tools:
            claude_tools = self._convert_tools_to_claude(tools)
        payload = {
            "model": self.model,
            "messages": filtered_messages,
            "max_tokens": kwargs.get("max_tokens", self.default_max_tokens),
            "temperature": kwargs.get("temperature", self.default_temperature),
        }
        if system_prompt:
            payload["system"] = system_prompt
        if claude_tools:
            payload["tools"] = claude_tools
            # Claude 的 tool_choice 格式：{"type": "auto"} 或 {"type": "any"} 或 {"name": "tool_name"}
            if tool_choice == "auto":
                payload["tool_choice"] = {"type": "auto"}
            elif tool_choice != "auto":
                payload["tool_choice"] = {"name": tool_choice}
        # 添加额外参数
        payload.update({k: v for k, v in kwargs.items() if k not in payload})

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        for attempt in range(self.max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self.api_url, json=payload, headers=headers) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            raise Exception(f"Claude API HTTP {resp.status}: {text}")
                        data = await resp.json()
                        # 解析响应
                        return self._parse_claude_response(data)
            except Exception as e:
                logger.warning(f"Claude attempt {attempt+1} failed: {e}")
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(1 * (attempt + 1))
        return {"error": "Max retries exceeded", "content": ""}

    async def stream_chat(self, messages, tools=None, tool_choice="auto", **kwargs) -> AsyncIterator[str]:
        # 简化：暂不支持流式，降级为非流式
        response = await self.chat(messages, tools, tool_choice, **kwargs)
        content = response.get("content", "")
        for ch in content:
            yield ch
            await asyncio.sleep(0.01)

    async def health_check(self) -> bool:
        try:
            await self.generate("ping", timeout=5.0)
            return True
        except Exception:
            return False

    def set_model(self, model: str) -> None:
        self.model = model

    def _convert_tools_to_claude(self, tools: List[Dict]) -> List[Dict]:
        """将 OpenAI 格式的工具定义转换为 Claude 格式"""
        claude_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                claude_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func["parameters"],
                })
        return claude_tools

    def _parse_claude_response(self, data: Dict) -> Dict[str, Any]:
        """将 Claude 响应转换为统一格式"""
        content_blocks = data.get("content", [])
        text_parts = []
        tool_calls = []
        for block in content_blocks:
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"]),
                    }
                })
        return {
            "role": "assistant",
            "content": "\n".join(text_parts),
            "tool_calls": tool_calls if tool_calls else None,
        }