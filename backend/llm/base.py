"""
大模型客户端抽象基类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
import asyncio


class BaseLLMClient(ABC):
    """大模型客户端抽象基类"""

    @abstractmethod
    async def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        """
        简单文本生成，适用于 RAG、摘要等场景。

        Args:
            prompt: 用户提示
            system: 系统提示
            **kwargs: 额外参数（如 temperature, max_tokens）

        Returns:
            生成的文本
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        对话接口，支持函数调用。

        Args:
            messages: 对话历史，每个元素包含 role 和 content
            tools: 函数定义列表
            tool_choice: 强制调用某个工具的模式
            **kwargs: 额外参数

        Returns:
            字典，包含 role, content, tool_calls 等字段
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式对话，每次返回一个文本片段。

        Args:
            同 chat

        Yields:
            文本片段
        """
        # 默认实现：非流式，一次性返回全部内容
        response = await self.chat(messages, tools, tool_choice, **kwargs)
        content = response.get("content", "")
        for chunk in content:  # 按字符模拟流式（子类应覆盖）
            yield chunk
            await asyncio.sleep(0.01)

    async def embed(self, text: str, **kwargs) -> List[float]:
        """
        文本嵌入（可选，子类可覆盖）。
        """
        raise NotImplementedError("Embedding not supported by this client.")

    async def health_check(self) -> bool:
        """
        健康检查，默认返回 True。子类可覆盖实现实际的 ping 测试。
        """
        return True

    def set_model(self, model: str) -> None:
        """
        动态切换模型（具体子类实现）。
        """
        pass

    # 辅助方法：带重试的调用（非抽象，供子类复用）
    async def generate_with_retry(self, prompt: str, max_retries: int = 3, **kwargs) -> str:
        """带重试的生成"""
        for i in range(max_retries):
            try:
                return await self.generate(prompt, **kwargs)
            except Exception as e:
                if i == max_retries - 1:
                    raise
                await asyncio.sleep(1 * (i + 1))
        return ""  # never reached

    async def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """带重试的对话"""
        for i in range(max_retries):
            try:
                return await self.chat(messages, **kwargs)
            except Exception as e:
                if i == max_retries - 1:
                    raise
                await asyncio.sleep(1 * (i + 1))
        return {}