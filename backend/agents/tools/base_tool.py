"""工具系统基类：BaseTool + ToolResult"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    requires_confirmation: bool = False


class BaseTool(ABC):
    """工具抽象基类"""
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...

    def to_openai_tool(self) -> Dict[str, Any]:
        """转成 OpenAI function calling 格式"""
        # 提取 required 字段名（从每个参数的 required 标记提取）
        required_params = [
            k for k, v in self.parameters.items()
            if v.get("required", False)
        ]
        # 构建 properties（不含 required 标记，Ollama 不识别它）
        properties = {}
        for k, v in self.parameters.items():
            prop = {pk: pv for pk, pv in v.items() if pk != "required"}
            properties[k] = prop

        result = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                },
            },
        }
        if required_params:
            result["function"]["parameters"]["required"] = required_params
        return result