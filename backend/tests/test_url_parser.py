import asyncio
import gzip

import httpx
import pytest

from app.core.exceptions import ValidationError
from app.infrastructure.parsers.jina_url_parser import JinaURLParser


class _PublicTestParser(JinaURLParser):
    @staticmethod
    async def _ensure_public_url(url: str) -> None:
        # MockTransport never opens a socket; DNS validation is covered by the
        # separate private-address test below.
        return None


def test_url_parser_reads_ordinary_html_without_jina():
    requested_hosts = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        html = """
            <html>
              <head><title>普通网页标题</title><script>不应保留的脚本</script></head>
              <body><nav>不应保留的导航</nav><article>这是可直接提取的网页正文，包含足够多的有效文字。</article></body>
            </html>
        """
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html; charset=utf-8",
                "content-encoding": "gzip",
            },
            content=gzip.compress(html.encode()),
        )

    parser = _PublicTestParser(transport=httpx.MockTransport(handler))
    result = asyncio.run(parser.parse(" https://example.com/article#comments "))

    assert requested_hosts == ["example.com"]
    assert result.title == "普通网页标题"
    assert "可直接提取的网页正文" in result.content
    assert "不应保留的脚本" not in result.content
    assert "不应保留的导航" not in result.content
    assert result.source_url == "https://example.com/article"
    assert result.metadata["parser"] == "direct"


def test_url_parser_falls_back_to_jina_when_direct_read_fails():
    requested_hosts = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        if request.url.host == "example.com":
            return httpx.Response(403, text="blocked")
        return httpx.Response(
            200,
            headers={"content-type": "text/markdown; charset=utf-8"},
            text="# Jina 解析标题\n\n这是第三方解析器返回的完整网页正文。",
        )

    parser = _PublicTestParser(transport=httpx.MockTransport(handler))
    result = asyncio.run(parser.parse("https://example.com/dynamic"))

    assert requested_hosts == ["example.com", "r.jina.ai"]
    assert result.title == "Jina 解析标题"
    assert result.metadata["parser"] == "jina"


def test_url_parser_bypasses_cached_error_page_and_strips_jina_envelope():
    requests = []
    cached_error = """Title: 你访问的页面不见了

URL Source: https://xhslink.cn/o/example

Warning: This is a cached snapshot of the original page, consider retry with caching opt-out.

Markdown Content:
你访问的页面不见了，你还可以返回上一页。

我要申诉 我知道了
"""
    fresh_page = """Title: 有效的小红书笔记

URL Source: https://www.xiaohongshu.com/explore/example

Markdown Content:
这是绕过缓存后提取到的有效笔记正文，其中包含足够多的知识内容。
"""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.host, request.headers.get("x-no-cache")))
        if request.url.host == "xhslink.cn":
            return httpx.Response(404, text="not found")
        return httpx.Response(
            200,
            headers={"content-type": "text/markdown; charset=utf-8"},
            text=fresh_page if request.headers.get("x-no-cache") == "true" else cached_error,
        )

    parser = _PublicTestParser(transport=httpx.MockTransport(handler))
    result = asyncio.run(parser.parse("https://xhslink.cn/o/example"))

    assert requests == [
        ("xhslink.cn", None),
        ("r.jina.ai", None),
        ("r.jina.ai", "true"),
    ]
    assert result.title == "有效的小红书笔记"
    assert result.content.startswith("这是绕过缓存后提取到的有效笔记正文")
    assert "URL Source:" not in result.content
    assert "cached snapshot" not in result.content
    assert result.metadata["parser"] == "jina"


def test_url_parser_rejects_cached_error_page_when_fresh_page_is_unavailable():
    jina_headers = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "xhslink.cn":
            return httpx.Response(404, text="not found")
        jina_headers.append(request.headers.get("x-no-cache"))
        if request.headers.get("x-no-cache") == "true":
            return httpx.Response(404, text="not found")
        return httpx.Response(
            200,
            headers={"content-type": "text/markdown; charset=utf-8"},
            text="""Title: 你访问的页面不见了

Warning: This is a cached snapshot of the original page.

Markdown Content:
你访问的页面不见了。返回上一页，我要申诉，我知道了。
""",
        )

    parser = _PublicTestParser(transport=httpx.MockTransport(handler))

    with pytest.raises(ValidationError, match="页面不存在或访问受限"):
        asyncio.run(parser.parse("https://xhslink.cn/o/expired"))
    assert jina_headers == [None, "true"]


def test_url_parser_returns_actionable_error_when_both_readers_fail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    parser = _PublicTestParser(transport=httpx.MockTransport(handler))

    with pytest.raises(ValidationError, match="粘贴文本"):
        asyncio.run(parser.parse("https://example.com/unavailable"))


def test_url_parser_rejects_private_network_addresses():
    parser = JinaURLParser()

    with pytest.raises(ValidationError, match="内网链接"):
        asyncio.run(parser.parse("http://127.0.0.1:8000/private"))
