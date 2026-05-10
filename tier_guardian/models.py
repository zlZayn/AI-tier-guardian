from __future__ import annotations

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from tier_guardian.config import (
    SurfaceRisk,
    IntentLabel,
    ViolationSeverity,
    FinalDecision,
    PatternCategory,
)


@dataclass
class PatternHit:
    id: str
    category: PatternCategory
    fragment: str
    span: list[int]


@dataclass
class SurfaceScannerOutput:
    """节点 A 输出"""
    patterns: list[PatternHit] = field(default_factory=list)
    surface_risk: SurfaceRisk = SurfaceRisk.LOW


@dataclass
class IntentProbeOutput:
    """节点 B 输出"""
    intent: IntentLabel = IntentLabel.OTHER
    confidence: float = 0.0


@dataclass
class Violation:
    """节点 C 违规判定"""
    is_violation: bool = False
    type: Optional[str] = None
    severity: Optional[ViolationSeverity] = None
    confidence: float = 0.0


@dataclass
class ContextJudgeOutput:
    """节点 C 输出"""
    violation: Violation = field(default_factory=Violation)
    reasoning_summary: str = ""
    rule_ids: list[str] = field(default_factory=list)


@dataclass
class SimilarCase:
    case_id: str
    resolution: str
    summary: str


@dataclass
class EvidenceSummarizerOutput:
    """节点 D 输出"""
    one_liner: str = ""
    highlight_ranges: list[list[int]] = field(default_factory=list)
    similar_cases: list[SimilarCase] = field(default_factory=list)
    suggested_action: str = ""


@dataclass
class NodesResult:
    surface: Optional[SurfaceScannerOutput] = None
    intent: Optional[IntentProbeOutput] = None
    judge: Optional[ContextJudgeOutput] = None
    summary: Optional[EvidenceSummarizerOutput] = None


@dataclass
class TaskContext:
    """统一任务上下文，随流程传递"""
    text: str
    locale: str = "zh-CN"
    scene: str = "comment"
    nodes: NodesResult = field(default_factory=NodesResult)
    final_decision: Optional[FinalDecision] = None
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "locale": self.locale,
            "scene": self.scene,
            "nodes": {
                "surface": _maybe_dataclass_to_dict(self.nodes.surface),
                "intent": _maybe_dataclass_to_dict(self.nodes.intent),
                "judge": _maybe_dataclass_to_dict(self.nodes.judge),
                "summary": _maybe_dataclass_to_dict(self.nodes.summary),
            },
            "final_decision": self.final_decision.value if self.final_decision else None,
            "metadata": {
                "task_id": self.task_id,
                "created_at": self.created_at,
            },
        }


def _maybe_dataclass_to_dict(obj) -> Optional[dict]:
    if obj is None:
        return None
    result = {}
    for f in obj.__dataclass_fields__.values():
        val = getattr(obj, f.name)
        if isinstance(val, Enum):
            result[f.name] = val.value
        elif hasattr(val, "__dataclass_fields__"):
            result[f.name] = _maybe_dataclass_to_dict(val)
        elif isinstance(val, list):
            result[f.name] = [
                _maybe_dataclass_to_dict(v) if hasattr(v, "__dataclass_fields__") else (v.value if isinstance(v, Enum) else v)
                for v in val
            ]
        else:
            result[f.name] = val
    return result
