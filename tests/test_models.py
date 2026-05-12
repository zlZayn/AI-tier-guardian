"""数据模型与序列化测试"""

from tier_guardian.config import (
    SurfaceRisk,
    IntentLabel,
    ViolationSeverity,
    FinalDecision,
    PatternCategory,
)
from tier_guardian.models import (
    TaskContext,
    PatternHit,
    SurfaceScannerOutput,
    IntentProbeOutput,
    Violation,
    ContextJudgeOutput,
    EvidenceSummarizerOutput,
)


class TestEnums:
    def test_surface_risk_values(self):
        assert SurfaceRisk.LOW.value == "low"
        assert SurfaceRisk.MEDIUM.value == "medium"
        assert SurfaceRisk.HIGH.value == "high"

    def test_intent_label_values(self):
        assert IntentLabel.NORMAL_SOCIAL.value == "normal_social"
        assert IntentLabel.HARASSMENT.value == "harassment"
        assert IntentLabel.SOLICITATION.value == "solicitation"

    def test_violation_severity_values(self):
        assert ViolationSeverity.EXTREME.value == "extreme"
        assert ViolationSeverity.HIGH.value == "high"

    def test_final_decision_values(self):
        assert FinalDecision.PASS.value == "PASS"
        assert FinalDecision.BLOCK.value == "BLOCK"
        assert FinalDecision.HUMAN_REVIEW.value == "HUMAN_REVIEW"


class TestPatternHit:
    def test_create(self):
        hit = PatternHit(
            id="P001",
            category=PatternCategory.CONTACT_EXPOSURE,
            fragment="13800138000",
            span=[10, 21],
        )
        assert hit.id == "P001"
        assert hit.category == PatternCategory.CONTACT_EXPOSURE


class TestSurfaceScannerOutput:
    def test_default(self):
        out = SurfaceScannerOutput()
        assert out.patterns == []
        assert out.surface_risk == SurfaceRisk.LOW

    def test_with_patterns(self):
        hit = PatternHit(id="P001", category=PatternCategory.INSULT_TEMPLATE, fragment="test", span=[0, 4])
        out = SurfaceScannerOutput(patterns=[hit], surface_risk=SurfaceRisk.HIGH)
        assert len(out.patterns) == 1
        assert out.surface_risk == SurfaceRisk.HIGH


class TestTaskContext:
    def test_create_minimal(self):
        ctx = TaskContext(text="hello")
        assert ctx.text == "hello"
        assert ctx.locale == "zh-CN"
        assert ctx.scene == "comment"
        assert ctx.nodes.surface is None
        assert ctx.nodes.intent is None
        assert ctx.nodes.judge is None
        assert ctx.nodes.summary is None
        assert ctx.final_decision is None
        assert ctx.task_id is not None
        assert ctx.created_at is not None

    def test_to_dict_empty(self):
        ctx = TaskContext(text="test")
        d = ctx.to_dict()
        assert d["text"] == "test"
        assert d["nodes"]["surface"] is None
        assert d["final_decision"] is None
        assert "task_id" in d["metadata"]

    def test_to_dict_with_decision(self):
        ctx = TaskContext(text="test", final_decision=FinalDecision.PASS)
        d = ctx.to_dict()
        assert d["final_decision"] == "PASS"

    def test_to_dict_full_pipeline(self):
        ctx = TaskContext(text="bad content")
        ctx.nodes.surface = SurfaceScannerOutput(
            patterns=[PatternHit(id="P001", category=PatternCategory.CONTACT_EXPOSURE, fragment="138xxx", span=[0, 5])],
            surface_risk=SurfaceRisk.HIGH,
        )
        ctx.nodes.intent = IntentProbeOutput(intent=IntentLabel.SOLICITATION, confidence=0.9)
        ctx.nodes.judge = ContextJudgeOutput(
            violation=Violation(is_violation=True, type="solicitation", severity=ViolationSeverity.HIGH, confidence=0.95),
            reasoning_summary="引导添加联系方式",
            rule_ids=["R101"],
        )
        ctx.nodes.summary = EvidenceSummarizerOutput(
            one_liner="用户引导添加联系方式",
            highlight_ranges=[[0, 5]],
            similar_cases=[],
            suggested_action="BLOCK",
        )
        ctx.final_decision = FinalDecision.BLOCK
        d = ctx.to_dict()
        assert d["final_decision"] == "BLOCK"
        assert d["nodes"]["surface"]["surface_risk"] == "high"
        assert d["nodes"]["intent"]["intent"] == "solicitation"
        assert d["nodes"]["judge"]["violation"]["is_violation"] is True
