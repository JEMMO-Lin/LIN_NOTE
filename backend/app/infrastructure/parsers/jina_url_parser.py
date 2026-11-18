"""URL 内容解析器。

普通网页优先由后端直接读取，避免链接导入完全依赖单个第三方服务；
直接读取失败或页面内容不足时，再使用 Jina Reader 解析动态页面。
"""

import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services.interfaces.content_parser import IContentParser, ParseResult


_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_REDIRECTS = 5
_MIN_USEFUL_TEXT_LENGTH = 20
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_UNAVAILABLE_PAGE_MARKERS = {
    "你访问的页面不见了",
    "访问的页面不存在",
    "页面不存在",
    "内容不存在",
    "笔记不存在",
    "笔记已删除",
    "该内容已删除",
    "page not found",
    "404 not found",
}
_BLOCKED_HTML_TAGS = {"script", "style", "noscript", "svg", "nav", "form"}
_BLOCK_TAGS = {
    "article",
    "aside",
    "blockquote",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "p",
    "pre",
    "section",
    "table",
    "td",
    "th",
    "tr",
}


class _UnavailablePageError(ValueError):
    """Raised when a successful HTTP response is an error/interstitial page."""


class _HTMLTextExtractor(HTMLParser):
    """Small dependency-free HTML-to-text extractor for ordinary articles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked_depth = 0
        self._in_title = False
        self._parts: list[str] = []
        self._title_parts: list[str] = []
        self.meta_title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _BLOCKED_HTML_TAGS:
            self._blocked_depth += 1
            return
        if self._blocked_depth:
            return
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            values = {key.lower(): value or "" for key, value in attrs}
            if values.get("property", "").lower() == "og:title":
                self.meta_title = values.get("content", "").strip()
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _BLOCKED_HTML_TAGS:
            self._blocked_depth = max(0, self._blocked_depth - 1)
            return
        if self._blocked_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._blocked_depth or not data.strip():
            return
        if self._in_title:
            self._title_parts.append(data)
        self._parts.append(data)

    @staticmethod
    def _clean(parts: list[str]) -> str:
        text = " ".join(parts)
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @property
    def title(self) -> str:
        return self.meta_title or self._clean(self._title_parts)

    @property
    def text(self) -> str:
        return self._clean(self._parts)


class JinaURLParser(IContentParser):
    """Read a public HTTP(S) page directly and fall back to Jina Reader."""

    def __init__(
        self,
        jina_api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = "https://r.jina.ai"
        self.api_key = jina_api_key or settings.jina_api_key
        self.transport = transport

    def can_parse(self, input_data: str, source_type: str) -> bool:
        return source_type == "url" and input_data.lower().startswith(("http://", "https://"))

    async def parse(self, input_data: str, **kwargs) -> ParseResult:
        """Parse a URL with a local-first, third-party-fallback strategy."""
        target_url = self._normalize_url(input_data)
        await self._ensure_public_url(target_url)

        errors: list[str] = []
        try:
            text, detected_title = await self._parse_direct(target_url)
            parser_name = "direct"
        except (httpx.HTTPError, UnicodeError, ValueError) as exc:
            errors.append(f"direct: {type(exc).__name__}")
            try:
                text, detected_title = await self._parse_with_jina(target_url)
                parser_name = "jina"
            except (httpx.HTTPError, UnicodeError, ValueError) as jina_exc:
                errors.append(f"jina: {type(jina_exc).__name__}")
                if isinstance(jina_exc, _UnavailablePageError):
                    message = (
                        "该链接当前返回“页面不存在或访问受限”，未保存到知识库。"
                        "请先在浏览器确认链接有效，或改用“粘贴文本”导入"
                    )
                else:
                    message = (
                        "暂时无法读取该链接，请确认网页可公开访问，"
                        "或改用“粘贴文本”导入"
                    )
                raise ValidationError(
                    message,
                    detail={"attempts": errors},
                ) from jina_exc

        if not self._has_useful_text(text) or self._looks_like_unavailable_page(
            detected_title, text
        ):
            raise ValidationError(
                "该链接没有提取到可读正文，请改用“粘贴文本”导入"
            )

        supplied_title = kwargs.get("title")
        return ParseResult(
            title=(supplied_title or detected_title or target_url)[:200],
            content=text,
            source_type="url",
            source_url=target_url,
            metadata={"parser": parser_name, "auto_title": not bool(supplied_title)},
        )

    async def _parse_direct(self, target_url: str) -> tuple[str, str]:
        headers = {
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36 KnowFlow/1.0"
            ),
        }
        timeout = httpx.Timeout(15.0, connect=8.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            response, final_url = await self._get_with_safe_redirects(
                client, target_url, headers
            )

        content_type = response.headers.get("content-type", "").lower()
        if not any(
            kind in content_type
            for kind in ("text/html", "application/xhtml+xml", "text/plain")
        ):
            raise ValueError("unsupported content type")

        body = response.content
        encoding = response.encoding or "utf-8"
        decoded = body.decode(encoding, errors="replace")
        if "html" not in content_type:
            text = decoded.strip()
            title = self._extract_title(final_url, text)
            if self._looks_like_unavailable_page(title, text):
                raise _UnavailablePageError(
                    "website returned an unavailable page"
                )
            if not self._has_useful_text(text):
                raise ValueError("page has no useful text")
            return text, title

        extractor = _HTMLTextExtractor()
        extractor.feed(decoded)
        text = extractor.text
        title = extractor.title or self._extract_title(final_url, text)
        if self._looks_like_unavailable_page(title, text):
            raise _UnavailablePageError("website returned an unavailable page")
        if not self._has_useful_text(text):
            raise ValueError("page has no useful text")
        return text, title

    async def _get_with_safe_redirects(
        self,
        client: httpx.AsyncClient,
        target_url: str,
        headers: dict[str, str],
    ) -> tuple[httpx.Response, str]:
        current_url = target_url
        for redirect_count in range(_MAX_REDIRECTS + 1):
            await self._ensure_public_url(current_url)
            async with client.stream("GET", current_url, headers=headers) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location or redirect_count == _MAX_REDIRECTS:
                        raise httpx.TooManyRedirects(
                            "too many redirects", request=response.request
                        )
                    current_url = self._normalize_url(urljoin(current_url, location))
                    continue

                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > _MAX_RESPONSE_BYTES:
                        raise ValueError("page is too large")

                # The streamed response is about to close; create a detached
                # response carrying the already-decoded, bounded body. Strip
                # transport headers so httpx does not try to decompress it a
                # second time.
                detached_headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower()
                    not in {"content-encoding", "content-length", "transfer-encoding"}
                }
                return (
                    httpx.Response(
                        status_code=response.status_code,
                        headers=detached_headers,
                        content=bytes(content),
                        request=response.request,
                    ),
                    current_url,
                )
        raise ValueError("unreachable redirect state")

    async def _parse_with_jina(self, target_url: str) -> tuple[str, str]:
        headers = {
            "Accept": "text/markdown",
            "X-Return-Format": "markdown",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        jina_url = f"{self.base_url}/{target_url}"
        timeout = httpx.Timeout(20.0, connect=8.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            raw_text = await self._request_jina(client, jina_url, headers)
            text, title = self._extract_jina_content(raw_text, target_url)

            # Jina can return a cached HTTP-200 snapshot of a platform's error
            # page. Retry once without cache before deciding the source is
            # unavailable; never persist the interstitial as article content.
            if self._looks_like_unavailable_page(title, text):
                fresh_headers = {**headers, "X-No-Cache": "true"}
                try:
                    raw_text = await self._request_jina(
                        client, jina_url, fresh_headers
                    )
                except httpx.HTTPError as exc:
                    raise _UnavailablePageError(
                        "fresh Jina request confirmed the source is unavailable"
                    ) from exc
                text, title = self._extract_jina_content(raw_text, target_url)

        if self._looks_like_unavailable_page(title, text):
            raise _UnavailablePageError("Jina returned an unavailable page")
        if not self._has_useful_text(text):
            raise ValueError("Jina returned no useful text")
        return text, title or self._extract_title(target_url, text)

    @staticmethod
    async def _request_jina(
        client: httpx.AsyncClient,
        jina_url: str,
        headers: dict[str, str],
    ) -> str:
        response = await client.get(jina_url, headers=headers)
        response.raise_for_status()
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise ValueError("Jina response is too large")
        return response.text.strip()

    @staticmethod
    def _extract_jina_content(raw_text: str, fallback_url: str) -> tuple[str, str]:
        """Remove Jina's metadata envelope and return only the page content."""
        title_match = re.search(r"(?mi)^Title:\s*(.+?)\s*$", raw_text)
        title = title_match.group(1).strip() if title_match else ""
        content_match = re.search(r"(?mi)^Markdown Content:\s*$", raw_text)
        content = (
            raw_text[content_match.end() :].strip()
            if content_match
            else raw_text.strip()
        )
        return content, title or JinaURLParser._extract_title(fallback_url, content)

    @staticmethod
    def _normalize_url(url: str) -> str:
        value = url.strip()
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise ValidationError("链接格式不正确，请输入完整的 http 或 https 地址") from exc
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValidationError("链接格式不正确，请输入完整的 http 或 https 地址")
        if parsed.username or parsed.password:
            raise ValidationError("链接不能包含用户名或密码")
        host = parsed.hostname.encode("idna").decode("ascii")
        netloc = f"[{host}]" if ":" in host else host
        if port is not None:
            netloc = f"{netloc}:{port}"
        return urlunsplit(
            (parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, "")
        )

    @staticmethod
    async def _ensure_public_url(url: str) -> None:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValidationError("链接缺少有效域名")

        try:
            addresses = [ipaddress.ip_address(hostname)]
        except ValueError:
            try:
                info = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: socket.getaddrinfo(
                        hostname,
                        parsed.port or (443 if parsed.scheme == "https" else 80),
                        type=socket.SOCK_STREAM,
                    ),
                )
            except socket.gaierror as exc:
                raise ValidationError("无法解析该链接的域名，请检查网址是否正确") from exc
            addresses = list({ipaddress.ip_address(item[4][0]) for item in info})

        if not addresses or any(not address.is_global for address in addresses):
            raise ValidationError("出于安全原因，不能导入本机或内网链接")

    @staticmethod
    def _has_useful_text(text: str) -> bool:
        compact = re.sub(r"\s+", "", text)
        return len(compact) >= _MIN_USEFUL_TEXT_LENGTH

    @staticmethod
    def _looks_like_unavailable_page(title: str, text: str) -> bool:
        normalized_title = re.sub(r"\s+", " ", title).strip().lower()
        normalized_text = re.sub(r"\s+", " ", text).strip().lower()
        combined = f"{normalized_title}\n{normalized_text}"
        if any(marker in combined for marker in _UNAVAILABLE_PAGE_MARKERS):
            return True

        # Common Chinese platform interstitial: avoid a broad single-phrase
        # match so an article discussing browser extensions is not rejected.
        interstitial_markers = (
            "返回上一页",
            "我要申诉",
            "我知道了",
            "广告屏蔽插件",
        )
        return sum(marker in combined for marker in interstitial_markers) >= 2

    @staticmethod
    def _extract_title(url: str, text: str) -> str:
        for line in text.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                return line[:200]
        return url
