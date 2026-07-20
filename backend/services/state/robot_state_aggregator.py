"""订阅多个 Agent 消息，聚合缓存，并在数据更新时重新构建前端 DTO。"""

import asyncio
from typing import Dict, Any
from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.schemas.messages import MessageType, Message
from backend.services.state.frontend_state_builder import FrontendStateBuilder
from backend.utils.logger_handler import logger


class RobotStateAggregator:
    def __init__(self, bus: MessageBus, builder: FrontendStateBuilder):
        self.bus = bus
        self.builder = builder
        self._robot_state = {}
        self._world_model = {}
        self._perception = {}
        self._task_state = {}
        self._coverage = {}
        self._running = False
        self._update_event = asyncio.Event()
        self._frontend_state = None

    async def start(self):
        await self.bus.subscribe(MessageType.ROBOT_STATE.value, self._on_robot_state)
        await self.bus.subscribe(MessageType.WORLD_MODEL.value, self._on_world_model)
        await self.bus.subscribe(MessageType.PERCEPTION.value, self._on_perception)
        await self.bus.subscribe(MessageType.TASK_STATE_CHANGED.value, self._on_task_state)
        await self.bus.subscribe(MessageType.COVERAGE_UPDATE.value, self._on_coverage)
        self._running = True
        asyncio.create_task(self._update_loop())
        logger.info("RobotStateAggregator started")

    async def stop(self):
        self._running = False
        await self.bus.unsubscribe(MessageType.ROBOT_STATE.value, self._on_robot_state)
        await self.bus.unsubscribe(MessageType.WORLD_MODEL.value, self._on_world_model)
        await self.bus.unsubscribe(MessageType.PERCEPTION.value, self._on_perception)
        await self.bus.unsubscribe(MessageType.TASK_STATE_CHANGED.value, self._on_task_state)
        await self.bus.unsubscribe(MessageType.COVERAGE_UPDATE.value, self._on_coverage)

    async def _on_robot_state(self, msg):
        self._robot_state = msg.payload
        self._update_event.set()

    async def _on_world_model(self, msg):
        self._world_model = msg.payload
        self._update_event.set()

    async def _on_perception(self, msg):
        self._perception = msg.payload
        self._update_event.set()

    async def _on_task_state(self, msg: Message):
        payload = msg.payload or {}
        state = payload.get("task_state", "idle")
        payload["task_state"] = state
        self._task_state = payload
        self._update_event.set()

    async def _on_coverage(self, msg):
        self._coverage = msg.payload
        self._update_event.set()

    async def _update_loop(self):
        while self._running:
            await self._update_event.wait()
            self._update_event.clear()
            self._frontend_state = self.builder.build(
                self._robot_state,
                self._world_model,
                self._perception,
                self._task_state,
                self._coverage,
            )

    def get_frontend_state(self) -> dict:
        return self._frontend_state.model_dump() if self._frontend_state else {}