"""
EventRouter 是系统中统一的事件分发中枢，主要作用：
    解耦事件发送与处理：任何组件（如 GraphExecutor、NavigationAgent）只需调用 emit(event)，无需关心谁会处理。
    支持通配符订阅：例如订阅 ui.* 可以接收所有 UI 事件，便于前端或监控模块批量监听。
    异步非阻塞：事件队列 + 后台消费协程，发送方不阻塞，处理方独立运行。
    容错性：单个事件处理器的异常不会影响其他处理器或整个路由器。
用于 Runtime 内部事件（runtime.*）和 UI 展示事件（ui.*），与负责点对点控制指令的 MessageBus 形成职责分离。
"""

import asyncio
from typing import Dict, Set, Callable, Awaitable, Optional
from collections import defaultdict
from backend.agents.core.event.event_types import Event
from backend.utils.logger_handler import logger


class EventRouter:
    """
    统一事件路由器，支持通配符订阅。
    仅处理 UI 事件（ui.*）和 Runtime 事件（runtime.*），不处理 Agent 消息（MessageBus 负责）。
    """

    def __init__(self):
        self._handlers: Dict[str, Set[Callable[[Event], Awaitable[None]]]] = defaultdict(set)
        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._consumer_task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: str, handler: Callable[[Event], Awaitable[None]]):
        """
        订阅特定类型的事件。
        支持通配符：例如 "ui.*" 匹配所有 ui 事件， "runtime.task_completed" 精确匹配。
        """
        self._handlers[event_type].add(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], Awaitable[None]]):
        """取消订阅"""
        self._handlers[event_type].discard(handler)

    async def emit(self, event: Event):
        """发送事件，若路由器未启动则自动启动"""
        if not self._running:
            await self.start()
        await self._event_queue.put(event)

    async def start(self):
        """启动事件路由器（消费协程）"""
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._consume())
        logger.info("EventRouter started")

    async def stop(self):
        """停止事件路由器"""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def _consume(self):
        """事件消费主循环：根据通配符匹配规则分发事件"""
        while self._running:
            try:
                event = await self._event_queue.get()
                matched = set()
                for pattern, handlers in self._handlers.items():
                    if self._matches(event.type, pattern):
                        matched.update(handlers)
                for handler in matched:
                    asyncio.create_task(self._safe_call(handler, event))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EventRouter error: {e}", exc_info=True)

    def _matches(self, event_type: str, pattern: str) -> bool:
        """
        通配符匹配规则：
        - "*" 匹配所有
        - 以 "*" 结尾的模式匹配前缀（如 "ui.*" 匹配 "ui.task_progress"）
        - 否则精确匹配
        """
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return event_type == pattern

    async def _safe_call(self, handler: Callable[[Event], Awaitable[None]], event: Event):
        """安全执行回调，防止单个处理器崩溃影响其他处理器"""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Event handler failed for {event.type}: {e}", exc_info=True)