
"""工具注册中心：注册、查找、执行、格式转换"""
from typing import Dict, List, Any, Optional
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.logger_handler import logger


class ToolRegistry:
    """管理所有可用工具"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        logger.info(f"Tool registered: {tool.name}")

    def register_many(self, *tools: BaseTool):
        for t in tools:
            self.register(t)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def list_names(self) -> List[str]:
        return list(self._tools.keys())

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{name}' not found")
        logger.info(f"Executing tool: {name}({arguments})")
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            logger.error(f"Tool '{name}' failed: {e}")
            return ToolResult(success=False, error=str(e))

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        return [t.to_openai_tool() for t in self._tools.values()]

    def __contains__(self, name: str) -> bool:
        return name in self._tools
