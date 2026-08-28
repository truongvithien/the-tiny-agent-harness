from typing import Any, Mapping

from tiny_harness.types import FinalAnswer, ModelDecision, ToolCall


def decode_decision(message: Mapping[str, Any]) -> ModelDecision:
    """Translate one OpenAI assistant message into a harness decision.

    A message looks like either of these:

        {"content": None,
         "tool_calls": [{"function": {"name": "lookup",
                                      "arguments": '{"key": "answer"}'}}]}

        {"content": "The value is 42.", "tool_calls": []}

    Return a ToolCall when the message requests a tool, and a FinalAnswer when
    it supplies text. Raise ValueError when the message can be neither.
    """
    raise NotImplementedError("complete the response translation from Lesson 6")
