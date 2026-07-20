from typing import Dict, Optional, List
from datetime import datetime
import asyncio
from backend.utils.logger_handler import logger


class AgentInfo:
    """智能体信息实体"""
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id: str = agent_id
        self.agent_type: str = agent_type
        self.registered_at: datetime = datetime.utcnow()
        self.last_heartbeat: datetime = datetime.utcnow()
        self.status: str = "active"  # active / inactive / dead


class AgentRegistry:
    """智能体注册中心：负责注册、心跳、状态监控、失效清理"""
    def __init__(self, heartbeat_timeout: int = 30):
        self._agents: Dict[str, AgentInfo] = {}
        self._heartbeat_timeout = heartbeat_timeout
        self._lock = asyncio.Lock()  # 修复：并发安全

    def register(self, agent_id: str, agent_type: str) -> None:
        """注册智能体"""
        if agent_id in self._agents:
            logger.warning(f"Agent {agent_id} already registered, updating info")
        self._agents[agent_id] = AgentInfo(agent_id, agent_type)
        logger.info(f"Agent {agent_id} registered successfully")

    def unregister(self, agent_id: str) -> None:
        """注销智能体"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Agent {agent_id} unregistered successfully")

    async def heartbeat(self, agent_id: str) -> None:
        """异步更新心跳（线程安全）"""
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                logger.warning(f"Received heartbeat from unknown agent: {agent_id}")
                return

            agent.last_heartbeat = datetime.utcnow()
            agent.status = "active"

    async def cleanup_stale_agents(self) -> None:
        """定期清理超时智能体（异步安全）"""
        async with self._lock:
            now = datetime.utcnow()
            for aid, agent in self._agents.items():
                delta = (now - agent.last_heartbeat).total_seconds()
                if delta >= self._heartbeat_timeout:
                    agent.status = "dead"
                    logger.warning(
                        f"Agent {aid} is dead. Last heartbeat: {agent.last_heartbeat}"
                    )

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """获取单个智能体信息"""
        return self._agents.get(agent_id)

    def list_all_agents(self) -> List[AgentInfo]:
        """获取所有智能体（含失效）"""
        return list(self._agents.values())

    def list_active_agents(self) -> List[AgentInfo]:
        """获取活跃智能体列表"""
        now = datetime.utcnow()
        return [
            agent for agent in self._agents.values()
            if (now - agent.last_heartbeat).total_seconds() < self._heartbeat_timeout
        ]

    def is_agent_alive(self, agent_id: str) -> bool:
        """快速判断智能体是否存活"""
        agent = self.get_agent(agent_id)
        if not agent:
            return False

        now = datetime.utcnow()
        return (now - agent.last_heartbeat).total_seconds() < self._heartbeat_timeout