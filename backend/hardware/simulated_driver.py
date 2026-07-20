import asyncio
import math
from typing import List, Dict, Any, Optional
from backend.hardware.base import RobotDriver, RobotState
from backend.agents.simulation.environment import SimulationEnvironment
from backend.models.physics.robot_state import Pose
from backend.utils.logger_handler import logger


class SimulatedDriver(RobotDriver):
    """模拟环境驱动：包装 SimulationEnvironment 实现 RobotDriver 接口。

    设计要点：
    - get_state() 直接从 env 内部状态读取，不走消息总线。
    - send_velocity() 在模拟模式下为空操作（总线驱动仿真）。
    """

    def __init__(self, env: SimulationEnvironment):
        self._env = env
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("SimulatedDriver started")

    async def close(self) -> None:
        self._running = False
        logger.info("SimulatedDriver closed")

    async def get_state(self) -> RobotState:
        env = self._env
        laser = getattr(env, "last_laser", [2.0] * 360)
        battery_pct = max(0.0, min(100.0, (env.battery_voltage - 10.0) / 2.0 * 100.0))
        return RobotState(
            pose=Pose(x=env.pose.x, y=env.pose.y, theta=env.pose.theta),
            linear_velocity=getattr(env, "_current_linear_vel", 0.0),
            angular_velocity=getattr(env, "_current_angular_vel", 0.0),
            battery_voltage=env.battery_voltage,
            battery_percent=battery_pct,
            battery_charging=False,
            collision=env.collision_detected,
            laser=laser,
            obstacles=env.scenario.get("obstacles", []),
            cleaned_area=env.cleaned_area,
        )

    async def send_velocity(self, linear: float, angular: float, duration: float = 0.2) -> None:
        pass

    async def stop(self) -> None:
        if hasattr(self._env, "_current_linear_vel"):
            self._env._current_linear_vel = 0.0
            self._env._current_angular_vel = 0.0
        logger.info("SimulatedDriver: stop requested")

    async def reset(self) -> None:
        await self._env.reset()
        logger.info("SimulatedDriver: env reset")

    def add_obstacle(self, x: float, y: float, radius: float = 0.3) -> None:
        self._env.add_obstacle(x, y, radius)

    def add_obstacles(self, positions: list, radius: float = 0.3) -> None:
        self._env.add_obstacles(positions, radius)

    def remove_obstacles(self, positions: list, tolerance: float = 0.5) -> None:
        self._env.remove_obstacles(positions, tolerance)

    def clear_obstacles(self) -> None:
        self._env.clear_obstacles()

    def get_obstacles(self) -> list:
        return self._env.scenario.get("obstacles", [])

    async def reload_scenario(self, name: str) -> None:
        await self._env.reload_scenario(name)

    def get_rooms(self) -> dict:
        rooms_data = self._env.scenario.get("rooms", [])
        rooms = {}
        for room in rooms_data:
            rooms[room["name"]] = {
                "polygon": room["polygon"],
                "center": room.get("center"),
                "entry_point": room.get("entry_point"),
            }
        return rooms

    @property
    def env(self) -> SimulationEnvironment:
        return self._env

    @property
    def pose(self):
        return self._env.pose

    @property
    def battery_voltage(self):
        return self._env.battery_voltage

    @property
    def cleaned_area(self):
        return self._env.cleaned_area

    @property
    def collision_detected(self):
        return self._env.collision_detected

    @property
    def scenario(self):
        return self._env.scenario
