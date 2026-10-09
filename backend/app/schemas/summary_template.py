"""总结模板 Schema。"""
from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field, field_serializer, field_validator


class TemplateField(BaseModel):
    name: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    label: str = Field(min_length=1, max_length=50)
    required: bool = True
    max_length: Optional[int] = Field(None, ge=20, le=5000)


class SummaryTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    fields: list[TemplateField] = Field(min_length=1, max_length=12)
    default_style: str = Field("medium", pattern="^(brief|medium|detailed)$")
    is_default: bool = False

    @field_validator("fields")
    @classmethod
    def unique_field_names(cls, value: list[TemplateField]):
        names = [field.name for field in value]
        if len(names) != len(set(names)):
            raise ValueError("模板字段名称不能重复")
        return value


class SummaryTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    fields: Optional[list[TemplateField]] = Field(None, min_length=1, max_length=12)
    default_style: Optional[str] = Field(None, pattern="^(brief|medium|detailed)$")
    is_default: Optional[bool] = None


class SummaryTemplateOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
    fields: list[TemplateField]
    default_style: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "user_id")
    def serialize_uuid(self, value: uuid.UUID) -> str:
        return str(value)

    model_config = {"from_attributes": True}
