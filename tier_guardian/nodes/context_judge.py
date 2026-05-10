"""节点 C - 语境裁决员 context_judge"""

from __future__ import annotations

import json
import logging

from tier_guardian.config import Config, ViolationSeverity
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import ContextJudgeOutput, Violation

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """仅输出严格JSON，禁止任何其他文本。

你是资深内容合规审核员。基于表层标记和意图判断，独立判定文本是否真正违规。
必须考虑中文网络文化：讽刺反讽、自嘲、圈子梗、黑话、玩笑语气（如"哈哈哈"）。

三步推理（内部完成，不输出推理过程）：
1. 字面语义是什么？
2. 中文网络语境内真实含义？是否讽刺、自嘲、玩笑？
3. 综合定性：是否存在真正违规？

违规类型枚举：insult, harassment, solicitation, spam, illegal_content, minor_risk, hate_speech
严重度枚举：low, medium, high, extreme
extreme仅限无争议严重违规（儿童色情、暴力恐怖），不准滥用。

is_violation=false时，type和severity必须为null。

输出格式（仅此JSON，无其他内容）：
{"violation":{"is_violation":false,"type":null,"severity":null,"confidence":0.95},"reasoning_summary":"文本为正常社交，未发现违规","rule_ids":[]}"""


def run_context_judge(
    client: LLMClient,
    text: str,
    locale: str,
    surface_flags: list[str],
    claimed_intent: str,
    config: Config,
) -> ContextJudgeOutput:
    node_config = config.context_judge
    user_message = f'text: """{text}"""\nsurface_flags: {json.dumps(surface_flags, ensure_ascii=False)}\nclaimed_intent: {claimed_intent}\n\n仅输出JSON对象。'

    try:
        result = client.chat(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            node_config=node_config,
            response_schema={"type": "json_object"},
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
        violation=Violation(is_violation=False, type=None, severity=None, confidence=0.0),
        reasoning_summary="",
        rule_ids=[],
    )
