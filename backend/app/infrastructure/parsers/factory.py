"""解析器工厂

对应架构文档 3.2 节 ParserFactory。
根据来源类型调度对应解析器，遵循可插拔原则——新增解析器仅需注册即可。
"""
from typing import Optional

from app.core.exceptions import ValidationError
from app.infrastructure.parsers.jina_url_parser import JinaURLParser
from app.infrastructure.parsers.ocr_parser import OCRParser
from app.infrastructure.parsers.text_parser import TextParser
from app.services.interfaces.content_parser import IContentParser


class ParserFactory:
    """解析器工厂"""

    def __init__(self):
        self._parsers: list[IContentParser] = [
            JinaURLParser(),
            TextParser(),
            OCRParser(),
        ]

    def register(self, parser: IContentParser) -> None:
        """注册自定义解析器"""
        self._parsers.append(parser)

    def get_parser(self, input_data: str, source_type: str) -> IContentParser:
        """根据输入与来源类型返回首个匹配的解析器"""
        for parser in self._parsers:
            if parser.can_parse(input_data, source_type):
                return parser
        raise ValidationError(
            "不支持的来源类型", detail={"source_type": source_type}
        )


# 全局单例
_parser_factory: Optional[ParserFactory] = None


def get_parser_factory() -> ParserFactory:
    """获取解析器工厂单例"""
    global _parser_factory
    if _parser_factory is None:
        _parser_factory = ParserFactory()
    return _parser_factory
