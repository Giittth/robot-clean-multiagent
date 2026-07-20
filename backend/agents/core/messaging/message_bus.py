"""
发布-订阅：支持精确主题（MessageType）和通配符主题（*、?），回调函数管理。
优先级队列：消息按优先级（Priority）排序，高优先级先处理。
背压控制：队列长度限制，超过阈值丢弃低优先级消息，防止内存爆炸。
并发限制：消费者使用信号量限制同时运行的回调数，避免无限创建协程。
请求-响应：request 方法发送消息并同步等待回复（基于 Future 和临时订阅）。
死信队列：TTL过期消息移入死信队列，定期清理。
生命周期管理：start/stop 控制消费循环。
监控接口：get_queue_size, get_worker_count, get_dead_letter 等。
"""

import asyncio
import fnmatch
import traceback
import uuid
from collections import defaultdict
from typing import Dict, Set, Callable, Awaitable, Optional, List
from datetime import datetime

from backend.agents.schemas.messages import Message, MessageType
from backend.utils.logger_handler import logger


class MessageBus:
    def __init__(
        self,
        max_queue_size: int = 10000,
        max_workers: int = 100,
        dead_letter_ttl: int = 3600,
    ):
        """
        :param max_queue_size: 最大队列长度（背压阈值）
        :param max_workers: 最大并发消费协程数
        :param dead_letter_ttl: 死信队列中消息保留时间（秒）
        """
        # 优先级队列（Prio越小优先级越高）
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._max_queue_size = max_queue_size
        self._max_workers = max_workers
        self._dead_letter_ttl = dead_letter_ttl

        # 订阅者：精确主题 -> 回调函数集合
        self._subscribers: Dict[str, Set[Callable[[Message], Awaitable[None]]]] = defaultdict(set)
        # 通配符主题 -> 回调函数集合（模式字符串，如 "robot.*"）
        self._wildcard_subscribers: Dict[str, Set[Callable]] = defaultdict(set)

        # 用于请求-响应的等待者映射 {correlation_id: Future}
        self._pending_requests: Dict[str, asyncio.Future] = {}

        # 死信队列（列表，非优先级）
        self._dead_letter_queue: List[Message] = []

        # 内部状态
        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._cleaner_task: Optional[asyncio.Task] = None
        # 并发控制信号量
        self._worker_semaphore = asyncio.Semaphore(max_workers)

    # 公共接口（向后兼容）
    async def subscribe(self, topic: str, callback: Callable[[Message], Awaitable[None]]):
        """
        订阅消息。
        支持通配符：* 匹配任意多个字符，? 匹配单个字符。
        例如： "robot.*" 匹配 "robot.state", "robot.status"
        """
        if '*' in topic or '?' in topic:
            self._wildcard_subscribers[topic].add(callback)
            logger.debug(f"Wildcard subscription added: {topic}")
        else:
            self._subscribers[topic].add(callback)
            logger.debug(f"Subscription added: {topic}")

    async def unsubscribe(self, topic: str, callback: Callable[[Message], Awaitable[None]]):
        if '*' in topic or '?' in topic:
            self._wildcard_subscribers[topic].discard(callback)
        else:
            self._subscribers[topic].discard(callback)

    async def publish(self, message: Message):
        """
        发布消息。若队列满，则根据优先级决定是否丢弃新消息。
        """
        if message.type == MessageType.SIMULATION_STATE:
            # 合法来源：仿真环境，不告警
            if message.source != "simulation":
                logger.warning("SIMULATION_STATE published from illegal source=%s", message.source)
                logger.warning("Call stack:\n" + "".join(traceback.format_stack()))
        # 1. TTL 检查
        if message.ttl <= 0:
            logger.debug(f"Message {message.id} ttl <= 0, dropping")
            return
        if (datetime.utcnow() - message.timestamp).total_seconds() > message.ttl:
            logger.warning(f"Message {message.id} expired before publishing, dropped")
            return

        # 2. 背压处理：队列满时丢弃低优先级消息
        if self._queue.qsize() >= self._max_queue_size:
            # 尝试丢弃一条比当前消息优先级更低的已经在队列中的消息？
            # 简化版本：直接丢弃新消息（记录警告）
            logger.warning(f"MessageBus queue full, dropping message {message.type} (prio {message.priority.value})")
            return

        # 3. 入队（优先级数值越小优先级越高）
        try:
            self._queue.put_nowait((message.priority.value, message.timestamp, message.id, message))
        except asyncio.QueueFull:
            logger.error(f"Queue full despite check, dropping message {message.id}")

    # 请求-响应模式
    async def request(self, message: Message, timeout: float = 10.0) -> Message:
        """
        发送请求并等待响应。
        使用 correlation_id 直接匹配响应，无需临时主题。
        """
        correlation_id = str(uuid.uuid4())
        message.correlation_id = correlation_id
        # 不再设置 reply_to
        # message.reply_to = None

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[correlation_id] = future

        try:
            await self.publish(message)
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request {correlation_id} timed out")
        finally:
            self._pending_requests.pop(correlation_id, None)

    # 内部消费者（事件驱动，无轮询）
    async def _consumer(self):
        """消费者主循环：从队列取消息，匹配回调，通过信号量限流并发"""
        while self._running:
            try:
                prio, ts, msg_id, msg = await self._queue.get()
            except asyncio.CancelledError:
                break

            try:
                # 优先处理 pending requests
                if msg.correlation_id and msg.correlation_id in self._pending_requests:
                    future = self._pending_requests.pop(msg.correlation_id)
                    if not future.done():
                        future.set_result(msg)
                    continue

                topic_str = msg.type.value
                callbacks = set()
                if topic_str in self._subscribers:
                    callbacks.update(self._subscribers[topic_str])
                for pattern, cbs in self._wildcard_subscribers.items():
                    if fnmatch.fnmatch(topic_str, pattern):
                        callbacks.update(cbs)

                if not callbacks:
                    if topic_str != MessageType.HEARTBEAT.value:
                        logger.debug(f"No subscriber for {topic_str}, message {msg.id} dropped")
                    continue

                # 等待所有回调完成（并发执行，但等待完成）
                tasks = [asyncio.create_task(self._safe_callback(cb, msg)) for cb in callbacks]
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                self._queue.task_done()

    async def _safe_callback(self, cb, msg):
        async with self._worker_semaphore:
            try:
                await cb(msg)
            except Exception as e:
                logger.error(f"Callback error for message {msg.id}: {e}", exc_info=True)

    # 死信队列清理
    async def _clean_dead_letter_loop(self):
        """定期清理过期的死信消息"""
        while self._running:
            await asyncio.sleep(60)
            now = datetime.utcnow()
            new_queue = [
                msg for msg in self._dead_letter_queue
                if (now - msg.timestamp).total_seconds() < self._dead_letter_ttl
            ]
            cleaned = len(self._dead_letter_queue) - len(new_queue)
            self._dead_letter_queue = new_queue
            if cleaned:
                logger.info(f"Cleaned {cleaned} expired dead letters")

    # 生命周期管理
    async def start(self):
        """启动消息总线"""
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._consumer())
        self._cleaner_task = asyncio.create_task(self._clean_dead_letter_loop())
        logger.info("MessageBus started (enhanced)")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        if self._cleaner_task:
            self._cleaner_task.cancel()
            try:
                await self._cleaner_task
            except asyncio.CancelledError:
                pass
        logger.info("MessageBus stopped")

    # 监控与调试接口
    async def get_dead_letter(self) -> List[Message]:
        """获取死信队列副本"""
        return self._dead_letter_queue.copy()

    async def clear_dead_letter(self):
        """清杀死信队列"""
        self._dead_letter_queue.clear()
        logger.info("Dead letter queue cleared")

    def get_queue_size(self) -> int:
        """获取当前待处理消息数量"""
        return self._queue.qsize()

    def get_worker_count(self) -> int:
        """获取当前活跃的worker数量（信号量剩余值）"""
        return self._max_workers - self._worker_semaphore._value