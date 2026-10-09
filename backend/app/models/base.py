"""模型基类与跨库兼容类型

提供统一的主键、时间戳字段，以及 SQLite / PostgreSQL 兼容的类型封装：
- GUID: UUID 主键（PG 用原生 UUID，SQLite 用 CHAR(36)）
- JSONB: JSON 字段（PG 用原生 JSONB，SQLite 用 JSON）
- StringArray: 字符串数组（PG 用 ARRAY(String)，SQLite 用 JSON 存储）
"""
import json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, TypeDecorator, func, types
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GUID(TypeDecorator):
    """跨平台 UUID 类型

    PG 使用原生 UUID，SQLite 使用 CHAR(36)。
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(types.UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSONB(TypeDecorator):
    """跨平台 JSON 类型

    PG 使用原生 JSONB，SQLite 使用 JSON（实际存为 TEXT）。
    """
    impl = types.JSON()
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB as PGJSONB

            return dialect.type_descriptor(PGJSONB())
        return dialect.type_descriptor(types.JSON())


class StringArray(TypeDecorator):
    """跨平台字符串数组类型

    PG 使用 ARRAY(String)，SQLite 用 JSON 存储为 list。
    """
    impl = types.JSON()
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import ARRAY
            return dialect.type_descriptor(ARRAY(String))
        return dialect.type_descriptor(types.JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return list(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        if isinstance(value, str):
            return json.loads(value)
        return list(value)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


class TimestampMixin:
    """创建 / 更新时间戳混入"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKey:
    """UUID 主键混入（使用跨平台 GUID 类型）"""
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
