import importlib.util
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

from tiny_harness.types import FinalAnswer, ModelDecision, ToolCall

EXERCISE = Path("course/06-openai-integration/exercise.py")
SOLUTION = Path("solutions/06-openai-integration/exercise.py")


def load_decode(path: Path) -> Callable[[Mapping[str, Any]], ModelDecision]:
    spec = importlib.util.spec_from_file_location("openai_exercise", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decode_decision


def tool_message(name: str, arguments: object) -> dict[str, Any]:
    return {
        "content": None,
        "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
    }


@pytest.mark.learner
def test_learner_decodes_a_tool_call() -> None:
    decode = load_decode(EXERCISE)

    assert decode(tool_message("lookup", '{"key": "answer"}')) == ToolCall(
        "lookup", {"key": "answer"}
    )


@pytest.mark.learner
def test_learner_decodes_a_final_answer() -> None:
    decode = load_decode(EXERCISE)

    assert decode({"content": "The value is 42."}) == FinalAnswer("The value is 42.")


@pytest.mark.learner
def test_learner_rejects_malformed_arguments() -> None:
    decode = load_decode(EXERCISE)

    with pytest.raises(ValueError):
        decode(tool_message("lookup", "{oops"))


def test_solution_decodes_a_tool_call() -> None:
    decode = load_decode(SOLUTION)

    assert decode(tool_message("lookup", '{"key": "answer"}')) == ToolCall(
        "lookup", {"key": "answer"}
    )


def test_solution_treats_absent_arguments_as_empty() -> None:
    decode = load_decode(SOLUTION)

    assert decode(tool_message("ping", "")) == ToolCall("ping", {})


def test_solution_decodes_a_final_answer() -> None:
    decode = load_decode(SOLUTION)

    assert decode({"content": "The value is 42.", "tool_calls": []}) == FinalAnswer(
        "The value is 42."
    )


def test_solution_prefers_a_tool_call_over_text() -> None:
    decode = load_decode(SOLUTION)

    message = {
        "content": "I will look it up.",
        "tool_calls": [{"function": {"name": "lookup", "arguments": "{}"}}],
    }

    assert decode(message) == ToolCall("lookup", {})


@pytest.mark.parametrize(
    "message",
    [
        {"content": "   "},
        {},
        {"content": None, "tool_calls": []},
    ],
)
def test_solution_rejects_an_empty_message(message: dict[str, Any]) -> None:
    decode = load_decode(SOLUTION)

    with pytest.raises(ValueError):
        decode(message)


@pytest.mark.parametrize("arguments", ["{oops", "[1, 2]"])
def test_solution_rejects_unusable_arguments(arguments: str) -> None:
    decode = load_decode(SOLUTION)

    with pytest.raises(ValueError):
        decode(tool_message("lookup", arguments))


def test_solution_rejects_a_nameless_tool_call() -> None:
    decode = load_decode(SOLUTION)

    with pytest.raises(ValueError):
        decode({"tool_calls": [{"function": {"arguments": "{}"}}]})
