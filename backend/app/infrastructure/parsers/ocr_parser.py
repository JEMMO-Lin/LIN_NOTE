"""基于 Tesseract 的本地 OCR 解析器。"""
import io

from app.core.exceptions import ValidationError
from app.services.interfaces.content_parser import IContentParser, ParseResult


class OCRParser(IContentParser):
    """OCR 图片解析器"""

    def can_parse(self, input_data: str, source_type: str) -> bool:
        return source_type == "image"

    async def parse(self, input_data, **kwargs) -> ParseResult:
        """识别图片文字

        input_data: 图片二进制或路径
        """
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(input_data))
            try:
                text = pytesseract.image_to_string(image, lang="chi_sim+eng")
            except pytesseract.TesseractError:
                text = pytesseract.image_to_string(image, lang="eng")
        except ImportError as exc:
            raise ValidationError("OCR 依赖未安装，请重新安装后端依赖") from exc
        except Exception as exc:
            raise ValidationError(f"图片识别失败：{exc}") from exc
        title_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return ParseResult(
            title=title_line[:80] or "图片内容",
            content=text.strip(),
            source_type="image",
            metadata={"parser": "tesseract", "auto_title": True},
        )
