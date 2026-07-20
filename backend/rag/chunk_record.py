from typing import List
from backend.models.db_model.knowledge import DocumentChunkDB
from backend.utils.rag_utils import split_text_to_chunks




# 核心：切片存入 MySQL
def split_and_save_chunks(
    db,
    kb_id: int,       # 必须来自知识库表
    doc_id: int,      # 必须来自文档表
    user_id: int,
    content: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[DocumentChunkDB]:
    """
    上传文档后的标准流程：
    1. 切分文本
    2. 批量存入切片表
    3. 返回切片列表
    """
    chunk_text_list = split_text_to_chunks(content, chunk_size, chunk_overlap)
    return save_chunk_batch(db, kb_id, doc_id, user_id, chunk_text_list)



def save_chunk_batch(
    db,
    kb_id: int,
    doc_id: int,
    user_id: int,
    content_list: List[str]
) -> List[DocumentChunkDB]:
    sql = """
    INSERT INTO document_chunks (kb_id, doc_id, user_id, content)
    VALUES (%s, %s, %s, %s)
    """
    with db.cursor() as cur:
        for content in content_list:
            cur.execute(sql, (kb_id, doc_id, user_id, content))
        db.commit()
    return get_chunks_by_doc_id(db, doc_id)


# 查询
def get_chunks_by_doc_id(db, doc_id: int) -> List[DocumentChunkDB]:
    sql = """
    SELECT id, kb_id, doc_id, user_id, content, create_time
    FROM document_chunks
    WHERE doc_id = %s
    ORDER BY id ASC
    """
    with db.cursor() as cur:
        cur.execute(sql, (doc_id,))
        rows = cur.fetchall()
    return [DocumentChunkDB(**row) for row in rows]


def get_chunks_by_kb_id(db, kb_id: int) -> List[DocumentChunkDB]:
    sql = """
    SELECT id, kb_id, doc_id, user_id, content, create_time
    FROM document_chunks
    WHERE kb_id = %s
    """
    with db.cursor() as cur:
        cur.execute(sql, (kb_id,))
        rows = cur.fetchall()
    return [DocumentChunkDB(**row) for row in rows]


# 删除
def delete_chunks_by_doc_id(db, doc_id: int) -> bool:
    sql = "DELETE FROM document_chunks WHERE doc_id = %s"
    with db.cursor() as cur:
        cur.execute(sql, (doc_id,))
        db.commit()
    return True


def delete_chunks_by_kb_id(db, kb_id: int) -> bool:
    sql = "DELETE FROM document_chunks WHERE kb_id = %s"
    with db.cursor() as cur:
        cur.execute(sql, (kb_id,))
        db.commit()
    return True