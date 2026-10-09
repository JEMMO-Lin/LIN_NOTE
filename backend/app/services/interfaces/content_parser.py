"""内容解析器接口

对应架构文档 3.3 节 IContentParser。
所有解析器（URL / 文本 / OCR）均实现此接口，通过 ParserFactory 装配。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParseResult:
    """解析结果"""

    title: str
    content: str
    source_type: str  # url|text|image
    source_url: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class IContentParser(ABC):
    """内容解析器接口"""

    @abstractmethod
    def can_parse(self, input_data: str, source_type: str) -> bool:
        """判断是否可以解析该输入"""
        pass

    @abstractmethod
    async def parse(self, input_data: str, **kwargs) -> ParseResult:
        """解析内容"""
        pass
