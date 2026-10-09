"""Anthropic Claude Provider

Anthropic 使用独立的 API 协议（Messages API），
与 OpenAI 不兼容，需单独适配。
"""
import logging
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.infrastructure.llm.providers.base import ILLMProvider
from app.services.interfaces.llm_router import LLMResponse

logger = logging.getLogger(__name__)

# Anthropic API 版本
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider(ILLMProvider):
    """Anthropic Claude Provider"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        timeout: float = 60.0,
    ):
        self.provider_name = "anthropic"
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """调用 Anthropic Messages API

        Anthropic 的消息格式与 OpenAI 不同：
        - system 消息需单独传入 system 参数
        - 其余消息 role 只能是 user / assistant
        """
        # 提取 system 消息
        system_content = ""
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            else:
                filtered_messages.append(msg)

        payload = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_content.strip():
            payload["system"] = system_content.strip()
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # Anthropic 返回格式: {"content": [{"type": "text", "text": "..."}], ...}
        content_parts = data.get("content", [])
        content = "".join(
            part["text"] for part in content_parts if part.get("type") == "text"
        )

        return LLMResponse(
            content=content,
            model=data.get("model", model),
            usage={
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
            raw=data,
        )

    async def embedding(
        self,
        model: str,
        text: str,
    ) -> list[float]:
        """Anthropic 暂不提供 Embedding API，降级报错"""
        raise NotImplementedError(
            "Anthropic 不提供 Embedding API，请在配置中指定其他厂商的 Embedding 模型"
        )
