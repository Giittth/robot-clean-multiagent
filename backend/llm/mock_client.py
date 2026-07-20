"""
模拟 LLM 客户端，用于测试和离线开发。
支持规则匹配、随机响应、模拟工具调用、延迟等。
"""

import json
import random
import asyncio
import re
from typing import List, Dict, Any, Optional, AsyncIterator
from backend.llm.base import BaseLLMClient
from backend.utils.logger_handler import logger


class MockLLMClient(BaseLLMClient):
    """
    增强版 Mock LLM 客户端
    支持规则匹配、随机响应、模拟工具调用、延迟等
    """

    def __init__(
        self,
        rules: Optional[List[Dict[str, Any]]] = None,
        default_response: str = "This is a mock response.",
        response_delay: float = 0.0,
        error_rate: float = 0.0,
        seed: int = 42,
    ):
        """
        :param rules: 规则列表，每条规则包含：
            - "pattern": 正则表达式字符串
            - "response": 响应文本（或 tool_calls 定义）
            - "tool_calls": 可选，模拟工具调用
            - "probability": 可选，命中概率（0~1）
        :param default_response: 无规则匹配时的默认回复
        :param response_delay: 模拟延迟（秒），固定或随机范围 (min, max)
        :param error_rate: 模拟错误概率 (0~1)，随机抛出异常
        :param seed: 随机种子，保证可复现
        """
        self.rules = rules or self._default_rules()
        self.default_response = default_response
        self.response_delay = response_delay
        self.error_rate = error_rate
        random.seed(seed)
        self._conversation_memory = []  # 简单记录多轮对话

    @staticmethod
    def _default_rules():
        """默认规则集"""
        return [
            {
                "pattern": r"(清扫|clean|打扫)",
                "response": "我将为您规划清扫任务。",
                "tool_calls": [
                    {
                        "id": "mock_1",
                        "type": "function",
                        "function": {
                            "name": "plan_cleaning_task",
                            "arguments": json.dumps({"area": "living_room", "strategy": "COVERAGE"})
                        }
                    }
                ],
                "probability": 1.0,
            },
            {
                "pattern": r"(导航|去|走到)(.*)",
                "response": "我将为您规划导航路径。",
                "tool_calls": [
                    {
                        "id": "mock_2",
                        "type": "function",
                        "function": {
                            "name": "navigate_to",
                            "arguments": json.dumps({"target": {"x": 5.0, "y": 3.0}})
                        }
                    }
                ],
                "probability": 1.0,
            },
            {
                "pattern": r"(状态|位置|电量)",
                "response": "机器人当前电量 85%，位置 (2.3, 1.5)，运行正常。",
                "tool_calls": None,
                "probability": 1.0,
            },
        ]

    async def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = await self.chat(messages, **kwargs)
        return response.get("content", "")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> Dict[str, Any]:
        # 模拟错误
        if random.random() < self.error_rate:
            raise Exception("Mock LLM random error")

        # 模拟延迟
        if self.response_delay:
            if isinstance(self.response_delay, (tuple, list)) and len(self.response_delay) == 2:
                delay = random.uniform(*self.response_delay)
            else:
                delay = float(self.response_delay)
            await asyncio.sleep(delay)

        # 提取用户消息（最后一条）
        user_messages = [m for m in messages if m["role"] == "user"]
        if not user_messages:
            last_user = ""
        else:
            last_user = user_messages[-1]["content"]

        # 存储到对话记忆（简单）
        self._conversation_memory.extend(messages)

        # 匹配规则
        for rule in self.rules:
            pattern = rule.get("pattern", "")
            prob = rule.get("probability", 1.0)
            if prob < 1.0 and random.random() > prob:
                continue
            if re.search(pattern, last_user, re.IGNORECASE):
                response = rule.get("response", self.default_response)
                tool_calls = rule.get("tool_calls")
                # 支持动态生成 arguments（例如从用户消息中提取坐标）
                if tool_calls and rule.get("dynamic_arguments"):
                    tool_calls = self._resolve_dynamic_arguments(tool_calls, last_user)
                return {
                    "role": "assistant",
                    "content": response,
                    "tool_calls": tool_calls,
                }

        # 默认响应
        return {
            "role": "assistant",
            "content": self.default_response,
            "tool_calls": None,
        }

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式聊天：模拟逐步输出响应内容。
        """
        # 先获取完整响应
        response = await self.chat(messages, tools, tool_choice, **kwargs)
        content = response.get("content", "")
        # 模拟流式输出，每个字符一个片段（或按词）
        # 为了简单，每次输出一个词
        words = content.split()
        for word in words:
            yield word + " "
            await asyncio.sleep(0.05)
        # 如果内容为空，输出空字符串
        if not content:
            yield ""

    def _resolve_dynamic_arguments(self, tool_calls: List[Dict], user_input: str) -> List[Dict]:
        """简单解析用户输入中的数字，用于动态参数（示例）"""
        numbers = re.findall(r"(\d+(?:\.\d+)?)", user_input)
        if numbers and len(numbers) >= 2:
            x, y = float(numbers[0]), float(numbers[1])
            for tc in tool_calls:
                if tc["function"]["name"] == "navigate_to":
                    args = json.loads(tc["function"]["arguments"])
                    args["target"]["x"] = x
                    args["target"]["y"] = y
                    tc["function"]["arguments"] = json.dumps(args)
        return tool_calls