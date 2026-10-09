"""OpenAI 兼容 Provider

适用于所有遵循 OpenAI API 协议的厂商：
- OpenAI 官方
- DeepSeek
- Moonshot (Kimi)
- 通义千问 (DashScope 兼容模式)
- Ollama (本地部署)
- 其他 OpenAI 兼容服务

只需配置不同的 base_url 和 api_key 即可切换厂商。
"""
import logging
import asyncio
from typing import Optional

import httpx

from app.infrastructure.llm.providers.base import ILLMProvider
from app.services.interfaces.llm_router import LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(ILLMProvider):
    """OpenAI 兼容协议 Provider"""

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        api_key: str,
        timeout: float = 20.0,
    ):
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """调用 /chat/completions 接口"""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        attempts = 1 if self.provider_name == "ollama" else 2
        timeout = 2.0 if self.provider_name == "ollama" else self.timeout
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                break
            except Exception as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.5)
        else:
            raise last_error or RuntimeError("LLM 请求失败")

        choice = data["choices"][0]["message"]["content"]
        return LLMResponse(
            content=choice,
            model=data.get("model", model),
            usage=data.get("usage", {}),
            raw=data,
        )

    async def embedding(
        self,
        model: str,
        text: str,
    ) -> list[float]:
        """调用 /embeddings 接口"""
        timeout = 2.0 if self.provider_name == "ollama" else 30.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={"model": model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
        return data["data"][0]["embedding"]
