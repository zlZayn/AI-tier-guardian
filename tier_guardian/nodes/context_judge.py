"""节点 C - 语境裁决员 context_judge"""

from __future__ import annotations

import json
import logging

from tier_guardian.config import Config, ViolationSeverity
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import ContextJudgeOutput, Violation
from tier_guardian.prompts import CONTEXT_JUDGE

logger = logging.getLogger(__name__)


def run_context_judge(
    client: LLMClient,
    text: str,
    surface_flags: list[str],
    claimed_intent: str,
    config: Config,
) -> ContextJudgeOutput:
    node_config = config.context_judge
    user_message = f'text: """{text}"""\nsurface_flags: {json.dumps(surface_flags, ensure_ascii=False)}\nclaimed_intent: {claimed_intent}'

    try:
        result = client.chat(
            system_prompt=CONTEXT_JUDGE.system_prompt,
            user_message=user_message,
            node_config=node_config,
            json_output=True,
        )
    except LLMClientError:
        logger.warning("Context judge failed, degrading to pass")
        return _degraded_output()

    return _parse_output(result)


def _parse_output(raw: dict) -> ContextJudgeOutput:
    try:
        violation_raw = raw.get("violation", {})
        is_violation = bool(violation_raw.get("is_violation", False))
        confidence = float(violation_raw.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        if is_violation:
            violation_type = violation_raw.get("type") or None
            severity_raw = violation_raw.get("severity")
            try:
                severity = ViolationSeverity(severity_raw) if severity_raw else None
            except ValueError:
                severity = ViolationSeverity.MEDIUM
        else:
            violation_type = None
            severity = None

        violation = Violation(
            is_violation=is_violation,
            type=violation_type,
            severity=severity,
            confidence=confidence,
        )

        reasoning = str(raw.get("reasoning_summary", ""))
        rule_ids = raw.get("rule_ids", [])
        if not isinstance(rule_ids, list):
            rule_ids = []

        return ContextJudgeOutput(
            violation=violation,
            reasoning_summary=reasoning,
            rule_ids=rule_ids,
        )
    except Exception:
        logger.exception("Failed to parse context judge output")
        return _degraded_output()


def _degraded_output() -> ContextJudgeOutput:
    return ContextJudgeOutput(
        violation=Violation(
            is_violation=False, type=None, severity=None, confidence=0.0
        ),
        reasoning_summary="",
        rule_ids=[],
    )
