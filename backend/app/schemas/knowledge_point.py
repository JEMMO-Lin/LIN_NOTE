"""知识点 Schema"""
from typing import Optional
import uuid

from pydantic import BaseModel, Field, field_serializer

from app.schemas.common import TimestampMixin


class KnowledgePointOut(TimestampMixin):
    id: uuid.UUID
    content_id: uuid.UUID
    kb_id: uuid.UUID
    title: str
    content: str
    importance: float = 0.5
    category: Optional[str] = None
    related_points: list[str] = Field(default_factory=list)

    @field_serializer("id", "content_id", "kb_id")
    def serialize_uuid(self, v: uuid.UUID) -> str:
        return str(v)

    model_config = {"from_attributes": True}


class KnowledgePointUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    importance: Optional[float] = Field(None, ge=0, le=1)
    category: Optional[str] = Field(None, max_length=100)
    related_points: Optional[list[str]] = None


class SearchResult(BaseModel):
    """检索结果项"""

    point_id: str
    title: str
    content: str
    score: float
    content_id: Optional[str] = None
    kb_id: Optional[str] = None


class SearchQuery(BaseModel):
    """检索请求"""

    query: str = Field(min_length=1)
    kb_id: Optional[str] = None
    mode: str = Field("hybrid", pattern="^(vector|keyword|hybrid)$")
    top_k: int = Field(10, ge=1, le=50)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    kb_id: Optional[str] = None
    top_k: int = Field(8, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    sources: list[SearchResult] = Field(default_factory=list)
    answer_source: str = Field("rag", pattern="^(rag|wiki)$")
    wiki_hit: bool = False
    ask_count: int = 0
    wiki_entry_id: Optional[str] = None
    wiki_created: bool = False


class KnowledgeTreeNode(BaseModel):
    id: str
    label: str
    category: Optional[str] = None
    importance: float = 0.5
    content_id: Optional[str] = None


class KnowledgeTreeEdge(BaseModel):
    source: str
    target: str
    relation: str = "related"


class KnowledgeTreeOut(BaseModel):
    nodes: list[KnowledgeTreeNode] = Field(default_factory=list)
    edges: list[KnowledgeTreeEdge] = Field(default_factory=list)
