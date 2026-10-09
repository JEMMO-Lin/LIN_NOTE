"""数据库连接与会话管理

基于 SQLAlchemy 2.x 异步引擎，提供 AsyncSession 工厂与 FastAPI 依赖注入。
SQLite 与 PostgreSQL 自动适配连接参数。
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _build_engine():
    """根据数据库类型构建异步引擎"""
    kwargs = {"echo": settings.db_echo, "future": True}
    # SQLite 不支持连接池参数
    if not settings.database_url.startswith("sqlite"):
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
    else:
        # SQLite 需开启外键约束
        from sqlalchemy import event

        engine = create_async_engine(settings.database_url, **kwargs)

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_fk(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine
    return create_async_engine(settings.database_url, **kwargs)


# 异步引擎
engine = _build_engine()

# 异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供数据库会话，自动提交与回滚"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
