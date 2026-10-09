"""基于 Jina Reader 的 URL 解析器

对应架构文档 3.3 节 JinaURLParser。
通过 https://r.jina.ai 前缀抓取目标页面并转为 Markdown，
支持 B 站 / 知乎 / 小红书 / 公众号 / 抖音 等主流内容平台。
"""
import httpx

from app.core.config import settings
from app.services.interfaces.content_parser import IContentParser, ParseResult


class JinaURLParser(IContentParser):
    """基于 Jina Reader 的 URL 解析器"""

    def __init__(self, jina_api_key: str | None = None):
        self.base_url = "https://r.jina.ai"
        self.api_key = jina_api_key or settings.jina_api_key
        self.supported_sites = [
            "bilibili.com",
            "zhihu.com",
            "xiaohongshu.com",
            "mp.weixin.qq.com",
            "douyin.com",
        ]

    def can_parse(self, input_data: str, source_type: str) -> bool:
        """仅处理 url 类型"""
        return source_type == "url" and input_data.startswith("http")

    async def parse(self, input_data: str, **kwargs) -> ParseResult:
        """调用 Jina Reader 抓取并解析 URL 内容"""
        jina_url = f"{self.base_url}/{input_data}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-Return-Format"] = "markdown"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(jina_url, headers=headers)
            resp.raise_for_status()
            text = resp.text

        supplied_title = kwargs.get("title")
        title = supplied_title or self._extract_title(input_data, text)
        return ParseResult(
            title=title,
            content=text,
            source_type="url",
            source_url=input_data,
            metadata={"parser": "jina", "auto_title": not bool(supplied_title)},
        )

    @staticmethod
    def _extract_title(url: str, text: str) -> str:
        """从返回内容首行或 URL 推断标题"""
        for line in text.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                return line[:200]
        return url
