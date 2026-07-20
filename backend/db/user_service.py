import bcrypt
from backend.models.db_model.user import UserDB
from typing import Optional



# 密码处理函数
def hash_password(password: str) -> str:
    """生成密码哈希"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# 用户管理函数
def create_user(db, username: str, password: str):
    """创建用户（密码自动哈希）"""
    hashed_pw = hash_password(password)
    try:
        with db.cursor() as cur:
            sql = "INSERT INTO users (username, password) VALUES (%s, %s)"
            cur.execute(sql, (username, hashed_pw))
        db.commit()
    except Exception:
        db.rollback()
        raise

def get_user_by_username(db, username: str) -> Optional[UserDB]:
    with db.cursor() as cur:
        sql = "SELECT id, username, password, create_time FROM users WHERE username = %s"
        cur.execute(sql, (username,))
        user_data = cur.fetchone()
        if user_data:
            return UserDB(**user_data)
        return None

def get_user_by_id(db, user_id: int) -> Optional[UserDB]:
    with db.cursor() as cur:
        sql = "SELECT id, username, password, create_time FROM users WHERE id = %s"
        cur.execute(sql, (user_id,))
        user_data = cur.fetchone()
        if user_data:
            return UserDB(**user_data)
        return None

