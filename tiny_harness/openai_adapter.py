from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from tiny_harness.types import FinalAnswer, ModelDecision, RunContext, ToolCall

DEFAULT_SYSTEM_PROMPT = (
    "You are the model inside an agent harness. Propose exactly one next step: "
    "either call one of the supplied tools or give a final answer. "
    "The harness authorizes, executes, records, and verifies every action, so "
    "never claim an action was performed unless a tool result reports it."
)


def _attribute(value: object, key: str) -> object:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def openai_tools(tool_specs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": dict(spec["input_schema"]),
            },
        }
        for spec in tool_specs
    ]


def openai_messages(
    context: RunContext,
    *,
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    criteria = "\n".join(f"- {criterion}" for criterion in context.acceptance_criteria)
    instructions = system_prompt or DEFAULT_SYSTEM_PROMPT
    messages = [
        {
            "role": "system",
            "content": (
                f"{instructions}\n\n"
                f"Acceptance criteria:\n{criteria or '- none supplied'}\n\n"
                f"Remaining iterations: {context.remaining_iterations}"
            ),
        },
        {"role": "user", "content": context.task},
    ]
    for observation in context.observations:
        messages.append(
            {
                "role": "user",
                "content": f"Result from {observation.source}:\n{observation.content}",
            }
        )
    return messages


def _decode_arguments(raw: object, name: str) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        return raw
    if raw is None or raw == "":
        return {}
    if not isinstance(raw, str):
        raise ValueError(f"tool call {name} has non-textual arguments")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"tool call {name} has malformed JSON arguments") from error
    if not isinstance(decoded, Mapping):
        raise ValueError(f"tool call {name} arguments must decode to an object")
    return decoded


def decode_decision(message: Mapping[str, Any]) -> ModelDecision:
    if not isinstance(message, Mapping):
        raise TypeError("message must be a mapping")
    tool_calls = message.get("tool_calls") or ()
    if tool_calls:
        function = _attribute(tool_calls[0], "function")
        name = _attribute(function, "name")
        if not isinstance(name, str) or not name:
            raise ValueError("tool call is missing a name")
        arguments = _decode_arguments(_attribute(function, "arguments"), name)
        return ToolCall(name, arguments)
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return FinalAnswer(content)
    raise ValueError("model returned neither a tool call nor text")


def _response_message(response: object) -> dict[str, Any]:
    choices = _attribute(response, "choices")
    if not choices:
        raise ValueError("model response contained no choices")
    message = _attribute(choices[0], "message")
    if message is None:
        raise ValueError("model response contained no message")
    raw_calls = _attribute(message, "tool_calls") or ()
    return {
        "content": _attribute(message, "content"),
        "tool_calls": [
            {
                "function": {
                    "name": _attribute(_attribute(call, "function"), "name"),
                    "arguments": _attribute(_attribute(call, "function"), "arguments"),
                }
            }
            for call in raw_calls
        ],
    }


class OpenAIModel:
    def __init__(
        self,
        *,
        client: Any,
        model: str,
        system_prompt: str | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._system_prompt = system_prompt

    def next_decision(
        self,
        context: RunContext,
        tool_specs: Sequence[Mapping[str, Any]],
    ) -> ModelDecision:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages(context, system_prompt=self._system_prompt),
        }
        tools = openai_tools(tool_specs)
        if tools:
            request["tools"] = tools
        response = self._client.chat.completions.create(**request)
        return decode_decision(_response_message(response))


def client_from_environment() -> Any:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    try:
        from openai import OpenAI
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "the openai package is not installed; "
            "install it with python -m pip install -e '.[openai]'"
        ) from error
    return OpenAI()
