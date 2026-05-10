"""LLM 客户端单元测试（不依赖实际 API）"""

import pytest
import json

from tier_guardian.llm_client import _try_repair_json


class TestJsonRepair:
    def test_valid_json_no_repair_needed(self):
        result = _try_repair_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_truncated_object(self):
        raw = '{"key": "value", "missing":'
        result = _try_repair_json(raw)
        assert result is not None
        assert result["key"] == "value"

    def test_truncated_array(self):
        raw = '[1, 2, 3'
        result = _try_repair_json(raw)
        assert result is not None
        assert result == [1, 2, 3]

    def test_truncated_nested(self):
        raw = '{"outer": {"inner": "val"'
        result = _try_repair_json(raw)
        assert result is not None
        assert result["outer"]["inner"] == "val"

    def test_truncated_string_content(self):
        raw = '{"key": "unclosed string'
        result = _try_repair_json(raw)
        assert result["key"] == "unclosed string"

    def test_completely_invalid(self):
        raw = "this is not json at all"
        result = _try_repair_json(raw)
        assert result is None
