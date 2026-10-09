"""LLM 配置路由

提供可用厂商查询、当前配置、模型切换等管理接口。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.deps import get_current_user_id
from app.infrastructure.llm.providers import (
    get_provider_registry,
    PROVIDER_DEFAULT_MODELS,
    PROVIDER_DISPLAY_NAMES,
)
from app.schemas.common import DataResponse

router = APIRouter()


class ProviderInfo(BaseModel):
    """厂商信息"""
    provider: str
    display_name: str
    available: bool
    models: dict[str, str]


class LLMConfigOut(BaseModel):
    """当前 LLM 配置"""
    model_config = {"protected_namespaces": ()}

    default_provider: str
    current_provider: str
    available_providers: list[ProviderInfo]
    model_fast: str
    model_balanced: str
    model_quality: str
    embedding_model: str


@router.get("/providers", response_model=DataResponse[list[ProviderInfo]])
async def list_providers(
    user_id: str = Depends(get_current_user_id),
):
    """列出所有可用 LLM 厂商"""
    registry = get_provider_registry()
    providers = registry.list_available()

    result = []
    for p in providers:
        models = PROVIDER_DEFAULT_MODELS.get(p["provider"], {})
        result.append(ProviderInfo(
            provider=p["provider"],
            display_name=p["display_name"],
            available=p["available"],
            models=models,
        ))

    return DataResponse(data=result)


@router.get("/config", response_model=DataResponse[LLMConfigOut])
async def get_llm_config(
    user_id: str = Depends(get_current_user_id),
):
    """获取当前 LLM 配置"""
    registry = get_provider_registry()
    current = registry.get_provider()

    providers_data = []
    for p in registry.list_available():
        models = PROVIDER_DEFAULT_MODELS.get(p["provider"], {})
        providers_data.append(ProviderInfo(
            provider=p["provider"],
            display_name=p["display_name"],
            available=p["available"],
            models=models,
        ))

    return DataResponse(data=LLMConfigOut(
        default_provider=settings.llm_default_provider,
        current_provider=current.provider_name,
        available_providers=providers_data,
        model_fast=settings.llm_model_fast or PROVIDER_DEFAULT_MODELS.get(current.provider_name, {}).get("fast", ""),
        model_balanced=settings.llm_model_balanced or PROVIDER_DEFAULT_MODELS.get(current.provider_name, {}).get("balanced", ""),
        model_quality=settings.llm_model_quality or PROVIDER_DEFAULT_MODELS.get(current.provider_name, {}).get("quality", ""),
        embedding_model=settings.llm_embedding_model,
    ))


class LLMTestRequest(BaseModel):
    """LLM 测试请求"""
    provider: Optional[str] = None
    prompt: str = "你好，请用一句话介绍你自己"


@router.post("/test", response_model=DataResponse)
async def test_llm(
    payload: LLMTestRequest,
    user_id: str = Depends(get_current_user_id),
):
    """测试 LLM 连通性"""
    from app.infrastructure.llm.router import get_llm_router, get_llm_router_with_provider
    from app.services.interfaces.llm_router import TaskType

    router_instance = get_llm_router_with_provider(payload.provider) if payload.provider else get_llm_router()
    try:
        resp = await router_instance.complete(
            prompt=payload.prompt,
            task_type=TaskType.ANSWER,
        )
        return DataResponse(
            data={
                "provider": router_instance._get_provider().provider_name,
                "model": resp.model,
                "content": resp.content,
                "usage": resp.usage,
            },
            message="LLM 调用成功",
        )
    except Exception as e:
        return DataResponse(
            code="LLM_ERROR",
            message=f"LLM 调用失败: {str(e)}",
            data=None,
        )
