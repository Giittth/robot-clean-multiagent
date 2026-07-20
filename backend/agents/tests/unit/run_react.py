"""ReAct 循环单元测试：task_router + react_prompt + AgentRuntime"""
import pytest
from backend.agents.runtime.task_router import is_simple_query, is_action_command, route
from backend.agents.runtime.react_prompt import build_with_tools
from backend.agents.runtime.agent_runtime import AgentRuntime, AgentResult


class TestTaskRouter:
    def test_simple_queries(self):
        for q in ["厨房扫完了吗","客厅多大面积","怎么清理滚刷",
                  "确认开始清扫","算一下3+5","今天天气","清扫南室1"]:
            assert is_simple_query(q), f"should be simple: {q}"

    def test_complex_commands(self):
        for c in ["先扫卧室再去厨房"]:
            assert not is_simple_query(c), f"should be complex: {c}"

    def test_action_command(self):
        assert is_action_command("清扫南室1")
        assert is_action_command("导航到客厅")
        assert is_action_command("回充")
        assert not is_action_command("厨房扫完了吗")
        assert not is_action_command("今天天气")

    def test_route_output(self):
        assert route("厨房扫完了吗") == "tool"
        assert route("清扫客厅") == "tool"


class TestReactPrompt:
    def test_build_with_tools(self):
        prompt = build_with_tools(["room_query: 查房间", "coverage_query: 查覆盖率"])
        assert "扫地机器人管家" in prompt
        assert "room_query" in prompt
        assert "call_planner" in prompt

    def test_empty_tools(self):
        prompt = build_with_tools([])
        assert "可用工具" in prompt or "扫地" in prompt


class TestAgentRuntime:
    def test_defaults(self):
        assert AgentRuntime.MAX_STEPS == 5

    def test_agent_result(self):
        r = AgentResult(action="direct_answer", answer="hello")
        assert r.action == "direct_answer"
        assert r.answer == "hello"

    def test_agent_result_with_graph(self):
        r = AgentResult(action="execute_graph", graph="fake_graph")
        assert r.action == "execute_graph"
        assert r.graph == "fake_graph"