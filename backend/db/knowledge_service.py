import json
from typing import Optional, List, Dict
from backend.utils.logger_handler import logger
from backend.models.db_model.knowledge import KnowledgeBaseDB, KnowledgeDocDB


# 知识库基础操作
def create_knowledge_base(
    db,
    name: str,
    description: Optional[str],
    user_id: int,
    is_public: int = 0
) -> KnowledgeBaseDB:
    """创建知识库（支持公共/私有）"""
    sql = """
    INSERT INTO knowledge_base (name, description, user_id, is_public)
    VALUES (%s, %s, %s, %s)
    """
    cursor = db.cursor()
    cursor.execute(sql, (name, description, user_id, is_public))
    db.commit()

    kb = KnowledgeBaseDB(
        id=cursor.lastrowid,
        name=name,
        description=description,
        user_id=user_id,
        is_public=is_public,
        create_time=None,
        update_time=None
    )
    logger.info(f"知识库创建成功：{name}，用户ID：{user_id}")
    return kb


def get_kb_by_id(db, kb_id: int, user_id: int) -> Optional[KnowledgeBaseDB]:
    """根据ID获取单个知识库（校验所属用户）"""
    sql = """
    SELECT id, name, description, user_id, is_public, create_time, update_time
    FROM knowledge_base
    WHERE id = %s AND user_id = %s
    """
    with db.cursor() as cur:
        cur.execute(sql, (kb_id, user_id))
        data = cur.fetchone()
        return KnowledgeBaseDB(**data) if data else None


def get_kb_by_id_no_auth(db, kb_id: int) -> Optional[KnowledgeBaseDB]:
    sql = """
    SELECT id, name, description, user_id, is_public, create_time, update_time
    FROM knowledge_base
    WHERE id = %s
    """
    with db.cursor() as cur:
        cur.execute(sql, (kb_id,))
        data = cur.fetchone()
        return KnowledgeBaseDB(**data) if data else None



def get_public_knowledge_base(db) -> Optional[KnowledgeBaseDB]:
    """获取系统公共知识库"""
    sql = """
    SELECT id, name, description, user_id, is_public, create_time, update_time
    FROM knowledge_base
    WHERE is_public = 1
    LIMIT 1
    """
    with db.cursor() as cur:
        cur.execute(sql)
        data = cur.fetchone()
        return KnowledgeBaseDB(**data) if data else None


def list_user_kb(db, user_id: int) -> List[KnowledgeBaseDB]:
    """获取当前用户所有私有知识库"""
    sql = """
    SELECT id, name, description, is_public, create_time, update_time
    FROM knowledge_base
    WHERE user_id = %s
    ORDER BY create_time DESC
    """
    with db.cursor() as cur:
        cur.execute(sql, (user_id,))
        data_list = cur.fetchall()
        return [KnowledgeBaseDB(**d) for d in data_list]


def update_kb_info(db, kb_id: int, name: str, description: Optional[str], user_id: int) -> bool:
    sql = """
    UPDATE knowledge_base
    SET name = %s, description = %s
    WHERE id = %s AND user_id = %s
    """
    with db.cursor() as cur:
        cur.execute(sql, (name, description, kb_id, user_id))
        db.commit()
        return cur.rowcount > 0


def delete_kb(db, kb_id: int, user_id: int) -> bool:
    sql = """
    DELETE FROM knowledge_base
    WHERE id = %s AND user_id = %s
    """
    with db.cursor() as cur:
        cur.execute(sql, (kb_id, user_id))
        db.commit()
        return cur.rowcount > 0


# 知识库文档操作
def create_knowledge_doc(
    db,
    kb_id: int,
    title: str,
    content: str,
    user_id: int,
    meta: Optional[Dict] = None
) -> int:
    sql = """
    INSERT INTO knowledge_doc (kb_id, title, content, meta, user_id)
    VALUES (%s, %s, %s, %s, %s)
    """
    meta_json = json.dumps(meta, ensure_ascii=False) if meta else None
    with db.cursor() as cur:
        cur.execute(sql, (kb_id, title, content, meta_json, user_id))
        db.commit()
        return cur.lastrowid


def get_doc_by_id(db, doc_id: int, user_id: int) -> Optional[KnowledgeDocDB]:
    sql = """
    SELECT id, kb_id, title, content, meta, create_time, update_time
    FROM knowledge_doc
    WHERE id = %s AND user_id = %s
    """
    with db.cursor() as cur:
        cur.execute(sql, (doc_id, user_id))
        data = cur.fetchone()
        return KnowledgeDocDB(**data) if data else None


def get_doc_content_only(db, doc_id: int) -> Optional[str]:
    """RAG专用：只获取文档内容（不校验用户）"""
    sql = "SELECT content FROM knowledge_doc WHERE id = %s"
    with db.cursor() as cur:
        cur.execute(sql, (doc_id,))
        res = cur.fetchone()
        return res["content"] if res else None


def list_doc_by_kb(db, kb_id: int, user_id: int) -> List[KnowledgeDocDB]:
    sql = """
    SELECT id, kb_id, title, create_time, update_time
    FROM knowledge_doc
    WHERE kb_id = %s AND user_id = %s
    ORDER BY create_time DESC
    """
    with db.cursor() as cur:
        cur.execute(sql, (kb_id, user_id))
        data_list = cur.fetchall()
        return [KnowledgeDocDB(**d) for d in data_list]


def get_all_docs_by_kb(db, kb_id: int) -> List[KnowledgeDocDB]:
    """RAG专用：获取知识库下所有文档（用于检索）"""
    sql = "SELECT id, kb_id, title, content, user_id, meta, create_time, update_time FROM knowledge_doc WHERE kb_id = %s"
    with db.cursor() as cur:
        cur.execute(sql, (kb_id,))
        data_list = cur.fetchall()
        return [KnowledgeDocDB(**d) for d in data_list]


def update_doc_content(
    db,
    doc_id: int,
    title: str,
    content: str,
    meta: Optional[Dict],
    user_id: int
) -> bool:
    sql = """
    UPDATE knowledge_doc
    SET title = %s, content = %s, meta = %s
    WHERE id = %s AND user_id = %s
    """
    meta_json = json.dumps(meta, ensure_ascii=False) if meta else None
    with db.cursor() as cur:
        cur.execute(sql, (title, content, meta_json, doc_id, user_id))
        db.commit()
        return cur.rowcount > 0


def delete_doc(db, doc_id: int, user_id: int) -> bool:
    sql = "DELETE FROM knowledge_doc WHERE id = %s AND user_id = %s"
    with db.cursor() as cur:
        cur.execute(sql, (doc_id, user_id))
        db.commit()
        return cur.rowcount > 0


# 扩展实用方法
def search_user_knowledge(db, user_id: int, keyword: str, kb_id: Optional[int] = None) -> List[KnowledgeDocDB]:
    like_key = f"%{keyword}%"
    if kb_id:
        sql = """
        SELECT id, kb_id, title, content
        FROM knowledge_doc
        WHERE user_id = %s AND kb_id = %s
        AND (title LIKE %s OR content LIKE %s)
        """
        params = (user_id, kb_id, like_key, like_key)
    else:
        sql = """
        SELECT id, kb_id, title, content
        FROM knowledge_doc
        WHERE user_id = %s
        AND (title LIKE %s OR content LIKE %s)
        """
        params = (user_id, like_key, like_key)

    with db.cursor() as cur:
        cur.execute(sql, params)
        data_list = cur.fetchall()
        return [KnowledgeDocDB(**d) for d in data_list]


def count_kb_doc(db, kb_id: int, user_id: int) -> int:
    sql = """
    SELECT COUNT(*) AS total
    FROM knowledge_doc
    WHERE kb_id = %s AND user_id = %s
    """
    with db.cursor() as cur:
        cur.execute(sql, (kb_id, user_id))
        res = cur.fetchone()
        return res["total"] if res else 0

def kb_belongs_to_user(db, kb_id: int, user_id: int) -> bool:
    sql = "SELECT 1 FROM knowledge_base WHERE id = %s AND user_id = %s"
    with db.cursor() as cur:
        cur.execute(sql, (kb_id, user_id))
        return cur.fetchone() is not None


# 权限判断（公共知识库保护）
def is_kb_public(db, kb_id: int) -> bool:
    """判断是否为公共知识库"""
    sql = "SELECT is_public FROM knowledge_base WHERE id = %s"
    with db.cursor() as cur:
        cur.execute(sql, (kb_id,))
        res = cur.fetchone()
    return res and res["is_public"] == 1


def is_public_kb_readonly(db, kb_id: int) -> bool:
    """
    公共知识库 = 只读
    如果返回 True → 不能编辑、不能删除、不能上传
    """
    return is_kb_public(db, kb_id)