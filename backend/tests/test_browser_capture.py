import asyncio

import pytest

from app.core.exceptions import ValidationError
from app.infrastructure.parsers.browser_capture_parser import BrowserCaptureParser
from app.services.interfaces.content_parser import ParseResult


def test_browser_capture_combines_multiple_images_into_one_content(monkeypatch):
    downloaded = []

    async def fake_download(self, client, image_url, referer):
        downloaded.append((image_url, referer))
        return image_url.encode()

    async def fake_ocr(self, image, **kwargs):
        number = image.decode().rsplit("/", 1)[-1].split(".")[0]
        return ParseResult(
            title=f"图片 {number}",
            content=f"第 {number} 张图片里的知识文字",
            source_type="image",
        )

    async def allow_test_domain(url):
        return None

    monkeypatch.setattr(BrowserCaptureParser, "_download_image", fake_download)
    monkeypatch.setattr(
        "app.infrastructure.parsers.browser_capture_parser.OCRParser.parse",
        fake_ocr,
    )
    monkeypatch.setattr(
        "app.infrastructure.parsers.browser_capture_parser.JinaURLParser._ensure_public_url",
        allow_test_domain,
    )

    parser = BrowserCaptureParser()
    result = asyncio.run(
        parser.parse(
            {
                "url": "https://www.xiaohongshu.com/explore/test",
                "title": "多图绘画笔记",
                "text": "作者发布的正文内容。",
                "page_type": "image",
                "image_urls": [
                    "https://img.example.com/1.jpg",
                    "https://img.example.com/2.jpg",
                ],
            }
        )
    )

    assert len(downloaded) == 2
    assert "作者发布的正文内容" in result.content
    assert "第 1 张图片里的知识文字" in result.content
    assert "第 2 张图片里的知识文字" in result.content
    assert result.metadata["image_count"] == 2
    assert result.metadata["image_ocr_count"] == 2
    assert result.metadata["page_type"] == "image"


def test_browser_capture_video_requires_copy_or_existing_subtitles(monkeypatch):
    async def allow_test_domain(url):
        return None

    monkeypatch.setattr(
        "app.infrastructure.parsers.browser_capture_parser.JinaURLParser._ensure_public_url",
        allow_test_domain,
    )
    parser = BrowserCaptureParser()

    with pytest.raises(ValidationError, match="暂不转写视频音轨"):
        asyncio.run(
            parser.parse(
                {
                    "url": "https://www.xiaohongshu.com/explore/video",
                    "title": "没有文案的视频",
                    "text": "",
                    "page_type": "video",
                    "has_video": True,
                    "subtitle_text": "",
                    "image_urls": [],
                }
            )
        )


def test_browser_capture_rejects_private_media_address():
    parser = BrowserCaptureParser()

    with pytest.raises(ValidationError, match="内网链接"):
        asyncio.run(
            parser.parse(
                {
                    "url": "http://127.0.0.1/private",
                    "title": "内网页面",
                    "text": "这是一个不应该被导入的内网页面正文。",
                    "image_urls": [],
                }
            )
        )
