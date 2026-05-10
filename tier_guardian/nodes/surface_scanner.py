"""节点 A - 表层扫描员 surface_scanner"""

from __future__ import annotations

import json
import logging

from tier_guardian.config import Config, SurfaceRisk, PatternCategory
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import PatternHit, SurfaceScannerOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """仅输出严格JSON，禁止任何其他文本。

你是字面模式扫描器。忽略语境、讽刺、隐含意义，仅匹配已知高风险字面模式。

检测类别：
- contact_exposure: 联系方式（电话、邮箱、社交账号）
- insult_template: 辱骂模板
- illegal_transaction_keywords: 违法交易词（毒品、枪支等）
- minor_protection_risk: 未成年人风险
- spam_template: 垃圾广告/刷屏
- other: 其他

规则：
- 最多返回5条命中，超过则仅前5条且surface_risk至少为medium
- 无命中时patterns为空数组，surface_risk为low
- span为字符起止索引（含首不含尾）

输出格式（仅此JSON，无其他内容）：
{"patterns":[{"id":"P001","category":"contact_exposure","fragment":"13800138000","span":[0,11]}],"surface_risk":"low"}"""


def run_surface_scanner(client: LLMClient, text: str, locale: str, config: Config) -> SurfaceScannerOutput:
    node_config = config.surface_scanner
    user_message = f'text: """{text}"""\nlocale: {locale}\n\n仅输出JSON对象。'

    try:
        result = client.chat(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            node_config=node_config,
            response_schema={"type": "json_object"},
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
            patterns.append(PatternHit(
                id=p.get("id", "UNKNOWN"),
                category=category,
                fragment=p.get("fragment", ""),
                span=p.get("span", []),
            ))
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
