"""节点 A - 表层扫描员 surface_scanner"""

from __future__ import annotations

import logging

from tier_guardian.config import Config, SurfaceRisk, PatternCategory
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import PatternHit, SurfaceScannerOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """仅输出严格json，禁止任何其他文本。

你是字面模式扫描器。忽略语境、讽刺、隐含意义，仅匹配已知高风险字面模式。不推理意图。

检测类别：
- contact_exposure: 明确索要或提供联系方式（电话号、邮箱、社交账号）。注意：仅提及平台名称不构成命中（如"微信支付很方便"不命中，"加我微信"才命中）
- insult_template: 辱骂模板（脏话、人身攻击词组）
- illegal_transaction_keywords: 违法交易关键词（毒品、枪支、违禁品买卖）
- minor_protection_risk: 涉及未成年人的不当内容
- spam_template: 垃圾广告/刷屏模板
- other: 其他可疑模式

规则：
- fragment必须是从原文本精确截取的子串，不可改写、不可省略
- span为字符起止索引（含首不含尾），必须和fragment长度一致
- 最多返回5条命中。若命中超过5条，仅保留前5条且surface_risk至少为"medium"
- 无命中时patterns为空数组，surface_risk为"low"

无命中时输出（参照此格式）：
{"patterns":[],"surface_risk":"low"}

有命中时输出（参照此格式）：
{"patterns":[{"id":"P001","category":"contact_exposure","fragment":"加我微信13800138000","span":[0,12]}],"surface_risk":"high"}"""


def run_surface_scanner(
    client: LLMClient, text: str, locale: str, config: Config
) -> SurfaceScannerOutput:
    node_config = config.surface_scanner
    user_message = f'text: """{text}"""\nlocale: {locale}'

    try:
        result = client.chat(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            node_config=node_config,
            json_output=True,
        )
    except LLMClientError:
        logger.warning("Surface scanner failed, degrading to medium risk")
        return _degraded_output()

    return _parse_output(result)


def _parse_output(raw: dict) -> SurfaceScannerOutput:
    try:
        patterns_raw = raw.get("patterns", [])
        patterns = []
        for p in patterns_raw[:5]:
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
        risk_raw = raw.get("surface_risk", "medium")
        try:
            surface_risk = SurfaceRisk(risk_raw)
        except ValueError:
            surface_risk = SurfaceRisk.MEDIUM
        return SurfaceScannerOutput(patterns=patterns, surface_risk=surface_risk)
    except Exception:
        logger.exception("Failed to parse surface scanner output")
        return _degraded_output()


def _degraded_output() -> SurfaceScannerOutput:
    return SurfaceScannerOutput(patterns=[], surface_risk=SurfaceRisk.MEDIUM)
