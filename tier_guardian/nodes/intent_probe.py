"""节点 B - 意图探测员 intent_probe"""

from __future__ import annotations

import logging

from tier_guardian.config import Config, IntentLabel
from tier_guardian.llm_client import LLMClient, LLMClientError
from tier_guardian.models import IntentProbeOutput
from tier_guardian.prompts import INTENT_PROBE

logger = logging.getLogger(__name__)


def run_intent_probe(
    client: LLMClient, text: str, scene: str, config: Config
) -> IntentProbeOutput:
    node_config = config.intent_probe
    user_message = f'scene: {scene}\ntext: """{text}"""'

    try:
        result = client.chat(
            system_prompt=INTENT_PROBE.system_prompt,
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
