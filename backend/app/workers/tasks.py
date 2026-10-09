"""可独立运行的 Celery 后台任务。"""
import asyncio
import logging

from app.core.database import async_session_factory
from app.infrastructure.llm.prompt_manager import get_prompt_manager
from app.infrastructure.llm.router import get_llm_router
from app.infrastructure.parsers.factory import get_parser_factory
from app.infrastructure.vector_store.chroma_store import (
    CONTENT_COLLECTION,
    KNOWLEDGE_POINT_COLLECTION,
    get_vector_store,
)
from app.models.content_item import ContentItem
from app.models.knowledge_point import KnowledgePoint
from app.services.ai_service import AIService
from app.services.content_service import ContentService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    return asyncio.run(coro)


async def _process_content(content_id: str) -> None:
    async with async_session_factory() as db:
        service = ContentService(
            db=db,
            parser_factory=get_parser_factory(),
            ai_service=AIService(
                llm_router=get_llm_router(),
                prompt_manager=get_prompt_manager(),
            ),
        )
        await service.process_with_ai(content_id)
        await db.commit()


async def _index_content(content_id: str) -> None:
    async with async_session_factory() as db:
        item = await db.get(ContentItem, content_id)
        if item is None:
            return
        llm = get_llm_router()
        vector_store = get_vector_store()
        # Never embed raw parsed material. Legacy rows must be reprocessed first.
        knowledge_text = (item.distilled_text or "").strip()
        if knowledge_text:
            content_embedding = await llm.embed(knowledge_text)
            await vector_store.upsert(
                CONTENT_COLLECTION,
                [str(item.id)],
                [content_embedding],
                [knowledge_text],
                [
                    {
                        "kb_id": str(item.kb_id),
                        "content_id": str(item.id),
                        "source_type": item.source_type,
                        "title": item.title,
                    }
                ],
            )
        else:
            await vector_store.delete(CONTENT_COLLECTION, [str(item.id)])
        from sqlalchemy import select

        # Reprocessing can replace every knowledge slice. Remove vectors for
        # previous slices first so filtered-out promotions cannot remain searchable.
        await vector_store.delete_where(
            KNOWLEDGE_POINT_COLLECTION, {"content_id": str(item.id)}
        )
        result = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.content_id == item.id)
        )
        points = list(result.scalars().all())
        if points:
            embeddings = [await llm.embed(point.content) for point in points]
            await vector_store.upsert(
                KNOWLEDGE_POINT_COLLECTION,
                [str(point.id) for point in points],
                embeddings,
                [point.content for point in points],
                [
                    {
                        "kb_id": str(point.kb_id),
                        "content_id": str(point.content_id),
                        "title": point.title,
                        "category": point.category or "",
                    }
                    for point in points
                ],
            )


@celery_app.task(name="process_content", bind=True, max_retries=3)
def process_content(self, content_id: str):
    try:
        _run(_process_content(content_id))
        _run(_index_content(content_id))
    except Exception as exc:
        logger.exception("内容处理失败: %s", content_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(name="index_content", bind=True, max_retries=3)
def index_content(self, content_id: str, text: str | None = None, kb_id: str | None = None):
    try:
        _run(_index_content(content_id))
    except Exception as exc:
        logger.exception("索引失败: %s", content_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(name="generate_summary", bind=True, max_retries=3)
def generate_summary(self, content_id: str, text: str | None = None):
    try:
        _run(_process_content(content_id))
    except Exception as exc:
        logger.exception("摘要生成失败: %s", content_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(name="extract_knowledge_points", bind=True, max_retries=3)
def extract_knowledge_points(self, content_id: str, text: str | None = None):
    try:
        _run(_process_content(content_id))
    except Exception as exc:
        logger.exception("知识点提取失败: %s", content_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
