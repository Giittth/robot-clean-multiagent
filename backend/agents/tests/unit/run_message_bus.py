import pytest
import asyncio
from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.schemas.messages import Message, MessageType, Priority

# 定义一个异步fixture，用于创建和清理 MessageBus 实例
# 注意：async fixture 的清理需要使用 yield 配合 try/finally，并加上 asyncio 标记[reference:0]
@pytest.fixture
async def bus():
    b = MessageBus()
    await b.start()
    # 使用 yield 将 MessageBus 实例提供给测试函数
    # 当测试函数运行完毕后，会继续执行 yield 之后的代码进行清理
    try:
        yield b
    finally:
        await b.stop()

# 所有测试函数都必须使用 @pytest.mark.asyncio 装饰器
# 这告诉 pytest 这是一个异步测试，需要用事件循环来运行它[reference:1]
@pytest.mark.asyncio
async def test_subscribe_and_publish(bus):
    received = []
    async def callback(msg: Message):
        received.append(msg.payload["value"])
    await bus.subscribe(MessageType.STATE, callback)
    msg = Message(type=MessageType.STATE, source="test", payload={"value": 42})
    await bus.publish(msg)
    # 等待异步任务完成
    await asyncio.sleep(0.1)
    assert received == [42]


@pytest.mark.asyncio
async def test_priority_order(bus):
    order = []
    async def high_cb(msg): order.append("high")
    async def low_cb(msg): order.append("low")
    await bus.subscribe(MessageType.CONTROL, high_cb)
    await bus.subscribe(MessageType.CONTROL, low_cb)
    low_msg = Message(type=MessageType.CONTROL, source="test", payload={}, priority=Priority.LOW)
    high_msg = Message(type=MessageType.CONTROL, source="test", payload={}, priority=Priority.HIGH)
    await bus.publish(low_msg)
    await bus.publish(high_msg)
    await asyncio.sleep(0.1)
    # 优先级高的应该先处理
    assert order == ["high", "low"]


@pytest.mark.asyncio
async def test_ttl_expiry(bus):
    expired = []
    async def cb(msg): expired.append(False)
    await bus.subscribe(MessageType.HEARTBEAT, cb)
    # TTL 设置为 0，消息应立即过期
    msg = Message(type=MessageType.HEARTBEAT, source="test", payload={}, ttl=0)
    await bus.publish(msg)
    await asyncio.sleep(0.1)
    # 消息不应被传递，所以列表应为空
    assert len(expired) == 0