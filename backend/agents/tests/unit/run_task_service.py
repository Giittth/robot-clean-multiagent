"""任务历史单元测试"""
import pytest
from datetime import datetime
from backend.models.db_model.task import TaskHistoryDB
from backend.db.task_service import save_task, get_task_stats, get_recent_tasks


class TestTaskHistoryModel:
    def test_create_model(self):
        t = TaskHistoryDB(id=1, command="test", task_type="clean", result="success")
        assert t.command == "test"
        assert t.task_type == "clean"
        assert t.result == "success"
        assert t.user_id == 0

    def test_default_user_id(self):
        t = TaskHistoryDB(id=2, command="x")
        assert t.user_id == 0

    def test_optional_fields(self):
        t = TaskHistoryDB(id=3, command="x", started_at=datetime.now())
        assert t.started_at is not None
        assert t.finished_at is None
        assert t.error_info is None
