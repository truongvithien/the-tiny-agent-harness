from dataclasses import FrozenInstanceError

import pytest

from tiny_harness.types import Risk, RunContext, ToolCall, ToolResult


def test_tool_call_copies_mutable_arguments() -> None:
    raw = {"ticket_id": "T-1"}
    call = ToolCall(name="read_ticket", arguments=raw)
    raw["ticket_id"] = "changed"
    assert call.arguments == {"ticket_id": "T-1"}


def test_tool_call_deeply_freezes_nested_model_arguments() -> None:
    raw = {
        "request": {
            "recipients": ["learner@example.test"],
            "metadata": {"priority": "normal"},
        }
    }

    call = ToolCall(name="publish", arguments=raw)
    raw["request"]["recipients"].append("changed@example.test")
    raw["request"]["metadata"]["priority"] = "changed"

    assert call.arguments == {
        "request": {
            "recipients": ("learner@example.test",),
            "metadata": {"priority": "normal"},
        }
    }
    with pytest.raises(AttributeError):
        call.arguments["request"]["recipients"].append("tampered@example.test")
    with pytest.raises(TypeError):
        call.arguments["request"]["metadata"]["priority"] = "tampered"


def test_tool_result_requires_an_error_when_unsuccessful() -> None:
    with pytest.raises(ValueError, match="error"):
        ToolResult(ok=False)


def test_context_is_immutable_at_its_boundary() -> None:
    context = RunContext(task="inspect", acceptance_criteria=("evidence",))
    with pytest.raises(FrozenInstanceError):
        context.task = "changed"  # type: ignore[misc]


def test_risk_values_are_stable_for_serialization() -> None:
    assert [risk.value for risk in Risk] == ["read", "write", "consequential"]
