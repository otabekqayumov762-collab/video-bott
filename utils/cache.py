import hashlib
import json
import logging
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

from data.config import REDIS_URL, CACHE_TTL

logger = logging.getLogger(__name__)


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()[:32]


class Cache:
    def __init__(self):
        self._client: Optional[Redis] = None

    async def connect(self):
        if self._client is not None:
            return
        try:
            self._client = Redis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._client = None

    async def close(self):
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    async def get_file(self, url: str) -> Optional[dict]:
        if not self._client:
            return None
        try:
            raw = await self._client.get(f"file:{_hash_url(url)}")
            if raw:
                return json.loads(raw)
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get failed: {e}")
        return None

    async def set_file(
        self,
        url: str,
        file_id: str,
        kind: str,
        title: str = "",
        duration: int = 0,
        width: int = 0,
        height: int = 0,
    ):
        if not self._client:
            return
        try:
            payload = json.dumps({
                "file_id": file_id,
                "kind": kind,
                "title": title,
                "duration": duration,
                "width": width,
                "height": height,
            })
            await self._client.set(f"file:{_hash_url(url)}", payload, ex=CACHE_TTL)
        except RedisError as e:
            logger.warning(f"Cache set failed: {e}")

    async def acquire_lock(self, url: str, ttl: int = 300) -> bool:
        """Prevent duplicate concurrent downloads for same URL."""
        if not self._client:
            return True
        try:
            return bool(await self._client.set(
                f"lock:{_hash_url(url)}", "1", ex=ttl, nx=True
            ))
        except RedisError:
            return True

    async def release_lock(self, url: str):
        if not self._client:
            return
        try:
            await self._client.delete(f"lock:{_hash_url(url)}")
        except RedisError:
            pass
