"""认证相关 Schema"""
from pydantic import BaseModel, EmailStr, Field, field_serializer
from typing import Optional
import uuid


class UserRegister(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: EmailStr
    avatar: Optional[str] = None
    settings: dict = Field(default_factory=dict)

    @field_serializer("id")
    def serialize_id(self, v: uuid.UUID) -> str:
        return str(v)

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=50)
    avatar: Optional[str] = Field(None, max_length=500)
    settings: Optional[dict] = None
