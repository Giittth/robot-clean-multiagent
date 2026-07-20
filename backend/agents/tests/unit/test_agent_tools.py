"""Agent Tools 单元测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest

# ── RoomQueryTool ──
from backend.agents.tools.builtin.room_query import RoomQueryTool


def _make_rooms():
    return [
        {"name": "living_room", "polygon": [
            {"x": 0, "y": 0}, {"x": 5, "y": 0}, {"x": 5, "y": 4}, {"x": 0, "y": 4},
        ], "center": [2.5, 2.0]},
        {"name": "room_north_1", "polygon": [
            {"x": 0, "y": 0}, {"x": 3, "y": 0}, {"x": 3, "y": 3}, {"x": 0, "y": 3},
        ], "center": [1.5, 1.5]},
    ]


class TestRoomQuery:
    async def test_list_all(self):
        t = RoomQueryTool(get_rooms_fn=_make_rooms)
        r = await t.execute(query="列出所有房间")
        assert r.success
        assert "2 个房间" in r.data["answer"]
        assert "living_room" in r.data["answer"]

    async def test_biggest(self):
        t = RoomQueryTool(get_rooms_fn=_make_rooms)
        r = await t.execute(query="最大的房间")
        assert r.success
        assert "living_room" in r.data["answer"]

    async def test_smallest(self):
        t = RoomQueryTool(get_rooms_fn=_make_rooms)
        r = await t.execute(query="最小的房间")
        assert r.success
        assert "room_north_1" in r.data["answer"]

    async def test_how_many(self):
        t = RoomQueryTool(get_rooms_fn=_make_rooms)
        r = await t.execute(query="几个房间")
        assert r.success
        assert "2 个" in r.data["answer"]

    async def test_no_rooms(self):
        t = RoomQueryTool(get_rooms_fn=lambda: [])
        r = await t.execute(query="有什么房间")
        assert r.success
        assert "没有" in r.data["answer"]

    async def test_fuzzy_north(self):
        t = RoomQueryTool(get_rooms_fn=_make_rooms)
        r = await t.execute(query="北室")
        assert r.success
        assert "room_north_1" in r.data["answer"]

    def test_calc_area(self):
        poly = [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 3}, {"x": 0, "y": 3}]
        area = RoomQueryTool._calc_area(poly)
        assert area == pytest.approx(12.0)

    def test_fuzzy_match_direct(self):
        rooms = [
            {"name": "kitchen", "area": 9.0},
            {"name": "room_north_2", "area": 12.0},
        ]
        r = RoomQueryTool._fuzzy_match(rooms, "北室")
        assert len(r) == 1
        assert "north" in r[0]["name"]


# ── CoverageQueryTool ──
from backend.agents.tools.builtin.coverage_query import CoverageQueryTool


def _make_coverage():
    return {
        "coverage_percent": 85.0,
        "room_coverage": {"living_room": 90.0, "kitchen": 50.0},
        "map_area": 60.0,
    }


class TestCoverageQuery:
    async def test_all(self):
        t = CoverageQueryTool(get_coverage_fn=_make_coverage)
        r = await t.execute(area="all")
        assert r.success
        assert "85" in r.data["answer"]

    async def test_specific_room(self):
        t = CoverageQueryTool(get_coverage_fn=_make_coverage)
        r = await t.execute(area="kitchen")
        assert r.success
        assert "50" in r.data["answer"]

    async def test_fuzzy_match(self):
        t = CoverageQueryTool(get_coverage_fn=_make_coverage)
        r = await t.execute(area="living")
        assert r.success
        assert "90" in r.data["answer"]

    async def test_detail_view(self):
        t = CoverageQueryTool(get_coverage_fn=_make_coverage)
        r = await t.execute(area="all", detail=True)
        assert r.success
        assert "living_room" in r.data["answer"]
        assert "kitchen" in r.data["answer"]

    def test_match_room_direct(self):
        room, cov = CoverageQueryTool._match_room("kitchen",
                                                   {"living_room": 90.0, "kitchen": 50.0})
        assert room == "kitchen"
        assert cov == pytest.approx(50.0)

    def test_match_room_fuzzy(self):
        room, cov = CoverageQueryTool._match_room("kit",
                                                   {"living_room": 90.0, "kitchen": 50.0})
        assert room == "kitchen"

    def test_match_room_miss(self):
        room, cov = CoverageQueryTool._match_room("bathroom",
                                                   {"living_room": 90.0})
        assert room is None


# ── RobotStatusTool ──
from backend.agents.tools.builtin.robot_status import RobotStatusTool


def _make_robot_state():
    return {
        "battery": {"voltage": 11.8, "percent": 90, "charging": False},
        "pose": {"x": 3.2, "y": 1.5, "theta": 0.1},
        "collision": False,
        "action": {"linear": 0.0, "angular": 0.0},
    }


class TestRobotStatus:
    async def test_all(self):
        t = RobotStatusTool(get_robot_state=_make_robot_state,
                            get_power_state=lambda: "IDLE")
        r = await t.execute(aspect="all")
        assert r.success
        ans = r.data["answer"]
        assert "11.8V" in ans
        assert "空闲" in ans

    async def test_battery_only(self):
        t = RobotStatusTool(get_robot_state=_make_robot_state,
                            get_power_state=lambda: "IDLE")
        r = await t.execute(aspect="battery")
        assert "90%" in r.data["answer"]

    async def test_position(self):
        t = RobotStatusTool(get_robot_state=_make_robot_state,
                            get_power_state=lambda: "IDLE")
        r = await t.execute(aspect="position")
        assert "(3.20, 1.50)" in r.data["answer"]

    async def test_power_off(self):
        t = RobotStatusTool(get_robot_state=_make_robot_state,
                            get_power_state=lambda: "OFF")
        r = await t.execute(aspect="power")
        assert "关机" in r.data["answer"]

    async def test_power_charging(self):
        t = RobotStatusTool(get_robot_state=_make_robot_state,
                            get_power_state=lambda: "CHARGING")
        r = await t.execute(aspect="power")
        assert "充电中" in r.data["answer"]


# ── TaskControlTool ──
from backend.agents.tools.builtin.task_control import TaskControlTool


class TestTaskControl:
    async def test_pause(self):
        calls = []
        async def _send(action):
            calls.append(action)
        t = TaskControlTool(send_control=_send)
        r = await t.execute(action="pause")
        assert r.success
        assert calls == ["pause"]
        assert "暂停" in r.data["answer"]

    async def test_stop(self):
        calls = []
        async def _send(action):
            calls.append(action)
        t = TaskControlTool(send_control=_send)
        r = await t.execute(action="stop")
        assert calls == ["stop"]

    async def test_resume(self):
        calls = []
        async def _send(action):
            calls.append(action)
        t = TaskControlTool(send_control=_send)
        r = await t.execute(action="resume")
        assert calls == ["resume"]

    async def test_no_action(self):
        async def _send(action):
            pass
        t = TaskControlTool(send_control=_send)
        r = await t.execute(action="")
        assert not r.success


# ── TimeTool ──
from backend.agents.tools.builtin.time_tool import TimeTool


class TestTimeTool:
    async def test_now(self):
        t = TimeTool()
        r = await t.execute(query_type="now")
        assert r.success
        assert "当前时间" in r.data["answer"]

    async def test_all(self):
        t = TimeTool()
        r = await t.execute(query_type="all")
        assert r.success
        assert "当前时间" in r.data["answer"]
        assert "最近任务" in r.data["answer"]


# ── CalcTool ──
from backend.agents.tools.builtin.calc_tool import CalcTool


class TestCalc:
    async def test_simple(self):
        r = await CalcTool().execute(expression="2+3")
        assert r.success
        assert r.data["result"] == 5

    async def test_complex(self):
        r = await CalcTool().execute(expression="(5 + 3) * 2")
        assert r.success
        assert r.data["result"] == 16

    async def test_division(self):
        r = await CalcTool().execute(expression="10 / 3")
        assert r.success
        assert r.data["result"] == pytest.approx(3.333, rel=0.01)

    async def test_invalid(self):
        r = await CalcTool().execute(expression="__import__('os')")
        assert not r.success


# ── ConfirmTool ──
from backend.agents.tools.builtin.confirm_tool import ConfirmTool


class TestConfirm:
    async def test_confirm(self):
        r = await ConfirmTool().execute(message="开始清扫")
        assert r.success
        assert r.data["confirmed"] is True


# ── AskUserTool ──
from backend.agents.tools.builtin.ask_user import AskUserTool


class TestAskUser:
    async def test_no_answer(self):
        r = await AskUserTool().execute(question="测试问题")
        # ask_user returns success=True with empty answer when no user responds
        assert r.success
        assert r.data["answer"] == ""


# ── ToolResult baseline ──
from backend.agents.tools.base_tool import ToolResult


class TestToolResult:
    def test_defaults(self):
        r = ToolResult()
        assert r.success is True
        assert r.data is None
        assert r.error is None

    def test_failure(self):
        r = ToolResult(success=False, error="something wrong")
        assert not r.success
        assert r.error == "something wrong"

    def test_to_openai_format(self):
        from backend.agents.tools.builtin.calc_tool import CalcTool
        spec = CalcTool().to_openai_tool()
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "calculator"
        assert "parameters" in spec["function"]


# ── ToolRegistry ──
from backend.agents.tools.tool_registry import ToolRegistry


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register(CalcTool())
        assert "calculator" in reg
        assert reg.get("calculator") is not None
        assert "calculator" in reg.list_names()

    def test_register_many(self):
        reg = ToolRegistry()
        reg.register_many(CalcTool(), ConfirmTool())
        assert len(reg.list_tools()) == 2

    def test_to_openai_tools(self):
        reg = ToolRegistry()
        reg.register(CalcTool())
        reg.register(ConfirmTool())
        tools = reg.to_openai_tools()
        assert len(tools) == 2
        for t in tools:
            assert t["type"] == "function"

    def test_execute_unknown(self):
        reg = ToolRegistry()
        import asyncio
        r = asyncio.get_event_loop().run_until_complete(
            reg.execute("nonexistent", {})
        )
        assert not r.success

    def test_overwrite(self):
        reg = ToolRegistry()
        reg.register(CalcTool())
        reg.register(CalcTool())  # should warn but not crash
        assert "calculator" in reg
