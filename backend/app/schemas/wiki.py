"""Schemas for LLM Wiki management."""
from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field, field_serializer

from app.schemas.knowledge_point import SearchResult


class WikiEntryOut(BaseModel):
    id: uuid.UUID
    kb_id: Optional[uuid.UUID] = None
    question: str
    answer: Optional[str] = None
    sources: list[SearchResult] = Field(default_factory=list)
    ask_count: int
    is_published: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "kb_id")
    def serialize_uuid(self, value: uuid.UUID | None) -> str | None:
        return str(value) if value is not None else None

    model_config = {"from_attributes": True}


class WikiEntryUpdate(BaseModel):
    question: Optional[str] = Field(None, min_length=1, max_length=1000)
    answer: Optional[str] = Field(None, min_length=1)
    is_published: Optional[bool] = None
