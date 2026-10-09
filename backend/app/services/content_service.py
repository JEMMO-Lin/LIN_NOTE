"""内容服务

对应架构文档 3.2 节。
职责：内容接入、解析、存储、管理。
通过 ParserFactory 调度解析器，解析后写入 content_items 并触发索引。
支持 AI 后处理：摘要生成、知识点提取。
"""
import logging
from collections.abc import Awaitable, Callable
from typing import Optional

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError, ValidationError
from app.models.content_item import ContentItem
from app.models.knowledge_point import KnowledgePoint
from app.models.knowledge_base import KnowledgeBase
from app.schemas.content_item import ContentUpdate
from app.services.interfaces.content_parser import ParseResult

logger = logging.getLogger(__name__)


class ProcessingCancelled(Exception):
    """Raised when the current AI processing job has been cancelled or replaced."""


class ContentService:
    """内容应用服务"""

    def __init__(
        self,
        db: AsyncSession,
        parser_factory,
        indexer=None,
        ai_service=None,
    ):
        self.db = db
        self.parser_factory = parser_factory
        self.indexer = indexer
        self.ai = ai_service

    async def import_from_url(self, url: str, kb_id: str, user_id: str) -> ContentItem:
        """从 URL 导入：通过解析器抓取并结构化"""
        parser = self.parser_factory.get_parser(url, "url")
        result = await parser.parse(url)
        await self._ensure_kb_access(kb_id, user_id)
        return await self._save_content(kb_id, result)

    async def import_from_text(
        self, text: str, kb_id: str, user_id: str, title: Optional[str] = None
    ) -> ContentItem:
        """从纯文本导入"""
        parser = self.parser_factory.get_parser(text, "text")
        result = await parser.parse(text, title=title)
        await self._ensure_kb_access(kb_id, user_id)
        return await self._save_content(kb_id, result)

    async def import_from_image(self, image: bytes, kb_id: str, user_id: str) -> ContentItem:
        """从图片导入：走 OCR 解析"""
        parser = self.parser_factory.get_parser("", "image")
        result = await parser.parse(image)
        await self._ensure_kb_access(kb_id, user_id)
        if not result.content.strip():
            raise ValidationError("没有从图片中识别到文字，请换一张更清晰的图片")
        return await self._save_content(kb_id, result)

    async def _save_content(self, kb_id: str, parsed: ParseResult) -> ContentItem:
        """持久化解析结果并触发索引"""
        item = ContentItem(
            kb_id=kb_id,
            source_type=parsed.source_type,
            source_url=parsed.source_url,
            title=parsed.title,
            original_text=parsed.content,
            metadata_json=parsed.metadata,
            status="pending",
        )
        self.db.add(item)
        await self.db.flush()

        # 触发向量化索引
        if self.indexer is not None:
            await self.indexer.index_content(item)

        return item

    async def process_with_ai(
        self,
        content_id: str,
        style: str = "medium",
        template_fields: list[dict] | None = None,
        cancel_check: Callable[[], Awaitable[None]] | None = None,
        job_id: str | None = None,
    ) -> ContentItem:
        """提纯原始材料，并仅基于提纯正文生成摘要和知识切片。"""
        item = await self.get_content(content_id)
        if self.ai is None:
            logger.warning("AI 服务未配置，跳过后处理")
            return item

        original_text = item.original_text
        source_type = item.source_type
        # Do not keep a database read transaction open during slow provider
        # calls. This is especially important for SQLite: the cancel endpoint
        # must be able to persist its terminal state immediately.
        await self.db.rollback()

        try:
            # 1. 所有来源先经过同一套语义提纯，原文只用于溯源。
            if cancel_check is not None:
                await cancel_check()
            distillation = await self.ai.distill_content(
                original_text, source_type=source_type
            )
            if cancel_check is not None:
                await cancel_check()
            distilled_text = str(distillation.get("distilled_text", "")).strip()
            main_topic = str(distillation.get("main_topic", "")).strip()

            # 2. 摘要只阅读提纯文本，避免推广信息二次进入结构化字段。
            if not distilled_text:
                summary_result = {
                    "summary": "未识别到可沉淀的知识内容。",
                    "points": [],
                }
            else:
                summary_result = await self.ai.summarize(
                    distilled_text, style=style, fields=template_fields
                )
            if cancel_check is not None:
                await cancel_check()

            extracted_knowledge = {
                **summary_result,
                "distillation": {
                    "main_topic": main_topic,
                    "key_information": distillation.get("key_information", []),
                    "removed_noise_types": distillation.get("removed_noise_types", []),
                    "method": distillation.get("method", "llm"),
                },
            }

            # 3. 知识点就是检索切片，同样不得回读原始噪声文本。
            points = (
                await self.ai.extract_knowledge_points(distilled_text)
                if distilled_text
                else []
            )
            if cancel_check is not None:
                await cancel_check()

            # Do not mutate persisted content until all expensive work has
            # completed and the final cancellation checkpoint has passed.
            if job_id is not None:
                claim = await self.db.execute(
                    update(ContentItem)
                    .where(
                        ContentItem.id == content_id,
                        ContentItem.status == "pending",
                        ContentItem.metadata_json["processing_job_id"].as_string()
                        == job_id,
                    )
                    .values(status="finalizing")
                    .execution_options(synchronize_session=False)
                )
                if claim.rowcount != 1:
                    await self.db.rollback()
                    raise ProcessingCancelled()

            item = await self.get_content(content_id)
            if item.status == "cancelled":
                raise ProcessingCancelled()
            item.distilled_text = distilled_text
            if main_topic and (item.metadata_json or {}).get("auto_title"):
                item.title = main_topic[:500]
            item.summary = self._summary_text(summary_result)
            item.extracted_knowledge = extracted_knowledge
            item.metadata_json = {
                key: value
                for key, value in (item.metadata_json or {}).items()
                if key not in {"processing_job_id", "processing_error"}
            }
            await self.db.execute(
                delete(KnowledgePoint).where(KnowledgePoint.content_id == item.id)
            )
            for point_data in points:
                try:
                    importance = min(1.0, max(0.0, float(point_data.get("importance", 0.5))))
                except (TypeError, ValueError):
                    importance = 0.5
                kp = KnowledgePoint(
                    content_id=item.id,
                    kb_id=item.kb_id,
                    title=point_data.get("title", "未命名知识点"),
                    content=point_data.get("content", ""),
                    category=point_data.get("category", ""),
                    importance=importance,
                )
                self.db.add(kp)

            item.status = "processed"
            await self.db.flush()
            logger.info("AI 处理完成: content_id=%s, points=%d", content_id, len(points))

        except ProcessingCancelled:
            raise
        except Exception as e:
            logger.error("AI 处理失败: content_id=%s, error=%s", content_id, e)
            item.status = "failed"
            await self.db.flush()
            raise

        return item

    async def get_content(
        self, content_id: str, user_id: str | None = None
    ) -> ContentItem:
        item = await self.db.get(ContentItem, content_id)
        if item is None:
            raise NotFoundError("内容不存在")
        if user_id is not None:
            await self._ensure_kb_access(str(item.kb_id), user_id)
        return item

    async def list_contents(
        self,
        kb_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        user_id: str | None = None,
        source_type: Optional[str] = None,
        keyword: Optional[str] = None,
        sort_by: str = "newest",
        include_merged: bool = False,
    ) -> tuple[list[ContentItem], int]:
        """分页列出内容"""
        from sqlalchemy import func

        if user_id is not None:
            await self._ensure_kb_access(kb_id, user_id)
        stmt = select(ContentItem).where(ContentItem.kb_id == kb_id)
        if status:
            stmt = stmt.where(ContentItem.status == status)
        if source_type:
            stmt = stmt.where(ContentItem.source_type == source_type)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    ContentItem.title.ilike(pattern),
                    ContentItem.summary.ilike(pattern),
                    ContentItem.original_text.ilike(pattern),
                )
            )
        if not include_merged:
            stmt = stmt.where(ContentItem.merge_status == "active")

        total = await self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        stmt = (
            stmt.order_by(
                ContentItem.created_at.asc()
                if sort_by == "oldest"
                else ContentItem.title.asc()
                if sort_by == "title"
                else ContentItem.created_at.desc()
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total or 0

    async def update_content(
        self, content_id: str, user_id: str, payload: ContentUpdate
    ) -> ContentItem:
        item = await self.get_content(content_id, user_id)
        data = payload.model_dump(exclude_unset=True)
        if "metadata" in data:
            item.metadata_json = data.pop("metadata")
        original_changed = "original_text" in data and data["original_text"] != item.original_text
        for key, value in data.items():
            setattr(item, key, value)
        if original_changed and "distilled_text" not in data:
            item.distilled_text = None
            item.summary = None
            item.extracted_knowledge = None
            item.status = "pending"
            await self.db.execute(
                delete(KnowledgePoint).where(KnowledgePoint.content_id == item.id)
            )
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def delete_content(self, content_id: str, user_id: str) -> None:
        item = await self.get_content(content_id, user_id)
        await self.db.delete(item)
        await self.db.flush()

    async def _ensure_kb_access(self, kb_id: str, user_id: str) -> KnowledgeBase:
        kb = await self.db.get(KnowledgeBase, kb_id)
        if kb is None:
            raise NotFoundError("知识库不存在")
        if str(kb.user_id) != user_id:
            raise PermissionError("无权访问该知识库")
        return kb

    @staticmethod
    def _summary_text(result: dict) -> str:
        if result.get("summary"):
            return str(result["summary"])
        parts = []
        for value in result.values():
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
            elif isinstance(value, list):
                parts.extend(str(item) for item in value[:3] if str(item).strip())
            if len(parts) >= 3:
                break
        return "；".join(parts)[:600]
