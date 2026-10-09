"""v1 路由聚合"""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    contents,
    knowledge_bases,
    knowledge_points,
    llm,
    merge,
    search,
    templates,
    wiki,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(knowledge_bases.router, prefix="/kb", tags=["知识库"])
api_router.include_router(contents.router, prefix="/contents", tags=["内容"])
api_router.include_router(knowledge_points.router, prefix="/points", tags=["知识点"])
api_router.include_router(search.router, prefix="/search", tags=["检索"])
api_router.include_router(llm.router, prefix="/llm", tags=["LLM 配置"])
api_router.include_router(templates.router, prefix="/templates", tags=["总结模板"])
api_router.include_router(merge.router, prefix="/merge", tags=["内容合并"])
api_router.include_router(wiki.router, prefix="/wiki", tags=["LLM Wiki"])
