"""Application service for the self-growing LLM Wiki."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError, ValidationError
from app.models.wiki_entry import WikiEntry
from app.schemas.wiki import WikiEntryUpdate
from app.services.interfaces.search_service import SearchHit


GLOBAL_SCOPE = "__all__"


def normalize_question(question: str) -> str:
    """Normalize harmless typography differences without changing semantics."""
    normalized = unicodedata.normalize("NFKC", question).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def question_hash(normalized_question: str) -> str:
    return hashlib.sha256(normalized_question.encode("utf-8")).hexdigest()


@dataclass
class WikiLookup:
    entry: WikiEntry
    is_hit: bool


class WikiService:
    def __init__(self, db: AsyncSession, publish_threshold: int = 5):
        self.db = db
        self.publish_threshold = max(1, publish_threshold)

    async def record_and_lookup(
        self, user_id: str, question: str, kb_id: str | None
    ) -> WikiLookup:
        """Count this question and return a published exact-normalized match."""
        normalized = normalize_question(question)
        digest = question_hash(normalized)
        scope_key = kb_id or GLOBAL_SCOPE
        result = await self.db.execute(
            select(WikiEntry).where(
                WikiEntry.user_id == user_id,
                WikiEntry.scope_key == scope_key,
                WikiEntry.question_hash == digest,
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            entry = WikiEntry(
                user_id=user_id,
                kb_id=kb_id,
                scope_key=scope_key,
                question=question.strip(),
                normalized_question=normalized,
                question_hash=digest,
                ask_count=1,
            )
            try:
                # The savepoint keeps simultaneous first asks from aborting the
                # whole request transaction when the unique key wins elsewhere.
                async with self.db.begin_nested():
                    self.db.add(entry)
                    await self.db.flush()
            except IntegrityError:
                result = await self.db.execute(
                    select(WikiEntry).where(
                        WikiEntry.user_id == user_id,
                        WikiEntry.scope_key == scope_key,
                        WikiEntry.question_hash == digest,
                    )
                )
                entry = result.scalar_one()
                entry.ask_count += 1
        else:
            entry.ask_count += 1

        return WikiLookup(
            entry=entry,
            is_hit=bool(entry.is_published and entry.answer),
        )

    async def learn(
        self, entry: WikiEntry, answer: str, hits: list[SearchHit]
    ) -> bool:
        """Refresh the candidate and publish it once it is frequently asked."""
        entry.answer = answer
        entry.sources = [
            {
                "point_id": hit.point_id,
                "title": hit.title,
                "content": hit.content,
                "score": hit.score,
                "content_id": hit.content_id,
                "kb_id": hit.kb_id,
            }
            for hit in hits
        ]
        just_published = (
            not entry.is_published and entry.ask_count >= self.publish_threshold
        )
        if just_published:
            entry.is_published = True
            entry.published_at = datetime.now(timezone.utc)
        await self.db.flush()
        return just_published

    @staticmethod
    def restore_sources(entry: WikiEntry) -> list[SearchHit]:
        return [
            SearchHit(
                point_id=item["point_id"],
                title=item["title"],
                content=item["content"],
                score=float(item.get("score", 0)),
                content_id=item.get("content_id"),
                kb_id=item.get("kb_id"),
            )
            for item in (entry.sources or [])
            if item.get("point_id") and item.get("title") is not None
        ]

    async def list_entries(
        self,
        user_id: str,
        kb_id: str | None = None,
        published_only: bool = True,
    ) -> list[WikiEntry]:
        stmt = select(WikiEntry).where(WikiEntry.user_id == user_id)
        if kb_id is not None:
            stmt = stmt.where(WikiEntry.kb_id == kb_id)
        if published_only:
            stmt = stmt.where(WikiEntry.is_published.is_(True))
        result = await self.db.execute(
            stmt.order_by(WikiEntry.ask_count.desc(), WikiEntry.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_entry(self, user_id: str, entry_id: str) -> WikiEntry:
        entry = await self.db.get(WikiEntry, entry_id)
        if entry is None:
            raise NotFoundError("Wiki 条目不存在")
        if str(entry.user_id) != user_id:
            raise PermissionError("无权访问该 Wiki 条目")
        return entry

    async def update_entry(
        self, user_id: str, entry_id: str, payload: WikiEntryUpdate
    ) -> WikiEntry:
        entry = await self.get_entry(user_id, entry_id)
        values = payload.model_dump(exclude_unset=True)
        if "question" in values:
            normalized = normalize_question(values["question"])
            entry.question = values["question"].strip()
            entry.normalized_question = normalized
            entry.question_hash = question_hash(normalized)
        if "answer" in values:
            entry.answer = values["answer"]
        if "is_published" in values:
            if values["is_published"] and not entry.answer:
                raise ValidationError("没有答案的候选条目不能发布到 Wiki")
            entry.is_published = values["is_published"]
            entry.published_at = (
                datetime.now(timezone.utc) if values["is_published"] else None
            )
        await self.db.flush()
        return entry

    async def delete_entry(self, user_id: str, entry_id: str) -> None:
        entry = await self.get_entry(user_id, entry_id)
        await self.db.delete(entry)
        await self.db.flush()
