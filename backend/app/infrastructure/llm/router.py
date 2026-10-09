"""LLM 路由器实现

对应架构文档 4.2 / 4.3 节。
按任务类型选择模型分级（FAST / BALANCED / QUALITY），
通过 Provider 注册表调度不同厂商，支持降级策略与重试。
"""
import logging
from typing import Optional

from app.core.config import settings
from app.infrastructure.llm.providers import get_provider_registry
from app.infrastructure.llm.providers.base import ILLMProvider
from app.services.interfaces.llm_router import (
    ILLMRouter,
    LLMResponse,
    ModelConfig,
    ModelTier,
    TaskType,
)

logger = logging.getLogger(__name__)


class LLMRouter(ILLMRouter):
    """LLM 路由器 - 多厂商调度"""

    # 任务类型 → 模型分级
    TIER_MAPPING = {
        TaskType.SUMMARIZE: ModelTier.BALANCED,
        TaskType.DISTILL: ModelTier.QUALITY,
        TaskType.MERGE: ModelTier.QUALITY,
        TaskType.SEARCH: ModelTier.FAST,
        TaskType.ANSWER: ModelTier.BALANCED,
        TaskType.TREE: ModelTier.QUALITY,
    }

    def __init__(self, provider_name: Optional[str] = None):
        """初始化路由器

        Args:
            provider_name: 指定厂商，None 则使用配置中的默认厂商
        """
        self.registry = get_provider_registry()
        self._provider_name = provider_name

    def _get_provider(self) -> ILLMProvider:
        """获取当前 Provider"""
        return self.registry.get_provider(self._provider_name)

    def _select_config(self, task_type: TaskType, provider_name: str) -> ModelConfig:
        """根据任务类型和厂商选择模型配置"""
        tier = self.TIER_MAPPING.get(task_type, ModelTier.BALANCED)
        model_name = self.registry.get_model_name(provider_name, tier.value)
        if not model_name:
            # A custom provider may only configure one model tier. Critical
            # distillation should still use its best available configured model.
            fallback_order = {
                ModelTier.QUALITY: [ModelTier.BALANCED, ModelTier.FAST],
                ModelTier.BALANCED: [ModelTier.FAST, ModelTier.QUALITY],
                ModelTier.FAST: [ModelTier.BALANCED, ModelTier.QUALITY],
            }
            for candidate in fallback_order[tier]:
                candidate_model = self.registry.get_model_name(
                    provider_name, candidate.value
                )
                if candidate_model:
                    logger.warning(
                        "Provider %s 未配置 %s 模型，任务 %s 降级到 %s",
                        provider_name,
                        tier.value,
                        task_type.value,
                        candidate.value,
                    )
                    tier = candidate
                    model_name = candidate_model
                    break

        # 获取 token 限制
        tier_token_limits = {
            ModelTier.FAST: (4096, 1024),
            ModelTier.BALANCED: (8192, 2048),
            ModelTier.QUALITY: (16384, 4096),
        }
        max_in, max_out = tier_token_limits.get(tier, (8192, 2048))

        return ModelConfig(
            provider=provider_name,
            model_name=model_name,
            tier=tier,
            max_input_tokens=max_in,
            max_output_tokens=max_out,
        )

    async def complete(
        self,
        prompt: str,
        task_type: TaskType,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """按任务类型路由到合适模型并完成调用"""
        provider = self._get_provider()
        config = self._select_config(task_type, provider.provider_name)

        if not config.model_name:
            raise ValueError(
                f"厂商 {provider.provider_name} 未配置 {config.tier.value} 级别的模型，"
                f"请在 .env 中设置 LLM_MODEL_{config.tier.value.upper()}"
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.info(
            "LLM 调用: provider=%s, model=%s, tier=%s, task=%s",
            provider.provider_name, config.model_name, config.tier.value, task_type.value,
        )

        return await provider.chat_completion(
            model=config.model_name,
            messages=messages,
            max_tokens=config.max_output_tokens,
            **kwargs,
        )

    async def embed(self, text: str) -> list[float]:
        """生成文本嵌入向量

        降级策略：
        1. 使用当前厂商的 embedding 模型
        2. 若当前厂商不支持，回退到 OpenAI（若可用）
        """
        provider = self._get_provider()
        embedding_model = self.registry.get_model_name(
            provider.provider_name, "embedding"
        )

        if not embedding_model:
            # 回退到 OpenAI embedding
            openai_provider = self.registry.get_provider("openai")
            if openai_provider.is_available() and openai_provider.provider_name != provider.provider_name:
                embedding_model = self.registry.get_model_name("openai", "embedding")
                if embedding_model:
                    logger.warning(
                        "厂商 %s 不支持 Embedding，降级到 OpenAI",
                        provider.provider_name,
                    )
                    return await openai_provider.embedding(embedding_model, text)
            raise NotImplementedError(
                f"厂商 {provider.provider_name} 不支持 Embedding，且无可用降级方案"
            )

        return await provider.embedding(embedding_model, text)


# 全局单例
_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


def get_llm_router_with_provider(provider_name: str) -> LLMRouter:
    """创建指定厂商的 LLM 路由器"""
    return LLMRouter(provider_name=provider_name)
