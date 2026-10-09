"""LLM 路由接口

对应架构文档 4 节 AI 引擎设计。
按任务类型选择模型分级（FAST / BALANCED / QUALITY），
支持降级策略与多供应商切换。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ModelTier(str, Enum):
    """模型质量分级"""

    FAST = "fast"        # 高频轻量任务
    BALANCED = "balanced"  # 平衡成本与质量
    QUALITY = "quality"  # 高质量任务


class TaskType(str, Enum):
    """AI 任务类型"""

    SUMMARIZE = "summarize"  # 内容总结
    DISTILL = "distill"      # 多来源材料语义提纯
    MERGE = "merge"          # 内容合并
    SEARCH = "search"        # 相似搜索
    ANSWER = "answer"        # 知识问答
    TREE = "tree"            # 知识树生成


@dataclass
class ModelConfig:
    """模型配置"""

    provider: str          # openai | anthropic | ...
    model_name: str
    tier: ModelTier
    max_input_tokens: int
    max_output_tokens: int


@dataclass
class LLMResponse:
    """LLM 响应"""

    content: str
    model: str
    usage: dict
    raw: Optional[dict] = None


class ILLMRouter(ABC):
    """LLM 路由器接口"""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        task_type: TaskType,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """按任务类型路由到合适模型并完成调用"""
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """生成文本嵌入向量"""
        pass
