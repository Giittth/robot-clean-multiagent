"""
    LLM 客户端工厂：根据配置创建和管理不同的 LLM 客户端
    支持单租户和多租户模式，自动缓存实例
"""
from typing import Dict, Optional, Any

from backend.llm.llm_enums import ProviderType
from backend.utils.logger_handler import logger
from backend.llm.base import BaseLLMClient
from backend.llm.mock_client import MockLLMClient
from backend.llm.openai_client import OpenAICompatibleClient
from backend.llm.claude_client import ClaudeClient
from backend.llm.gemini_client import GeminiClient


class LLMClientFactory:
    def __init__(self, default_config: Dict[str, Any]):
        """
        :param default_config: 默认配置，至少包含 provider 字段
            示例:
            {
                "provider": "openai",
                "api_url": "https://api.openai.com/v1/chat/completions",
                "api_key": "sk-xxx",
                "model": "gpt-4",
                "timeout": 30,
                "max_retries": 2,
                "temperature": 0.7,
                "max_tokens": 4096,
            }
        """
        self.default_config = default_config
        self._clients: Dict[str, BaseLLMClient] = {}  # tenant_id -> client
        self._default_client: Optional[BaseLLMClient] = None

    def get_client(self, tenant_id: Optional[str] = None) -> BaseLLMClient:
        """
        获取大模型客户端实例。
        - 如果 tenant_id 为 None，返回默认客户端（基于 default_config 创建）。
        - 如果 tenant_id 不为 None，返回该租户专用的客户端（首次创建并缓存）。
        """
        if tenant_id is None:
            if self._default_client is None:
                self._default_client = self._create_client(self.default_config)
            return self._default_client

        if tenant_id not in self._clients:
            # 从数据库或租户配置中心加载租户专属配置（示例：调用 _load_tenant_config）
            tenant_config = self._load_tenant_config(tenant_id)
            if tenant_config is None:
                # 如果没有租户配置，回退到默认配置
                logger.warning(f"No config for tenant {tenant_id}, using default")
                tenant_config = self.default_config
            self._clients[tenant_id] = self._create_client(tenant_config)
        return self._clients[tenant_id]

    def _create_client(self, config: Dict[str, Any]) -> BaseLLMClient:
        """根据配置字典创建对应的客户端实例"""
        provider = config.get("provider", "mock").lower()
        logger.info(f"Creating LLM client for provider: {provider}")

        if provider == ProviderType.MOCK:
            return MockLLMClient(
                rules=config.get("rules"),
                default_response=config.get("default_response", ""),
                response_delay=config.get("response_delay", 0.0),
                error_rate=config.get("error_rate", 0.0),
            )
        elif provider == ProviderType.OPENAI:
            return OpenAICompatibleClient(
                api_url=config["api_url"],
                api_key=config.get("api_key", ""),
                model=config.get("model", "gpt-4"),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 2),
                max_tokens=config.get("max_tokens", 4096),
                temperature=config.get("temperature", 0.7),
            )
        elif provider == ProviderType.CLAUDE:
            return ClaudeClient(
                api_url=config.get("api_url", "https://api.anthropic.com/v1/messages"),
                api_key=config["api_key"],
                model=config.get("model", "claude-3-sonnet-20240229"),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 2),
                max_tokens=config.get("max_tokens", 4096),
                temperature=config.get("temperature", 0.7),
            )
        elif provider == ProviderType.GEMINI:
            return GeminiClient(
                api_url=config.get("api_url", "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"),
                api_key=config["api_key"],
                model=config.get("model", "gemini-1.5-pro"),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 2),
                temperature=config.get("temperature", 0.7),
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _load_tenant_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        加载租户配置。实际应用中应从数据库或配置中心读取。
        此处提供示例实现（从环境变量或固定映射获取）。
        """
        # 示例：假设有环境变量 TENANT_{tenant_id}_LLM_CONFIG
        import os
        import json
        env_key = f"TENANT_{tenant_id.upper()}_LLM_CONFIG"
        config_str = os.getenv(env_key)
        if config_str:
            try:
                return json.loads(config_str)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON for tenant {tenant_id}: {config_str}")
        # 也可从数据库查询
        # 这里简单返回 None，表示使用默认配置
        return None

    def clear_cache(self, tenant_id: Optional[str] = None):
        """清除缓存，强制下次重新创建"""
        if tenant_id is None:
            self._default_client = None
        else:
            self._clients.pop(tenant_id, None)

    def list_tenants(self) -> list:
        """返回已缓存的租户列表"""
        return list(self._clients.keys())