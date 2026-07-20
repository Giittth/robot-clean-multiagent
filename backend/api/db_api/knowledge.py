from fastapi import APIRouter, Depends, HTTPException
from pymysql.cursors import DictCursor
from typing import List

from backend.db.database import get_db
from backend.db.knowledge_service import (
    create_knowledge_base,
    get_kb_by_id,
    get_public_knowledge_base,
    list_user_kb,
    update_kb_info,
    delete_kb,
    create_knowledge_doc,
    get_doc_by_id,
    list_doc_by_kb,
    update_doc_content,
    delete_doc,
    kb_belongs_to_user,
    count_kb_doc,
    is_public_kb_readonly,
)
from backend.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeDocCreate,
    KnowledgeDocResponse
)
from backend.rag.chunk_record import (
    split_and_save_chunks,
    delete_chunks_by_doc_id,
    delete_chunks_by_kb_id
)
from backend.rag.vector.vector_store_new import vector_store



router = APIRouter(prefix="/knowledge", tags=["知识库模块"])


def check_public_kb_write_permission(db, kb_id: int):
    """API 层专用,公共库禁止写入"""
    if is_public_kb_readonly(db, kb_id):
        raise HTTPException(
            status_code=403,
            detail="公共知识库不可编辑、不可删除、不可上传文档"
        )


# 公共知识库（所有人可用）
@router.get("/public", response_model=KnowledgeBaseResponse)
def get_public_kb(db: DictCursor = Depends(get_db)):
    kb = get_public_knowledge_base(db)
    if not kb:
        raise HTTPException(status_code=404, detail="公共知识库不存在")
    return kb


# 个人知识库操作
@router.post("/create", response_model=KnowledgeBaseResponse)
def create_kb(
    kb_in: KnowledgeBaseCreate,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    return create_knowledge_base(db, kb_in.name, kb_in.description, user_id)


@router.get("/list", response_model=List[KnowledgeBaseResponse])
def list_my_kb(
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    return list_user_kb(db, user_id)


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def get_kb_detail(
    kb_id: int,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    kb = get_kb_by_id(db, kb_id, user_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@router.put("/{kb_id}")
def update_kb(
    kb_id: int,
    kb_in: KnowledgeBaseCreate,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    # 权限拦截
    check_public_kb_write_permission(db, kb_id)

    ok = update_kb_info(db, kb_id, kb_in.name, kb_in.description, user_id)
    if not ok:
        raise HTTPException(status_code=400, detail="更新失败")
    return {"msg": "更新成功"}


@router.delete("/{kb_id}")
def delete_kb_api(
    kb_id: int,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    # 权限拦截
    check_public_kb_write_permission(db, kb_id)

    # 自动清空该知识库下所有切片
    delete_chunks_by_kb_id(db, kb_id)

    ok = delete_kb(db, kb_id, user_id)
    if not ok:
        raise HTTPException(status_code=400, detail="删除失败")
    return {"msg": "删除成功"}


# 文档操作（上传/查询/修改/删除）
@router.post("/doc/create", response_model=KnowledgeDocResponse)
def create_doc(
        doc_in: KnowledgeDocCreate,
        user_id: int,
        db: DictCursor = Depends(get_db)
):
    check_public_kb_write_permission(db, doc_in.kb_id)
    if not kb_belongs_to_user(db, doc_in.kb_id, user_id):
        raise HTTPException(403, "无权限")

    # 创建文档（存入文档表）
    doc_id = create_knowledge_doc(
        db,
        kb_id=doc_in.kb_id,
        title=doc_in.title,
        content=doc_in.content,
        user_id=user_id,
        meta=doc_in.meta
    )

    # 切分文档 → 存入切片表
    chunks = split_and_save_chunks(
        db=db,
        kb_id=doc_in.kb_id,
        doc_id=doc_id,
        user_id=user_id,
        content=doc_in.content
    )
    # 存入向量库
    vector_store.add_chunks(chunks)

    return get_doc_by_id(db, doc_id, user_id)


@router.get("/{kb_id}/docs", response_model=List[KnowledgeDocResponse])
def list_kb_docs(
    kb_id: int,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    if not kb_belongs_to_user(db, kb_id, user_id):
        raise HTTPException(status_code=403, detail="无权限")
    return list_doc_by_kb(db, kb_id, user_id)


@router.get("/doc/{doc_id}", response_model=KnowledgeDocResponse)
def get_doc_detail(
    doc_id: int,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    doc = get_doc_by_id(db, doc_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.put("/doc/{doc_id}")
def update_doc(
    doc_id: int,
    doc_in: KnowledgeDocCreate,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    doc = get_doc_by_id(db, doc_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 权限检查
    check_public_kb_write_permission(db, doc.kb_id)

    # 删除旧切片
    delete_chunks_by_doc_id(db, doc_id)

    # 删除旧向量
    vector_store.delete_by_doc_id(doc_id)

    # 更新数据库里的文档内容
    ok = update_doc_content(
        db,
        doc_id=doc_id,
        title=doc_in.title,
        content=doc_in.content,
        meta=doc_in.meta,
        user_id=user_id
    )
    if not ok:
        raise HTTPException(status_code=400, detail="更新失败")

    # 重新切片 → 存入新切片
    chunks = split_and_save_chunks(
        db=db,
        kb_id=doc.kb_id,
        doc_id=doc_id,
        user_id=user_id,
        content=doc_in.content
    )

    # 加入新向量
    vector_store.add_chunks(chunks)

    return {"msg": "更新成功"}


@router.delete("/doc/{doc_id}")
def delete_doc_api(
    doc_id: int,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    doc = get_doc_by_id(db, doc_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    check_public_kb_write_permission(db, doc.kb_id)

    # 自动删除该文档的所有切片
    delete_chunks_by_doc_id(db, doc_id)

    # 删除向量
    vector_store.delete_by_doc_id(doc_id)

    ok = delete_doc(db, doc_id, user_id)
    if not ok:
        raise HTTPException(status_code=400, detail="删除失败")
    return {"msg": "删除成功"}


# 统计
@router.get("/{kb_id}/count")
def count_doc(
    kb_id: int,
    user_id: int,
    db: DictCursor = Depends(get_db)
):
    total = count_kb_doc(db, kb_id, user_id)
    return {"total": total}
