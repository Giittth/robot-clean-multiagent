"""
从原始 Agent 消息构建前端 DTO，包含平滑滤波逻辑。
"""

from typing import Dict, Any
from backend.schemas.frontend_state import FrontendRobotState, PoseDTO, SensorDTO, ActionDTO, ObstacleDTO
from backend.services.state.smoothing_filter import SmoothingFilter
from backend.utils.logger_handler import logger


class FrontendStateBuilder:
    def __init__(self):
        # 为不同变量创建独立的滤波器
        self._filter_x = SmoothingFilter(0.15)
        self._filter_y = SmoothingFilter(0.15)
        self._filter_theta = SmoothingFilter(0.15)
        self._filter_battery = SmoothingFilter(0.2)

    def build(self,
              robot_state: Dict[str, Any],
              world_model: Dict[str, Any],
              perception: Dict[str, Any],
              task_state: Dict[str, Any],
              coverage: Dict[str, Any] = None) -> FrontendRobotState:
        robot_state = robot_state or {}
        world_model = world_model or {}
        perception = perception or {}
        task_state = task_state or {}
        coverage = coverage or {}

        pose_raw = robot_state.get("pose", {})
        battery_raw = robot_state.get("battery", {}).get("voltage", 12.0)
        collision = robot_state.get("collision", False)
        target_vel = robot_state.get("target_velocity", {})
        rag_advice = robot_state.get("rag_advice", "")
        power_state = robot_state.get("power_state", "OFF")

        cleaned_area = world_model.get("cleaned_area", 0.0)
        obstacles_raw = world_model.get("obstacles", [])
        # Coverage: prefer COVERAGE_UPDATE from NavigationAgent over WORLD_MODEL
        coverage_grid = coverage.get("grid", world_model.get("coverage_grid", []))

        # 激光数据：优先使用 PERCEPTION，其次 ROBOT_STATE 中的 sensor
        laser = perception.get("laser", [])
        if not laser:
            laser = robot_state.get("sensor", {}).get("laser", [])

        # 平滑滤波（位姿、电池）
        x = self._filter_x.filter(pose_raw.get("x", 0.0))
        y = self._filter_y.filter(pose_raw.get("y", 0.0))
        theta = self._filter_theta.filter(pose_raw.get("theta", 0.0))
        theta %= (2 * 3.14159)          # 角度规范到 [0, 2π)
        battery = self._filter_battery.filter(battery_raw)

        # 任务状态
        task_state_str = task_state.get("task_state", "idle")
        # 将终端状态强制映射为 idle，避免前端显示异常
        if task_state_str in ["completed", "failed", "success"]:
            task_state_str = "idle"
        task_id = task_state.get("task_id")
        progress = min(1.0, max(0.0, task_state.get("progress", 0.0)))

        # 构建 DTO（所有字段均有默认值，保证返回对象不为 None）
        # 注意：FrontendRobotState 必须在 schema 中定义 power_state 字段
        return FrontendRobotState(
            pose=PoseDTO(x=round(x, 3), y=round(y, 3), theta=round(theta, 3)),
            sensor=SensorDTO(battery_voltage=round(battery, 2), collision=collision, laser=laser),
            cleaned_area=round(cleaned_area, 2),
            action=ActionDTO(linear=target_vel.get("linear", 0.0), angular=target_vel.get("angular", 0.0)),
            rag_advice=rag_advice,
            obstacles=[ObstacleDTO(**obs) for obs in obstacles_raw] if obstacles_raw else [],
            task_state=task_state_str,
            task_id=task_id,
            progress=progress,
            power_state=power_state,          # 新增：电源状态（小写）
            coverage_grid=coverage_grid,       # 新增：覆盖地图栅格
        )