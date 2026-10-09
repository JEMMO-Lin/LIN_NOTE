"""知识库 Schema"""
from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field, field_serializer

from app.schemas.common import TimestampMixin


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: list[str] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[list[str]] = None
    settings: Optional[dict] = None


class KnowledgeBaseOut(TimestampMixin):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)

    @field_serializer("id", "user_id")
    def serialize_uuid(self, v: uuid.UUID) -> str:
        return str(v)

    model_config = {"from_attributes": True}


class KBStats(BaseModel):
    """知识库统计信息"""

    kb_id: uuid.UUID
    content_count: int = 0
    knowledge_point_count: int = 0
    last_updated: Optional[datetime] = None

    @field_serializer("kb_id")
    def serialize_kb_id(self, v: uuid.UUID) -> str:
        return str(v)
