"""节点 B - 意图探测员 intent_probe"""

from __future__ import annotations

import logging

from tier_guardian.config import Config, IntentLabel
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import IntentProbeOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """仅输出严格json，禁止任何其他文本。

你是沟通意图分类器。结合对话场景，从以下7类中选择最匹配的意图：

选择范围：
- normal_social: 正常社交（问候、闲聊、友好交流、日常寒暄）
- solicitation: 诱导（索要联系方式、引导加微信加群、导流到其他平台）
- harassment: 骚扰（人身攻击、辱骂、威胁、恐吓）
- spam_promotion: 垃圾推广（广告、刷屏、营销文案、传销话术）
- information_seeking: 信息寻求（提问、求助、打听）
- opinion_expression: 观点表达（发表看法、评论、吐槽、推荐）
- other: 以上均不匹配

边界参考：
  你好/在吗/今天天气不错 → normal_social
  加微信/加Q群/扫码添加 → solicitation
  白痴/滚/sb/你妈的 → harassment
  点击购买/最低价/月入十万 → spam_promotion
  请问/怎么/如何看待 → information_seeking
  我觉得/推荐/这玩意真 → opinion_expression

confidence 锚定：
  0.95 = 文本意图极其明确，无二义性
  0.70 = 有一定把握但存在其他可能解读
  0.50 = 非常模糊，几乎无法判断（此时选 other）

当文本可被多重解读时，选最可能类别并适当降低 confidence。不因文本极短或纯标点而强行分类为 normal_social——纯标点应归 other 且 confidence 较低。

输出示例 — 意图明确：
{"intent":"normal_social","confidence":0.95}

输出示例 — 意图模糊：
{"intent":"other","confidence":0.50}"""


def run_intent_probe(
    client: LLMClient, text: str, scene: str, config: Config
) -> IntentProbeOutput:
    node_config = config.intent_probe
    user_message = f'scene: {scene}\ntext: """{text}"""'

    try:
        result = client.chat(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            node_config=node_config,
            json_output=True,
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
