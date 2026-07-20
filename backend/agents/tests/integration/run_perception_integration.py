# backend/agents/tests/test_perception.py
import asyncio
import random
from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.core.lifecycle.registry import AgentRegistry
from backend.agents.implementations.perception_agent import PerceptionAgent
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.agents.schemas.agent_messages import RawSensorData, PerceptionResult

def generate_complex_laser():
    """生成复杂激光数据：前方障碍物、左侧墙壁、右侧空旷"""
    laser = [2.0] * 360
    # 前方 0-60度 障碍物距离 0.3~1.0 米
    for deg in range(0, 61):
        laser[deg] = 0.3 + (deg/60)*0.7
    # 左侧 90-180度 墙体 1.5 米
    for deg in range(90, 181):
        laser[deg] = 1.5
    # 添加噪声
    for i in range(0, 360, 10):
        laser[i] += random.uniform(-0.05, 0.05)
    return laser

async def main():
    bus = MessageBus()
    registry = AgentRegistry()
    await bus.start()
    agent = PerceptionAgent("percept", "perception", bus, registry)
    await agent.start()

    raw = RawSensorData(
        robot_id="robot",
        timestamp=0,
        laser=generate_complex_laser(),
        bump_left=False,
        bump_right=False,
        cliff_sensors=[False]*4
    )
    msg = Message(type=MessageType.SENSOR, source="test", payload=raw.model_dump(), priority=Priority.NORMAL)
    result_queue = asyncio.Queue()
    async def cb(m):
        await result_queue.put(PerceptionResult(**m.payload))
    await bus.subscribe(MessageType.PERCEPTION, cb)
    await bus.publish(msg)
    perception = await asyncio.wait_for(result_queue.get(), timeout=2.0)
    print(f"障碍物数量: {len(perception.obstacles)}")
    print(f"地面类型: {perception.ground_type}")
    print(f"可通行栅格尺寸: {len(perception.free_space_grid)}x{len(perception.free_space_grid[0])}")
    await agent.stop()
    await bus.stop()

if __name__ == "__main__":
    asyncio.run(main())