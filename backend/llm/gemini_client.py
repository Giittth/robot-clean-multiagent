import aiohttp
import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncIterator
from backend.llm.base import BaseLLMClient
from backend.utils.logger_handler import logger


class GeminiClient(BaseLLMClient):
    def __init__(
        self,
        api_url: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        api_key: str = "",
        model: str = "gemini-1.5-pro",
        timeout: int = 30,
        max_retries: int = 2,
        temperature: float = 0.7,
    ):
        # Gemini API URL 模板：需要替换 {model}
        self.base_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_temperature = temperature

    @property
    def _full_url(self) -> str:
        return self.base_url.replace("{model}", self.model) + f"?key={self.api_key}"

    async def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        messages = []
        if system:
            messages.append({"role": "user", "content": system + "\n" + prompt})
        else:
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
        # 转换消息为 Gemini 格式
        contents = self._convert_messages_to_gemini(messages)
        # 转换工具定义
        gemini_tools = None
        if tools:
            gemini_tools = self._convert_tools_to_gemini(tools)
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", self.default_temperature),
                "maxOutputTokens": kwargs.get("max_tokens", 4096),
            }
        }
        if gemini_tools:
            payload["tools"] = [{"functionDeclarations": gemini_tools}]
            if tool_choice != "auto":
                payload["toolConfig"] = {"functionCallingConfig": {"mode": "ANY"}}  # 强制调用
        # 添加额外参数
        payload.update({k: v for k, v in kwargs.items() if k not in payload})

        for attempt in range(self.max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self._full_url, json=payload) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            raise Exception(f"Gemini API HTTP {resp.status}: {text}")
                        data = await resp.json()
                        return self._parse_gemini_response(data)
            except Exception as e:
                logger.warning(f"Gemini attempt {attempt+1} failed: {e}")
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(1 * (attempt + 1))
        return {"error": "Max retries exceeded", "content": ""}

    async def stream_chat(self, messages, tools=None, tool_choice="auto", **kwargs) -> AsyncIterator[str]:
        # 简化：Gemini 流式需另外支持，先降级
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

    def _convert_messages_to_gemini(self, messages: List[Dict[str, str]]) -> List[Dict]:
        """将内部消息列表转换为 Gemini contents 格式"""
        contents = []
        for msg in messages:
            role = msg["role"]
            if role == "assistant":
                gemini_role = "model"
            elif role == "user":
                gemini_role = "user"
            else:
                # system 角色：可以合并到第一条 user 消息，或忽略
                continue
            contents.append({
                "role": gemini_role,
                "parts": [{"text": msg["content"]}]
            })
        return contents

    def _convert_tools_to_gemini(self, tools: List[Dict]) -> List[Dict]:
        """将 OpenAI 格式的工具定义转换为 Gemini functionDeclarations"""
        functions = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                functions.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func["parameters"],
                })
        return functions

    def _parse_gemini_response(self, data: Dict) -> Dict[str, Any]:
        """解析 Gemini 响应，转换为统一格式"""
        candidates = data.get("candidates", [])
        if not candidates:
            return {"role": "assistant", "content": "", "tool_calls": None}
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        text_parts = []
        tool_calls = []
        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append({
                    "id": fc.get("name", "unknown"),
                    "type": "function",
                    "function": {
                        "name": fc["name"],
                        "arguments": json.dumps(fc.get("args", {})),
                    }
                })
        return {
            "role": "assistant",
            "content": "\n".join(text_parts),
            "tool_calls": tool_calls if tool_calls else None,
        }