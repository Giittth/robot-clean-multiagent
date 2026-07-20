"""
WebSocket 服务，负责连接管理、接收客户端消息、广播前端状态。
不包含任何业务逻辑，仅作为传输层。
"""

import asyncio
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from backend.services.websocket.connection_manager import ConnectionManager
from backend.services.state.robot_state_aggregator import RobotStateAggregator
from backend.schemas.websocket_protocol import ClientMessage
from backend.utils.logger_handler import logger
from backend.agents.core.messaging.message_bus import MessageBus
from backend.agents.schemas.messages import MessageType, Message


class RobotWebSocketService:
    def __init__(self, aggregator: RobotStateAggregator, message_bus: MessageBus):
        self.aggregator = aggregator
        self.manager = ConnectionManager()
        self.message_bus = message_bus
        self._running = False
        self._broadcast_task = None
        self.latest_rooms = None
        self._ws_semaphore = asyncio.Semaphore(50)   # 限制并发发送任务数
        # Cache graph_structure, task_node_status, and task_state for reconnecting clients
        self._last_graph_structure: Optional[dict] = None
        self._last_node_status: Optional[dict] = None
        self._last_task_state: Optional[dict] = None

    async def start(self):
        """启动广播循环，并订阅房间更新消息"""
        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        await self.message_bus.subscribe(MessageType.ROOMS_UPDATE, self._on_rooms_update)
        logger.info("RobotWebSocketService started")

    async def stop(self):
        """停止广播，取消订阅，关闭所有连接"""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
        await self.message_bus.unsubscribe(MessageType.ROOMS_UPDATE, self._on_rooms_update)
        for ws in list(self.manager._active):
            await ws.close()
        logger.info("RobotWebSocketService stopped")

    async def register_websocket(self, ws: WebSocket):
        """注册新连接，进入接收循环（处理客户端消息），并保持连接"""
        await self.manager.connect(ws)
        if self.latest_rooms:
            data = {"type": "rooms_update", "payload": self.latest_rooms}
            await self._safe_send(ws, data)   # 改用安全发送方法
        # Replay latest graph_structure and task_node_status for reconnecting clients
        if self._last_graph_structure:
            await self._safe_send(ws, self._last_graph_structure)
        if self._last_node_status:
            await self._safe_send(ws, self._last_node_status)
        if self._last_task_state:
            await self._safe_send(ws, self._last_task_state)
        try:
            while self._running:
                try:
                    raw = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                    await self._handle_client_message(ws, raw)
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    logger.info("WebSocket client disconnected")
                    break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.manager.disconnect(ws)

    async def _handle_client_message(self, ws: WebSocket, raw: str):
        try:
            msg = ClientMessage.parse_raw(raw)
            if msg.type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg.type == "control":
                logger.info(f"Control command: {msg.command}")
            elif msg.type == "subscribe":
                logger.debug(f"Subscribe to {msg.topic}")
        except Exception:
            logger.warning(f"Invalid client message: {raw}")

    async def _broadcast_loop(self):
        """定期获取聚合状态并广播（20Hz）"""
        while self._running:
            await asyncio.sleep(0.05)
            if not self.manager._active:
                continue
            state = self.aggregator.get_frontend_state()
            if state:
                message = {"type": "robot_state", **state}
                await self._broadcast_to_all(message)

    async def _broadcast_to_all(self, data: dict):
        """并发广播到所有客户端，使用信号量限制并发，避免单个慢客户端阻塞"""
        if not self.manager._active:
            return
        tasks = [asyncio.create_task(self._safe_send(ws, data)) for ws in list(self.manager._active)]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, ws: WebSocket, data: dict):
        """带信号量限制的发送，避免并发过高，发送失败时自动断开连接"""
        async with self._ws_semaphore:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.debug(f"WebSocket send error: {e}, disconnecting client")
                # 从活跃集合中移除并关闭连接
                self.manager._active.discard(ws)
                try:
                    await ws.close()
                except:
                    pass

    async def _on_rooms_update(self, msg: Message):
        """当 WorldModelAgent 发布 ROOMS_UPDATE 时，将房间数据广播给所有前端"""
        self.latest_rooms = msg.payload
        data = {"type": "rooms_update", "payload": msg.payload}
        await self._broadcast_to_all(data)
        logger.debug("Broadcast rooms_update to all clients")
    async def on_supervisor_broadcast(self, data: dict):
        """SupervisorAgent broadcast callback.

        Broadcasts to all WebSocket clients AND caches
        graph_structure/task_node_status for reconnecting clients.
        """
        msg_type = data.get("type")
        if msg_type == "graph_structure":
            self._last_graph_structure = data
        elif msg_type == "task_node_status":
            self._last_node_status = data
        elif msg_type == "task_state_changed":
            self._last_task_state = data
        await self._broadcast_to_all(data)
