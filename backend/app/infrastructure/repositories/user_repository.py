"""用户仓储"""
from typing import Optional

from sqlalchemy import select

from app.infrastructure.repositories.base import BaseRepository
from app.models.user import User


class UserRepository(BaseRepository[User]):
    """用户仓储"""

    model = User

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
