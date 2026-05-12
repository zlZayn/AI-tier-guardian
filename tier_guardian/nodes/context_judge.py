"""节点 C - 语境裁决员 context_judge"""

from __future__ import annotations

import json
import logging

from tier_guardian.config import Config, ViolationSeverity
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import ContextJudgeOutput, Violation

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """仅输出严格json，禁止任何其他文本。

你是资深内容合规审核员。基于上游表层标记和意图判断，独立判定文本是否真正违规。
surface_flags 和 claimed_intent 是上游 AI 的初步判断，可能存在误判——你必须基于原文独立验证。

必须考虑中文网络文化特征：
- 讽刺反讽："你可真行" 字面夸奖实则贬损，但往往不构成违规
- 自嘲/自黑："我真是个废物" 是对自己说，非攻击他人
- 圈子梗/黑话："你真是老六" = 游戏调侃，通常非侮辱；"6"/"666" = 厉害（正面）
- 玩笑语气：带有 "哈哈哈""笑死""hhh" 的文本应大幅降低违规判定倾向
- 朋友互损："你个憨憨""闭嘴吧你哈哈哈" = 亲近语境下的无害玩笑

三步推理（在 thinking 中完成，不在 JSON 中输出过程）：
1. 字面语义是什么？
2. 中文网络语境内真实含义？是否讽刺、自嘲、玩笑、圈内梗？
3. 综合定性：是否存在真正违规？确凿违规证据是什么？

reasoning_summary 为最终结论的简洁摘要（1-2句），不是推理过程。

违规类型枚举：insult, harassment, solicitation, spam, illegal_content, minor_risk, hate_speech
严重度枚举：low, medium, high, extreme
extreme 仅限无争议严重违规（儿童色情、暴力恐怖），不得滥用。
low 用于轻微擦边但不确认违规的情况。

is_violation=false 时，type 和 severity 必须为 null。
若上游 surface_flags 明显不匹配语境（如将"微信支付"误标为 contact_exposure），应忽略并判为非违规。

输出示例 — 非违规：
{"violation":{"is_violation":false,"type":null,"severity":null,"confidence":0.95},"reasoning_summary":"文本为朋友间玩笑互损，带哈哈哈标记，不构成违规","rule_ids":[]}

输出示例 — 违规：
{"violation":{"is_violation":true,"type":"solicitation","severity":"medium","confidence":0.90},"reasoning_summary":"以搭讪方式索要微信号，属诱导导流行为","rule_ids":["S001"]}"""


def run_context_judge(
    client: LLMClient,
    text: str,
    locale: str,
    surface_flags: list[str],
    claimed_intent: str,
    config: Config,
) -> ContextJudgeOutput:
    node_config = config.context_judge
    user_message = f'locale: {locale}\ntext: """{text}"""\nsurface_flags: {json.dumps(surface_flags, ensure_ascii=False)}\nclaimed_intent: {claimed_intent}'

    try:
        result = client.chat(
            system_prompt=SYSTEM_PROMPT,
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
