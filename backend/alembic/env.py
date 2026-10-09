"""Alembic 迁移环境

适配 SQLite 与 PostgreSQL：
- SQLite 使用同步驱动，开启 batch 模式（ALTER TABLE 限制）
- PostgreSQL 使用异步驱动
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models import Base  # 导入所有模型以支持 autogenerate

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_IS_SQLITE = settings.database_url.startswith("sqlite")


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_IS_SQLITE,  # SQLite batch 模式
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=_IS_SQLITE,  # SQLite batch 模式
        user_module_prefix="",  # 自定义类型直接用类名（配合 script.py.mako 的 import）
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    """异步在线模式：PostgreSQL"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online_sync() -> None:
    """同步在线模式：SQLite

    aiosqlite 是异步驱动，同步迁移需切换为内置 sqlite3 驱动。
    """
    from sqlalchemy import create_engine

    url = config.get_main_option("sqlalchemy.url")
    # sqlite+aiosqlite:// → sqlite://
    if "+aiosqlite" in url:
        url = url.replace("+aiosqlite", "")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif _IS_SQLITE:
    run_migrations_online_sync()
else:
    asyncio.run(run_migrations_online_async())
