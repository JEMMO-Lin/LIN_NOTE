"""总结模板应用服务。"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError
from app.models.summary_template import SummaryTemplate
from app.schemas.summary_template import SummaryTemplateCreate, SummaryTemplateUpdate


class TemplateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_templates(self, user_id: str) -> list[SummaryTemplate]:
        result = await self.db.execute(
            select(SummaryTemplate)
            .where(SummaryTemplate.user_id == user_id)
            .order_by(SummaryTemplate.is_default.desc(), SummaryTemplate.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_template(self, user_id: str, template_id: str) -> SummaryTemplate:
        item = await self.db.get(SummaryTemplate, template_id)
        if item is None:
            raise NotFoundError("总结模板不存在")
        if str(item.user_id) != user_id:
            raise PermissionError("无权访问该总结模板")
        return item

    async def create_template(
        self, user_id: str, payload: SummaryTemplateCreate
    ) -> SummaryTemplate:
        data = payload.model_dump()
        data["fields"] = [field.model_dump() for field in payload.fields]
        if payload.is_default:
            await self._clear_default(user_id)
        item = SummaryTemplate(user_id=user_id, **data)
        self.db.add(item)
        await self.db.flush()
        return item

    async def update_template(
        self, user_id: str, template_id: str, payload: SummaryTemplateUpdate
    ) -> SummaryTemplate:
        item = await self.get_template(user_id, template_id)
        data = payload.model_dump(exclude_unset=True)
        if "fields" in data and data["fields"] is not None:
            data["fields"] = [
                field.model_dump() if hasattr(field, "model_dump") else field
                for field in data["fields"]
            ]
        if data.get("is_default"):
            await self._clear_default(user_id)
        for key, value in data.items():
            setattr(item, key, value)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def delete_template(self, user_id: str, template_id: str) -> None:
        item = await self.get_template(user_id, template_id)
        await self.db.delete(item)
        await self.db.flush()

    async def _clear_default(self, user_id: str) -> None:
        await self.db.execute(
            update(SummaryTemplate)
            .where(SummaryTemplate.user_id == user_id)
            .values(is_default=False)
        )
