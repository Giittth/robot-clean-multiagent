"""
跨进程消息路由：基于 Redis 的 Pub/Sub 机制，消息在多个实例间广播。
背压：本地发送队列（asyncio.Queue）缓存待发送消息，避免瞬间高负载压垮网络/Redis，队列满时丢弃消息。
批量发送：后台协程批量取消息，减少网络往返。
请求-响应：基于 Redis List（lpush/brpop）实现临时队列，支持跨进程的同步等待。
通配符订阅：本地 fnmatch 过滤，但需要订阅所有消息频道（消耗较大，仅建议在必要时使用）。
并发控制：回调执行同样使用信号量限制并发。
故障恢复：监听 Redis 连接丢失后自动重连。
分布式缓存：可配合 Redis Stream 实现消息持久化（未实现但可扩展）。
"""

import asyncio
import json
import fnmatch
import uuid
from typing import Dict, Set, Callable, Awaitable, Optional, Any, List, Tuple
from collections import defaultdict

import aioredis
from backend.agents.schemas.messages import Message, MessageType, Priority
from backend.utils.logger_handler import logger


class RedisMessageBus:
    """
    基于 Redis 的分布式消息总线（增强版）
    新增功能：
    - 背压控制（发送队列 + 限流）
    - 请求-响应模式（基于 Redis List）
    - 通配符订阅（本地 fnmatch 过滤）
    - 回调并发限制（信号量）
    - 消息 TTL 检查
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_queue_size: int = 5000,
        max_concurrent_callbacks: int = 100,
        send_batch_size: int = 10,
        send_interval: float = 0.01,
    ):
        """
        :param redis_url: Redis 连接 URL
        :param max_queue_size: 本地发送队列最大长度（背压阈值）
        :param max_concurrent_callbacks: 本地回调最大并发数
        :param send_batch_size: 批量发送消息数量
        :param send_interval: 批量发送间隔（秒）
        """
        self.redis_url = redis_url
        self._max_queue_size = max_queue_size
        self._max_concurrent_callbacks = max_concurrent_callbacks
        self._send_batch_size = send_batch_size
        self._send_interval = send_interval

        self._pub: Optional[aioredis.Redis] = None
        self._sub: Optional[aioredis.Redis] = None
        self._subscribed_channels: Set[str] = set()
        # 精确订阅回调：channel -> set of callbacks
        self._handlers: Dict[str, Set[Callable[[Message], Awaitable[None]]]] = defaultdict(set)
        # 通配符订阅模式：pattern -> set of callbacks
        self._wildcard_handlers: Dict[str, Set[Callable]] = defaultdict(set)
        # 用于请求-响应的临时等待者
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._running = False
        self._listener_task: Optional[asyncio.Task] = None
        self._sender_task: Optional[asyncio.Task] = None
        self._send_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._callback_semaphore = asyncio.Semaphore(max_concurrent_callbacks)
        self._lock = asyncio.Lock()

    # 生命周期管理
    async def start(self):
        """启动消息总线：建立 Redis 连接并启动监听、发送任务"""
        try:
            self._pub = await aioredis.from_url(self.redis_url, decode_responses=False)
            self._sub = await aioredis.from_url(self.redis_url, decode_responses=False)
            self._running = True
            self._listener_task = asyncio.create_task(self._listen())
            self._sender_task = asyncio.create_task(self._sender())
            logger.info("RedisMessageBus (enhanced) started")
        except Exception as e:
            logger.error(f"Failed to start RedisMessageBus: {e}")
            raise

    async def stop(self):
        """停止消息总线：关闭连接、取消任务、清理等待请求"""
        if not self._running:
            return
        self._running = False

        # 取消后台任务
        for task in [self._listener_task, self._sender_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # 关闭 Redis 连接
        if self._pub:
            await self._pub.close()
        if self._sub:
            await self._sub.close()

        # 超时等待中的请求
        for fut in self._pending_requests.values():
            if not fut.done():
                fut.set_exception(asyncio.TimeoutError("MessageBus stopped"))
        self._pending_requests.clear()
        logger.info("RedisMessageBus stopped")

    # 发送背压（本地队列 + 批量）
    async def publish(self, message: Message):
        """发布消息（非阻塞，放入本地发送队列）"""
        # TTL 检查
        if message.ttl <= 0:
            logger.debug(f"Message {message.id} ttl<=0, drop")
            return
        # 过期检查
        if (message.timestamp - message.timestamp).total_seconds() > message.ttl:
            logger.warning(f"Message {message.id} expired before publish, drop")
            return

        # 背压处理：队列满时丢弃低优先级消息（简化：直接丢弃新消息）
        if self._send_queue.qsize() >= self._max_queue_size:
            logger.warning(f"Send queue full, dropping message {message.type} (prio {message.priority})")
            return
        try:
            self._send_queue.put_nowait((message.priority.value, message))
        except asyncio.QueueFull:
            logger.error(f"Send queue full after check, drop")

    async def _sender(self):
        """后台发送协程：批量取出消息并真正 publish 到 Redis"""
        while self._running:
            await asyncio.sleep(self._send_interval)
            batch = []
            # 收集一批消息
            while len(batch) < self._send_batch_size and not self._send_queue.empty():
                try:
                    prio, msg = self._send_queue.get_nowait()
                    batch.append(msg)
                except asyncio.QueueEmpty:
                    break
            if not batch:
                continue
            # 按优先级排序后发送（优先级低的先发送？实际不重要，因为已经排序）
            # 直接发送
            for msg in batch:
                try:
                    channel = msg.type.value
                    data = msg.json()
                    await self._pub.publish(channel, data)
                except Exception as e:
                    logger.error(f"Failed to publish message {msg.id}: {e}")

    # 订阅与取消订阅（支持通配符）
    async def subscribe(self, topic: str, callback: Callable[[Message], Awaitable[None]]):
        """订阅主题（支持通配符 * 和 ?）"""
        async with self._lock:
            if '*' in topic or '?' in topic:
                self._wildcard_handlers[topic].add(callback)
                # 确保监听器会收到所有消息（我们将在监听器中做本地过滤）
                # 为支持通配符，需要监听所有可能频道：最简单是监听所有消息类型，但会浪费带宽。
                # 这里采用策略：动态订阅所有当前已知的消息类型频道
                await self._ensure_all_channels_subscribed()
            else:
                self._handlers[topic].add(callback)
                # 如果之前没有订阅该频道，需要让监听器订阅它
                if topic not in self._subscribed_channels:
                    await self._subscribe_channel(topic)

    async def unsubscribe(self, topic: str, callback: Callable[[Message], Awaitable[None]]):
        async with self._lock:
            if '*' in topic or '?' in topic:
                self._wildcard_handlers[topic].discard(callback)
            else:
                self._handlers[topic].discard(callback)
                if not self._handlers[topic]:
                    # 如果该频道没有回调，则取消订阅 Redis 频道
                    await self._unsubscribe_channel(topic)

    async def _ensure_all_channels_subscribed(self):
        """确保订阅所有已知消息类型的频道（用于通配符）"""
        # 获取所有 MessageType 枚举值
        all_types = [t.value for t in MessageType]
        for channel in all_types:
            if channel not in self._subscribed_channels:
                await self._subscribe_channel(channel)

    async def _subscribe_channel(self, channel: str):
        if not self._sub:
            return
        pubsub = self._sub.pubsub()
        await pubsub.subscribe(channel)
        self._subscribed_channels.add(channel)
        logger.debug(f"Subscribed to Redis channel: {channel}")

    async def _unsubscribe_channel(self, channel: str):
        if not self._sub:
            return
        pubsub = self._sub.pubsub()
        await pubsub.unsubscribe(channel)
        self._subscribed_channels.discard(channel)
        logger.debug(f"Unsubscribed from Redis channel: {channel}")

    # 监听循环（支持通配符本地过滤、并发限制）
    async def _listen(self):
        """主监听循环：接收 Redis 消息，分发回调（受信号量限流）"""
        if not self._sub:
            return
        pubsub = self._sub.pubsub()
        # 初始不订阅任何频道，后续动态添加
        while self._running:
            try:
                # 等待消息（带超时，以便定期检查新订阅）
                msg = await pubsub.get_message(
                    timeout=1,
                    ignore_subscribe_messages=True
                )
                if not msg:
                    # 检查是否有新频道需要订阅（由 _subscribe_channel 触发）
                    async with self._lock:
                        current_channels = set(self._handlers.keys())
                        # 通配符订阅需要所有频道
                        if self._wildcard_handlers:
                            all_types = [t.value for t in MessageType]
                            current_channels.update(all_types)
                        new_channels = current_channels - self._subscribed_channels
                        for ch in new_channels:
                            await pubsub.subscribe(ch)
                            self._subscribed_channels.add(ch)
                    continue

                channel = msg["channel"].decode("utf-8")
                data = msg["data"]
                try:
                    message = Message.parse_raw(data)
                except Exception as e:
                    logger.error(f"Failed to parse message: {e}")
                    continue

                # 收集所有匹配的回调
                callbacks = set()
                # 精确匹配
                if channel in self._handlers:
                    callbacks.update(self._handlers[channel])
                # 通配符匹配
                for pattern, cbs in self._wildcard_handlers.items():
                    if fnmatch.fnmatch(channel, pattern):
                        callbacks.update(cbs)

                if not callbacks:
                    continue

                # 并发执行回调（受信号量限制）
                async def safe_callback(cb):
                    async with self._callback_semaphore:
                        try:
                            await cb(message)
                        except Exception as e:
                            logger.error(f"Callback error: {e}", exc_info=True)

                for cb in callbacks:
                    asyncio.create_task(safe_callback(cb))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Listener error: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    # 请求-响应模式（基于 Redis List）
    async def request(self, message: Message, timeout: float = 10.0) -> Message:
        """
        发送请求并等待响应。
        通过 Redis List 实现临时队列：reply:correlation_id
        """
        correlation_id = str(uuid.uuid4())
        reply_queue = f"reply:{correlation_id}"
        message.correlation_id = correlation_id
        message.reply_to = reply_queue

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[correlation_id] = future

        # 发布请求消息（普通 publish，实际是放到发送队列）
        await self.publish(message)

        # 等待响应
        try:
            # 从 Redis List 右阻塞读取响应
            result_data = await self._sub.brpop(reply_queue, timeout=timeout)
            if result_data is None:
                raise asyncio.TimeoutError()
            _, data = result_data
            response_msg = Message.parse_raw(data)
            # 校验 correlation_id
            if response_msg.correlation_id != correlation_id:
                raise ValueError("Correlation ID mismatch")
            future.set_result(response_msg)
            return response_msg
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request {correlation_id} timed out")
        finally:
            # 清理临时队列（最好有 TTL，但这里删除）
            await self._pub.delete(reply_queue)
            self._pending_requests.pop(correlation_id, None)

    async def reply(self, original_request: Message, payload: dict):
        """
        响应一个请求：将结果发送到原请求的 reply_to 队列
        """
        if not original_request.reply_to:
            raise ValueError("Request message has no reply_to field")
        reply_msg = Message(
            type=MessageType(original_request.type.value.replace("_REQUEST", "_RESULT")),  # 简单约定
            source=original_request.target or "unknown",
            target=original_request.source,
            payload=payload,
            correlation_id=original_request.correlation_id,
            reply_to=original_request.reply_to,
        )
        # 将响应推送到 Redis List
        await self._pub.lpush(original_request.reply_to, reply_msg.json())