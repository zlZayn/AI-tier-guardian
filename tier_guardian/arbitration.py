"""纯程序仲裁逻辑 - 前置分流 + 深度仲裁
零 Token 消耗，纯 Python 函数。
"""

from __future__ import annotations

from tier_guardian.config import (
    Config,
    FinalDecision,
    Layer1Result,
    SurfaceRisk,
    ViolationSeverity,
    IntentLabel,
)
from tier_guardian.models import Violation


def pre_filter(surface_risk: SurfaceRisk, intent: IntentLabel) -> Layer1Result:
    """前置分流仲裁（纯程序，零 Token）

    根据表层扫描和意图探测结果，决定内容进入 PASS 还是 LAYER2。
    对应计划文档中的 pre_filter 函数。

    Args:
        surface_risk: 表层风险等级
        intent: 意图分类标签

    Returns:
        PASS: 直接放行，不调用后续 AI
        LAYER2: 进入深度审查层（节点 C）
    """
    if surface_risk == SurfaceRisk.HIGH:
        return Layer1Result.LAYER2
    if intent in (IntentLabel.HARASSMENT, IntentLabel.SOLICITATION):
        return Layer1Result.LAYER2
    if surface_risk == SurfaceRisk.LOW and intent in (
        IntentLabel.NORMAL_SOCIAL,
        IntentLabel.OPINION_EXPRESSION,
        IntentLabel.INFORMATION_SEEKING,
    ):
        return Layer1Result.PASS
    return Layer1Result.LAYER2


def deep_judge(violation: Violation, config: Config) -> FinalDecision:
    """深度仲裁（纯程序，零 Token）

    根据语境裁决员的违规判定，确定最终处理决定。

    Args:
        violation: 违规判定对象
        config: 系统配置（包含阈值参数）

    Returns:
        PASS: 放行
        BLOCK: 自动拦截
        HUMAN_REVIEW: 转入人工审核队列
    """
    if not violation.is_violation:
        return FinalDecision.PASS

    conf = violation.confidence
    sev = violation.severity

    if conf >= config.auto_block_confidence and sev in (
        ViolationSeverity.HIGH,
        ViolationSeverity.EXTREME,
    ):
        return FinalDecision.BLOCK

    if conf >= config.human_review_confidence or sev in (
        ViolationSeverity.HIGH,
        ViolationSeverity.EXTREME,
    ):
        return FinalDecision.HUMAN_REVIEW

    return FinalDecision.PASS
