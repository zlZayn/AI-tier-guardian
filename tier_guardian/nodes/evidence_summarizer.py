"""节点 D - 证据摘要员 evidence_summarizer"""

from __future__ import annotations

import json
import logging

from tier_guardian.config import Config
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import (
    ContextJudgeOutput,
    EvidenceSummarizerOutput,
    SimilarCase,
)
from tier_guardian.prompts import EVIDENCE_SUMMARIZER

logger = logging.getLogger(__name__)


def run_evidence_summarizer(
    client: LLMClient,
    text: str,
    surface_risk: str,
    intent: str,
    judge_output: ContextJudgeOutput,
    similar_cases: list[SimilarCase],
    config: Config,
) -> EvidenceSummarizerOutput:
    node_config = config.evidence_summarizer
    user_message = f'text: """{text}"""\nsurface_risk: {surface_risk}\nintent: {intent}\njudge: {json.dumps({"is_violation": judge_output.violation.is_violation, "type": judge_output.violation.type, "severity": judge_output.violation.severity.value if judge_output.violation.severity else None, "confidence": judge_output.violation.confidence, "reasoning": judge_output.reasoning_summary, "rule_ids": judge_output.rule_ids}, ensure_ascii=False)}\ncases: {json.dumps([{"case_id": c.case_id, "resolution": c.resolution, "summary": c.summary} for c in similar_cases], ensure_ascii=False)}'

    try:
        result = client.chat(
            system_prompt=EVIDENCE_SUMMARIZER.system_prompt,
            user_message=user_message,
            node_config=node_config,
            json_output=True,
        )
    except LLMClientError:
        logger.warning("Evidence summarizer failed, providing minimal summary")
        return _fallback_output(text, judge_output)

    return _parse_output(result, similar_cases)


def _parse_output(
    raw: dict, similar_cases_from_input: list[SimilarCase]
) -> EvidenceSummarizerOutput:
    try:
        one_liner = str(raw.get("one_liner", ""))
        highlight_ranges = raw.get("highlight_ranges", [])
        if not isinstance(highlight_ranges, list):
            highlight_ranges = []

        cases_raw = raw.get("similar_cases", [])
        cases = (
            similar_cases_from_input
            if not cases_raw
            else [
                SimilarCase(
                    case_id=c.get("case_id", ""),
                    resolution=c.get("resolution", ""),
                    summary=c.get("summary", ""),
                )
                for c in cases_raw[:5]
            ]
        )

        suggested_action = str(raw.get("suggested_action", "HUMAN_REVIEW"))

        return EvidenceSummarizerOutput(
            one_liner=one_liner,
            highlight_ranges=highlight_ranges,
            similar_cases=cases,
            suggested_action=suggested_action,
        )
    except Exception:
        logger.exception("Failed to parse evidence summarizer output")
        return EvidenceSummarizerOutput(
            one_liner="解析失败，请人工审核",
            suggested_action="HUMAN_REVIEW",
        )


def _fallback_output(
    text: str, judge_output: ContextJudgeOutput
) -> EvidenceSummarizerOutput:
    return EvidenceSummarizerOutput(
        one_liner=f"文本被标记为可疑（置信度{judge_output.violation.confidence}），需人工审核",
        highlight_ranges=[],
        similar_cases=[],
        suggested_action="HUMAN_REVIEW",
    )
