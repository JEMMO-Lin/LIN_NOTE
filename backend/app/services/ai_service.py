"""AI 服务

对应架构文档 4 节。
职责：通过 LLM 路由器完成内容总结、合并、问答、知识树生成等 AI 任务，
结合 Prompt 管理器与缓存策略。
"""
import json
import logging
import re
from typing import Optional

from app.services.interfaces.llm_router import ILLMRouter, TaskType
from app.services.content_filter import clean_content_locally

logger = logging.getLogger(__name__)


def _parse_llm_json(text: str, default=None):
    """健壮地解析 LLM 返回的 JSON

    LLM 可能返回：
    - 标准 JSON
    - Markdown 代码块包裹的 JSON
    - 带额外文字的 JSON
    """
    if default is None:
        default = []

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 代码块中提取
    match = re.search(r"```json\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { 或 [ 到最后一个 } 或 ]
    for pattern in [(r"\{.*\}", True), (r"\[.*\]", False)]:
        p, is_obj = pattern
        match = re.search(p, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    logger.warning("无法解析 LLM JSON 输出，返回默认值: %s...", text[:100])
    return default


class AIService:
    """AI 应用服务"""

    # Small enough for Chinese OCR/transcripts to return complete JSON even on
    # providers whose balanced model has a modest output-token limit.
    MAX_CHUNK_CHARS = 3500

    def __init__(
        self,
        llm_router: ILLMRouter,
        prompt_manager,
        cache=None,
    ):
        self.llm = llm_router
        self.prompts = prompt_manager
        self.cache = cache

    async def distill_content(self, text: str, source_type: str = "text") -> dict:
        """Turn parsed source material into the canonical knowledge text."""
        chunks = self._chunk_text(text)
        results = [
            await self._distill_once(chunk, source_type)
            for chunk in chunks
        ]
        if len(results) == 1:
            return results[0]

        key_information = list(dict.fromkeys(
            str(value).strip()
            for result in results
            for value in result.get("key_information", [])
            if str(value).strip()
        ))
        removed_types = list(dict.fromkeys(
            str(value).strip()
            for result in results
            for value in result.get("removed_noise_types", [])
            if str(value).strip()
        ))
        combined = clean_content_locally(
            "\n\n".join(result.get("distilled_text", "") for result in results)
        )
        return {
            "main_topic": next(
                (result.get("main_topic", "") for result in results if result.get("main_topic")),
                "",
            ),
            "distilled_text": combined,
            "key_information": key_information,
            "removed_noise_types": removed_types,
            "method": "llm_chunked",
        }

    async def _distill_once(self, text: str, source_type: str) -> dict:
        prompt = self.prompts.render(
            "distill", text=text, source_type=source_type
        )
        try:
            resp = await self.llm.complete(prompt, task_type=TaskType.DISTILL)
            result = _parse_llm_json(resp.content, default={})
            if not isinstance(result, dict):
                raise ValueError("内容提纯结果不是 JSON 对象")
            if "distilled_text" not in result:
                raise ValueError("内容提纯结果缺少 distilled_text")
            distilled = clean_content_locally(str(result["distilled_text"]))
            key_information = result.get("key_information", [])
            removed_types = result.get("removed_noise_types", [])
            return {
                "main_topic": str(result.get("main_topic", "")).strip(),
                "distilled_text": distilled,
                "key_information": key_information if isinstance(key_information, list) else [],
                "removed_noise_types": removed_types if isinstance(removed_types, list) else [],
                "method": "llm",
            }
        except Exception as exc:
            logger.warning("LLM 内容提纯不可用，启用本地降噪: %s", exc)
            return {
                "main_topic": "",
                "distilled_text": clean_content_locally(text),
                "key_information": [],
                "removed_noise_types": ["规则识别的推广、页面组件或 OCR 噪声"],
                "method": "local_fallback",
            }

    async def summarize(
        self,
        text: str,
        style: str = "medium",
        fields: list[dict] | None = None,
    ) -> dict:
        """内容总结，返回结构化 dict"""
        chunks = self._chunk_text(text)
        if len(chunks) > 1:
            partials = [
                await self._summarize_once(chunk, style="brief", fields=None)
                for chunk in chunks
            ]
            combined = "\n".join(
                str(partial.get("summary", "")) for partial in partials
            )
            return await self._summarize_once(combined, style, fields)
        return await self._summarize_once(text, style, fields)

    async def _summarize_once(
        self, text: str, style: str, fields: list[dict] | None
    ) -> dict:
        prompt = self.prompts.build_summary_prompt(text, style=style, fields=fields)
        try:
            resp = await self.llm.complete(prompt, task_type=TaskType.SUMMARIZE)
            result = _parse_llm_json(resp.content, default={"summary": resp.content})
            if isinstance(result, dict):
                return result
            return {"summary": str(result)}
        except Exception as exc:
            logger.warning("LLM 总结不可用，启用本地降级: %s", exc)
            return self._fallback_summary(text, fields)

    async def merge(self, contents: list[str]) -> str:
        """内容合并（去重融合）"""
        joined = "\n\n---\n\n".join(contents)
        prompt = self.prompts.render("merge", content=joined)
        try:
            resp = await self.llm.complete(prompt, task_type=TaskType.MERGE)
            return resp.content
        except Exception as exc:
            logger.warning("LLM 合并不可用，启用本地降级: %s", exc)
            return self._fallback_merge(contents)

    async def extract_knowledge_points(self, text: str) -> list[dict]:
        """从文本提取知识点列表

        返回格式: [{"title": "...", "content": "...", "category": "..."}]
        """
        all_points = []
        for chunk in self._chunk_text(text):
            all_points.extend(await self._extract_points_once(chunk))
        unique = []
        fingerprints = set()
        for point in all_points:
            fingerprint = re.sub(
                r"\W+", "", f"{point.get('title', '')}{point.get('content', '')}"
            ).casefold()
            if fingerprint and fingerprint not in fingerprints:
                fingerprints.add(fingerprint)
                unique.append(point)
        return unique

    async def _extract_points_once(self, text: str) -> list[dict]:
        prompt = self.prompts.render("extract_points", text=text)
        try:
            resp = await self.llm.complete(prompt, task_type=TaskType.SUMMARIZE)
            points = _parse_llm_json(resp.content, default=[])
        except Exception as exc:
            logger.warning("LLM 知识点提取不可用，启用本地降级: %s", exc)
            return self._fallback_points(text)

        if not isinstance(points, list):
            if isinstance(points, dict) and "points" in points:
                points = points["points"]
            else:
                points = [points]

        # 规范化每个知识点
        normalized = []
        for i, p in enumerate(points):
            if not isinstance(p, dict):
                normalized.append({
                    "title": f"知识点 {i+1}",
                    "content": str(p),
                    "category": "",
                })
                continue

            normalized.append({
                "title": p.get("title", p.get("name", f"知识点 {i+1}")),
                "content": p.get("content", p.get("text", str(p))),
                "category": p.get("category", p.get("tag", "")),
                "importance": p.get("importance", 0.5),
            })
        return [
            point
            for point in normalized
            if str(point["title"]).strip() and str(point["content"]).strip()
        ]

    @classmethod
    def _chunk_text(cls, text: str) -> list[str]:
        """Split long OCR/transcripts on paragraph boundaries for stable prompts."""
        stripped = text.strip()
        if not stripped:
            return [""]
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", stripped) if part.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            pieces = [
                paragraph[index : index + cls.MAX_CHUNK_CHARS]
                for index in range(0, len(paragraph), cls.MAX_CHUNK_CHARS)
            ]
            for piece in pieces:
                candidate = f"{current}\n\n{piece}".strip() if current else piece
                if current and len(candidate) > cls.MAX_CHUNK_CHARS:
                    chunks.append(current)
                    current = piece
                else:
                    current = candidate
        if current:
            chunks.append(current)
        return chunks or [stripped]

    async def answer(self, question: str, context: str) -> str:
        """基于上下文的问答"""
        prompt = self.prompts.render("answer", question=question, context=context)
        try:
            resp = await self.llm.complete(prompt, task_type=TaskType.ANSWER)
            return resp.content
        except Exception as exc:
            logger.warning("LLM 问答不可用，启用本地降级: %s", exc)
            excerpt = context[:1200].strip()
            return (
                f"根据当前知识库中检索到的内容：{excerpt}"
                if excerpt
                else "当前知识库中没有足够的信息回答这个问题。"
            )

    async def build_knowledge_tree(self, kb_id: str) -> dict:
        """生成知识树结构"""
        prompt = self.prompts.render("knowledge_tree", kb_id=kb_id)
        try:
            resp = await self.llm.complete(prompt, task_type=TaskType.TREE)
            result = _parse_llm_json(resp.content, default={"nodes": [], "edges": []})
            if isinstance(result, dict):
                return result
            return {"nodes": [], "edges": [], "raw": resp.content}
        except Exception as exc:
            logger.warning("LLM 知识树不可用: %s", exc)
            return {"nodes": [], "edges": []}

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [
            sentence.strip()
            for sentence in re.split(r"(?<=[。！？!?；;\n])", text)
            if sentence.strip()
        ]

    def _fallback_summary(self, text: str, fields: list[dict] | None) -> dict:
        sentences = self._sentences(clean_content_locally(text))
        summary = "".join(sentences[:3])[:320] or text[:320]
        result: dict = {"summary": summary}
        for field in fields or []:
            name = field.get("name")
            if not name or name == "summary":
                continue
            label = field.get("label", name)
            if name in {"points", "knowledge_points", "key_points"}:
                result[name] = [s[:150] for s in sentences[:6]]
            else:
                result[name] = f"{label}：{summary[:180]}"
        return result

    def _fallback_points(self, text: str) -> list[dict]:
        sentences = self._sentences(clean_content_locally(text))
        return [
            {
                "title": sentence[:28].rstrip("，。；:：") or f"知识点 {index + 1}",
                "content": sentence[:300],
                "category": "自动提取",
                "importance": 0.5,
            }
            for index, sentence in enumerate(sentences[:8])
        ]

    def _fallback_merge(self, contents: list[str]) -> str:
        unique: list[str] = []
        fingerprints: set[str] = set()
        for text in contents:
            text = clean_content_locally(text)
            for sentence in self._sentences(text):
                fingerprint = re.sub(r"\W+", "", sentence).lower()
                if fingerprint and fingerprint not in fingerprints:
                    fingerprints.add(fingerprint)
                    unique.append(sentence)
        return "\n".join(unique)
