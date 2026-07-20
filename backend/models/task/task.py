from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
import uuid
from dataclasses import dataclass
from backend.models.physics.robot_state import Pose


class TaskState(str, Enum):
    """任务状态（Supervisor 唯一真相源）"""
    IDLE = "idle"                # 空闲（无任务）
    PENDING = "pending"          # 初始状态
    READY = "ready"
    DISPATCHED = "dispatched"    # 已分发但尚未开始执行
    RUNNING = "running"          # 正在执行
    PAUSED = "paused"            # 已暂停
    RECHARGING = "recharging"    # 回充中
    CHARGING = "charging"        # 充电中
    STOPPED = "stopped"          # 外部停止
    CANCELLED = "cancelled"      # 用户取消
    SUCCESS = "success"          # 成功完成
    FAILED = "failed"            # 执行失败（可重试）
    RETRY = "retry"              # 正在重试（可选）
    SKIPPED = "skipped"          # 条件不满足跳过
    EMERGENCY_STOP = "emergency_stop"   # 急停（不可恢复）


@dataclass
class TaskContext:
    """保存任务恢复所需的核心信息（不包含动态进度）"""
    task_id: str
    graph_id: str
    current_node: str            # 当前正在执行的任务节点ID
    current_goal: Pose           # 当前导航目标点
    current_path: List[Pose]     # 当前路径点列表
    path_index: int              # 已走过的路径点索引
    room_id: str                 # 清扫区域

@dataclass
class ResumeContext:
    """用于回充后断点续扫的上下文"""
    task_context: TaskContext          # 原始任务上下文
    waypoint_index: int                # 覆盖路径的当前索引
    progress: float                    # 0~100
    current_goal: Optional[Pose] = None
    current_path: List[Pose] = None


class TaskType(str, Enum):
    CLEANING = "cleaning"
    COVERAGE_TEST = "coverage_test"
    COLLISION_TEST = "collision_test"
    NAVIGATION_BENCHMARK = "navigation_benchmark"
    SIMULATION_RUN = "simulation_run"
    NAVIGATE_TO = "navigate_to"           # 导航到指定坐标
    NAVIGATE_TO_AREA = "navigate_to_area" # 导航到区域（自动选点）
    EXPLORE_AREA = "explore_area"         # 探索某区域（全覆盖）
    RETURN_TO_CHARGE = "return_to_charge"
    RECOVER_STUCK = "recover_stuck"       # 卡死恢复
    WAIT = "wait"                         # 等待
    STOP = "stop"
    CLEAN_AREA = "clean_area"             # 区域清扫任务


class Task(BaseModel):
    """
    自动化测试任务（核心调度对象）
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType
    status: TaskState = TaskState.PENDING   # 使用 TaskState 枚举
    robot_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    success_rate: float = 0.0
    coverage_score: float = 0.0
    collision_count: int = 0
    max_retries: int = 0
    retry_delay: float = 1.0
    result: Optional[Dict[str, Any]] = None
    required_resources: List[str] = Field(default_factory=list)
    timeout: float = 30.0
    priority: int = 1
    version: int = 0   # 任务状态版本号，每次状态变更时递增