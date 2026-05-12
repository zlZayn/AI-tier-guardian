"""中央编排器 orchestrator

Layer 1（并行）：A 表层扫描 + B 意图探测 → 前置仲裁 → PASS / LAYER2
Layer 2（串行）：C 语境裁决 → 深度仲裁 → PASS / BLOCK / HUMAN_REVIEW
Layer 3（按需）：D 证据摘要，仅 HUMAN_REVIEW 时触发
"""

from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import asdict

from tier_guardian.arbitration import deep_judge, pre_filter
from tier_guardian.cache import CacheManager
from tier_guardian.config import (
    Config,
    FinalDecision,
    IntentLabel,
    Layer1Result,
    PatternCategory,
    SurfaceRisk,
    ViolationSeverity,
)
from tier_guardian.llm_client import LLMClient
from tier_guardian.models import (
    ContextJudgeOutput,
    EvidenceSummarizerOutput,
    IntentProbeOutput,
    PatternHit,
    SimilarCase,
    SurfaceScannerOutput,
    TaskContext,
    Violation,
)
from tier_guardian.nodes.context_judge import run_context_judge
from tier_guardian.nodes.evidence_summarizer import run_evidence_summarizer
from tier_guardian.nodes.intent_probe import run_intent_probe
from tier_guardian.nodes.surface_scanner import run_surface_scanner

logger = logging.getLogger(__name__)


class Orchestrator:
    """中央编排器，控制全链路流程。

    用法:
        orch = Orchestrator(config)
        result = orch.process("用户评论内容", scene="comment")
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._llm = LLMClient(config)
        self._cache = CacheManager(config)

    def close(self) -> None:
        self._llm.close()

    def process(
        self, text: str, scene: str = "comment", locale: str = "zh-CN"
    ) -> TaskContext:
        ctx = TaskContext(text=text, locale=locale, scene=scene)

        cached = self._cache.get_request_cache(text, scene, locale)
        if cached is not None:
            logger.info("Request cache hit, returning cached decision")
            ctx.final_decision = FinalDecision(cached["final_decision"])
            return ctx

        surface_output, intent_output = self._run_layer1(text, locale, scene)

        ctx.nodes.surface = surface_output
        ctx.nodes.intent = intent_output

        decision = pre_filter(surface_output.surface_risk, intent_output.intent)

        if decision == Layer1Result.PASS:
            ctx.final_decision = FinalDecision.PASS
            self._cache_result(ctx)
            logger.info("Layer1 PASS: task_id=%s", ctx.task_id)
            return ctx

        surface_flags = [p.category.value for p in surface_output.patterns]
        claimed_intent = intent_output.intent.value

        judge_output = self._run_layer2(text, locale, surface_flags, claimed_intent)
        ctx.nodes.judge = judge_output

        final = deep_judge(judge_output.violation, self._config)
        ctx.final_decision = final

        if final == FinalDecision.HUMAN_REVIEW:
            summary_output = self._run_summary(
                text, surface_output, intent_output, judge_output
            )
            ctx.nodes.summary = summary_output

        self._cache_result(ctx)
        logger.info(
            "Pipeline complete: task_id=%s final=%s",
            ctx.task_id,
            ctx.final_decision.value,
        )
        return ctx

    def _run_layer1(
        self, text: str, locale: str, scene: str
    ) -> tuple[SurfaceScannerOutput, IntentProbeOutput]:
        """并行运行节点 A 和 B"""

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            surface_future = executor.submit(self._run_surface_with_cache, text, locale)
            intent_future = executor.submit(self._run_intent_with_cache, text, scene)

            try:
                surface_output = surface_future.result()
            except Exception:
                logger.warning("Surface scanner failed, degrading")
                surface_output = SurfaceScannerOutput(
                    patterns=[], surface_risk=SurfaceRisk.MEDIUM
                )

            try:
                intent_output = intent_future.result()
            except Exception:
                logger.warning("Intent probe failed, degrading")
                intent_output = IntentProbeOutput()

        return surface_output, intent_output

    def _run_surface_with_cache(self, text: str, locale: str) -> SurfaceScannerOutput:
        input_params = {"text": text, "locale": locale}
        cached = self._cache.get_node_cache("surface_scanner", input_params)
        if cached is not None:
            return _reconstruct_surface_output(cached)
        output = run_surface_scanner(self._llm, text, locale, self._config)
        self._cache.set_node_cache("surface_scanner", input_params, asdict(output))
        return output

    def _run_intent_with_cache(self, text: str, scene: str) -> IntentProbeOutput:
        input_params = {"text": text, "scene": scene}
        cached = self._cache.get_node_cache("intent_probe", input_params)
        if cached is not None:
            return _reconstruct_intent_output(cached)
        output = run_intent_probe(self._llm, text, scene, self._config)
        self._cache.set_node_cache("intent_probe", input_params, asdict(output))
        return output

    def _run_layer2(
        self, text: str, locale: str, surface_flags: list[str], claimed_intent: str
    ) -> ContextJudgeOutput:
        input_params = {
            "text": text,
            "locale": locale,
            "surface_flags": surface_flags,
            "claimed_intent": claimed_intent,
        }
        cached = self._cache.get_node_cache("context_judge", input_params)
        if cached is not None:
            return _reconstruct_judge_output(cached)
        output = run_context_judge(
            self._llm, text, locale, surface_flags, claimed_intent, self._config
        )
        self._cache.set_node_cache("context_judge", input_params, asdict(output))
        return output

    def _run_summary(
        self,
        text: str,
        surface_output: SurfaceScannerOutput,
        intent_output: IntentProbeOutput,
        judge_output: ContextJudgeOutput,
    ) -> EvidenceSummarizerOutput:
        similar_cases = self._load_similar_cases(judge_output)
        output = run_evidence_summarizer(
            self._llm,
            text,
            surface_output.surface_risk.value,
            intent_output.intent.value,
            judge_output,
            similar_cases,
            self._config,
        )
        return output

    def _load_similar_cases(
        self, judge_output: ContextJudgeOutput
    ) -> list[SimilarCase]:
        # TODO: 集成向量检索，从案例库中加载相似历史案例
        return []

    def _cache_result(self, ctx: TaskContext) -> None:
        self._cache.set_request_cache(
            ctx.text,
            ctx.scene,
            ctx.locale,
            {
                "final_decision": ctx.final_decision.value
                if ctx.final_decision
                else None
            },
        )

    @property
    def cache_stats(self):
        return self._cache.stats


def _reconstruct_surface_output(data: dict) -> SurfaceScannerOutput:
    patterns = []
    for p in data.get("patterns", []):
        try:
            category = PatternCategory(p.get("category", "other"))
        except ValueError:
            category = PatternCategory.OTHER
        patterns.append(
            PatternHit(
                id=p.get("id", "UNKNOWN"),
                category=category,
                fragment=p.get("fragment", ""),
                span=p.get("span", []),
            )
        )
    try:
        risk = SurfaceRisk(data.get("surface_risk", "medium"))
    except ValueError:
        risk = SurfaceRisk.MEDIUM
    return SurfaceScannerOutput(patterns=patterns, surface_risk=risk)


def _reconstruct_intent_output(data: dict) -> IntentProbeOutput:
    try:
        intent = IntentLabel(data.get("intent", "other"))
    except ValueError:
        intent = IntentLabel.OTHER
    confidence = float(data.get("confidence", 0.0))
    return IntentProbeOutput(intent=intent, confidence=confidence)


def _reconstruct_judge_output(data: dict) -> ContextJudgeOutput:
    v_data = data.get("violation", {})
    is_violation = bool(v_data.get("is_violation", False))
    confidence = float(v_data.get("confidence", 0.0))

    if is_violation:
        v_type = v_data.get("type") or None
        sev_raw = v_data.get("severity")
        try:
            severity = ViolationSeverity(sev_raw) if sev_raw else None
        except ValueError:
            severity = ViolationSeverity.MEDIUM
    else:
        v_type = None
        severity = None

    violation = Violation(
        is_violation=is_violation,
        type=v_type,
        severity=severity,
        confidence=confidence,
    )
    return ContextJudgeOutput(
        violation=violation,
        reasoning_summary=str(data.get("reasoning_summary", "")),
        rule_ids=data.get("rule_ids", []),
    )
