"""LLM Provider 基类

定义所有厂商 Provider 的统一接口。
每个 Provider 负责与特定厂商 API 通信，对上层透明。
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.services.interfaces.llm_router import LLMResponse


class ILLMProvider(ABC):
    """LLM 厂商 Provider 接口"""

    provider_name: str = ""

    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        """对话补全

        Args:
            model: 模型名称
            messages: 消息列表 [{"role": "system|user|assistant", "content": "..."}]
            max_tokens: 最大输出 token 数
            temperature: 采样温度
        """
        pass

    @abstractmethod
    async def embedding(
        self,
        model: str,
        text: str,
    ) -> list[float]:
        """文本向量化"""
        pass

    def is_available(self) -> bool:
        """检查 Provider 是否可用（如 API Key 是否配置）"""
        return True
