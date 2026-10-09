"""通用 Schema：统一响应、分页结果"""
from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseBase(BaseModel):
    """统一响应包装"""

    code: str = "OK"
    message: str = "success"


class DataResponse(ResponseBase, Generic[T]):
    """带数据的统一响应"""

    data: Optional[T] = None


class PaginatedResponse(ResponseBase, Generic[T]):
    """分页响应"""

    data: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.page_size else 0


class PageParams(BaseModel):
    """分页查询参数"""

    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class TimestampMixin(BaseModel):
    """时间戳响应混入"""

    created_at: datetime
    updated_at: datetime
