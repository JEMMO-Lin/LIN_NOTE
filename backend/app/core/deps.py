"""FastAPI 公共依赖

提供当前用户、数据库会话等通用依赖注入。
"""
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthError
from app.core.security import decode_token


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
) -> str:
    """从 Authorization 头解析当前用户 ID

    格式：Bearer <token>
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("缺少认证令牌")
    token = authorization.removeprefix("Bearer ").strip()
    user_id = decode_token(token)
    if user_id is None:
        raise AuthError("无效或过期的令牌")
    return user_id


async def get_current_user_with_db(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """组合依赖：当前用户 + 数据库会话"""
    return {"user_id": user_id, "db": db}
