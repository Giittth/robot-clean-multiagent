from enum import Enum

class ProviderType(str, Enum):
    """大模型提供商类型"""
    OPENAI = "openai"      # 兼容 OpenAI 格式（包括本地 Ollama、国产模型等）
    CLAUDE = "claude"      # Anthropic Claude
    GEMINI = "gemini"      # Google Gemini
    MOCK = "mock"          # 模拟客户端（测试用）
    ADAPTER = "adapter"    # 通用适配器（通过自定义函数接入）