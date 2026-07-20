"""
    模型信息 API：返回可用的大模型列表 + API Key 管理
"""
import json
import os
from pathlib import Path
from fastapi import APIRouter
from backend.llm.model_registry import get_available_models, get_default_model_id, get_all_models_with_availability, MODEL_REGISTRY
from backend.utils.logger_handler import logger


router = APIRouter(tags=["models"])

_KEYS_FILE = Path(__file__).parent.parent.parent / "data" / "api_keys.json"


def _load_api_keys() -> dict:
    try:
        if _KEYS_FILE.exists():
            with open(_KEYS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load API keys: {e}")
    return {}


def _save_api_keys(keys: dict):
    _KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_api_keys()
    existing.update(keys)
    with open(_KEYS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


@router.get("/")
async def list_models():
    saved_keys = _load_api_keys()
    models = get_all_models_with_availability(saved_keys)
    default_id = get_default_model_id()
    return {
        "models": list(models.values()),
        "default_model_id": default_id,
    }


@router.get("/keys/status")
async def get_api_key_status():
    """返回哪些 API Key 已配置（不暴露 key 值本身）"""
    saved = _load_api_keys()
    env_keys = set()
    for cfg in MODEL_REGISTRY.values():
        env = cfg.get("api_key_env")
        if env:
            env_keys.add(env)
    result = {}
    for env_var in sorted(env_keys):
        has_key = bool(os.getenv(env_var)) or bool(saved.get(env_var))
        result[env_var] = has_key
    return {"status": result, "configured_providers": [k for k, v in result.items() if v]}


@router.post("/keys")
async def save_api_keys(keys: dict):
    """保存用户提交的 API Keys"""
    _save_api_keys(keys)
    logger.info(f"Saved API keys for: {list(keys.keys())}")
    return {"status": "ok", "saved_keys": list(keys.keys())}
