"""ChromaDB 向量存储

对应架构文档 6.1 节。
管理两个 Collection：content_embeddings 与 knowledge_point_embeddings，
支持写入、按 KB 过滤的 HNSW 近邻检索与删除。

MVP 单机模式下 chromadb 可选——未安装或连接失败时检索功能降级。
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Collection 名称
CONTENT_COLLECTION = "content_embeddings"
KNOWLEDGE_POINT_COLLECTION = "knowledge_point_embeddings"


class ChromaVectorStore:
    """ChromaDB 向量存储"""

    def __init__(self):
        self._client = None
        self._available: bool | None = None

    async def _get_client(self):
        """惰性初始化异步客户端；chromadb 不可用时返回 None"""
        if self._client is not None:
            return self._client
        if self._available is False:
            return None
        try:
            import chromadb
            self._client = await chromadb.AsyncHttpClient(
                host=settings.chromadb_host,
                port=settings.chromadb_port,
            )
            await self._client.heartbeat()
            self._available = True
            logger.info("ChromaDB 已连接")
        except ImportError:
            self._available = False
            logger.warning("chromadb 未安装，向量检索功能不可用")
        except Exception as e:
            self._available = False
            logger.warning("ChromaDB 连接失败，向量检索降级: %s", e)
        return self._client

    async def _get_collection(self, name: str):
        client = await self._get_client()
        if client is None:
            return None
        return await client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    async def upsert(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """写入 / 更新向量（chromadb 不可用时静默跳过）"""
        collection = await self._get_collection(collection_name)
        if collection is None:
            return
        await collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    async def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        kb_id: Optional[str] = None,
        top_k: int = 10,
    ) -> list[dict]:
        """向量近邻检索，可按 kb_id 过滤（chromadb 不可用时返回空）"""
        collection = await self._get_collection(collection_name)
        if collection is None:
            return []
        where = {"kb_id": kb_id} if kb_id else None
        result = await collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
        return self._format_result(result)

    async def delete(self, collection_name: str, ids: list[str]) -> None:
        """按 ID 删除向量"""
        collection = await self._get_collection(collection_name)
        if collection is None:
            return
        await collection.delete(ids=ids)

    async def delete_where(self, collection_name: str, where: dict) -> None:
        """Delete all vectors matching metadata (used before rebuilding chunks)."""
        collection = await self._get_collection(collection_name)
        if collection is None:
            return
        await collection.delete(where=where)

    @staticmethod
    def _format_result(result: dict) -> list[dict]:
        """整理 ChromaDB 返回结构为统一格式"""
        if not result or not result.get("ids"):
            return []
        ids = result["ids"][0]
        documents = result["documents"][0] if result.get("documents") else [""]
        metadatas = result["metadatas"][0] if result.get("metadatas") else [{}]
        distances = result["distances"][0] if result.get("distances") else [0.0]
        hits = []
        for i, _id in enumerate(ids):
            # 余弦距离转相似度
            score = 1.0 - (distances[i] if distances[i] < 1.0 else 1.0)
            hits.append(
                {
                    "id": _id,
                    "document": documents[i],
                    "metadata": metadatas[i],
                    "score": score,
                }
            )
        return hits


# 全局单例
_vector_store: Optional[ChromaVectorStore] = None


def get_vector_store() -> ChromaVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = ChromaVectorStore()
    return _vector_store
