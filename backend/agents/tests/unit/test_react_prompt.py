"""ReAct Prompt 单元测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest
from backend.agents.runtime.react_prompt import BASE_SYSTEM, build_with_tools


class TestReactPrompt:
    def test_base_has_chinese(self):
        assert "智能扫地机器人" in BASE_SYSTEM
        assert "工作方式" in BASE_SYSTEM

    def test_base_has_english(self):
        assert "Working Modes" in BASE_SYSTEM
        assert "Rules" in BASE_SYSTEM

    def test_base_has_call_planner(self):
        assert "call_planner" in BASE_SYSTEM

    def test_base_forbids_composing(self):
        assert "不要尝试用其他工具组合实现" in BASE_SYSTEM
        assert "don't compose other tools" in BASE_SYSTEM.lower()

    def test_base_language_rule(self):
        assert "中文回复" in BASE_SYSTEM
        assert "same language" in BASE_SYSTEM.lower()

    def test_build_with_tools_empty(self):
        result = build_with_tools([])
        assert result == BASE_SYSTEM + "\n"

    def test_build_with_tools_list(self):
        descs = [
            "room_query: 查询房间信息",
            "calculator: 执行数学计算",
        ]
        result = build_with_tools(descs)
        assert "room_query" in result
        assert "calculator" in result
        assert BASE_SYSTEM in result

    def test_max_steps_reference(self):
        """AgentRuntime.MAX_STEPS should be >= 5"""
        from backend.agents.runtime.agent_runtime import AgentRuntime
        assert AgentRuntime.MAX_STEPS >= 5

    def test_max_tools_per_step_sane(self):
        """MAX_TOOLS_PER_STEP should be reasonable"""
        from backend.agents.runtime.agent_runtime import AgentRuntime
        assert 1 <= AgentRuntime.MAX_TOOLS_PER_STEP <= 10
