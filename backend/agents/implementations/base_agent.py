"""
request方法：用于发送请求并等待响应。
subscribe_topic方法，支持主题通配符订阅，允许订阅字符串主题（包括通配符 *、?）。
将 subscribe 内部转换为字符串主题（保持子类接口不变，仍接受 MessageType 枚举）。
统一存储订阅信息：使用字符串 topic 存储，以便 unsubscribe 时正确匹配。
"""

import asyncio
import uuid
import time
from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable, Tuple, List, Union, Any, Dict

from backend.agents.core.messaging.message_bus import MessageBus
# 导入心跳载荷模型（和 Message/MessageType 同文件）
from backend.agents.schemas.messages import Message, MessageType, Priority, HeartbeatPayload
from backend.agents.core.lifecycle.registry import AgentRegistry
from backend.agents.core.event.event_router import EventRouter
from backend.agents.core.event.event_types import Event, UIEventType
from backend.utils.logger_handler import logger


class BaseAgent(ABC):
    """
    所有智能体的抽象基类
    提供：注册、心跳、订阅、发布、请求-响应、统一命令/事件接口、生命周期管理

    消息发送指南：
    - 使用 send_command() 发送点对点控制指令，可以等待或不等待回复。
    - 使用 emit_event() 广播状态/进度/结果等事件，不需要等待回复。
    - 订阅消息使用 subscribe()（底层 MessageBus），订阅事件使用 event_router.subscribe()。
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        message_bus: MessageBus,
        registry: AgentRegistry,
        event_router: Optional[EventRouter] = None,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.bus = message_bus
        self.registry = registry
        self.event_router = event_router
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        # 记录订阅，用于退出时取消 (topic, callback)
        self._subscriptions: List[Tuple[str, Callable[[Message], Awaitable[None]]]] = []

    async def start(self):
        """启动智能体：注册、订阅、启动心跳"""
        self.registry.register(self.agent_id, self.agent_type)

        # 子类定义的订阅逻辑
        await self._subscribe_messages()

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._send_heartbeat())

        await self.on_start()
        logger.info(f"Agent {self.agent_id} started successfully")

    async def stop(self):
        """停止智能体：取消心跳、取消订阅、注销"""
        if not self._running:
            return

        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 取消所有订阅
        for topic, callback in self._subscriptions:
            await self.bus.unsubscribe(topic, callback)
        self._subscriptions.clear()

        self.registry.unregister(self.agent_id)

        await self.on_stop()
        logger.info(f"Agent {self.agent_id} stopped gracefully")

    async def _send_heartbeat(self):
        """定期发送心跳【已适配 Pydantic HeartbeatPayload】"""
        while self._running:
            await asyncio.sleep(10)
            try:
                await self.registry.heartbeat(self.agent_id)
                # ========== 变更1：使用标准 HeartbeatPayload 构造心跳 ==========
                hb_payload = HeartbeatPayload(
                    agent_id=self.agent_id,
                    timestamp=time.time(),
                    status="alive"
                )
                heartbeat_msg = Message(
                    type=MessageType.HEARTBEAT,
                    source=self.agent_id,
                    payload=hb_payload.model_dump()
                )
                await self.bus.publish(heartbeat_msg)
            except Exception as e:
                logger.error(f"Heartbeat failed for {self.agent_id}: {e}")

    # ========== 订阅与发布（向后兼容） ==========
    async def subscribe(self, msg_type: MessageType, callback: Callable[[Message], Awaitable[None]]):
        """
        订阅指定消息类型（转换为字符串主题）
        子类在 _subscribe_messages 中调用此方法
        """
        topic = msg_type.value   # 枚举值作为主题字符串
        await self.bus.subscribe(topic, callback)
        self._subscriptions.append((topic, callback))

    async def subscribe_topic(self, topic: str, callback: Callable[[Message], Awaitable[None]]):
        """
        订阅带通配符的主题（支持 * 和 ?）
        例如：subscribe_topic("robot.*", callback)
        """
        await self.bus.subscribe(topic, callback)
        self._subscriptions.append((topic, callback))

    async def publish(
        self,
        msg_type: MessageType,
        payload: dict,
        target: Optional[str] = None,
        priority: Priority = Priority.NORMAL
    ):
        """便捷发布消息（自动填充 source）"""
        # ========== 变更2：强拦截 普通Agent禁止发送 SIMULATION_STATE ==========
        if msg_type == MessageType.SIMULATION_STATE:
            logger.warning(f"[Forbidden] Agent {self.agent_id} 不允许发送 SIMULATION_STATE，已拦截")
            return

        msg = Message(
            type=msg_type,
            source=self.agent_id,
            target=target,
            payload=payload,
            priority=priority
        )
        await self.bus.publish(msg)

    async def publish_message(self, message: Message):
        """直接发布已构造好的 Message 对象"""
        # ========== 变更3：对直接发送Message对象也做拦截（防止绕开publish） ==========
        if message.type == MessageType.SIMULATION_STATE:
            logger.warning(f"[Forbidden] Agent {self.agent_id} 直接转发 SIMULATION_STATE，已拦截")
            return
        await self.bus.publish(message)

    # ========== 统一命令/事件接口 ==========
    async def send_command(
        self,
        target: str,
        command_type: Union[MessageType, str],
        payload: Dict[str, Any],
        *,
        timeout: float = 10.0,
        expect_reply: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        发送点对点控制指令，通常用于请求-响应场景（如导航请求）。

        :param target: 目标 Agent ID
        :param command_type: 指令类型（MessageType 或字符串）
        :param payload: 指令参数
        :param timeout: 等待响应的超时时间（秒）
        :param expect_reply: 是否期望回复
        :return: 如果 expect_reply=True，返回响应 payload；否则返回 None
        """
        # 兼容字符串类型
        if isinstance(command_type, str):
            # 尝试转为 MessageType，如果失败则视为自定义类型（需要确保 MessageBus 支持）
            try:
                msg_type = MessageType(command_type)
            except ValueError:
                # 使用自定义字符串作为 type，但 Message 要求 MessageType 枚举，这里不推荐
                raise ValueError(f"command_type must be a valid MessageType or convertible string, got {command_type}")
        else:
            msg_type = command_type

        msg = Message(
            type=msg_type,
            source=self.agent_id,
            target=target,
            payload=payload,
            correlation_id=str(uuid.uuid4()) if expect_reply else None,
        )
        if expect_reply:
            response = await self.bus.request(msg, timeout=timeout)
            return response.payload
        else:
            await self.bus.publish(msg)
            return None

    async def emit_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        *,
        task_id: Optional[str] = None,
    ):
        """
        广播事件，通常用于状态更新、进度通知、结果公布等。

        :param event_type: 事件类型字符串（如 "ui.task_progress"）
        :param payload: 事件数据
        :param task_id: 关联的任务 ID（可选）
        """
        if self.event_router is None:
            logger.warning(f"Agent {self.agent_id} has no event_router, cannot emit event")
            return
        event = Event(
            type=event_type,
            source=self.agent_id,
            task_id=task_id,
            payload=payload,
        )
        await self.event_router.emit(event)

    # ========== 请求-响应（旧接口，推荐使用 send_command） ==========
    async def request(
        self,
        msg_type: MessageType,
        payload: dict,
        target: Optional[str] = None,
        timeout: float = 10.0
    ) -> Message:
        """
        发送请求并等待响应（返回整个 Message 对象）
        推荐使用 send_command 代替。
        """
        # 同样增加拦截
        if msg_type == MessageType.SIMULATION_STATE:
            logger.warning(f"[Forbidden] Agent {self.agent_id} 使用 request 发送 SIMULATION_STATE，已拦截")
            raise RuntimeError("不允许请求 SIMULATION_STATE 类型消息")

        msg = Message(
            type=msg_type,
            source=self.agent_id,
            target=target,
            payload=payload,
        )
        return await self.bus.request(msg, timeout)

    # ========== 子类钩子 ==========
    @abstractmethod
    async def on_start(self):
        """子类实现：启动后逻辑"""
        pass

    @abstractmethod
    async def on_stop(self):
        """子类实现：停止前清理"""
        pass

    async def _subscribe_messages(self):
        """子类重写：在此方法内调用 subscribe 或 subscribe_topic"""
        pass

    async def send_task_feedback(self, task_id: str, status: str, progress: float, message: str):
        """发送任务进度事件（ui.task_progress）"""
        await self.emit_event(
            UIEventType.TASK_PROGRESS.value,
            task_id=task_id,
            payload={
                "status": status,
                "progress": progress,
                "message": message
            }
        )

    async def send_task_result(self, task_id: str, success: bool, result: dict = None):
        """发送任务最终结果事件（ui.task_result）"""
        await self.emit_event(
            UIEventType.TASK_RESULT.value,
            task_id=task_id,
            payload={
                "success": success,
                "result": result or {}
            }
        )