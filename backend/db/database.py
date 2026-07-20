import os
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# 所有表的结构定义
TABLE_SCHEMAS = {
    # 用户表
    "users": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "username VARCHAR(50) NOT NULL UNIQUE",
            "password VARCHAR(255) NOT NULL",
            "create_time DATETIME DEFAULT CURRENT_TIMESTAMP"
        ],
        "indexes": []
    },

    "chat_history": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "user_id INT NOT NULL",
            "kb_id INT NOT NULL",
            "user_msg TEXT NOT NULL",
            "ai_msg TEXT NOT NULL",
            "create_time DATETIME DEFAULT CURRENT_TIMESTAMP"
        ],
        "indexes": [
            "INDEX idx_user_kb_time (user_id, kb_id, create_time)"   # 复合索引
        ]
    },

    # 知识库表（顶层：公共/私有）
    "knowledge_base": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "name VARCHAR(100) NOT NULL",
            "description TEXT NULL",
            "user_id INT NOT NULL",
            "is_public TINYINT DEFAULT 0",  # 0=私有 1=公共（你要的关键字段！）
            "create_time DATETIME DEFAULT CURRENT_TIMESTAMP",
            "update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        ],
        "indexes": [
            "INDEX idx_user_id (user_id)",
            "INDEX idx_is_public (is_public)"
        ]
    },

    # 文档表（中间层）
    "knowledge_doc": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "kb_id INT NOT NULL",
            "title VARCHAR(255) NOT NULL",
            "content TEXT NOT NULL",
            "meta JSON NULL",
            "user_id INT NOT NULL",
            "create_time DATETIME DEFAULT CURRENT_TIMESTAMP",
            "update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        ],
        "indexes": [
            "INDEX idx_kb_id (kb_id)",
            "INDEX idx_user_id (user_id)"
        ]
    },

    # 文档切片表（底层：RAG检索用）
    "document_chunks": {
        "columns": [
            "id VARCHAR(255) PRIMARY KEY",
            "kb_id INT NOT NULL",
            "document_id INT NOT NULL",
            "file_name VARCHAR(255) NOT NULL",
            "chunk_metadata JSON NULL",
            "hash VARCHAR(255) NOT NULL"
        ],
        "indexes": [
            "INDEX idx_kb (kb_id)",
            "INDEX idx_document_id (document_id)",
            "INDEX idx_hash (hash)"
        ]
    }
,
    "task_history": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "user_id INT NOT NULL DEFAULT 0",
            "command VARCHAR(500) NOT NULL",
            "task_type VARCHAR(50)",
            "result VARCHAR(20)",
            "room VARCHAR(100)",
            "error_info TEXT",
            "answer TEXT",
            "started_at DATETIME",
            "finished_at DATETIME",
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ],
        "indexes": [
            "INDEX idx_user_result (user_id, result)",
            "INDEX idx_created (created_at)"
        ]
    },
    # ── Mission History (P0) ──
    "mission_history": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "user_id INT NOT NULL DEFAULT 0",
            "command VARCHAR(500) NOT NULL",
            "graph_id VARCHAR(64)",
            "session_id VARCHAR(64)",
            "status VARCHAR(20) NOT NULL DEFAULT 'running'",
            "duration FLOAT DEFAULT 0",
            "coverage_percent FLOAT DEFAULT 0",
            "error_info TEXT",
            "started_at DATETIME",
            "finished_at DATETIME",
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ],
        "indexes": [
            "INDEX idx_user (user_id)",
            "INDEX idx_created (created_at)"
        ]
    },
    # ── Mission Task Nodes (P1) ──
    "mission_task_nodes": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "mission_id INT NOT NULL",
            "task_id VARCHAR(64) NOT NULL",
            "task_type VARCHAR(50) NOT NULL",
            "status VARCHAR(20) NOT NULL DEFAULT 'pending'",
            "error_info TEXT",
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ],
        "indexes": [
            "INDEX idx_mission (mission_id)"
        ]
    },
    # ── Mission Replay (P2) ──
    "mission_replay": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "mission_id INT NOT NULL",
            "x FLOAT NOT NULL",
            "y FLOAT NOT NULL",
            "theta FLOAT DEFAULT 0",
            "coverage_percent FLOAT DEFAULT 0",
            "recorded_at DATETIME NOT NULL"
        ],
        "indexes": [
            "INDEX idx_mission_time (mission_id, recorded_at)"
        ]
    },
    "schedules": {
        "columns": [
            "id INT PRIMARY KEY AUTO_INCREMENT",
            "user_id INT NOT NULL DEFAULT 0",
            "command VARCHAR(500) NOT NULL",
            "cron_expression VARCHAR(100) NOT NULL",
            "description VARCHAR(200)",
            "enabled TINYINT DEFAULT 1",
            "next_run DATETIME",
            "last_run DATETIME",
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ],
        "indexes": [
            "INDEX idx_enabled_next (enabled, next_run)"
        ]
    }}


# 数据库连接配置
def get_db_config():
    return {
        "host": os.getenv("DB_HOST"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "cursorclass": DictCursor,
        "autocommit": True,
        "charset": "utf8mb4"
    }

def get_db_connection():
    return pymysql.connect(**get_db_config())


# 自动同步表结构（不存在创建，有新增字段自动更新）
def sync_tables():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for table_name, schema in TABLE_SCHEMAS.items():
                cols = schema["columns"]
                indexes = schema["indexes"]

                # 检查表是否存在
                cur.execute("SHOW TABLES LIKE %s", (table_name,))
                exists = cur.fetchone()

                if not exists:
                    # 自动创建表
                    col_sql = ", ".join(cols)
                    idx_sql = ", ".join(indexes) if indexes else ""
                    total_parts = [col_sql]
                    if idx_sql:
                        total_parts.append(idx_sql)
                    full_sql = f"CREATE TABLE {table_name} ({', '.join(total_parts)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
                    cur.execute(full_sql)
                    print(f"表已创建: {table_name}")
                else:
                    # 自动新增字段
                    cur.execute(f"DESCRIBE {table_name}")
                    existing_cols = {row["Field"] for row in cur.fetchall()}

                    for col_def in cols:
                        col_name = col_def.split(" ")[0]
                        if col_name not in existing_cols:
                            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_def}")
                            print(f"表 {table_name} 新增字段: {col_name}")
                    print(f"表已同步: {table_name}")

        print("\n所有表结构自动同步完成！")
    finally:
        conn.close()


# 初始化入口
def init_db_tables():
    sync_tables()


# FastAPI 依赖注入
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()