from datetime import datetime
from typing import Any, Optional, Dict
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class MessageType(str, Enum):
    """消息类型枚举"""
    # 感知/状态
    SENSOR = "sensor"
    PERCEPTION = "perception"
    WORLD_MODEL = "world_model"
    ROBOT_STATE = "robot_state"

    # 导航/执行
    NAVIGATION = "navigation"
    EXECUTION = "execution"
    NAVIGATION_RESULT = "navigation_result"

    # 用户控制
    USER_COMMAND = "user_command"           # 前端 → Supervisor
    TASK = "task"                           # 用户/UI 下发高层任务
    CONTROL = "control"                     # UI 直接控制（暂停/恢复/停止）

    # Agent Command
    NAVIGATION_REQUEST = "navigation_request"       # 发给 NavigationAgent 的高层导航目标
    EXECUTION_CONTROL = "execution_control"         # 发给 ExecutionAgent 的全局控制（暂停/恢复/停止）
    NAVIGATION_CONTROL = "navigation_control"       # 发给 NavigationAgent 的路径跟踪控制（暂停/恢复/停止）

    # 任务控制（统一指令）
    TASK_CONTROL = "task_control"                   # 统一任务控制指令（pause/resume/cancel/recharge/emergency_stop）

    # 状态同步
    TASK_STATE_CHANGED = "task_state_changed"       # 任务状态变更通知

    # 系统
    HEARTBEAT = "heartbeat"

    # 模拟
    SIMULATION_STATE = "simulation_state"
    # 地图
    MAP_METADATA = "map_metadata"

    # 加载房间
    ROOMS_READY = "rooms_ready"
    # 房间的信息
    ROOMS_UPDATE = "rooms_update"

    GET_NAVIGATION_STATE = "get_navigation_state"
    NAVIGATION_STATE = "navigation_state"

    # 覆盖更新
    COVERAGE_UPDATE = "coverage_update"


class Priority(int, Enum):
    """消息优先级（数值越小优先级越高）"""
    HIGHEST = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    LOWEST = 4


class Message(BaseModel):
    """系统统一消息格式（用于消息总线）"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType                      # 消息类型
    source: str                            # 发送方ID
    target: Optional[str] = None           # 接收方ID，None=广播
    payload: Dict[str, Any]                # 消息体
    priority: Priority = Priority.NORMAL   # 优先级
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ttl: int = 60                          # 过期时间（秒）

    correlation_id: Optional[str] = None   # 关联请求与响应
    reply_to: Optional[str] = None         # 响应应该发送到的主题

    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"


# 心跳消息载荷模型
class HeartbeatPayload(BaseModel):
    agent_id: str
    timestamp: float
    status: str = Field(default="ok", description="Agent状态：ok/busy/error")