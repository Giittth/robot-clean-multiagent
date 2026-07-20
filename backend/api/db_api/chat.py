"""
聊天 API（集成 RAG 服务，支持短期/长期记忆、流式响应）
"""
import os
import json
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pymysql.cursors import DictCursor

from backend.config import settings
from backend.db.database import get_db
from backend.db.chat_service import get_user_chat_history, format_chat_history, clear_user_chat_history
from backend.schemas.chat import ChatRequest, ChatResponse, ChatHistoryResponse
from backend.rag.rag_service import RagService
from backend.utils.sse_handler import SSE
from backend.utils.logger_handler import logger
from backend.db.database import get_db_connection
from backend.db.task_service import save_task
from backend.llm.factory import LLMClientFactory
from backend.llm.base import BaseLLMClient
from backend.llm.model_registry import get_model_config, get_default_model_id

# 模型客户端缓存（避免每次请求都重新创建）
_model_client_cache: Dict[str, BaseLLMClient] = {}


def _load_saved_api_keys() -> dict:
    """? JSON ????????? API Keys"""
    from pathlib import Path as _Path
    keys_file = _Path(__file__).parent.parent.parent / "data" / "api_keys.json"
    try:
        if keys_file.exists():
            with open(keys_file, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load API keys: {e}")
    return {}


def _get_llm_client(model_id: str, app_container) -> BaseLLMClient:
    """根据 model_id 获取或创建 LLM 客户端"""
    if not model_id or model_id == "default":
        return app_container.llm_client

    if model_id in _model_client_cache:
        return _model_client_cache[model_id]

    config = get_model_config(model_id)
    if config is None:
        logger.warning(f"Unknown model '{model_id}', falling back to default")
        return app_container.llm_client

    from backend.llm.llm_enums import ProviderType
    provider = config["provider"]
    api_url = config["api_url"]
    # ????????? API Key?????????
    _env_name = config.get("api_key_env")
    if _env_name:
        saved_keys = _load_saved_api_keys()
        api_key = saved_keys.get(_env_name, "") or os.getenv(_env_name, "")
    else:
        api_key = ""

    client_config = {
        "provider": provider.value if hasattr(provider, 'value') else provider,
        "api_url": api_url,
        "api_key": api_key,
        "model": model_id,
        "timeout": 60,
        "max_retries": 2,
        "temperature": 0.1,
        "max_tokens": 4096,
    }

    factory = LLMClientFactory(client_config)
    client = factory.get_client()
    _model_client_cache[model_id] = client
    logger.info(f"Created LLM client for model '{model_id}' (provider: {provider})")
    return client


router = APIRouter(prefix="/chat", tags=["聊天模块（RAG）"])


def _save_chat_task(query: str, answer: str = "", error_info: str = ""):
    """Save chat interaction to task_history table with AI response."""
    try:
        db = get_db_connection()
        try:
            save_task(db, command=query, task_type="chat",
                      result="failed" if error_info else "success",
                      error_info=error_info,
                      answer=answer)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Save chat task failed: {e}")


@router.post("/")
async def chat(
    request: ChatRequest,
    fastapi_request: Request,
    stream: bool = Query(False, description="是否启用流式响应（SSE）"),
    db: DictCursor = Depends(get_db)
):
    """
    发送消息，返回 AI 回答。
    - 非流式：返回 JSON（包含 answer, reference, history）
    - 流式：返回 Server-Sent Events，每块为文本片段，最后发送 [DONE] 标记
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 根据模型选择获取对应的 LLM 客户端
    container = fastapi_request.app.state.container
    llm_client = _get_llm_client(request.model, container)
    rag = RagService(user_id=request.user_id, llm_client=llm_client, kb_id=request.kb_id)

    # 流式响应
    if stream:
        async def event_generator():
            # 收集完整回答（流结束后再保存记忆和历史查询以及 task_history）
            full_answer = ""
            async for chunk in rag.generate_answer_stream(query=request.message):
                if chunk:
                    full_answer += chunk
                    yield SSE.format({"content": chunk})
            # 流结束标记
            yield SSE.format({"done": True})
            # 流结束后保存到 task_history（含 AI 回复）
            _save_chat_task(request.message, answer=full_answer)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # 非流式：完整响应
    result = await rag.generate_answer(query=request.message)
    # 保存到 task_history（含 AI 回复）
    _save_chat_task(request.message, answer=result.get("answer", ""))

    # 获取历史（仅登录用户且提供 kb_id）
    history = []
    if request.user_id > 0 and request.kb_id:
        history_raw = get_user_chat_history(db, request.user_id, request.kb_id, limit=15)
        history = format_chat_history(history_raw)

    return {
        "answer": result["answer"],
        "reference": result["reference"],
        "history": history
    }


# 以下端点不变（获取历史、清空）
@router.get("/history/{user_id}/{kb_id}", response_model=List[ChatHistoryResponse])
def get_chat_history(
    user_id: int,
    kb_id: int,
    limit: int = 15,
    db: DictCursor = Depends(get_db)
):
    if user_id <= 0:
        return []
    history_raw = get_user_chat_history(db, user_id, kb_id, limit)
    return format_chat_history(history_raw)


@router.delete("/clear/{user_id}/{kb_id}")
def clear_chat_history(
    user_id: int,
    kb_id: int,
    db: DictCursor = Depends(get_db)
):
    if user_id <= 0:
        raise HTTPException(status_code=403, detail="游客无法清空历史")
    clear_user_chat_history(db, user_id, kb_id)
    return {"status": "success", "msg": "聊天记录已清空"}
