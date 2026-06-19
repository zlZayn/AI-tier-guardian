"""节点 A - 表层扫描员 surface_scanner"""

from __future__ import annotations

import logging

from tier_guardian.config import Config, SurfaceRisk, PatternCategory
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import PatternHit, SurfaceScannerOutput
from tier_guardian.prompts import SURFACE_SCANNER

logger = logging.getLogger(__name__)


def run_surface_scanner(
    client: LLMClient, text: str, config: Config
) -> SurfaceScannerOutput:
    node_config = config.surface_scanner
    user_message = f'text: """{text}"""'

    try:
        result = client.chat(
            system_prompt=SURFACE_SCANNER.system_prompt,
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
