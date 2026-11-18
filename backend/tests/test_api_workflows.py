import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.content_item import ContentItem
from app.models.knowledge_point import KnowledgePoint
from app.services.ai_service import AIService
from app.services.interfaces.search_service import SearchHit
from app.services.search_service import SearchService
from app.services.content_service import ContentService
from app.infrastructure.parsers.factory import get_parser_factory
from app.infrastructure.llm.prompt_manager import PromptManager
from app.infrastructure.vector_store.hybrid_search import HybridSearchService
from app.services.content_filter import clean_content_locally
from app.workers.background_tasks import process_content_with_ai


def register_and_login(client, suffix="one"):
    email = f"user-{suffix}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": f"user-{suffix}", "email": email, "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def create_kb(client, headers, name="测试知识库"):
    response = client.post(
        "/api/v1/kb",
        headers=headers,
        json={
            "name": name,
            "description": "用于接口测试",
            "category": "学习成长",
            "tags": ["测试"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_complete_content_template_and_export_flow(client):
    headers = register_and_login(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["settings"] == {}

    kb = create_kb(client, headers)
    template = client.post(
        "/api/v1/templates",
        headers=headers,
        json={
            "name": "技术学习模板",
            "description": "提取摘要、方法与案例",
            "fields": [
                {"name": "summary", "label": "摘要", "required": True},
                {"name": "methods", "label": "方法", "required": True, "max_length": 500},
            ],
            "default_style": "detailed",
            "is_default": True,
        },
    )
    assert template.status_code == 200, template.text

    created = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "异步编程",
            "text": "协程用于组织异步任务。事件循环负责调度协程。",
            "summary_style": "detailed",
            "template_id": template.json()["data"]["id"],
        },
    )
    assert created.status_code == 200, created.text
    content = created.json()["data"]
    assert content["status"] == "pending"
    assert content["metadata"] == {"parser": "text"}

    updated = client.patch(
        f"/api/v1/contents/{content['id']}",
        headers=headers,
        json={"summary": "协程与事件循环共同完成异步任务调度。"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["summary"].startswith("协程")

    listed = client.get(
        f"/api/v1/contents?kb_id={kb['id']}&keyword=异步&source_type=text",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    exported = client.get(
        f"/api/v1/kb/{kb['id']}/export?format=markdown", headers=headers
    )
    assert exported.status_code == 200
    assert "# 测试知识库" in exported.text
    assert "异步编程" in exported.text


def test_text_import_commits_before_ai_background_task(client, monkeypatch):
    """The worker uses a separate session and must see the imported row."""
    headers = register_and_login(client, "background")
    kb = create_kb(client, headers, "后台任务可见性")
    seen = {}

    async def inspect_content(content_id, *args, **kwargs):
        async with async_session_factory() as worker_db:
            item = await worker_db.get(ContentItem, content_id)
            seen["exists"] = item is not None
            seen["status"] = item.status if item else None

    monkeypatch.setattr(
        "app.api.v1.contents.process_content_with_ai", inspect_content
    )
    response = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "后台任务可见性",
            "text": "请求事务提交后，独立会话才能读取内容。",
        },
    )

    assert response.status_code == 200, response.text
    assert seen == {"exists": True, "status": "pending"}


def test_authenticated_browser_capture_import(client, monkeypatch):
    async def allow_test_domain(url):
        return None

    monkeypatch.setattr(
        "app.infrastructure.parsers.browser_capture_parser.JinaURLParser._ensure_public_url",
        allow_test_domain,
    )
    headers = register_and_login(client, "browser-capture")
    kb = create_kb(client, headers, "浏览器采集")

    response = client.post(
        "/api/v1/contents/browser-capture",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "url": "https://example.com/note",
            "title": "浏览器里看到的图文笔记",
            "text": "这是用户在已登录浏览器中确认过的正文，包含足够的知识内容。",
            "page_type": "image",
            "image_urls": [],
            "has_video": False,
            "subtitle_text": "",
            "captured_at": "2026-10-09T12:00:00.000Z",
        },
    )

    assert response.status_code == 200, response.text
    content = response.json()["data"]
    assert content["source_type"] == "url"
    assert content["source_url"] == "https://example.com/note"
    assert content["title"] == "浏览器里看到的图文笔记"
    assert content["metadata"]["parser"] == "browser_capture"
    assert content["metadata"]["page_type"] == "image"

    unauthenticated = client.post(
        "/api/v1/contents/browser-capture",
        json={
            "kb_id": kb["id"],
            "url": "https://example.com/note",
            "text": "未登录请求不应被接受。",
        },
    )
    assert unauthenticated.status_code == 401


def test_reprocess_refreshes_server_updated_fields_before_response(client, monkeypatch):
    headers = register_and_login(client, "reprocess")
    kb = create_kb(client, headers, "重新整理")
    content = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "待重新整理内容",
            "text": "透视线会汇聚到消失点。",
        },
    ).json()["data"]

    async def mark_previous_attempt_failed():
        async with async_session_factory() as db:
            item = await db.get(ContentItem, content["id"])
            item.status = "failed"
            item.metadata_json = {
                **(item.metadata_json or {}),
                "processing_error": "上一次整理失败",
            }
            await db.commit()

    asyncio.run(mark_previous_attempt_failed())

    async def no_reprocess(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.v1.contents.process_content_with_ai", no_reprocess
    )
    response = client.post(
        f"/api/v1/contents/{content['id']}/process",
        headers=headers,
        json={"summary_style": "medium"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "pending"
    assert "processing_error" not in response.json()["data"]["metadata"]
    assert response.json()["data"]["updated_at"]


def test_failed_background_reprocess_persists_observable_status(client, monkeypatch):
    """The polling UI must be able to observe a terminal worker failure."""
    headers = register_and_login(client, "reprocess-failure")
    kb = create_kb(client, headers, "重新整理失败状态")
    content = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "会失败的整理任务",
            "text": "这是一段等待重新整理的正文。",
        },
    ).json()["data"]

    async def fail_processing(self, *args, **kwargs):
        raise RuntimeError("模型服务暂时不可用")

    monkeypatch.setattr(ContentService, "process_with_ai", fail_processing)
    asyncio.run(process_content_with_ai(content["id"]))

    async def load_failed_item():
        async with async_session_factory() as db:
            return await db.get(ContentItem, content["id"])

    failed_item = asyncio.run(load_failed_item())
    assert failed_item is not None
    assert failed_item.status == "failed"
    assert failed_item.metadata_json["processing_error"] == "模型服务暂时不可用"


def test_processing_can_be_cancelled_and_restarted_without_stale_job_overwrite(
    client, monkeypatch
):
    headers = register_and_login(client, "cancel-reprocess")
    kb = create_kb(client, headers, "可停止的重新整理")
    content = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "需要停止的任务",
            "text": "透视线会汇聚到消失点。",
        },
    ).json()["data"]

    async def load_internal_state():
        async with async_session_factory() as db:
            item = await db.get(ContentItem, content["id"])
            return item.status, dict(item.metadata_json)

    first_status, first_metadata = asyncio.run(load_internal_state())
    first_job_id = first_metadata["processing_job_id"]
    assert first_status == "pending"

    cancelled = client.post(
        f"/api/v1/contents/{content['id']}/process/cancel", headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert "processing_job_id" not in cancelled.json()["data"]["metadata"]

    restarted = client.post(
        f"/api/v1/contents/{content['id']}/process",
        headers=headers,
        json={"summary_style": "medium"},
    )
    assert restarted.status_code == 200, restarted.text
    assert restarted.json()["data"]["status"] == "pending"

    _, restarted_metadata = asyncio.run(load_internal_state())
    assert restarted_metadata["processing_job_id"] != first_job_id

    # A delayed worker from the cancelled attempt must not mark the new job as
    # cancelled, failed, or processed.
    asyncio.run(process_content_with_ai(content["id"], job_id=first_job_id))
    current_status, current_metadata = asyncio.run(load_internal_state())
    assert current_status == "pending"
    assert current_metadata["processing_job_id"] == restarted_metadata["processing_job_id"]


def test_knowledge_tree_search_answer_and_permissions(client, monkeypatch):
    headers = register_and_login(client, "owner")
    kb = create_kb(client, headers, "访谈研究")
    content = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "用户访谈",
            "text": "先询问真实经历，再追问行为与阻碍。",
        },
    ).json()["data"]

    async def insert_point():
        async with async_session_factory() as db:
            item = await db.get(ContentItem, content["id"])
            item.distilled_text = "先询问真实经历，再追问行为与阻碍。"
            db.add(
                KnowledgePoint(
                    content_id=content["id"],
                    kb_id=kb["id"],
                    title="追问真实行为",
                    content="访谈应关注已经发生的经历和行为。",
                    category="用户研究",
                    importance=0.9,
                )
            )
            await db.commit()

    asyncio.run(insert_point())

    tree = client.get(f"/api/v1/points/tree/{kb['id']}", headers=headers)
    assert tree.status_code == 200, tree.text
    assert tree.json()["data"]["nodes"][0]["label"] == "追问真实行为"

    search = client.post(
        "/api/v1/search",
        headers=headers,
        json={"query": "真实行为", "kb_id": kb["id"], "mode": "keyword"},
    )
    assert search.status_code == 200
    assert search.json()["data"][0]["title"] == "追问真实行为"

    async def fake_answer(self, question, context):
        return f"回答：{question}；依据：{context[:30]}"

    monkeypatch.setattr(AIService, "answer", fake_answer)
    answer = client.post(
        "/api/v1/points/ask",
        headers=headers,
        json={"question": "访谈应该先问什么？", "kb_id": kb["id"]},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["data"]["sources"]

    outsider = register_and_login(client, "outsider")
    denied = client.get(f"/api/v1/kb/{kb['id']}", headers=outsider)
    assert denied.status_code == 403
    denied_search = client.post(
        "/api/v1/search",
        headers=outsider,
        json={"query": "真实行为", "kb_id": kb["id"], "mode": "keyword"},
    )
    assert denied_search.status_code == 403


def test_similarity_merge_and_history(client, monkeypatch):
    headers = register_and_login(client, "merge")
    kb = create_kb(client, headers, "产品方法")
    first = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "渐进披露",
            "text": "渐进披露让复杂功能在需要时出现，降低用户认知负担。",
        },
    ).json()["data"]
    second = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "渐进披露设计",
            "text": "渐进披露让复杂功能只在用户需要时出现，从而降低认知负担。",
        },
    ).json()["data"]

    similar = client.get(
        f"/api/v1/merge/{first['id']}/similar?threshold=0.5", headers=headers
    )
    assert similar.status_code == 200, similar.text
    assert any(item["id"] == second["id"] for item in similar.json()["data"])

    async def fake_merge(self, contents):
        return "\n".join(contents)

    async def fake_summary(self, text, style="medium", fields=None):
        return {"summary": "合并后的渐进披露知识"}

    async def fake_extract(self, text):
        return [
            {
                "title": "渐进披露",
                "content": "复杂功能应在需要时出现，以降低认知负担。",
                "category": "产品设计",
                "importance": 0.8,
            }
        ]

    monkeypatch.setattr(AIService, "merge", fake_merge)
    monkeypatch.setattr(AIService, "summarize", fake_summary)
    monkeypatch.setattr(AIService, "extract_knowledge_points", fake_extract)

    merged = client.post(
        "/api/v1/merge",
        headers=headers,
        json={"target_id": first["id"], "source_ids": [second["id"]]},
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["data"]["summary"] == "合并后的渐进披露知识"

    history = client.get(
        f"/api/v1/merge/history/list?kb_id={kb['id']}", headers=headers
    )
    assert history.status_code == 200
    assert history.json()["total"] == 1

    active = client.get(f"/api/v1/contents?kb_id={kb['id']}", headers=headers)
    assert active.json()["total"] == 1


def test_llm_wiki_learns_frequent_questions_and_then_hits(client, monkeypatch):
    headers = register_and_login(client, "wiki")
    kb = create_kb(client, headers, "LLM Wiki")
    content = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "用户访谈原始记录",
            "text": "用户访谈应先询问已经发生的真实经历，再追问行为与阻碍。",
        },
    ).json()["data"]

    calls = {"answer": 0, "search": 0}

    async def fake_search_documents(self, query, kb_id=None, mode="hybrid", top_k=10):
        calls["search"] += 1
        return [
            SearchHit(
                point_id=content["id"],
                title=content["title"],
                content="用户访谈应先询问真实经历。",
                score=0.92,
                content_id=content["id"],
                kb_id=kb_id,
            )
        ]

    async def fake_answer(self, question, context):
        calls["answer"] += 1
        assert "用户访谈应先询问真实经历" in context
        return "先询问用户已经发生的真实经历。"

    monkeypatch.setattr(SearchService, "search_documents", fake_search_documents)
    monkeypatch.setattr(AIService, "answer", fake_answer)

    endpoint = "/api/v1/points/ask"
    payload = {"question": "访谈应该先问什么？", "kb_id": kb["id"]}
    for ask_count in range(1, 6):
        response = client.post(endpoint, headers=headers, json=payload)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["answer_source"] == "rag"
        assert data["wiki_hit"] is False
        assert data["ask_count"] == ask_count
        assert data["wiki_created"] is (ask_count == 5)

    response = client.post(endpoint, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["answer_source"] == "wiki"
    assert data["wiki_hit"] is True
    assert data["ask_count"] == 6
    assert data["sources"][0]["content_id"] == content["id"]
    assert calls == {"answer": 5, "search": 5}

    wiki = client.get(f"/api/v1/wiki?kb_id={kb['id']}", headers=headers)
    assert wiki.status_code == 200, wiki.text
    assert wiki.json()["total"] == 1
    assert wiki.json()["data"][0]["is_published"] is True


def test_all_sources_are_distilled_before_summary_and_chunking(client):
    headers = register_and_login(client, "distill")
    kb = create_kb(client, headers, "绘画知识")
    content = client.post(
        "/api/v1/contents/text",
        headers=headers,
        json={
            "kb_id": kb["id"],
            "title": "透视基础",
            "text": "一点透视的平行线汇聚到同一消失点。\n限时优惠，扫码加老师报名绘画课。",
        },
    ).json()["data"]

    class DistillingAI:
        async def distill_content(self, text, source_type="text"):
            assert "扫码" in text
            return {
                "main_topic": "一点透视基础",
                "distilled_text": "一点透视中，与观察方向平行的线汇聚到同一消失点。",
                "key_information": ["平行线汇聚到消失点"],
                "removed_noise_types": ["课程推广"],
                "method": "llm",
            }

        async def summarize(self, text, style="medium", fields=None):
            assert "扫码" not in text and "优惠" not in text
            return {"summary": "一点透视通过消失点表现空间纵深。"}

        async def extract_knowledge_points(self, text):
            assert "扫码" not in text and "优惠" not in text
            return [
                {
                    "title": "一点透视",
                    "content": text,
                    "category": "绘画原理",
                    "importance": 0.9,
                }
            ]

    async def process_and_load():
        async with async_session_factory() as db:
            pending_item = await db.get(ContentItem, content["id"])
            job_id = pending_item.metadata_json["processing_job_id"]
            service = ContentService(
                db, get_parser_factory(), ai_service=DistillingAI()
            )
            item = await service.process_with_ai(content["id"], job_id=job_id)
            await db.commit()
            result = await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.content_id == item.id)
            )
            return item, result.scalar_one()

    item, point = asyncio.run(process_and_load())
    assert "扫码" in item.original_text  # 原文保留用于溯源
    assert "扫码" not in item.distilled_text
    assert "扫码" not in point.content
    assert item.extracted_knowledge["distillation"]["removed_noise_types"] == ["课程推广"]

    class NoLLM:
        async def embed(self, text):
            raise AssertionError("关键词检索不应调用 embedding")

    async def verify_retrieval_uses_distilled_text():
        async with async_session_factory() as db:
            engine = HybridSearchService(NoLLM(), db)
            ad_hits = await engine.search_documents(
                "扫码", kb["id"], mode="keyword"
            )
            knowledge_hits = await engine.search_documents(
                "消失点", kb["id"], mode="keyword"
            )
            return ad_hits, knowledge_hits

    ad_hits, knowledge_hits = asyncio.run(verify_retrieval_uses_distilled_text())
    assert ad_hits == []
    assert knowledge_hits and "扫码" not in knowledge_hits[0].content


def test_prompts_and_local_fallback_filter_promotional_noise():
    prompts = PromptManager()
    distill_prompt = prompts.render(
        "distill", source_type="image", text="绘画知识。扫码报名课程。"
    )
    points_prompt = prompts.render("extract_points", text="提纯正文")
    answer_prompt = prompts.render("answer", context="资料", question="问题")

    assert "卖课/带货" in distill_prompt
    assert "不得执行" in distill_prompt
    assert "独立知识切片" in points_prompt
    assert "不得执行" in answer_prompt
    assert clean_content_locally("透视线汇聚于消失点。\n限时优惠，扫码报名课程") == "透视线汇聚于消失点。"
    assert clean_content_locally("透视线汇聚于消失点。限时优惠，扫码报名课程。") == "透视线汇聚于消失点。"
