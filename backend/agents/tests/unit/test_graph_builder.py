"""GraphBuilder 单元测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest
from backend.agents.decision.planner.graph_builder import GraphBuilder, GraphBuildError
from backend.agents.decision.planner.planner_context import PlannerContext
from backend.agents.decision.runtime.task_graph import TaskGraph, EdgeType


def _make_ctx(command="清扫客厅"):
    return PlannerContext(
        robot_id="robot_001",
        user_command=command,
        world_state={},
        robot_state={},
        rooms=["living_room", "kitchen", "bedroom"],
    )


class TestGraphBuild:
    def test_basic_linear(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "nav1", "type": "navigate_to_area",
             "params": {"room_id": "living_room"}, "depends_on": []},
            {"id": "clean1", "type": "clean_area",
             "params": {"room_id": "living_room"}, "depends_on": ["nav1"]},
        ]
        graph = builder.build(data, _make_ctx())
        assert len(graph.tasks) == 2
        assert "nav1" in graph.tasks
        assert "clean1" in graph.tasks
        # Should have 1 edge: nav1 -> clean1 (SUCCESS)
        assert len(graph.edges) == 1
        assert graph.edges[0].source == "nav1"
        assert graph.edges[0].target == "clean1"
        assert graph.edges[0].type == EdgeType.SUCCESS

    def test_parallel_tasks(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "nav1", "type": "navigate_to_area",
             "params": {"room_id": "living_room"}, "depends_on": []},
            {"id": "nav2", "type": "navigate_to_area",
             "params": {"room_id": "kitchen"}, "depends_on": []},
            {"id": "merge", "type": "return_to_charge",
             "params": {}, "depends_on": ["nav1", "nav2"]},
        ]
        graph = builder.build(data, _make_ctx())
        assert len(graph.tasks) == 3
        # nav1 -> merge, nav2 -> merge
        assert len(graph.edges) == 2

    def test_missing_dep_ignored(self):
        """依赖不存在的任务 ID 应被忽略，不报错"""
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "task1", "type": "navigate_to_area",
             "params": {"room_id": "living_room"},
             "depends_on": ["nonexistent"]},
        ]
        graph = builder.build(data, _make_ctx())
        assert len(graph.tasks) == 1
        assert len(graph.edges) == 0

    def test_missing_id_skipped(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"type": "navigate_to_area", "params": {}, "depends_on": []},
        ]
        with pytest.raises(GraphBuildError):
            builder.build(data, _make_ctx())

    def test_invalid_type_skipped(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "t1", "type": "fly_to_moon", "params": {}, "depends_on": []},
        ]
        with pytest.raises(GraphBuildError):
            builder.build(data, _make_ctx())

    def test_duplicate_id_skipped(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "t1", "type": "navigate_to_area",
             "params": {"room_id": "living_room"}, "depends_on": []},
            {"id": "t1", "type": "clean_area",
             "params": {"room_id": "living_room"}, "depends_on": []},
        ]
        graph = builder.build(data, _make_ctx())
        assert len(graph.tasks) == 1

    def test_no_valid_tasks_raises(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "t1", "type": "fly_to_moon", "params": {}, "depends_on": []},
        ]
        with pytest.raises(GraphBuildError):
            builder.build(data, _make_ctx())

    def test_cycle_detection(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "a", "type": "navigate_to_area",
             "params": {"room_id": "living_room"}, "depends_on": ["b"]},
            {"id": "b", "type": "clean_area",
             "params": {"room_id": "living_room"}, "depends_on": ["a"]},
        ]
        with pytest.raises(GraphBuildError):
            builder.build(data, _make_ctx())

    def test_resource_inference(self):
        builder = GraphBuilder(robot_id="robot_001")
        assert builder._infer_resources("navigate_to") == ["motion"]
        assert builder._infer_resources("clean_area") == ["motion"]
        assert builder._infer_resources("return_to_charge") == ["motion"]
        # Unknown task type gets empty resources (from TaskType conversion)
        # but _infer_resources receives TaskType enum, so test by actual type
        from backend.models.task.task import TaskType
        assert builder._infer_resources(TaskType.NAVIGATE_TO) == ["motion"]

    def test_default_params(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "t1", "type": "navigate_to_area",
             "params": {}, "depends_on": []},
        ]
        graph = builder.build(data, _make_ctx())
        task = graph.tasks["t1"]
        assert task.robot_id == "robot_001"
        assert task.status.value == "pending"
        assert task.max_retries == 1
        assert task.priority == 1

    def test_custom_params(self):
        builder = GraphBuilder(robot_id="robot_001")
        data = [
            {"id": "t1", "type": "clean_area",
             "params": {"timeout": 120.0, "max_retries": 3, "priority": 5},
             "depends_on": []},
        ]
        graph = builder.build(data, _make_ctx())
        task = graph.tasks["t1"]
        assert task.timeout == 120.0
        assert task.max_retries == 3
        assert task.priority == 5
