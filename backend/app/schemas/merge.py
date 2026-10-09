"""内容合并 Schema。"""
from datetime import datetime
import uuid

from pydantic import BaseModel, Field, field_serializer


class MergePreviewOut(BaseModel):
    target_id: str
    source_ids: list[str]
    merged_title: str
    merged_summary: str
    merged_text: str
    conflicts: list[dict] = Field(default_factory=list)


class MergeHistoryOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    kb_id: uuid.UUID
    target_id: uuid.UUID
    source_ids: list[str]
    source_titles: list[str]
    merged_result_id: uuid.UUID
    strategy: str
    summary: str | None = None
    conflicts: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "user_id", "kb_id", "target_id", "merged_result_id")
    def serialize_uuid(self, value: uuid.UUID) -> str:
        return str(value)

    model_config = {"from_attributes": True}
