from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import OpenAI

from tier_guardian.config import Config, NodeConfig

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    pass


class LLMResponseError(LLMClientError):
    pass


class LLMClient:
    """统一的 LLM 调用客户端，使用 openai SDK 通信。
    所有 AI 节点共享同一实例，通过参数独立控制思考模式与生成配置。
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url,
        )

    def close(self) -> None:
        self._client.close()

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        node_config: NodeConfig,
        json_output: bool = False,
    ) -> dict[str, Any]:
        try:
            kwargs: dict[str, Any] = {
                "model": self._config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": node_config.temperature,
                "max_tokens": node_config.max_tokens,
            }
            if node_config.thinking:
                kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            if json_output:
                kwargs["response_format"] = {"type": "json_object"}

            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            raise LLMResponseError(f"LLM call failed: {e}")

        content = response.choices[0].message.content or ""

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            repaired = _try_repair_json(content)
            if repaired is not None:
                logger.warning("JSON was truncated, repaired successfully")
                return repaired
            logger.warning("Failed to parse AI output as JSON: %s", content[:200])
            raise LLMResponseError("Failed to parse AI output as JSON")


def _try_repair_json(raw: str) -> Optional[dict[str, Any]]:
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in raw:
        if escape:
            escape = False
            continue
        if ch == '"' and not in_string:
            in_string = True
            continue
        if ch == '"' and in_string:
            in_string = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    repaired = raw.rstrip()

    if in_string:
        repaired += '"'

    if repaired.rstrip().endswith(":"):
        repaired += '""'

    for opener in reversed(stack):
        if opener == "{":
            repaired += "}"
        elif opener == "[":
            repaired += "]"

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    if not stack:
        return None

    repaired2 = raw.rstrip()
    if in_string:
        repaired2 += '"'
    if repaired2.rstrip().endswith(":"):
        repaired2 += "null"

    for opener in reversed(stack):
        if opener == "{":
            repaired2 += "}"
        elif opener == "[":
            repaired2 += "]"

    try:
        return json.loads(repaired2)
    except json.JSONDecodeError:
        return None
