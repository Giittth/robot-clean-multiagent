import asyncio
from datetime import datetime
from typing import List

from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.core.lifecycle.registry import AgentRegistry
from backend.agents.implementations.perception_agent import PerceptionAgent
from backend.agents.implementations.navigation_agent import NavigationAgent
from backend.agents.implementations.execution_agent import ExecutionAgent
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.agents.schemas.agent_messages import RawSensorData
from backend.utils.logger_handler import logger


def generate_laser_data(robot_x: float = 0, robot_y: float = 0) -> List[float]:
    """模拟激光雷达数据：正前方1米处有障碍物"""
    laser = [2.0] * 360
    for angle in range(-10, 11):
        idx = (angle + 360) % 360
        laser[idx] = 0.5
    return laser


async def main():
    # 初始化核心组件
    bus = MessageBus()
    registry = AgentRegistry()
    await bus.start()

    # 创建智能体
    perception = PerceptionAgent(
        agent_id="perception_1",
        agent_type="perception",
        message_bus=bus,
        registry=registry
    )
    navigation = NavigationAgent(
        agent_id="nav_1",
        agent_type="navigation",
        message_bus=bus,
        registry=registry,
        map_size=(20, 20)
    )
    execution = ExecutionAgent(
        agent_id="exec_1",
        agent_type="execution",
        message_bus=bus,
        registry=registry
    )

    # 启动所有智能体
    await perception.start()
    await navigation.start()
    await execution.start()
    logger.info("All agents started successfully")

    # 仿真循环：发布传感器数据
    robot_pose = {"x": 0.0, "y": 0.0, "theta": 0.0}
    for step in range(10):
        robot_pose["x"] += 0.2
        robot_pose["theta"] += 0.05

        # 生成模拟激光
        laser = generate_laser_data(robot_pose["x"], robot_pose["y"])

        # 使用新模型字段（bump_left / bump_right / cliff_sensors）
        raw_data = RawSensorData(
            robot_id="robot_001",
            timestamp=datetime.utcnow().timestamp(),
            laser=laser,
            bump_left=False,
            bump_right=False,
            cliff_sensors=[False, False, False, False]
        )

        # 发布到消息总线
        msg = Message(
            type=MessageType.SENSOR,
            source="simulator",
            target=None,
            payload=raw_data.model_dump(),
            priority=Priority.NORMAL
        )
        await bus.publish(msg)

        logger.info(f"Published sensor data | x={robot_pose['x']:.2f}, y={robot_pose['y']:.2f}")
        await asyncio.sleep(1)

    # 等待消息处理完毕
    await asyncio.sleep(3)

    # 优雅停止
    await perception.stop()
    await navigation.stop()
    await execution.stop()
    await bus.stop()
    logger.info("All agents stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())