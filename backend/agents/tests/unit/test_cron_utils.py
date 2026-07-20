"""Cron 工具单元测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest
from datetime import datetime, timedelta
from backend.utils.cron_utils import matches_cron, compute_next_run, validate_cron


class TestMatchesCron:
    def test_every_minute(self):
        assert matches_cron("* * * * *")

    def test_specific_minute(self):
        dt = datetime(2026, 6, 15, 10, 30)
        assert matches_cron("30 10 * * *", dt)
        assert not matches_cron("31 10 * * *", dt)

    def test_step_interval(self):
        """每5分钟"""
        dt = datetime(2026, 6, 15, 10, 10)  # minute=10, 10%5=0
        assert matches_cron("*/5 * * * *", dt)
        dt2 = datetime(2026, 6, 15, 10, 11)  # minute=11, 11%5=1
        assert not matches_cron("*/5 * * * *", dt2)

    def test_weekday_sunday(self):
        """Cron: 0=Sunday, datetime.weekday(): Monday=0, Sunday=6"""
        # 2026-06-21 is a Sunday
        dt = datetime(2026, 6, 21, 10, 0)
        assert matches_cron("0 10 * * 0", dt)

    def test_weekday_monday(self):
        """Cron: 1=Monday"""
        # 2026-06-15 is a Monday
        dt = datetime(2026, 6, 15, 10, 0)
        assert matches_cron("0 10 * * 1", dt)

    def test_weekday_saturday(self):
        """Cron: 6=Saturday"""
        # 2026-06-20 is a Saturday
        dt = datetime(2026, 6, 20, 10, 0)
        assert matches_cron("0 10 * * 6", dt)

    def test_daily_10am(self):
        dt = datetime(2026, 6, 15, 10, 0)
        assert matches_cron("0 10 * * *", dt)
        dt2 = datetime(2026, 6, 15, 11, 0)
        assert not matches_cron("0 10 * * *", dt2)

    def test_comma_separated(self):
        """逗号分隔的字段"""
        dt = datetime(2026, 6, 15, 10, 0)
        assert matches_cron("0 10 1,15 * *", dt)   # day=15 matches
        assert not matches_cron("0 10 1,14 * *", dt)

    def test_range(self):
        """范围语法 1-5"""
        dt = datetime(2026, 6, 3, 10, 0)  # day=3, in range 1-5
        assert matches_cron("0 10 1-5 * *", dt)
        dt2 = datetime(2026, 6, 6, 10, 0)  # day=6, not in range
        assert not matches_cron("0 10 1-5 * *", dt2)

    def test_invalid_format(self):
        assert not matches_cron("invalid")
        assert not matches_cron("* * * *")  # only 4 fields
        assert not matches_cron("")  # empty


class TestComputeNextRun:
    def test_next_minute(self):
        dt = datetime(2026, 6, 15, 10, 0)
        result = compute_next_run("* * * * *", dt)
        assert result == datetime(2026, 6, 15, 10, 1)

    def test_daily_10am_from_9am(self):
        """从9点开始，下一个10点应该是今天10点"""
        dt = datetime(2026, 6, 15, 9, 0)
        result = compute_next_run("0 10 * * *", dt)
        assert result == datetime(2026, 6, 15, 10, 0)

    def test_daily_10am_from_11am(self):
        """从11点开始，下一个10点应该是明天10点"""
        dt = datetime(2026, 6, 15, 11, 0)
        result = compute_next_run("0 10 * * *", dt)
        assert result == datetime(2026, 6, 16, 10, 0)

    def test_weekly_sunday(self):
        """下一个周日"""
        # 2026-06-15 is Monday, next Sunday is 06-21
        dt = datetime(2026, 6, 15, 9, 0)
        result = compute_next_run("0 10 * * 0", dt)
        assert result == datetime(2026, 6, 21, 10, 0)

    def test_every_5_minutes(self):
        dt = datetime(2026, 6, 15, 10, 1)
        result = compute_next_run("*/5 * * * *", dt)
        assert result == datetime(2026, 6, 15, 10, 5)


class TestValidateCron:
    def test_valid(self):
        assert validate_cron("* * * * *") is None
        assert validate_cron("0 10 * * *") is None
        assert validate_cron("*/5 * * * 0") is None

    def test_invalid_fields(self):
        assert validate_cron("* * * *") is not None

    def test_invalid_format(self):
        assert validate_cron("abc def ghi jkl mno") is not None
