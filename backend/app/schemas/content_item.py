"""内容项 Schema"""
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.schemas.common import TimestampMixin


class ContentImportFromURL(BaseModel):
    """从 URL 导入"""

    url: str = Field(min_length=1, max_length=500)
    kb_id: str


class ContentImportFromText(BaseModel):
    """从文本导入"""

    text: str = Field(min_length=1)
    title: Optional[str] = Field(None, max_length=500)
    kb_id: str
    summary_style: str = Field("medium", pattern="^(brief|medium|detailed)$")
    template_id: Optional[str] = None


class ContentImportFromImage(BaseModel):
    """从图片导入（OCR）"""

    kb_id: str


class ContentImportFromBrowser(BaseModel):
    """Import content explicitly collected in the user's logged-in browser."""

    kb_id: str
    url: str = Field(min_length=1, max_length=500)
    title: Optional[str] = Field(None, max_length=500)
    text: str = Field("", max_length=200_000)
    page_type: Literal["article", "image", "video"] = "article"
    image_urls: list[str] = Field(default_factory=list, max_length=10)
    has_video: bool = False
    subtitle_text: str = Field("", max_length=200_000)
    video_duration: Optional[float] = Field(None, ge=0, le=86_400)
    captured_at: Optional[str] = Field(None, max_length=100)

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, value: list[str]) -> list[str]:
        if any(len(url) > 2_000 for url in value):
            raise ValueError("图片地址过长")
        return value


class ContentOut(TimestampMixin):
    id: uuid.UUID
    kb_id: uuid.UUID
    source_type: str
    source_url: Optional[str] = None
    title: str
    original_text: str
    distilled_text: Optional[str] = None
    summary: Optional[str] = None
    status: str = "processed"
    extracted_knowledge: Optional[dict] = None
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_json")
    merge_status: str = "active"
    merged_into_id: Optional[uuid.UUID] = None

    @field_serializer("id", "kb_id", "merged_into_id")
    def serialize_uuid(self, v: Optional[uuid.UUID]) -> Optional[str]:
        return str(v) if v is not None else None

    @field_serializer("metadata")
    def serialize_public_metadata(self, value: dict) -> dict:
        """Do not expose worker coordination details through the public API."""
        return {
            key: item
            for key, item in value.items()
            if key not in {"processing_job_id", "processing_error"}
        }

    model_config = {"from_attributes": True}


class ContentWithKnowledgePoints(ContentOut):
    """带知识点的内容详情"""

    extracted_knowledge: Optional[dict] = None


class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    original_text: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = None
    extracted_knowledge: Optional[dict] = None
    metadata: Optional[dict] = None


class ContentProcessRequest(BaseModel):
    summary_style: str = Field("medium", pattern="^(brief|medium|detailed)$")
    template_id: Optional[str] = None


class SimilarContentOut(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    source_type: str
    similarity: float
    created_at: str


class MergeRequest(BaseModel):
    target_id: str
    source_ids: list[str] = Field(min_length=1, max_length=20)


class MergePreviewRequest(MergeRequest):
    pass
