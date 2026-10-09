"""检索服务接口

对应架构文档 6 节向量检索设计。
定义检索抽象，由基础设施层提供向量 / 关键词 / 混合检索实现。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchHit:
    """检索命中项"""

    point_id: str
    title: str
    content: str
    score: float
    content_id: Optional[str] = None
    kb_id: Optional[str] = None


class ISearchService(ABC):
    """检索服务接口"""

    @abstractmethod
    async def search(
        self,
        query: str,
        kb_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> list[SearchHit]:
        """检索

        mode:
        - vector: 纯向量检索
        - keyword: 纯关键词检索
        - hybrid: 混合检索（推荐）
        """
        pass
