"""场景加载单元测试"""
import pytest
from backend.agents.simulation.scenario_loader import SCENARIOS


class TestScenarioLoader:
    def test_12_scenarios_exist(self):
        assert len(SCENARIOS) == 12

    def test_each_scenario_has_required_keys(self):
        for name, s in SCENARIOS.items():
            assert "start" in s, f"{name} missing start"
            assert isinstance(s["start"], tuple), f"{name} start not tuple"
            assert len(s["start"]) == 2, f"{name} start len != 2"
            assert "obstacles" in s, f"{name} missing obstacles"
            assert "rooms" in s, f"{name} missing rooms"

    def test_rooms_have_required_keys(self):
        for name, s in SCENARIOS.items():
            for r in s.get("rooms", []):
                assert "name" in r, f"{name} room missing name"
                assert "polygon" in r, f"{name} room {r.get('name')} missing polygon"
                assert "center" in r, f"{name} room {r.get('name')} missing center"
                assert len(r["polygon"]) >= 3, f"{name} {r.get('name')} polygon < 3 pts"

    def test_named_scenarios(self):
        expected = {"standard", "open_plan", "apartment", "villa",
                     "mansion", "office", "studio", "school_floor",
                     "restaurant", "mall_floor"}
        for name in expected:
            assert name in SCENARIOS, f"Missing: {name}"
