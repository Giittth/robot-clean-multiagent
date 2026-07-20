"""确认系统单元测试：ConfirmationManager + ConfirmTool"""
import pytest
import asyncio
from backend.agents.tools.confirmation_manager import ConfirmationManager
from backend.agents.tools.builtin.confirm_tool import ConfirmTool


class TestConfirmationManager:
    def test_empty_pending(self):
        cm = ConfirmationManager()
        assert cm.get_pending() == []

    @pytest.mark.asyncio
    async def test_request_and_resolve(self):
        cm = ConfirmationManager()
        async def req():
            return await cm.request("test?", timeout=5.0)

        task = asyncio.create_task(req())
        await asyncio.sleep(0.05)
        pending = cm.get_pending()
        assert len(pending) == 1
        cid = pending[0]["id"]
        assert pending[0]["message"] == "test?"
        cm.resolve(cid, True)
        result = await task
        assert result is True
        assert cm.get_pending() == []

    @pytest.mark.asyncio
    async def test_reject(self):
        cm = ConfirmationManager()
        task = asyncio.create_task(cm.request("reject?", timeout=5.0))
        await asyncio.sleep(0.05)
        cid = cm.get_pending()[0]["id"]
        cm.resolve(cid, False)
        result = await task
        assert result is False

    def test_invalid_id(self):
        cm = ConfirmationManager()
        ok = cm.resolve("nonexistent", True)
        assert ok is False

    @pytest.mark.asyncio
    async def test_timeout(self):
        cm = ConfirmationManager()
        result = await cm.request("timeout?", timeout=0.1)
        assert result is False
        assert cm.get_pending() == []


class TestConfirmTool:
    def test_schema(self):
        ct = ConfirmTool()
        assert ct.name == "confirm"
        assert "message" in ct.parameters
        assert ct.description != ""