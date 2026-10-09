"""Provider 工厂注册表

根据配置创建对应的 LLM Provider 实例。
支持运行时动态切换厂商。
"""
import logging
from typing import Optional

from app.core.config import settings
from app.infrastructure.llm.providers.anthropic_provider import AnthropicProvider
from app.infrastructure.llm.providers.base import ILLMProvider
from app.infrastructure.llm.providers.openai_provider import OpenAICompatibleProvider

logger = logging.getLogger(__name__)

# 各厂商默认模型配置
PROVIDER_DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "custom": {
        "fast": "",      # 由 CUSTOM_MODEL_FAST 环境变量配置
        "balanced": "",  # 由 CUSTOM_MODEL_BALANCED 环境变量配置
        "quality": "",   # 由 CUSTOM_MODEL_QUALITY 环境变量配置
        "embedding": "",  # 由 CUSTOM_EMBEDDING_MODEL 环境变量配置
    },
    "openai": {
        "fast": "gpt-4o-mini",
        "balanced": "gpt-4o-mini",
        "quality": "gpt-4o",
        "embedding": "text-embedding-3-small",
    },
    "deepseek": {
        "fast": "deepseek-chat",
        "balanced": "deepseek-chat",
        "quality": "deepseek-reasoner",
        "embedding": "",  # DeepSeek 暂无 embedding
    },
    "moonshot": {
        "fast": "moonshot-v1-8k",
        "balanced": "moonshot-v1-8k",
        "quality": "moonshot-v1-32k",
        "embedding": "text-embedding-3-small",  # Moonshot 暂无，回退 OpenAI
    },
    "qwen": {
        "fast": "qwen-turbo",
        "balanced": "qwen-plus",
        "quality": "qwen-max",
        "embedding": "text-embedding-v3",
    },
    "anthropic": {
        "fast": "claude-3-5-haiku-20241022",
        "balanced": "claude-3-5-sonnet-20241022",
        "quality": "claude-3-5-sonnet-20241022",
        "embedding": "",  # Anthropic 无 embedding
    },
    "ollama": {
        "fast": "qwen2.5:7b",
        "balanced": "qwen2.5:14b",
        "quality": "qwen2.5:32b",
        "embedding": "nomic-embed-text",
    },
}

# 厂商显示名
PROVIDER_DISPLAY_NAMES = {
    "custom": "自定义中转站",
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "moonshot": "Moonshot (Kimi)",
    "qwen": "通义千问",
    "anthropic": "Anthropic Claude",
    "ollama": "Ollama (本地)",
}


class ProviderRegistry:
    """Provider 工厂注册表"""

    def __init__(self):
        self._providers: dict[str, ILLMProvider] = {}
        self._init_providers()

    def _init_providers(self):
        """根据配置初始化所有可用 Provider"""
        # 自定义中转站（任意 OpenAI 兼容服务）
        if settings.custom_api_key and settings.custom_base_url:
            self._providers["custom"] = OpenAICompatibleProvider(
                provider_name="custom",
                base_url=settings.custom_base_url,
                api_key=settings.custom_api_key,
            )
            logger.info("LLM Provider 已注册: 自定义中转站 (%s)", settings.custom_base_url)

        # OpenAI
        if settings.openai_api_key:
            self._providers["openai"] = OpenAICompatibleProvider(
                provider_name="openai",
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
            )
            logger.info("LLM Provider 已注册: OpenAI")

        # DeepSeek
        if settings.deepseek_api_key:
            self._providers["deepseek"] = OpenAICompatibleProvider(
                provider_name="deepseek",
                base_url=settings.deepseek_base_url,
                api_key=settings.deepseek_api_key,
            )
            logger.info("LLM Provider 已注册: DeepSeek")

        # Moonshot
        if settings.moonshot_api_key:
            self._providers["moonshot"] = OpenAICompatibleProvider(
                provider_name="moonshot",
                base_url=settings.moonshot_base_url,
                api_key=settings.moonshot_api_key,
            )
            logger.info("LLM Provider 已注册: Moonshot")

        # Qwen
        if settings.qwen_api_key:
            self._providers["qwen"] = OpenAICompatibleProvider(
                provider_name="qwen",
                base_url=settings.qwen_base_url,
                api_key=settings.qwen_api_key,
            )
            logger.info("LLM Provider 已注册: 通义千问")

        # Anthropic
        if settings.anthropic_api_key:
            self._providers["anthropic"] = AnthropicProvider(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url,
            )
            logger.info("LLM Provider 已注册: Anthropic")

        # Ollama（本地部署，始终注册）
        self._providers["ollama"] = OpenAICompatibleProvider(
            provider_name="ollama",
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
        )
        logger.info("LLM Provider 已注册: Ollama (本地)")

    def get_provider(self, name: Optional[str] = None) -> ILLMProvider:
        """获取指定 Provider，未指定则返回默认厂商

        降级策略：
        1. 优先使用指定的 provider
        2. 若不可用，回退到默认 provider
        3. 若默认也不可用，回退到 ollama（本地）
        """
        target = name or settings.llm_default_provider

        if target in self._providers and self._providers[target].is_available():
            return self._providers[target]

        # 降级：默认厂商 → 任意可用 → ollama
        if settings.llm_default_provider in self._providers:
            p = self._providers[settings.llm_default_provider]
            if p.is_available():
                logger.warning("Provider %s 不可用，降级到 %s", target, settings.llm_default_provider)
                return p

        for name, p in self._providers.items():
            if p.is_available():
                logger.warning("Provider %s 不可用，降级到 %s", target, name)
                return p

        # 最终回退到 ollama
        logger.warning("所有 Provider 不可用，降级到 Ollama（本地）")
        return self._providers.get("ollama")

    def list_available(self) -> list[dict]:
        """列出所有可用 Provider"""
        result = []
        for name, p in self._providers.items():
            result.append({
                "provider": name,
                "display_name": PROVIDER_DISPLAY_NAMES.get(name, name),
                "available": p.is_available(),
            })
        return result

    def get_model_name(self, provider: str, tier: str) -> str:
        """获取指定厂商指定分级的模型名

        优先级：
        1. 全局环境变量覆盖 (LLM_MODEL_FAST 等)
        2. custom 厂商的专属配置 (CUSTOM_MODEL_FAST 等)
        3. 厂商默认模型表
        """
        # 1. 全局环境变量覆盖
        env_key = f"llm_model_{tier}"
        env_val = getattr(settings, env_key, "")
        if env_val:
            return env_val

        # 2. custom 厂商专属配置
        if provider == "custom":
            custom_key = f"custom_model_{tier}" if tier != "embedding" else "custom_embedding_model"
            custom_val = getattr(settings, custom_key, "")
            if custom_val:
                return custom_val

        # 3. 厂商默认模型表
        defaults = PROVIDER_DEFAULT_MODELS.get(provider, {})
        return defaults.get(tier, "")


# 全局单例
_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """获取 Provider 注册表单例"""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
