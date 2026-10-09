"""Deterministic safety net for removing common ingestion noise.

The LLM performs the semantic filtering.  These rules cover obvious ads, page
chrome and OCR garbage when the model is unavailable or returns malformed JSON.
They deliberately work line-by-line so useful surrounding material is retained.
"""
import re


NOISE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:扫码|扫描).{0,12}(?:购买|咨询|报名|进群|添加|领取)",
        r"(?:加|添加|联系)(?:微信|vx|v信|客服|助教|老师)",
        r"(?:限时|立即|点击).{0,12}(?:购买|报名|抢购|下单|领取)",
        r"(?:课程|训练营|会员).{0,10}(?:售价|优惠价|原价|现价|仅需|报名)",
        r"(?:关注|点赞|收藏|转发|投币|一键三连|订阅).{0,12}(?:我|我们|账号|频道|公众号)?",
        r"(?:商务合作|广告合作|课程咨询|购买链接|报名链接|客服微信)",
        r"(?:copyright|版权所有|未经许可不得转载|免责声明)",
        r"^(?:首页|登录|注册|上一页|下一页|返回顶部|展开全文|阅读原文)$",
        r"^(?:https?://|www\.)\S+$",
    )
]


def _normalize_line(line: str) -> str:
    return re.sub(r"[ \t\u3000]+", " ", line).strip()


def is_noise_line(line: str) -> bool:
    normalized = _normalize_line(line)
    if not normalized:
        return True
    # OCR commonly produces lines containing almost no letters or numbers.
    meaningful = re.sub(r"[^\w\u4e00-\u9fff]", "", normalized)
    if len(meaningful) < 2 and len(normalized) > 1:
        return True
    return any(pattern.search(normalized) for pattern in NOISE_PATTERNS)


def clean_content_locally(text: str) -> str:
    """Remove obvious noise, duplicate lines and excessive whitespace."""
    kept: list[str] = []
    seen: set[str] = set()
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        # Split mixed lines so a useful sentence is not discarded merely
        # because an advertisement follows it on the same OCR line.
        units = re.split(r"(?<=[。！？!?；;])", raw_line)
        for raw_unit in units:
            unit = _normalize_line(raw_unit)
            if is_noise_line(unit):
                continue
            fingerprint = re.sub(r"\W+", "", unit).casefold()
            if fingerprint and fingerprint not in seen:
                seen.add(fingerprint)
                kept.append(unit)
    return "\n".join(kept).strip()
