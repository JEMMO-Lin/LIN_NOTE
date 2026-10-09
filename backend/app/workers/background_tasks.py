"""后台任务处理器

FastAPI BackgroundTasks 在请求结束后执行，此时请求级别的 db session 已关闭。
本模块提供独立的 db session 管理，确保后台任务能正常访问数据库。
"""
import asyncio
import logging
import sys
from typing import Optional

from sqlalchemy import update

from app.core.database import async_session_factory
from app.infrastructure.llm.prompt_manager import get_prompt_manager
from app.infrastructure.llm.router import get_llm_router
from app.infrastructure.parsers.factory import get_parser_factory
from app.models.content_item import ContentItem
from app.services.ai_service import AIService
from app.services.content_service import ContentService, ProcessingCancelled

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

_active_processing_tasks: dict[str, tuple[str, asyncio.Task]] = {}


def cancel_active_processing(content_id: str, job_id: str) -> bool:
    """Cancel a local in-flight task; persisted state handles other workers."""
    active = _active_processing_tasks.get(content_id)
    if active is None or active[0] != job_id or active[1].done():
        return False
    active[1].cancel()
    return True


async def _ensure_job_active(content_id: str, job_id: str) -> None:
    async with async_session_factory() as db:
        item = await db.get(ContentItem, content_id)
        if (
            item is None
            or item.status != "pending"
            or (item.metadata_json or {}).get("processing_job_id") != job_id
        ):
            raise ProcessingCancelled()


async def _mark_job_terminal(
    content_id: str,
    job_id: str | None,
    status: str,
    error: str | None = None,
) -> None:
    """Persist a terminal state without overwriting a newer processing job."""
    async with async_session_factory() as db:
        conditions = [
            ContentItem.id == content_id,
            ContentItem.status.in_(["pending", "finalizing"]),
        ]
        if job_id is not None:
            conditions.append(
                ContentItem.metadata_json["processing_job_id"].as_string() == job_id
            )
        result = await db.execute(
            update(ContentItem)
            .where(*conditions)
            .values(status=status)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            await db.rollback()
            return
        item = await db.get(ContentItem, content_id)
        metadata = {
            key: value
            for key, value in (item.metadata_json or {}).items()
            if key not in {"processing_job_id", "processing_error"}
        }
        if error:
            metadata["processing_error"] = error[:500]
        item.metadata_json = metadata
        await db.commit()


async def process_content_with_ai(
    content_id: str,
    style: str = "medium",
    template_fields: list[dict] | None = None,
    job_id: str | None = None,
) -> None:
    """后台任务：对内容执行 AI 后处理

    使用独立的 db session，避免请求结束后 session 关闭的问题。
    """
    print(f"[BG_TASK] Starting AI processing for content_id={content_id}", flush=True)
    current_task = asyncio.current_task()
    if job_id is not None and current_task is not None:
        _active_processing_tasks[content_id] = (job_id, current_task)
    try:
        async with async_session_factory() as db:
            llm_router = get_llm_router()
            ai_service = AIService(
                llm_router=llm_router,
                prompt_manager=get_prompt_manager(),
            )
            service = ContentService(
                db=db,
                parser_factory=get_parser_factory(),
                ai_service=ai_service,
            )
            result = await service.process_with_ai(
                content_id,
                style=style,
                template_fields=template_fields,
                cancel_check=(
                    lambda: _ensure_job_active(content_id, job_id)
                    if job_id is not None
                    else None
                ),
                job_id=job_id,
            )
            await db.commit()
            try:
                # Index only after distillation is committed. Index failures do
                # not invalidate the structured knowledge saved above.
                from app.workers.tasks import _index_content

                await _index_content(content_id)
            except Exception as index_error:
                logger.warning(
                    "提纯内容向量索引失败，将使用数据库本地检索: content_id=%s, error=%s",
                    content_id,
                    index_error,
                )
            print(f"[BG_TASK] AI processing completed: content_id={content_id}, summary={'exists' if result.summary else 'empty'}", flush=True)
    except (asyncio.CancelledError, ProcessingCancelled):
        logger.info("AI 后台处理已取消: content_id=%s", content_id)
        await _mark_job_terminal(content_id, job_id, "cancelled")
    except Exception as e:
        print(f"[BG_TASK] AI processing FAILED: content_id={content_id}, error={e}", flush=True)
        logger.error("AI 后台处理失败: content_id=%s, error=%s", content_id, e)
        await _mark_job_terminal(content_id, job_id, "failed", str(e))
    finally:
        active = _active_processing_tasks.get(content_id)
        if active is not None and active == (job_id, current_task):
            _active_processing_tasks.pop(content_id, None)


async def process_content_with_ai_quiet(content_id: str) -> Optional[str]:
    """后台任务：静默处理（失败不抛出异常，返回错误信息）"""
    async with async_session_factory() as db:
        try:
            llm_router = get_llm_router()
            ai_service = AIService(
                llm_router=llm_router,
                prompt_manager=get_prompt_manager(),
            )
            service = ContentService(
                db=db,
                parser_factory=get_parser_factory(),
                ai_service=ai_service,
            )
            await service.process_with_ai(content_id)
            await db.commit()
            try:
                from app.workers.tasks import _index_content

                await _index_content(content_id)
            except Exception as index_error:
                logger.warning("提纯内容向量索引失败: %s", index_error)
            return None
        except Exception as e:
            await db.rollback()
            failed_item = await db.get(ContentItem, content_id)
            if failed_item is not None:
                failed_item.status = "failed"
                failed_item.metadata_json = {
                    **(failed_item.metadata_json or {}),
                    "processing_error": str(e)[:500],
                }
                await db.commit()
            return str(e)
