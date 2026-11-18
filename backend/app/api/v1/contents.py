"""内容导入、管理和 AI 后处理路由。"""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, UploadFile
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import ValidationError
from app.infrastructure.llm.prompt_manager import get_prompt_manager
from app.infrastructure.llm.router import get_llm_router
from app.infrastructure.parsers.factory import get_parser_factory
from app.schemas.common import DataResponse, PaginatedResponse
from app.schemas.content_item import (
    ContentImportFromBrowser,
    ContentImportFromText,
    ContentImportFromURL,
    ContentOut,
    ContentProcessRequest,
    ContentUpdate,
)
from app.services.ai_service import AIService
from app.services.content_service import ContentService
from app.services.interfaces.llm_router import ILLMRouter
from app.services.template_service import TemplateService
from app.models.content_item import ContentItem
from app.workers.background_tasks import cancel_active_processing, process_content_with_ai

router = APIRouter()


def _prepare_processing(item: ContentItem) -> str:
    job_id = str(uuid.uuid4())
    item.status = "pending"
    item.metadata_json = {
        **{
            key: value
            for key, value in (item.metadata_json or {}).items()
            if key not in {"processing_error", "processing_job_id"}
        },
        "processing_job_id": job_id,
    }
    return job_id


def _get_content_service(db: AsyncSession, llm_router: ILLMRouter) -> ContentService:
    return ContentService(
        db=db,
        parser_factory=get_parser_factory(),
        ai_service=AIService(
            llm_router=llm_router,
            prompt_manager=get_prompt_manager(),
        ),
    )


@router.post("/url", response_model=DataResponse[ContentOut])
async def import_from_url(
    payload: ContentImportFromURL,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    llm_router: ILLMRouter = Depends(get_llm_router),
):
    service = _get_content_service(db, llm_router)
    item = await service.import_from_url(payload.url, payload.kb_id, user_id)
    job_id = _prepare_processing(item)
    # BackgroundTasks runs with a separate database session.  Commit the new
    # row before enqueueing the task so that session can read it.
    await db.commit()
    await db.refresh(item)
    background_tasks.add_task(process_content_with_ai, item.id, "medium", None, job_id)
    return DataResponse(data=ContentOut.model_validate(item))


@router.post("/text", response_model=DataResponse[ContentOut])
async def import_from_text(
    payload: ContentImportFromText,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    llm_router: ILLMRouter = Depends(get_llm_router),
):
    template_fields = None
    if payload.template_id:
        template = await TemplateService(db).get_template(user_id, payload.template_id)
        template_fields = template.fields
    service = _get_content_service(db, llm_router)
    item = await service.import_from_text(
        payload.text, payload.kb_id, user_id, payload.title
    )
    job_id = _prepare_processing(item)
    # The AI worker opens its own session, so the imported content must be
    # visible outside this request transaction before the task starts.
    await db.commit()
    await db.refresh(item)
    background_tasks.add_task(
        process_content_with_ai,
        item.id,
        payload.summary_style,
        template_fields,
        job_id,
    )
    return DataResponse(data=ContentOut.model_validate(item))


@router.post("/image", response_model=DataResponse[ContentOut])
async def import_from_image(
    kb_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    llm_router: ILLMRouter = Depends(get_llm_router),
):
    service = _get_content_service(db, llm_router)
    item = await service.import_from_image(await file.read(), kb_id, user_id)
    job_id = _prepare_processing(item)
    await db.commit()
    await db.refresh(item)
    background_tasks.add_task(process_content_with_ai, item.id, "medium", None, job_id)
    return DataResponse(data=ContentOut.model_validate(item))


@router.post("/browser-capture", response_model=DataResponse[ContentOut])
async def import_from_browser_capture(
    payload: ContentImportFromBrowser,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    llm_router: ILLMRouter = Depends(get_llm_router),
):
    """Receive user-reviewed content from the browser capture helper."""
    service = _get_content_service(db, llm_router)
    capture = payload.model_dump(exclude={"kb_id"})
    item = await service.import_from_browser_capture(
        capture, payload.kb_id, user_id
    )
    job_id = _prepare_processing(item)
    await db.commit()
    await db.refresh(item)
    background_tasks.add_task(
        process_content_with_ai, item.id, "medium", None, job_id
    )
    return DataResponse(data=ContentOut.model_validate(item))


@router.post("/{content_id}/process", response_model=DataResponse[ContentOut])
async def process_content(
    content_id: str,
    payload: ContentProcessRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    llm_router: ILLMRouter = Depends(get_llm_router),
):
    template_fields = None
    if payload.template_id:
        template = await TemplateService(db).get_template(user_id, payload.template_id)
        template_fields = template.fields
    service = _get_content_service(db, llm_router)
    item = await service.get_content(content_id, user_id)
    if item.status in {"pending", "finalizing"}:
        raise ValidationError("内容正在整理中，请先停止当前任务")
    job_id = _prepare_processing(item)
    await db.flush()
    # Make the pending status visible to the worker's independent session.
    await db.commit()
    # ``updated_at`` is generated by the database on UPDATE and SQLAlchemy marks
    # it expired after the flush. Refresh before Pydantic accesses attributes;
    # otherwise async ORM I/O is attempted from synchronous validation and
    # raises MissingGreenlet.
    await db.refresh(item)
    background_tasks.add_task(
        process_content_with_ai,
        content_id,
        payload.summary_style,
        template_fields,
        job_id,
    )
    return DataResponse(data=ContentOut.model_validate(item), message="AI 处理已启动")


@router.post("/{content_id}/process/cancel", response_model=DataResponse[ContentOut])
async def cancel_content_processing(
    content_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = ContentService(db=db, parser_factory=get_parser_factory())
    item = await service.get_content(content_id, user_id)
    if item.status == "cancelled":
        return DataResponse(data=ContentOut.model_validate(item), message="整理已停止")
    if item.status != "pending":
        message = "整理结果正在写入，已无法安全停止" if item.status == "finalizing" else "当前没有正在运行的整理任务"
        raise ValidationError(message)

    job_id = str((item.metadata_json or {}).get("processing_job_id", ""))
    metadata = {
        key: value
        for key, value in (item.metadata_json or {}).items()
        if key not in {"processing_job_id", "processing_error"}
    }
    cancelled = await db.execute(
        update(ContentItem)
        .where(
            ContentItem.id == content_id,
            ContentItem.status == "pending",
            ContentItem.metadata_json["processing_job_id"].as_string() == job_id,
        )
        .values(status="cancelled", metadata_json=metadata)
        .execution_options(synchronize_session=False)
    )
    if cancelled.rowcount != 1:
        await db.rollback()
        current = await service.get_content(content_id, user_id)
        message = "整理结果正在写入，已无法安全停止" if current.status == "finalizing" else "整理任务状态已经变化，请刷新后查看"
        raise ValidationError(message)

    await db.commit()
    if job_id:
        cancel_active_processing(content_id, job_id)
    await db.refresh(item)
    return DataResponse(data=ContentOut.model_validate(item), message="整理已停止")


@router.get("", response_model=PaginatedResponse[ContentOut])
async def list_contents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    source_type: str | None = Query(None, pattern="^(text|url|image)$"),
    keyword: str | None = None,
    sort_by: str = Query("newest", pattern="^(newest|oldest|title)$"),
    include_merged: bool = False,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = ContentService(db=db, parser_factory=get_parser_factory())
    items, total = await service.list_contents(
        kb_id,
        status=status,
        page=page,
        page_size=page_size,
        user_id=user_id,
        source_type=source_type,
        keyword=keyword,
        sort_by=sort_by,
        include_merged=include_merged,
    )
    return PaginatedResponse(
        data=[ContentOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{content_id}", response_model=DataResponse[ContentOut])
async def get_content(
    content_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = await ContentService(
        db=db, parser_factory=get_parser_factory()
    ).get_content(content_id, user_id)
    return DataResponse(data=ContentOut.model_validate(item))


@router.patch("/{content_id}", response_model=DataResponse[ContentOut])
async def update_content(
    content_id: str,
    payload: ContentUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = await ContentService(
        db=db, parser_factory=get_parser_factory()
    ).update_content(content_id, user_id, payload)
    return DataResponse(data=ContentOut.model_validate(item), message="已保存")


@router.delete("/{content_id}", response_model=DataResponse)
async def delete_content(
    content_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await ContentService(
        db=db, parser_factory=get_parser_factory()
    ).delete_content(content_id, user_id)
    return DataResponse(message="已删除")
