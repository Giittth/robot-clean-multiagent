"""记忆系统单元测试：WorkingMemory + AgentMemory + EpisodicMemory"""
import pytest
from backend.agents.memory.working_memory import WorkingMemory, TurnRecord
from backend.agents.memory.agent_memory import AgentMemory


class TestWorkingMemory:
    def test_set_task(self):
        wm = WorkingMemory()
        wm.set_task("测试指令")
        assert wm.user_command == "测试指令"

    def test_update_state(self):
        wm = WorkingMemory()
        wm.update_state(robot_state={"battery": {"voltage": 12.5}})
        summary = wm.get_summary()
        assert "12.5" in summary

    def test_turn_history(self):
        wm = WorkingMemory()
        wm.add_turn(TurnRecord(action="test", action_input={}, observation="ok"))
        assert len(wm.history) == 1
        assert wm.last_action() == "test"
        assert len(wm.get_recent_turns(3)) == 1

    def test_reset(self):
        wm = WorkingMemory()
        wm.set_task("x")
        wm.reset()
        assert wm.user_command == ""


class TestAgentMemory:
    def test_create_with_episodic(self):
        m = AgentMemory()
        assert hasattr(m, "episodic")
        assert m.episodic is None

    def test_working_property(self):
        m = AgentMemory()
        assert hasattr(m, "working")
        assert m.working.user_command == ""

    @pytest.mark.asyncio
    async def test_build_context(self):
        m = AgentMemory()
        m.working.set_task("test")
        ctx = await m.build_context("test")
        assert "test" in ctx

    @pytest.mark.asyncio
    async def test_query_knowledge(self):
        m = AgentMemory()
        r = await m.query_knowledge("test")
        assert r == ""


class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_empty_query(self):
        from backend.agents.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        r = await em.query_similar("test")
        assert r == ""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        from backend.agents.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory()
        r = await em.get_stats()
        assert "未配置" in r


class TestMemoryInjector:
    def test_build_relevant_context(self):
        from backend.agents.memory.memory_injector import build_relevant_context
        from backend.agents.memory.agent_memory import AgentMemory
        m = AgentMemory()
        m.working.set_task("test")
        ctx = build_relevant_context(m)
        assert "test" in ctx

    def test_format_context_block(self):
        from backend.agents.memory.memory_injector import format_context_block
        r = format_context_block("标题", "内容")
        assert "标题" in r and "内容" in r