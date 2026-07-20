from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any
from backend.models.physics.robot_state import Pose


@dataclass
class RobotState:
    pose: Pose = field(default_factory=lambda: Pose(x=0.0, y=0.0, theta=0.0))
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    battery_voltage: float = 12.0
    battery_percent: float = 100.0
    battery_charging: bool = False
    collision: bool = False
    laser: List[float] = field(default_factory=lambda: [2.0] * 360)
    obstacles: List[Dict[str, Any]] = field(default_factory=list)
    cleaned_area: float = 0.0


class RobotDriver(ABC):
    @abstractmethod
    async def get_state(self) -> RobotState:
        ...

    @abstractmethod
    async def send_velocity(self, linear: float, angular: float, duration: float = 0.2) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def reset(self) -> None:
        ...

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass
