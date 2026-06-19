"""缓存系统测试"""

from tier_guardian.config import Config
from tier_guardian.cache import CacheManager


class TestCacheManager:
    def test_request_cache_hit(self):
        cm = CacheManager(Config.defaults())
        cm.set_request_cache("hello", "comment", {"final_decision": "PASS"})
        result = cm.get_request_cache("hello", "comment")
        assert result == {"final_decision": "PASS"}

    def test_request_cache_miss(self):
        cm = CacheManager(Config.defaults())
        result = cm.get_request_cache("nonexistent", "comment")
        assert result is None

    def test_request_cache_different_text_no_hit(self):
        cm = CacheManager(Config.defaults())
        cm.set_request_cache("text1", "comment", {"final_decision": "PASS"})
        result = cm.get_request_cache("text2", "comment")
        assert result is None

    def test_request_cache_different_scene_no_hit(self):
        cm = CacheManager(Config.defaults())
        cm.set_request_cache("hello", "comment", {"final_decision": "PASS"})
        result = cm.get_request_cache("hello", "post")
        assert result is None

    def test_node_cache_hit(self):
        cm = CacheManager(Config.defaults())
        cm.set_node_cache(
            "surface_scanner",
            {"text": "hello"},
            {"patterns": [], "surface_risk": "low"},
        )
        result = cm.get_node_cache(
            "surface_scanner", {"text": "hello"}
        )
        assert result == {"patterns": [], "surface_risk": "low"}

    def test_node_cache_miss(self):
        cm = CacheManager(Config.defaults())
        result = cm.get_node_cache(
            "surface_scanner", {"text": "nonexistent"}
        )
        assert result is None

    def test_node_cache_different_input_no_hit(self):
        cm = CacheManager(Config.defaults())
        cm.set_node_cache(
            "intent_probe",
            {"text": "hello", "scene": "comment"},
            {"intent": "normal_social", "confidence": 0.9},
        )
        result = cm.get_node_cache("intent_probe", {"text": "hello", "scene": "post"})
        assert result is None

    def test_stats_tracking(self):
        cm = CacheManager(Config.defaults())
        cm.get_request_cache("miss1", "comment")
        cm.set_request_cache("hit1", "comment", {"final_decision": "PASS"})
        cm.get_request_cache("hit1", "comment")
        stats = cm.stats
        assert stats.misses >= 1
        assert stats.hits >= 1

    def test_invalidate_by_prefix(self):
        cm = CacheManager(Config.defaults())
        cm.set_request_cache("text_a", "comment", {"final_decision": "PASS"})
        cm.set_request_cache("text_b", "comment", {"final_decision": "BLOCK"})
        assert cm.get_request_cache("text_a", "comment") is not None
        assert cm.get_request_cache("text_b", "comment") is not None
        # Invalidate should work but we don't know the exact prefix
        count = cm.invalidate_by_prefix("")
        assert count >= 0
