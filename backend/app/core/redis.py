"""Redis 缓存客户端

提供异步 Redis 连接与统一缓存接口。
MVP 单机模式下 Redis 可选——连接失败时降级为无缓存，不影响主流程。
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)
_redis = None
_redis_available: bool | None = None


async def get_redis():
    """获取 Redis 客户端单例；连接失败时返回 None（降级模式）"""
    global _redis, _redis_available
    if _redis is not None:
        return _redis
    if _redis_available is False:
        return None
    try:
        from redis.asyncio import from_url
        _redis = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        await _redis.ping()
        _redis_available = True
        logger.info("Redis 已连接")
    except Exception as e:
        _redis_available = False
        _redis = None
        logger.warning("Redis 不可用，降级为无缓存模式: %s", e)
    return _redis


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None


class CacheService:
    """统一缓存服务封装（Redis 不可用时为空操作）"""

    def __init__(self, redis):
        self.redis = redis

    async def get(self, key: str) -> Optional[str]:
        if self.redis is None:
            return None
        return await self.redis.get(key)

    async def set(self, key: str, value: str, expire: int = 3600) -> None:
        if self.redis is None:
            return
        await self.redis.set(key, value, ex=expire)

    async def delete(self, key: str) -> None:
        if self.redis is None:
            return
        await self.redis.delete(key)
