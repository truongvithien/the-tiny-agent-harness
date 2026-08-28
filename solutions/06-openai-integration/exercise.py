import json
from typing import Any, Mapping

from tiny_harness.types import FinalAnswer, ModelDecision, ToolCall


def decode_decision(message: Mapping[str, Any]) -> ModelDecision:
    tool_calls = message.get("tool_calls") or ()
    if tool_calls:
        function = tool_calls[0]["function"]
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("tool call is missing a name")
        raw = function.get("arguments")
        if isinstance(raw, Mapping):
            arguments: Mapping[str, Any] = raw
        elif raw is None or raw == "":
            arguments = {}
        else:
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"tool call {name} has malformed JSON arguments"
                ) from error
            if not isinstance(decoded, Mapping):
                raise ValueError(f"tool call {name} arguments must decode to an object")
            arguments = decoded
        return ToolCall(name, arguments)
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return FinalAnswer(content)
    raise ValueError("model returned neither a tool call nor text")
