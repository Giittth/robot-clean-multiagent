from fastapi import APIRouter, Depends, HTTPException
from pymysql.cursors import DictCursor

from backend.db.database import get_db
from backend.db.user_service import create_user, get_user_by_username, get_user_by_id, verify_password
from backend.db.chat_service import get_user_chat_history, clear_user_chat_history, format_chat_history
from backend.schemas.user import UserCreate, UserResponse
from backend.schemas.chat import ChatHistoryResponse


router = APIRouter(prefix="/users", tags=["用户模块"])


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: DictCursor = Depends(get_db)):
    exists = get_user_by_username(db, user.username)
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    create_user(db, user.username, user.password)
    new_user = get_user_by_username(db, user.username)
    return new_user


@router.post("/login")
def login(user: UserCreate, db: DictCursor = Depends(get_db)):
    db_user = get_user_by_username(db, user.username)
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"msg": "登录成功", "user_id": db_user.id}

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: DictCursor = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.get("/{user_id}/chat_history", response_model=list[ChatHistoryResponse])
def get_history(
    user_id: int,
    kb_id: int,          # 必填，不再默认为 None
    limit: int = 10,
    db: DictCursor = Depends(get_db)
):
    rows = get_user_chat_history(db, user_id, kb_id, limit)
    return format_chat_history(rows)   # rows 是 List[ChatHistoryDB]，格式兼容


@router.delete("/{user_id}/chat_history")
def clear_history(
    user_id: int,
    kb_id: int,          # 必填
    db: DictCursor = Depends(get_db)
):
    clear_user_chat_history(db, user_id, kb_id)
    return {"msg": "清空成功"}