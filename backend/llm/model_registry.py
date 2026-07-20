"""
    模型注册表：定义所有可用的 LLM 模型及其配置。
    分类：local（本地 Ollama）、free（免费云端）、paid（付费 API）
"""

import os
from typing import Dict, Any, Optional

from backend.config import settings
from backend.llm.llm_enums import ProviderType


# ---------------------------------------------------------------------------
# 模型定义
# 每条记录包含：
#   provider    - 对应 LLM 客户端类型（openai / claude / gemini）
#   label       - 前端显示名称
#   api_url     - API 端点
#   api_key_env - 从环境变量读取 API Key 的名称，None 表示不需要 Key
#   category    - local / free / paid（前端分组）
#   is_default  - 是否为默认模型（仅一个）
#   description - 简短说明
# ---------------------------------------------------------------------------


MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {

    # ===== 本地模型 (Ollama) =====
    "default": {
        "provider": ProviderType.OPENAI,
        "label": "Qwen3:8B (本地 Ollama)",
        "api_url": f"{settings.base_url}/v1/chat/completions",
        "api_key_env": None,
        "category": "local",
        "is_default": True,
        "description": "本地部署的 Qwen3:8B，无需 API Key",
    },
    "qwen2.5:7b": {
        "provider": ProviderType.OPENAI,
        "label": "Qwen2.5:7B (本地 Ollama)",
        "api_url": f"{settings.base_url}/v1/chat/completions",
        "api_key_env": None,
        "category": "local",
        "is_default": False,
        "description": "本地部署的 Qwen2.5:7B，轻量级选择",
    },
    "llama3.1:8b": {
        "provider": ProviderType.OPENAI,
        "label": "Llama 3.1:8B (本地 Ollama)",
        "api_url": f"{settings.base_url}/v1/chat/completions",
        "api_key_env": None,
        "category": "local",
        "is_default": False,
        "description": "本地部署的 Llama 3.1:8B，Meta 开源模型",
    },
    "glm4:9b": {
        "provider": ProviderType.OPENAI,
        "label": "GLM-4:9B (本地 Ollama)",
        "api_url": f"{settings.base_url}/v1/chat/completions",
        "api_key_env": None,
        "category": "local",
        "is_default": False,
        "description": "本地部署的 GLM-4:9B，智谱开源模型",
    },

    # ===== 免费 / 开源云端模型 =====
    "gemini-2.0-flash": {
        "provider": ProviderType.GEMINI,
        "label": "Gemini 2.0 Flash (Google)",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "api_key_env": "GEMINI_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "Google Gemini 2.0 Flash，速度快，免费额度充足",
    },
    "gemini-1.5-flash": {
        "provider": ProviderType.GEMINI,
        "label": "Gemini 1.5 Flash (Google)",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "api_key_env": "GEMINI_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "Google Gemini 1.5 Flash，兼容性好，免费额度高",
    },
    "gemini-2.5-flash": {
        "provider": ProviderType.GEMINI,
        "label": "Gemini 2.5 Flash (Google)",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "api_key_env": "GEMINI_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "Google Gemini 2.5 Flash，最新快速模型",
    },
    "gemini-2.5-pro": {
        "provider": ProviderType.GEMINI,
        "label": "Gemini 2.5 Pro (Google，有免费额度)",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "api_key_env": "GEMINI_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "Google Gemini 2.5 Pro，最强推理模型免费版",
    },
    "glm-4-flash": {
        "provider": ProviderType.OPENAI,
        "label": "GLM-4-Flash (智谱)",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "GLM_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "智谱 GLM-4-Flash，国内可用，免费调用",
    },
    "qwen-turbo-latest": {
        "provider": ProviderType.OPENAI,
        "label": "Qwen Turbo (阿里通义)",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_env": "QWEN_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "阿里通义千问 Turbo，有免费额度，速度快",
    },
    "qwen-plus": {
        "provider": ProviderType.OPENAI,
        "label": "Qwen Plus (阿里通义，有免费额度)",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_env": "QWEN_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "阿里通义千问 Plus，更强的长文本能力",
    },
    "deepseek-chat": {
        "provider": ProviderType.OPENAI,
        "label": "DeepSeek V3 (免费额度)",
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "api_key_env": "DEEPSEEK_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "DeepSeek V3，性价比极高，新用户有免费额度",
    },
    "doubao-lite-32k": {
        "provider": ProviderType.OPENAI,
        "label": "豆包 Lite 32K (字节跳动，免费额度)",
        "api_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "api_key_env": "ARK_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "字节跳动豆包 Lite，32K 上下文，有免费额度",
    },
    "doubao-lite-128k": {
        "provider": ProviderType.OPENAI,
        "label": "豆包 Lite 128K (字节跳动，免费额度)",
        "api_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "api_key_env": "ARK_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "字节跳动豆包 Lite，128K 超长上下文",
    },
    "ernie-speed": {
        "provider": ProviderType.OPENAI,
        "label": "ERNIE Speed (百度文心，免费额度)",
        "api_url": "https://qianfan.baidubce.com/v2/chat/completions",
        "api_key_env": "BAIDU_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "百度文心一言 ERNIE Speed，有免费额度",
    },
    "hunyuan-lite": {
        "provider": ProviderType.OPENAI,
        "label": "混元 Lite (腾讯，免费额度)",
        "api_url": "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
        "api_key_env": "HUNYUAN_API_KEY",
        "category": "free",
        "is_default": False,
        "description": "腾讯混元 Lite，有免费额度",
    },

    # ===== 付费 API 模型 =====
    "gpt-4.1": {
        "provider": ProviderType.OPENAI,
        "label": "GPT-4.1 (OpenAI 最新)",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "OpenAI 最新 GPT-4.1，综合能力最强",
    },
    "gpt-4.1-mini": {
        "provider": ProviderType.OPENAI,
        "label": "GPT-4.1 Mini (OpenAI)",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "OpenAI 轻量模型，高性价比",
    },
    "gpt-4.1-nano": {
        "provider": ProviderType.OPENAI,
        "label": "GPT-4.1 Nano (OpenAI)",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "OpenAI 最小最快模型",
    },
    "gpt-4o": {
        "provider": ProviderType.OPENAI,
        "label": "GPT-4o (OpenAI)",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "OpenAI 旗舰模型，综合能力强",
    },
    "gpt-4o-mini": {
        "provider": ProviderType.OPENAI,
        "label": "GPT-4o-mini (OpenAI)",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "OpenAI 4o mini，轻量级性价比高",
    },
    "o3-mini": {
        "provider": ProviderType.OPENAI,
        "label": "o3-mini (OpenAI)",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "OpenAI o3-mini，推理能力增强版",
    },
    "o4-mini": {
        "provider": ProviderType.OPENAI,
        "label": "o4-mini (OpenAI 最新推理)",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "OpenAI 最新推理模型 o4-mini",
    },
    "claude-3-opus-20240229": {
        "provider": ProviderType.CLAUDE,
        "label": "Claude 3 Opus (Anthropic)",
        "api_url": "https://api.anthropic.com/v1/messages",
        "api_key_env": "ANTHROPIC_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "Anthropic Claude 3 Opus，最强推理能力",
    },
    "claude-3-5-sonnet-20241022": {
        "provider": ProviderType.CLAUDE,
        "label": "Claude 3.5 Sonnet (Anthropic)",
        "api_url": "https://api.anthropic.com/v1/messages",
        "api_key_env": "ANTHROPIC_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "Anthropic Claude 3.5 Sonnet，编程首选",
    },
    "claude-3-5-haiku-20241022": {
        "provider": ProviderType.CLAUDE,
        "label": "Claude 3.5 Haiku (Anthropic 快速)",
        "api_url": "https://api.anthropic.com/v1/messages",
        "api_key_env": "ANTHROPIC_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "Anthropic Claude 3.5 Haiku，速度最快最便宜",
    },
    "claude-sonnet-4-20250514": {
        "provider": ProviderType.CLAUDE,
        "label": "Claude Sonnet 4 (Anthropic 最新)",
        "api_url": "https://api.anthropic.com/v1/messages",
        "api_key_env": "ANTHROPIC_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "Anthropic Claude Sonnet 4，最新旗舰",
    },
    "claude-3-haiku-20240307": {
        "provider": ProviderType.CLAUDE,
        "label": "Claude 3 Haiku (Anthropic)",
        "api_url": "https://api.anthropic.com/v1/messages",
        "api_key_env": "ANTHROPIC_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "Anthropic Claude 3 Haiku，旧版快速模型",
    },
    "deepseek-reasoner": {
        "provider": ProviderType.OPENAI,
        "label": "DeepSeek R1 (DeepSeek 推理)",
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "api_key_env": "DEEPSEEK_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "DeepSeek R1 推理模型，擅长复杂推理",
    },
    "qwen-max": {
        "provider": ProviderType.OPENAI,
        "label": "Qwen Max (阿里通义)",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_env": "QWEN_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "阿里通义千问 Max，旗舰模型",
    },
    "qwen-max-plus": {
        "provider": ProviderType.OPENAI,
        "label": "Qwen Max+ (阿里通义旗舰)",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_env": "QWEN_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "阿里通义千问 Max Plus，顶尖性能",
    },
    "glm-4-plus": {
        "provider": ProviderType.OPENAI,
        "label": "GLM-4-Plus (智谱)",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "GLM_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "智谱 GLM-4-Plus，综合能力强",
    },
    "glm-4-air": {
        "provider": ProviderType.OPENAI,
        "label": "GLM-4-Air (智谱轻量)",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "GLM_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "智谱 GLM-4-Air，高性价比轻量版",
    },
    "doubao-pro-32k": {
        "provider": ProviderType.OPENAI,
        "label": "豆包 Pro 32K (字节跳动)",
        "api_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "api_key_env": "ARK_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "字节跳动豆包 Pro，32K 上下文",
    },
    "doubao-pro-128k": {
        "provider": ProviderType.OPENAI,
        "label": "豆包 Pro 128K (字节跳动)",
        "api_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "api_key_env": "ARK_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "字节跳动豆包 Pro，128K 超长上下文",
    },
    "ernie-4-5": {
        "provider": ProviderType.OPENAI,
        "label": "ERNIE 4.5 (百度文心旗舰)",
        "api_url": "https://qianfan.baidubce.com/v2/chat/completions",
        "api_key_env": "BAIDU_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "百度文心一言 ERNIE 4.5，旗舰版",
    },
    "hunyuan-pro": {
        "provider": ProviderType.OPENAI,
        "label": "混元 Pro (腾讯)",
        "api_url": "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
        "api_key_env": "HUNYUAN_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "腾讯混元 Pro，主力模型",
    },
    "moonshot-v1-8k": {
        "provider": ProviderType.OPENAI,
        "label": "Moonshot v1 8K (月之暗面)",
        "api_url": "https://api.moonshot.cn/v1/chat/completions",
        "api_key_env": "MOONSHOT_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "月之暗面 Moonshot v1，8K 上下文",
    },
    "moonshot-v1-32k": {
        "provider": ProviderType.OPENAI,
        "label": "Moonshot v1 32K (月之暗面)",
        "api_url": "https://api.moonshot.cn/v1/chat/completions",
        "api_key_env": "MOONSHOT_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "月之暗面 Moonshot v1，32K 长上下文",
    },
    "yi-lightning": {
        "provider": ProviderType.OPENAI,
        "label": "Yi-Lightning (零一万物)",
        "api_url": "https://api.lingyiwanwu.com/v1/chat/completions",
        "api_key_env": "YI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "零一万物 Yi-Lightning，高性价比",
    },
    "minimax-text-01": {
        "provider": ProviderType.OPENAI,
        "label": "MiniMax-Text-01 (MiniMax)",
        "api_url": "https://api.minimax.chat/v1/chat/completions",
        "api_key_env": "MINIMAX_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "MiniMax Text-01，国产长上下文模型",
    },
    "baichuan-4": {
        "provider": ProviderType.OPENAI,
        "label": "Baichuan 4 (百川智能)",
        "api_url": "https://api.baichuan-ai.com/v1/chat/completions",
        "api_key_env": "BAICHUAN_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "百川智能 Baichuan 4，国产新秀",
    },
    "mistral-large-latest": {
        "provider": ProviderType.OPENAI,
        "label": "Mistral Large (Mistral AI)",
        "api_url": "https://api.mistral.ai/v1/chat/completions",
        "api_key_env": "MISTRAL_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "Mistral Large，欧洲领先的开源大模型",
    },
    "grok-2": {
        "provider": ProviderType.OPENAI,
        "label": "Grok 2 (xAI)",
        "api_url": "https://api.x.ai/v1/chat/completions",
        "api_key_env": "XAI_API_KEY",
        "category": "paid",
        "is_default": False,
        "description": "xAI Grok 2，马斯克旗下 AI",
    },

}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def get_model_config(model_id: str) -> Optional[Dict[str, Any]]:
    """按 model_id 获取模型配置"""
    return MODEL_REGISTRY.get(model_id)


def get_default_model_id() -> str:
    """获取默认模型 ID"""
    for mid, cfg in MODEL_REGISTRY.items():
        if cfg.get("is_default"):
            return mid
    return "default"


def get_available_models() -> Dict[str, Dict[str, Any]]:
    """
    只检查环境变量，前端不宜直接使用。
    请使用 get_all_models_with_availability() 代替。
    """
    result = {}
    for mid, cfg in MODEL_REGISTRY.items():
        if cfg["category"] == "local":
            result[mid] = _strip_internal(cfg)
            continue
        env_key = cfg.get("api_key_env")
        if env_key and os.getenv(env_key):
            result[mid] = _strip_internal(cfg)
        elif not env_key:
            result[mid] = _strip_internal(cfg)
    return result


def _strip_internal(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """去掉内部字段，只返回前端所需的信息"""
    return {
        "id": cfg.get("id", ""),
        "provider": cfg["provider"].value if hasattr(cfg["provider"], "value") else cfg["provider"],
        "label": cfg["label"],
        "category": cfg["category"],
        "is_default": cfg["is_default"],
        "description": cfg.get("description", ""),
        "api_key_env": cfg.get("api_key_env"),
    }


def get_all_models_with_availability(saved_api_keys=None):
    """
    返回所有模型及其可用状态。
    - local 模型始终 available=True
    - free / paid 模型检查环境变量或已保存的 API Key
    saved_api_keys: 从 api_keys.json 加载的 { env_var: key_value } 字典
    """
    if saved_api_keys is None:
        saved_api_keys = {}
    result = {}
    for mid, cfg in MODEL_REGISTRY.items():
        info = _strip_internal(cfg)
        if cfg["category"] == "local":
            info["available"] = True
        else:
            env_key = cfg.get("api_key_env")
            if not env_key:
                info["available"] = True
            else:
                env_key_available = bool(os.getenv(env_key))
                if not env_key_available:
                    env_key_available = bool(saved_api_keys.get(env_key))
                info["available"] = env_key_available
        result[mid] = info
    return result


def _inject_ids():
    """注入 model_id 到每条配置中"""
    for mid, cfg in MODEL_REGISTRY.items():
        cfg["id"] = mid


_inject_ids()
