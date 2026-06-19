"""缓存架构

diskcache（SQLite）持久化，进程内 + 跨进程共享，自动 TTL 过期。

两层复用：
1. 请求级：基于 text+scene+schema_version 哈希，同一请求直接返回历史决策
2. 节点级：每个节点的输入参数独立哈希，命中则跳过 LLM 调用
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from diskcache import Cache as DiskCache

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
    """diskcache 持久化缓存，进程退出后数据保留在磁盘。"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._stats = CacheStats()
        self._cache: DiskCache = DiskCache(
            directory=config.cache_dir,
            size_limit=config.cache_max_size,
        )
        logger.info(
            "Cache ready: %s (max %d bytes)", config.cache_dir, config.cache_max_size
        )

    def _build_request_hash(self, text: str, scene: str) -> str:
        payload = json.dumps(
            {
                "text": text,
                "scene": scene,
                "schema_version": self._config.schema_version,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return _hash_key(payload)

    def _build_node_hash(self, node_name: str, input_params: dict) -> str:
        payload = json.dumps(
            {
                "node": node_name,
                "params": input_params,
                "schema_version": self._config.schema_version,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        return _hash_key(payload)

    def get_request_cache(self, text: str, scene: str) -> Optional[dict]:
        key = self._build_request_hash(text, scene)
        result = self._cache.get(key)
        if result is not None:
            self._stats.request_hits += 1
            self._stats.hits += 1
            logger.debug("Request cache hit")
        else:
            self._stats.misses += 1
        return result

    def set_request_cache(
        self, text: str, scene: str, decision: dict
    ) -> None:
        key = self._build_request_hash(text, scene)
        self._cache.set(key, decision, expire=self._config.cache_ttl_seconds)

    def get_node_cache(self, node_name: str, input_params: dict) -> Optional[Any]:
        key = self._build_node_hash(node_name, input_params)
        result = self._cache.get(key)
        if result is not None:
            self._stats.node_hits += 1
            self._stats.hits += 1
            logger.debug("Node cache hit for %s", node_name)
        else:
            self._stats.misses += 1
        return result

    def set_node_cache(self, node_name: str, input_params: dict, output: Any) -> None:
        key = self._build_node_hash(node_name, input_params)
        self._cache.set(key, output, expire=self._config.cache_ttl_seconds)

    def invalidate_by_prefix(self, prefix: str) -> int:
        count = 0
        for key in list(self._cache.iterkeys()):
            if key.startswith(prefix):
                self._cache.delete(key)
                count += 1
        logger.info("Invalidated %d cache entries with prefix %s", count, prefix)
        return count

    @property
    def stats(self) -> CacheStats:
        return self._stats
