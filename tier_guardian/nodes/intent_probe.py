"""节点 B - 意图探测员 intent_probe"""

from __future__ import annotations

import json
import logging

from tier_guardian.config import Config, IntentLabel
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import IntentProbeOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """仅输出严格JSON，禁止任何其他文本。

你是沟通意图分类器。从以下7类中选择最匹配的：

选择范围：
- normal_social: 正常社交（问候、闲聊、友好交流）
- solicitation: 诱导（索要联系方式、引导加微信加群、导流到其他平台）
- harassment: 骚扰（人身攻击、辱骂、威胁）
- spam_promotion: 垃圾推广（广告、刷屏、营销文案）
- information_seeking: 信息寻求（提问、求助）
- opinion_expression: 观点表达（发表看法、评论）
- other: 以上均不匹配

边界参考：你好/在吗→normal_social | 加微信加Q群→solicitation | 白痴/滚/sb→harassment | 点击购买/最低价→spam_promotion | 请问/怎么/如何看待→information_seeking | 我觉得/推荐→opinion_expression

输出格式（仅此JSON，无其他内容）：
{"intent":"normal_social","confidence":0.95}"""


def run_intent_probe(client: LLMClient, text: str, scene: str, config: Config) -> IntentProbeOutput:
    node_config = config.intent_probe
    user_message = f'text: """{text}"""\n\n仅输出JSON对象。'

    try:
        result = client.chat(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            node_config=node_config,
            response_schema={"type": "json_object"},
        )
    except LLMClientError:
        logger.warning("Intent probe failed, degrading")
        return _degraded_output()

    return _parse_output(result)


def _parse_output(raw: dict) -> IntentProbeOutput:
    try:
        intent_raw = raw.get("intent", "other")
        try:
            intent = IntentLabel(intent_raw)
        except ValueError:
            intent = IntentLabel.OTHER
        confidence = float(raw.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
        return IntentProbeOutput(intent=intent, confidence=confidence)
    except Exception:
        logger.exception("Failed to parse intent probe output")
        return _degraded_output()


def _degraded_output() -> IntentProbeOutput:
    return IntentProbeOutput(intent=IntentLabel.OTHER, confidence=0.0)
