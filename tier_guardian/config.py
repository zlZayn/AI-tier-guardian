from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class SurfaceRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntentLabel(str, Enum):
    NORMAL_SOCIAL = "normal_social"
    SOLICITATION = "solicitation"
    HARASSMENT = "harassment"
    SPAM_PROMOTION = "spam_promotion"
    INFORMATION_SEEKING = "information_seeking"
    OPINION_EXPRESSION = "opinion_expression"
    OTHER = "other"


class ViolationSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class FinalDecision(str, Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class Layer1Result(str, Enum):
    PASS = "PASS"
    LAYER2 = "LAYER2"


class PatternCategory(str, Enum):
    CONTACT_EXPOSURE = "contact_exposure"
    INSULT_TEMPLATE = "insult_template"
    ILLEGAL_TRANSACTION_KEYWORDS = "illegal_transaction_keywords"
    MINOR_PROTECTION_RISK = "minor_protection_risk"
    SPAM_TEMPLATE = "spam_template"
    OTHER = "other"


@dataclass
class NodeConfig:
    thinking: bool
    temperature: float
    max_tokens: int


@dataclass
class Config:
    model_name: str = "deepseek-chat"
    api_base_url: str = "https://api.deepseek.com/v1"
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))

    surface_scanner: NodeConfig = field(default_factory=lambda: NodeConfig(
        thinking=False, temperature=0.0, max_tokens=150,
    ))
    intent_probe: NodeConfig = field(default_factory=lambda: NodeConfig(
        thinking=False, temperature=0.0, max_tokens=120,
    ))
    context_judge: NodeConfig = field(default_factory=lambda: NodeConfig(
        thinking=True, temperature=0.3, max_tokens=400,
    ))
    evidence_summarizer: NodeConfig = field(default_factory=lambda: NodeConfig(
        thinking=False, temperature=0.0, max_tokens=250,
    ))

    auto_block_confidence: float = 0.9
    human_review_confidence: float = 0.7

    schema_version: str = "v2.3.1"

    cache_ttl_seconds: int = 86400
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    cache_max_size: int = 10000

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        path = Path(path)
        if path.suffix == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix in (".yaml", ".yml"):
            import yaml  # type: ignore
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")
        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        cfg = cls()
        if "model_name" in data:
            cfg.model_name = data["model_name"]
        if "api_base_url" in data:
            cfg.api_base_url = data["api_base_url"]
        if "api_key" in data:
            cfg.api_key = data["api_key"]
        for node_key in ("surface_scanner", "intent_probe", "context_judge", "evidence_summarizer"):
            if node_key in data:
                setattr(cfg, node_key, NodeConfig(**data[node_key]))
        if "auto_block_confidence" in data:
            cfg.auto_block_confidence = data["auto_block_confidence"]
        if "human_review_confidence" in data:
            cfg.human_review_confidence = data["human_review_confidence"]
        if "schema_version" in data:
            cfg.schema_version = data["schema_version"]
        if "cache_ttl_seconds" in data:
            cfg.cache_ttl_seconds = data["cache_ttl_seconds"]
        if "redis_url" in data:
            cfg.redis_url = data["redis_url"]
        if "cache_max_size" in data:
            cfg.cache_max_size = data["cache_max_size"]
        return cfg
