import asyncio
from datetime import datetime
from typing import List, Tuple

from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.core.lifecycle.registry import AgentRegistry
from backend.agents.implementations.perception_agent import PerceptionAgent
from backend.agents.implementations.navigation_agent import NavigationAgent
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.agents.schemas.agent_messages import RawSensorData
from backend.utils.logger_handler import logger


# 辅助函数：模拟激光雷达数据（简单生成一条直线上的障碍物）
def generate_laser_data(robot_x: float = 0, robot_y: float = 0) -> List[float]:
    # 360度数据，假设前方2米处有障碍物
    laser = [2.0] * 360
    # 在 0度方向（正前方）放置一个障碍物
    for angle in range(-10, 11):
        idx = (angle + 360) % 360
        laser[idx] = 0.5
    return laser

async def main():
    # 1. 创建总线与注册中心
    bus = MessageBus()
    registry = AgentRegistry()
    await bus.start()

    # 2. 创建 Agent
    perception_agent = PerceptionAgent(
        agent_id="perception_1",
        agent_type="perception",
        message_bus=bus,
        registry=registry
    )
    # 地图大小 10x10 网格，每个网格 0.2m
    navigation_agent = NavigationAgent(
        agent_id="nav_1",
        agent_type="navigation",
        message_bus=bus,
        registry=registry,
        map_size=(20, 20)   # 4m x 4m 地图
    )

    # 启动 Agent
    await perception_agent.start()
    await navigation_agent.start()

    # 3. 模拟仿真循环：每1秒发布一次传感器数据，机器人位置逐渐前移
    robot_pose = {"x": 0.0, "y": 0.0, "theta": 0.0}
    for step in range(10):
        # 更新机器人位置（模拟移动）
        robot_pose["x"] += 0.2
        robot_pose["theta"] += 0.05

        # 生成模拟激光数据（基于当前位置）
        laser = generate_laser_data(robot_pose["x"], robot_pose["y"])

        raw_data = RawSensorData(
            robot_id="robot_001",
            timestamp=datetime.now().timestamp(),
            laser=laser,
            bump_left=False,
            bump_right=False,
            cliff_sensors=[False, False, False, False]
        )

        # 发布传感器数据
        msg = Message(
            type=MessageType.SENSOR,
            source="simulator",
            target=None,
            payload=raw_data.model_dump(),
            priority=Priority.NORMAL
        )
        await bus.publish(msg)
        logger.info(f"Published sensor data, robot pose: x={robot_pose['x']:.2f}, y={robot_pose['y']:.2f}, theta={robot_pose['theta']:.2f}")

        # 等待处理
        await asyncio.sleep(1)

    # 4. 再等待几秒，让导航Agent完成最后输出
    await asyncio.sleep(3)

    # 5. 清理
    await perception_agent.stop()
    await navigation_agent.stop()
    await bus.stop()

if __name__ == "__main__":
    asyncio.run(main())