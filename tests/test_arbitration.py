"""仲裁逻辑单元测试"""

from tier_guardian.config import (
    Config,
    FinalDecision,
    IntentLabel,
    Layer1Result,
    SurfaceRisk,
    ViolationSeverity,
)
from tier_guardian.arbitration import pre_filter, deep_judge
from tier_guardian.models import Violation


class TestPreFilter:
    def test_high_surface_risk_goes_to_layer2(self):
        assert (
            pre_filter(SurfaceRisk.HIGH, IntentLabel.NORMAL_SOCIAL)
            == Layer1Result.LAYER2
        )

    def test_harassment_goes_to_layer2(self):
        assert (
            pre_filter(SurfaceRisk.LOW, IntentLabel.HARASSMENT) == Layer1Result.LAYER2
        )

    def test_solicitation_goes_to_layer2(self):
        assert (
            pre_filter(SurfaceRisk.LOW, IntentLabel.SOLICITATION) == Layer1Result.LAYER2
        )

    def test_low_risk_normal_passes(self):
        assert (
            pre_filter(SurfaceRisk.LOW, IntentLabel.NORMAL_SOCIAL) == Layer1Result.PASS
        )
        assert (
            pre_filter(SurfaceRisk.LOW, IntentLabel.OPINION_EXPRESSION)
            == Layer1Result.PASS
        )
        assert (
            pre_filter(SurfaceRisk.LOW, IntentLabel.INFORMATION_SEEKING)
            == Layer1Result.PASS
        )

    def test_medium_risk_normal_goes_to_layer2(self):
        assert (
            pre_filter(SurfaceRisk.MEDIUM, IntentLabel.NORMAL_SOCIAL)
            == Layer1Result.LAYER2
        )

    def test_medium_risk_opinion_goes_to_layer2(self):
        assert (
            pre_filter(SurfaceRisk.MEDIUM, IntentLabel.OPINION_EXPRESSION)
            == Layer1Result.LAYER2
        )

    def test_low_risk_other_goes_to_layer2(self):
        assert pre_filter(SurfaceRisk.LOW, IntentLabel.OTHER) == Layer1Result.LAYER2

    def test_low_risk_spam_goes_to_layer2(self):
        assert (
            pre_filter(SurfaceRisk.LOW, IntentLabel.SPAM_PROMOTION)
            == Layer1Result.LAYER2
        )


class TestDeepJudge:
    def test_no_violation_passes(self):
        v = Violation(is_violation=False)
        assert deep_judge(v, Config.defaults()) == FinalDecision.PASS

    def test_high_confidence_high_severity_auto_blocks(self):
        v = Violation(
            is_violation=True,
            confidence=0.95,
            severity=ViolationSeverity.HIGH,
            type="insult",
        )
        assert deep_judge(v, Config.defaults()) == FinalDecision.BLOCK

    def test_high_confidence_extreme_auto_blocks(self):
        v = Violation(
            is_violation=True,
            confidence=0.90,
            severity=ViolationSeverity.EXTREME,
            type="illegal_content",
        )
        assert deep_judge(v, Config.defaults()) == FinalDecision.BLOCK

    def test_medium_confidence_high_severity_human_review(self):
        v = Violation(
            is_violation=True,
            confidence=0.75,
            severity=ViolationSeverity.HIGH,
            type="insult",
        )
        assert deep_judge(v, Config.defaults()) == FinalDecision.HUMAN_REVIEW

    def test_low_confidence_pass(self):
        v = Violation(
            is_violation=True,
            confidence=0.65,
            severity=ViolationSeverity.LOW,
            type="spam",
        )
        assert deep_judge(v, Config.defaults()) == FinalDecision.PASS

    def test_threshold_boundary_auto_block(self):
        v = Violation(
            is_violation=True,
            confidence=0.90,
            severity=ViolationSeverity.HIGH,
            type="harassment",
        )
        assert (
            deep_judge(v, Config._from_dict({"auto_block_confidence": 0.9}))
            == FinalDecision.BLOCK
        )

    def test_threshold_boundary_human_review(self):
        v = Violation(
            is_violation=True,
            confidence=0.70,
            severity=ViolationSeverity.MEDIUM,
            type="spam",
        )
        assert (
            deep_judge(v, Config._from_dict({"human_review_confidence": 0.7}))
            == FinalDecision.HUMAN_REVIEW
        )
