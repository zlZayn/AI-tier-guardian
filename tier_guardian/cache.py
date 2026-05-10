"""缓存架构
支持三层缓存：
1. 请求级去重：基于 text+scene+locale+schema_version 计算哈希，同一请求直接返回历史完整决策
2. 节点级缓存：每个节点的输入参数单独生成 SHA256 哈希，命中则返回该节点输出
3. 规则版本变更：schema_version 更新时按前缀批量失效相关节点缓存

存储：本地内存 LRU + Redis 持久化（可选）
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from cachetools import LRUCache

from tier_guardian.config import Config

logger = logging.getLogger(__name__)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    request_hits: int = 0
    node_hits: int = 0


class CacheManager:
    """两层缓存管理器：内存 LRU + Redis（可选）"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._stats = CacheStats()
        self._lru: LRUCache = LRUCache(maxsize=config.cache_max_size)
        self._redis = None
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis
            self._redis = redis.from_url(self._config.redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("Redis cache connected: %s", self._config.redis_url)
        except Exception:
            self._redis = None
            logger.info("Redis unavailable, using in-memory LRU only")

    def _build_request_hash(self, text: str, scene: str, locale: str) -> str:
        payload = json.dumps({
            "text": text,
            "scene": scene,
            "locale": locale,
            "schema_version": self._config.schema_version,
        }, sort_keys=True, ensure_ascii=False)
        return _hash_key(payload)

    def _build_node_hash(self, node_name: str, input_params: dict) -> str:
        payload = json.dumps({
            "node": node_name,
            "params": input_params,
            "schema_version": self._config.schema_version,
        }, sort_keys=True, ensure_ascii=False, default=str)
        return _hash_key(payload)

    def get_request_cache(self, text: str, scene: str, locale: str) -> Optional[dict]:
        key = self._build_request_hash(text, scene, locale)
        result = self._get(key)
        if result is not None:
            self._stats.request_hits += 1
            self._stats.hits += 1
            logger.debug("Request cache hit")
        else:
            self._stats.misses += 1
        return result

    def set_request_cache(self, text: str, scene: str, locale: str, decision: dict) -> None:
        key = self._build_request_hash(text, scene, locale)
        self._set(key, decision)

    def get_node_cache(self, node_name: str, input_params: dict) -> Optional[Any]:
        key = self._build_node_hash(node_name, input_params)
        result = self._get(key)
        if result is not None:
            self._stats.node_hits += 1
            self._stats.hits += 1
            logger.debug("Node cache hit for %s", node_name)
        else:
            self._stats.misses += 1
        return result

    def set_node_cache(self, node_name: str, input_params: dict, output: Any) -> None:
        key = self._build_node_hash(node_name, input_params)
        self._set(key, output)

    def _get(self, key: str) -> Optional[Any]:
        if key in self._lru:
            return self._lru[key]
        if self._redis:
            try:
                raw = self._redis.get(key)
                if raw:
                    value = json.loads(raw)
                    self._lru[key] = value
                    return value
            except Exception:
                logger.warning("Redis get failed for key %s", key[:16])
        return None

    def _set(self, key: str, value: Any) -> None:
        self._lru[key] = value
        if self._redis:
            try:
                raw = json.dumps(value, ensure_ascii=False, default=str)
                self._redis.setex(key, self._config.cache_ttl_seconds, raw)
            except Exception:
                logger.warning("Redis set failed for key %s", key[:16])

    def invalidate_by_prefix(self, prefix: str) -> int:
        """按前缀批量失效缓存（用于规则版本变更）"""
        count = 0
        to_delete = [k for k in self._lru if k.startswith(prefix)]
        for k in to_delete:
            del self._lru[k]
            count += 1
        if self._redis:
            try:
                for k in to_delete:
                    self._redis.delete(k)
            except Exception:
                logger.warning("Redis batch delete failed")
        logger.info("Invalidated %d cache entries with prefix %s", count, prefix)
        return count

    @property
    def stats(self) -> CacheStats:
        return self._stats
