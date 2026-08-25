from collections.abc import Mapping, Sequence
from typing import Any

import pytest
import tiny_harness

from tiny_harness.events import MemoryEventSink
from tiny_harness.models import ModelAdapter, ScriptedModel
from tiny_harness.policy import RiskPolicy
from tiny_harness.runner import RunConfig, Runner
from tiny_harness.tools import FunctionTool, ToolRegistry
from tiny_harness.types import (
    FinalAnswer,
    ModelDecision,
    Risk,
    RunContext,
    RunStatus,
    ToolCall,
    ToolResult,
    VerificationResult,
)
from tiny_harness.verification import AcceptFinalAnswer, Verifier


def test_runner_executes_one_tool_then_verifies_final_answer() -> None:
    events = MemoryEventSink(run_id="run-1")
    runner = Runner(
        model=ScriptedModel(
            [ToolCall("lookup", {"key": "answer"}), FinalAnswer("The value is 42.")]
        ),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="lookup",
                    description="Read a value.",
                    input_schema={"type": "object"},
                    risk=Risk.READ,
                    handler=lambda _: ToolResult(ok=True, output="42"),
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=4, timeout_seconds=5),
    )
    result = runner.run("Find the value", ("State the retrieved value",))
    assert result.status is RunStatus.SUCCEEDED
    assert result.answer == "The value is 42."
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "tool_result",
        "model_decision",
        "verification",
        "run_finished",
    ]


def test_runner_refuses_consequential_call_without_invoking_handler() -> None:
    invocations: list[Mapping[str, Any]] = []
    events = MemoryEventSink(run_id="run-refused")
    runner = Runner(
        model=ScriptedModel([ToolCall("publish", {"message": "hello"})]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="publish",
                    description="Publish a message.",
                    input_schema={"type": "object"},
                    risk=Risk.CONSEQUENTIAL,
                    handler=lambda arguments: (
                        invocations.append(arguments) or ToolResult(ok=True)
                    ),
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Publish a greeting", ("Greeting is published",))

    assert result.status is RunStatus.APPROVAL_REFUSED
    assert invocations == []
    assert events.events[-1].kind == "run_finished"
    assert result.event_count == len(events.events)


def test_runner_stops_at_exact_iteration_budget_without_final_answer() -> None:
    invocations = 0

    def count_invocation(_arguments: Mapping[str, Any]) -> ToolResult:
        nonlocal invocations
        invocations += 1
        return ToolResult(ok=True, output="still working")

    events = MemoryEventSink(run_id="run-budget")
    runner = Runner(
        model=ScriptedModel([ToolCall("work", {}) for _ in range(3)]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="work",
                    description="Perform one unit of work.",
                    input_schema={"type": "object"},
                    risk=Risk.WRITE,
                    handler=count_invocation,
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=3),
    )

    result = runner.run("Keep working", ("Return a final answer",))

    assert result.status is RunStatus.BUDGET_EXHAUSTED
    assert invocations == 3
    assert sum(event.kind == "model_decision" for event in events.events) == 3
    assert events.events[-1].kind == "run_finished"


def test_runner_rejects_false_completion_as_failure() -> None:
    class RejectEvidence:
        def verify(
            self, _context: RunContext, _answer: FinalAnswer
        ) -> VerificationResult:
            return VerificationResult(accepted=False, reason="missing evidence")

    events = MemoryEventSink(run_id="run-rejected")
    runner = Runner(
        model=ScriptedModel([FinalAnswer("Done")]),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=RejectEvidence(),
    )

    result = runner.run("Prove the claim", ("Include evidence",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == "missing evidence"
    assert events.events[-1].kind == "run_finished"


def test_runner_exposes_unknown_tool_failure_to_next_model_iteration() -> None:
    contexts: list[RunContext] = []

    class ObservingModel:
        def next_decision(
            self,
            context: RunContext,
            _tool_specs: Sequence[Mapping[str, Any]],
        ) -> ModelDecision:
            contexts.append(context)
            if len(contexts) == 1:
                return ToolCall("missing", {})
            return FinalAnswer("The requested tool is unavailable.")

    events = MemoryEventSink(run_id="run-unknown")
    runner = Runner(
        model=ObservingModel(),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Use a missing tool", ("Report what happened",))

    assert result.status is RunStatus.SUCCEEDED
    second_context = contexts[1]
    assert second_context.observations[0].source == "missing"
    assert second_context.observations[0].content == "unknown tool: missing"
    tool_events = [event for event in events.events if event.kind == "tool_result"]
    assert len(tool_events) == 1
    assert tool_events[0].payload["error"] == "unknown tool: missing"


def test_runner_records_model_error_and_finishes_as_failed() -> None:
    events = MemoryEventSink(run_id="run-model-error")
    runner = Runner(
        model=ScriptedModel([]),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Ask the model", ("Return an answer",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert "scripted model has no remaining decisions" in result.reason
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_error",
        "run_finished",
    ]
    assert result.event_count == 3


def test_runner_fails_when_equivalent_retryable_failure_exceeds_limit() -> None:
    invocations = 0

    def retryable_failure(_arguments: Mapping[str, Any]) -> ToolResult:
        nonlocal invocations
        invocations += 1
        return ToolResult(ok=False, error="service unavailable", retryable=True)

    events = MemoryEventSink(run_id="run-retries")
    runner = Runner(
        model=ScriptedModel([ToolCall("fetch", {}) for _ in range(4)]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="fetch",
                    description="Fetch a remote value.",
                    input_schema={"type": "object"},
                    risk=Risk.READ,
                    handler=retryable_failure,
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=5, retry_limit=2),
    )

    result = runner.run("Fetch a value", ("Return the value",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert "retry limit exceeded" in result.reason
    assert invocations == 3
    assert sum(event.kind == "model_decision" for event in events.events) == 3
    assert events.events[-1].kind == "run_finished"


def test_runner_finishes_as_budget_exhausted_when_deadline_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter((10.0, 16.0))
    monkeypatch.setattr("tiny_harness.runner.monotonic", lambda: next(clock))
    events = MemoryEventSink(run_id="run-timeout")
    runner = Runner(
        model=ScriptedModel([FinalAnswer("Too late")]),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
        config=RunConfig(timeout_seconds=5),
    )

    result = runner.run("Answer quickly", ("Meet the deadline",))

    assert result.status is RunStatus.BUDGET_EXHAUSTED
    assert result.answer is None
    assert result.reason == "time budget exhausted"
    assert [event.kind for event in events.events] == ["run_started", "run_finished"]
    assert result.event_count == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_iterations", 0),
        ("max_iterations", -1),
        ("timeout_seconds", 0),
        ("timeout_seconds", -0.1),
        ("retry_limit", 0),
        ("retry_limit", -1),
    ],
)
def test_run_config_rejects_non_positive_values(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=field):
        RunConfig(**{field: value})


def test_package_reexports_runtime_interfaces() -> None:
    assert tiny_harness.ModelAdapter is ModelAdapter
    assert tiny_harness.ScriptedModel is ScriptedModel
    assert tiny_harness.Verifier is Verifier
    assert tiny_harness.AcceptFinalAnswer is AcceptFinalAnswer
    assert tiny_harness.RunConfig is RunConfig
    assert tiny_harness.Runner is Runner
