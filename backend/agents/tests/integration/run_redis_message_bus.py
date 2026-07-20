import asyncio
import pytest
from backend.agents.core.messaging.broker import RedisMessageBus
from backend.agents.schemas.messages import Message, MessageType, Priority

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def redis_bus():
    # bus = RedisMessageBus(redis_url="redis://localhost:6379")
    await bus.start()
    await asyncio.sleep(0.2)  # 等待连接稳定
    yield bus
    await bus.stop()

async def test_subscribe_and_publish(redis_bus):
    received = []

    async def callback(msg: Message):
        received.append(msg.payload["value"])

    await redis_bus.subscribe(MessageType.STATE, callback)
    await asyncio.sleep(0.2)  # 👈 关键：等订阅生效

    msg = Message(type=MessageType.STATE, source="test", payload={"value": 42})
    await redis_bus.publish(msg)

    await asyncio.sleep(0.3)
    assert len(received) == 1
    assert received[0] == 42

async def test_multiple_subscribers(redis_bus):
    results = []

    async def cb1(msg): results.append("cb1")
    async def cb2(msg): results.append("cb2")

    await redis_bus.subscribe(MessageType.STATE, cb1)
    await redis_bus.subscribe(MessageType.STATE, cb2)
    await asyncio.sleep(0.2)  # 👈 关键

    msg = Message(type=MessageType.STATE, source="test", payload={})
    await redis_bus.publish(msg)

    await asyncio.sleep(0.3)
    assert set(results) == {"cb1", "cb2"}

async def test_unsubscribe(redis_bus):
    called = False

    async def callback(msg):
        nonlocal called
        called = True

    await redis_bus.subscribe(MessageType.STATE, callback)
    await asyncio.sleep(0.2)

    await redis_bus.unsubscribe(MessageType.STATE, callback)
    await asyncio.sleep(0.2)

    msg = Message(type=MessageType.STATE, source="test", payload={})
    await redis_bus.publish(msg)

    await asyncio.sleep(0.3)
    assert not called