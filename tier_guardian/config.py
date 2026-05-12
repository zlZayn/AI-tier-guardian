from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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
    model_name: str
    api_base_url: str
    api_key: str
    surface_scanner: NodeConfig
    intent_probe: NodeConfig
    context_judge: NodeConfig
    evidence_summarizer: NodeConfig
    auto_block_confidence: float
    human_review_confidence: float
    schema_version: str
    cache_ttl_seconds: int
    cache_dir: str
    cache_max_size: int

    @classmethod
    def defaults(cls) -> "Config":
        return cls._from_dict({})

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
        def _node(key: str, thinking: bool, temperature: float, max_tokens: int) -> NodeConfig:
            d = data.get(key, {})
            return NodeConfig(
                thinking=d.get("thinking", thinking),
                temperature=d.get("temperature", temperature),
                max_tokens=d.get("max_tokens", max_tokens),
            )

        return cls(
            model_name=data.get("model_name", "deepseek-v4-flash"),
            api_base_url=data.get("api_base_url", "https://api.deepseek.com/v1"),
            api_key=data.get("api_key", os.getenv("DEEPSEEK_API_KEY", "")),
            surface_scanner=_node("surface_scanner", thinking=False, temperature=0.0, max_tokens=250),
            intent_probe=_node("intent_probe", thinking=False, temperature=0.0, max_tokens=120),
            context_judge=_node("context_judge", thinking=True, temperature=0.3, max_tokens=600),
            evidence_summarizer=_node("evidence_summarizer", thinking=False, temperature=0.0, max_tokens=300),
            auto_block_confidence=data.get("auto_block_confidence", 0.9),
            human_review_confidence=data.get("human_review_confidence", 0.7),
            schema_version=data.get("schema_version", "v2.3.1"),
            cache_ttl_seconds=data.get("cache_ttl_seconds", 86400),
            cache_dir=data.get("cache_dir", ".cache"),
            cache_max_size=data.get("cache_max_size", 1073741824),
        )
