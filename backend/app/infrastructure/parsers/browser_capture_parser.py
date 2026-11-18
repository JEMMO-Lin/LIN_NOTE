"""Parser for content collected inside the user's authenticated browser."""

from urllib.parse import urljoin

import httpx

from app.core.exceptions import ValidationError
from app.infrastructure.parsers.jina_url_parser import JinaURLParser
from app.infrastructure.parsers.ocr_parser import OCRParser
from app.services.interfaces.content_parser import IContentParser, ParseResult


_MAX_IMAGES = 10
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class BrowserCaptureParser(IContentParser):
    """Combine browser-visible text, subtitles and multi-image OCR."""

    def can_parse(self, input_data: str, source_type: str) -> bool:
        return source_type == "browser"

    async def parse(self, input_data: dict, **kwargs) -> ParseResult:
        page_url = JinaURLParser._normalize_url(str(input_data.get("url", "")))
        await JinaURLParser._ensure_public_url(page_url)

        title = str(input_data.get("title") or "浏览器采集内容").strip()[:500]
        page_type = str(input_data.get("page_type") or "article")
        visible_text = str(input_data.get("text") or "").strip()
        subtitle_text = str(input_data.get("subtitle_text") or "").strip()
        image_urls = list(dict.fromkeys(input_data.get("image_urls") or []))[
            :_MAX_IMAGES
        ]

        if JinaURLParser._looks_like_unavailable_page(title, visible_text):
            raise ValidationError(
                "当前浏览器页面是错误页或访问受限提示，未保存到知识库"
            )

        text_parts: list[str] = []
        if visible_text:
            text_parts.append(visible_text)
        if subtitle_text and subtitle_text not in visible_text:
            text_parts.append(f"视频字幕：\n{subtitle_text}")

        ocr_success_count = 0
        image_failures: list[dict[str, str | int]] = []
        if image_urls:
            timeout = httpx.Timeout(15.0, connect=8.0)
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
            ) as client:
                for index, image_url in enumerate(image_urls, start=1):
                    try:
                        image = await self._download_image(
                            client, str(image_url), referer=page_url
                        )
                        result = await OCRParser().parse(image)
                        if result.content.strip():
                            text_parts.append(
                                f"图片 {index} OCR：\n{result.content.strip()}"
                            )
                            ocr_success_count += 1
                    except Exception as exc:
                        image_failures.append(
                            {"index": index, "reason": type(exc).__name__}
                        )

        content = "\n\n".join(part for part in text_parts if part.strip()).strip()
        if len("".join(content.split())) < 10:
            if page_type == "video" and not subtitle_text:
                raise ValidationError(
                    "该视频页面没有可读取的文案或字幕。浏览器采集暂不转写视频音轨，"
                    "请改用文本或字幕导入"
                )
            raise ValidationError(
                "浏览器没有采集到足够的正文或图片文字，请确认页面内容已经加载完成"
            )

        return ParseResult(
            title=title,
            content=content,
            source_type="url",
            source_url=page_url[:500],
            metadata={
                "parser": "browser_capture",
                "auto_title": not bool(input_data.get("title")),
                "page_type": page_type,
                "image_count": len(image_urls),
                "image_ocr_count": ocr_success_count,
                "image_failures": image_failures,
                "has_video": bool(input_data.get("has_video")),
                "has_subtitles": bool(subtitle_text),
                "video_duration": input_data.get("video_duration"),
                "captured_at": input_data.get("captured_at"),
            },
        )

    async def _download_image(
        self,
        client: httpx.AsyncClient,
        image_url: str,
        referer: str,
    ) -> bytes:
        current_url = JinaURLParser._normalize_url(image_url)
        headers = {
            "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.5",
            "Referer": referer,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        }

        for redirect_count in range(4):
            await JinaURLParser._ensure_public_url(current_url)
            async with client.stream("GET", current_url, headers=headers) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location or redirect_count == 3:
                        raise ValueError("image redirected too many times")
                    current_url = JinaURLParser._normalize_url(
                        urljoin(current_url, location)
                    )
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if not content_type.startswith("image/"):
                    raise ValueError("media URL did not return an image")

                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > _MAX_IMAGE_BYTES:
                        raise ValueError("image is larger than 10 MB")
                if not content:
                    raise ValueError("empty image")
                return bytes(content)

        raise ValueError("unreachable redirect state")
