"""Task Router 单元测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest
from backend.agents.runtime.task_router import is_simple_query, is_action_command, route


class TestIsSimpleQuery:
    def test_knowledge_query(self):
        assert is_simple_query("现在电量多少")
        assert is_simple_query("客厅扫完了吗")
        assert is_simple_query("最大的房间是哪个")

    def test_preference_query(self):
        assert is_simple_query("记住先扫主卧")
        assert is_simple_query("我有什么偏好")

    def test_calc_query(self):
        assert is_simple_query("50平米等于多少")
        assert is_simple_query("算一下3+5")

    def test_status_query(self):
        assert is_simple_query("扫完了吗")
        assert is_simple_query("覆盖率多少")

    def test_not_query(self):
        """动作指令不应被识别为简单查询"""
        result = is_simple_query("你好")
        # "你好" doesn't match any query pattern
        assert not result


class TestIsActionCommand:
    def test_clean(self):
        assert is_action_command("清扫客厅")
        assert is_action_command("清洁厨房")
        assert is_action_command("打扫北室")

    def test_navigate(self):
        assert is_action_command("导航到客厅")

    def test_charge(self):
        assert is_action_command("回充")

    def test_stop(self):
        assert is_action_command("停止")

    def test_not_action(self):
        assert not is_action_command("现在几点")
        assert not is_action_command("你好")


class TestRoute:
    def test_action_to_planner(self):
        assert route("清扫客厅") == "planner"
        assert route("导航到厨房") == "planner"
        assert route("回充") == "planner"
        assert route("停止") == "planner"

    def test_query_to_tool(self):
        assert route("电量多少") == "tool"
        assert route("客厅扫完了吗") == "tool"

    def test_default_to_planner(self):
        """未知命令默认走 Planner"""
        assert route("你好") == "planner"
