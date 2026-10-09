"""纯文本解析器

直接存储输入文本，不做外部抓取。
"""
from app.services.interfaces.content_parser import IContentParser, ParseResult


class TextParser(IContentParser):
    """纯文本解析器"""

    def can_parse(self, input_data: str, source_type: str) -> bool:
        return source_type == "text"

    async def parse(self, input_data: str, **kwargs) -> ParseResult:
        supplied_title = kwargs.get("title")
        title = supplied_title or self._derive_title(input_data)
        return ParseResult(
            title=title,
            content=input_data,
            source_type="text",
            metadata={
                "parser": "text",
                **({"auto_title": True} if not supplied_title else {}),
            },
        )

    @staticmethod
    def _derive_title(text: str) -> str:
        first_line = text.strip().splitlines()[0] if text.strip() else "未命名"
        return first_line[:200]
