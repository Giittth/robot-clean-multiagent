from fastapi import APIRouter, Depends, HTTPException
from backend.rag.long_term_memory import LongTermMemory

router = APIRouter(prefix="/memory", tags=["长期记忆管理"])


@router.get("/{user_id}")
async def list_memories(user_id: int):
    if user_id <= 0:
        raise HTTPException(status_code=403, detail="游客无长期记忆")
    ltm = LongTermMemory(user_id)
    memories = await ltm.alist_memories()   # 直接调用异步方法
    return memories


@router.delete("/{user_id}/{memory_id}")
async def delete_memory(user_id: int, memory_id: str):
    if user_id <= 0:
        raise HTTPException(status_code=403, detail="游客无长期记忆")
    ltm = LongTermMemory(user_id)
    success = await ltm.adelete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="记忆不存在或删除失败")
    return {"status": "deleted"}


@router.delete("/{user_id}")
async def clear_all_memories(user_id: int):
    if user_id <= 0:
        raise HTTPException(status_code=403, detail="游客无长期记忆")
    ltm = LongTermMemory(user_id)
    success = await ltm.aclear_all_memories()
    if not success:
        raise HTTPException(status_code=500, detail="清空失败")
    return {"status": "cleared"}