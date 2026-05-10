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

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """仅输出严格JSON，禁止任何其他文本。

你是人工审核员助理。基于已有判定信息，整理为审核摘要。
不要重新做出违规判断。不要添加新解释或推断。

任务：
1. one_liner: 一句话概括可疑行为
2. highlight_ranges: 可疑字符的起止索引区间
3. similar_cases: 直接引用输入中的相似案例
4. suggested_action: BLOCK/PASS/HUMAN_REVIEW

输出格式（仅此JSON，无其他内容）：
{"one_liner":"用户以评论为掩护，引导添加私人联系方式","highlight_ranges":[[12,24]],"similar_cases":[{"case_id":"CASE-2341","resolution":"BLOCK","summary":"伪装活动导流"}],"suggested_action":"BLOCK"}"""


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
    user_message = f'text: """{text}"""\nsurface_risk: {surface_risk}\nintent: {intent}\njudge: {json.dumps({"is_violation":judge_output.violation.is_violation,"type":judge_output.violation.type,"severity":judge_output.violation.severity.value if judge_output.violation.severity else None,"confidence":judge_output.violation.confidence,"reasoning":judge_output.reasoning_summary,"rule_ids":judge_output.rule_ids}, ensure_ascii=False)}\ncases: {json.dumps([{"case_id":c.case_id,"resolution":c.resolution,"summary":c.summary} for c in similar_cases], ensure_ascii=False)}\n\n仅输出JSON对象。'

    try:
        result = client.chat(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            node_config=node_config,
            response_schema={"type": "json_object"},
        )
    except LLMClientError:
        logger.warning("Evidence summarizer failed, providing minimal summary")
        return _fallback_output(text, judge_output)

    return _parse_output(result, similar_cases)


def _parse_output(raw: dict, similar_cases_from_input: list[SimilarCase]) -> EvidenceSummarizerOutput:
    try:
        one_liner = str(raw.get("one_liner", ""))
        highlight_ranges = raw.get("highlight_ranges", [])
        if not isinstance(highlight_ranges, list):
            highlight_ranges = []

        cases_raw = raw.get("similar_cases", [])
        cases = similar_cases_from_input if not cases_raw else [
            SimilarCase(
                case_id=c.get("case_id", ""),
                resolution=c.get("resolution", ""),
                summary=c.get("summary", ""),
            )
            for c in cases_raw[:5]
        ]

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


def _fallback_output(text: str, judge_output: ContextJudgeOutput) -> EvidenceSummarizerOutput:
    return EvidenceSummarizerOutput(
        one_liner=f"文本被标记为可疑（置信度{judge_output.violation.confidence}），需人工审核",
        highlight_ranges=[],
        similar_cases=[],
        suggested_action="HUMAN_REVIEW",
    )
