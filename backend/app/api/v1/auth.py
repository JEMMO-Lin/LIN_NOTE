"""认证路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AuthError
from app.core.security import create_access_token, hash_password, verify_password
from app.infrastructure.repositories.user_repository import UserRepository
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserOut, UserRegister, UserUpdate
from app.schemas.common import DataResponse

router = APIRouter()


@router.post("/register", response_model=DataResponse[UserOut])
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    repo = UserRepository(db)
    if await repo.get_by_email(payload.email):
        raise AuthError("邮箱已注册")
    if await repo.get_by_username(payload.username):
        raise AuthError("用户名已存在")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    await repo.add(user)
    return DataResponse(data=UserOut.model_validate(user))


@router.post("/login", response_model=DataResponse[TokenResponse])
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    repo = UserRepository(db)
    user = await repo.get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthError("邮箱或密码错误")
    if not user.is_active:
        raise AuthError("账户已被禁用")

    token = create_access_token(subject=str(user.id))
    return DataResponse(
        data=TokenResponse(access_token=token, expires_in=86400)
    )


@router.get("/me", response_model=DataResponse[UserOut])
async def get_me(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise AuthError("用户不存在")
    return DataResponse(data=UserOut.model_validate(user))


@router.patch("/me", response_model=DataResponse[UserOut])
async def update_me(
    payload: UserUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    user = await db.get(User, user_id)
    if user is None:
        raise AuthError("用户不存在")
    data = payload.model_dump(exclude_unset=True)
    if "username" in data and data["username"] != user.username:
        if await repo.get_by_username(data["username"]):
            raise AuthError("用户名已存在")
    for key, value in data.items():
        setattr(user, key, value)
    await db.flush()
    return DataResponse(data=UserOut.model_validate(user))
