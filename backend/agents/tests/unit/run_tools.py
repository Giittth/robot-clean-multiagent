"""P0/P1 工具系统单元测试"""
import pytest
from backend.agents.tools.tool_registry import ToolRegistry
from backend.agents.tools.builtin.room_query import RoomQueryTool
from backend.agents.tools.builtin.coverage_query import CoverageQueryTool
from backend.agents.tools.builtin.knowledge_query import KnowledgeQueryTool
from backend.agents.tools.builtin.memory_tool import MemoryTool
from backend.agents.tools.builtin.confirm_tool import ConfirmTool
from backend.agents.tools.builtin.calc_tool import CalcTool
from backend.agents.tools.builtin.call_planner import CallPlannerTool


class TestBaseTool:
    def test_to_openai_tool_format(self):
        t = RoomQueryTool(lambda: [])
        ot = t.to_openai_tool()
        assert "type" in ot and ot["type"] == "function"
        assert ot["function"]["name"] == "room_query"
        assert "parameters" in ot["function"]

    def test_tool_parameters_have_descriptions(self):
        for tool in [
            RoomQueryTool(lambda: []),
            CoverageQueryTool(lambda: {}),
            KnowledgeQueryTool(),
            MemoryTool(),
            ConfirmTool(),
            CalcTool(),
        ]:
            for name, param in tool.parameters.items():
                assert "description" in param, f"{tool.name}.{name} missing description"


class TestToolRegistry:
    def test_register_and_list(self):
        reg = ToolRegistry()
        reg.register_many(
            RoomQueryTool(lambda: []), CoverageQueryTool(lambda: {}),
            KnowledgeQueryTool(), MemoryTool(), ConfirmTool(),
        )
        assert len(reg.list_tools()) == 5
        assert set(reg.list_names()) == {"room_query", "coverage_query",
                                          "knowledge_query", "memory", "confirm"}

    def test_to_openai_tools(self):
        reg = ToolRegistry()
        reg.register(CalcTool())
        tools = reg.to_openai_tools()
        assert len(tools) == 1
        assert "function" in tools[0]

    @pytest.mark.asyncio
    async def test_execute_room_query(self):
        rooms = [{"name": "living_room", "polygon": [{"x":0,"y":0},{"x":4,"y":0},{"x":4,"y":4},{"x":0,"y":4}]}]
        r = await RoomQueryTool(lambda: rooms).execute(query="x")
        assert r.success and "living_room" in r.data.get("answer","")

    @pytest.mark.asyncio
    async def test_execute_calc(self):
        r = await CalcTool().execute(expression="3+5*2")
        assert r.success and "13" in r.data.get("answer","")

    @pytest.mark.asyncio
    async def test_execute_coverage(self):
        r = await CoverageQueryTool(lambda: {"coverage_percent":75.0}).execute(area="all")
        assert r.success and "75" in r.data.get("answer","")

    @pytest.mark.asyncio
    async def test_execute_memory(self):
        r = await MemoryTool().execute(action="query")
        assert r.success

    @pytest.mark.asyncio
    async def test_execute_confirm(self):
        r = await ConfirmTool().execute(message="test?")
        assert r.success and r.data.get("confirmed") is True

    @pytest.mark.asyncio
    async def test_call_planner_schema(self):
        ct = CallPlannerTool(None, lambda c: None)
        assert ct.name == "call_planner" and "command" in ct.parameters