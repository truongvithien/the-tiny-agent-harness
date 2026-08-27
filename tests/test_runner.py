from collections.abc import Mapping, Sequence
from threading import Event
from time import monotonic as wall_clock
from typing import Any, cast

import pytest
import tiny_harness

from tiny_harness.events import MemoryEventSink
from tiny_harness.models import ModelAdapter, ScriptedModel
from tiny_harness.policy import RiskPolicy
from tiny_harness.runner import RunConfig, Runner
from tiny_harness.tools import FunctionTool, Tool, ToolRegistry
from tiny_harness.types import (
    FinalAnswer,
    ModelDecision,
    PolicyDecision,
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
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "approval_requested",
        "approval_decision",
        "run_finished",
    ]
    assert events.events[2].payload == {
        "tool": "publish",
        "decision": "approval_required",
    }
    assert events.events[4].payload == {"tool": "publish", "granted": False}
    assert result.event_count == len(events.events)


def test_runner_traces_granted_approval_without_collapsing_policy_decision() -> None:
    invocations = 0

    def publish(_arguments: Mapping[str, Any]) -> ToolResult:
        nonlocal invocations
        invocations += 1
        return ToolResult(ok=True, output="published")

    events = MemoryEventSink(run_id="run-approved")
    runner = Runner(
        model=ScriptedModel(
            [ToolCall("publish", {"message": "hello"}), FinalAnswer("Published.")]
        ),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="publish",
                    description="Publish a message.",
                    input_schema={"type": "object"},
                    risk=Risk.CONSEQUENTIAL,
                    handler=publish,
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: True,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Publish a greeting", ("Greeting is published",))

    assert result.status is RunStatus.SUCCEEDED
    assert invocations == 1
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "approval_requested",
        "approval_decision",
        "tool_result",
        "model_decision",
        "verification",
        "run_finished",
    ]
    assert events.events[2].payload["decision"] == "approval_required"
    assert events.events[4].payload == {"tool": "publish", "granted": True}


def test_policy_and_approval_cannot_mutate_nested_arguments_before_execution() -> None:
    mutation_attempts: list[str] = []
    executed_arguments: list[dict[str, object]] = []

    class MutatingPolicy:
        def evaluate(self, _tool: Tool, call: ToolCall) -> PolicyDecision:
            mutation_attempts.append("policy")
            try:
                call.arguments["request"]["recipients"].append("policy-added")
            except (AttributeError, TypeError):
                pass
            return PolicyDecision.APPROVAL_REQUIRED

    def mutating_approval(_tool: Tool, call: ToolCall) -> bool:
        mutation_attempts.append("approval")
        try:
            call.arguments["request"]["metadata"]["approved_by"] = "callback"
        except (AttributeError, TypeError):
            pass
        return True

    def capture_arguments(arguments: Mapping[str, Any]) -> ToolResult:
        request = arguments["request"]
        executed_arguments.append(
            {
                "recipients": tuple(request["recipients"]),
                "metadata": dict(request["metadata"]),
            }
        )
        return ToolResult(ok=True, output="published")

    call = ToolCall(
        "publish",
        {
            "request": {
                "recipients": ["learner@example.test"],
                "metadata": {"priority": "normal"},
            }
        },
    )
    events = MemoryEventSink(run_id="run-frozen-call")
    runner = Runner(
        model=ScriptedModel([call, FinalAnswer("Published without mutation.")]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="publish",
                    description="Publish a message.",
                    input_schema={"type": "object"},
                    risk=Risk.CONSEQUENTIAL,
                    handler=capture_arguments,
                )
            ]
        ),
        policy=MutatingPolicy(),
        approval=mutating_approval,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Publish safely", ("Preserve proposed arguments",))

    assert result.status is RunStatus.SUCCEEDED
    assert mutation_attempts == ["policy", "approval"]
    assert executed_arguments == [
        {
            "recipients": ("learner@example.test",),
            "metadata": {"priority": "normal"},
        }
    ]
    assert events.events[1].payload["arguments"] == {
        "request": {
            "recipients": ("learner@example.test",),
            "metadata": {"priority": "normal"},
        }
    }


def test_runner_distinguishes_direct_policy_denial_from_approval_refusal() -> None:
    invocations = 0

    class DenyPolicy:
        def evaluate(self, _tool: Tool, _call: ToolCall) -> PolicyDecision:
            return PolicyDecision.DENY

    def count_invocation(_arguments: Mapping[str, Any]) -> ToolResult:
        nonlocal invocations
        invocations += 1
        return ToolResult(ok=True)

    events = MemoryEventSink(run_id="run-denied")
    runner = Runner(
        model=ScriptedModel([ToolCall("write", {})]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="write",
                    description="Write a value.",
                    input_schema={"type": "object"},
                    risk=Risk.WRITE,
                    handler=count_invocation,
                )
            ]
        ),
        policy=DenyPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Write safely", ("Respect policy",))

    assert result.status is RunStatus.POLICY_DENIED
    assert result.reason == "policy denied tool: write"
    assert invocations == 0
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "run_finished",
    ]
    assert events.events[2].payload == {"tool": "write", "decision": "deny"}


def test_runner_fails_closed_for_an_invalid_runtime_tool_risk() -> None:
    invocations = 0

    def count_invocation(_arguments: Mapping[str, Any]) -> ToolResult:
        nonlocal invocations
        invocations += 1
        return ToolResult(ok=True)

    events = MemoryEventSink(run_id="run-invalid-risk")
    runner = Runner(
        model=ScriptedModel([ToolCall("publish", {})]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="publish",
                    description="Publish a value.",
                    input_schema={"type": "object"},
                    risk=cast(Risk, "consequential"),
                    handler=count_invocation,
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: True,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Publish safely", ("Respect policy",))

    assert result.status is RunStatus.FAILED
    assert result.reason == "policy error: TypeError"
    assert invocations == 0
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_error",
        "run_finished",
    ]


def test_runner_fails_closed_for_a_non_boolean_approval_result() -> None:
    invocations = 0

    def count_invocation(_arguments: Mapping[str, Any]) -> ToolResult:
        nonlocal invocations
        invocations += 1
        return ToolResult(ok=True)

    events = MemoryEventSink(run_id="run-invalid-approval")
    runner = Runner(
        model=ScriptedModel([ToolCall("publish", {})]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="publish",
                    description="Publish a value.",
                    input_schema={"type": "object"},
                    risk=Risk.CONSEQUENTIAL,
                    handler=count_invocation,
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: cast(bool, "no"),
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Publish safely", ("Respect approval",))

    assert result.status is RunStatus.FAILED
    assert result.reason == "approval error: TypeError"
    assert invocations == 0
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "approval_requested",
        "approval_error",
        "run_finished",
    ]


def test_runner_fails_closed_for_an_invalid_policy_decision() -> None:
    class InvalidPolicy:
        def evaluate(self, _tool: Tool, _call: ToolCall) -> PolicyDecision:
            return cast(PolicyDecision, "allow")

    events = MemoryEventSink(run_id="run-invalid-policy")
    runner = Runner(
        model=ScriptedModel([ToolCall("read", {})]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="read",
                    description="Read a value.",
                    input_schema={"type": "object"},
                    risk=Risk.READ,
                    handler=lambda _arguments: ToolResult(ok=True),
                )
            ]
        ),
        policy=InvalidPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Read safely", ("Respect policy",))

    assert result.status is RunStatus.FAILED
    assert result.reason == "policy error: TypeError"
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_error",
        "run_finished",
    ]


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


def test_runner_records_malformed_handler_result_as_typed_failure_and_finishes() -> None:
    events = MemoryEventSink(run_id="run-malformed-handler")
    runner = Runner(
        model=ScriptedModel(
            [ToolCall("malformed", {}), FinalAnswer("The tool result was invalid.")]
        ),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="malformed",
                    description="Return the wrong runtime type.",
                    input_schema={"type": "object"},
                    risk=Risk.READ,
                    handler=lambda _arguments: cast(ToolResult, "not a ToolResult"),
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Handle a bad tool", ("Report the failure",))

    assert result.status is RunStatus.SUCCEEDED
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "tool_result",
        "model_decision",
        "verification",
        "run_finished",
    ]
    assert events.events[3].payload == {
        "tool": "malformed",
        "ok": False,
        "output": "",
        "error": "tool malformed returned an invalid result",
        "retryable": False,
    }


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
    assert result.reason == "model error: RuntimeError"
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
    assert [event.kind for event in events.events] == [
        "run_started",
        "timeout",
        "run_finished",
    ]
    assert events.events[1].payload == {
        "boundary": "run",
        "call_may_still_be_running": False,
        "late_result_ignored": False,
    }
    assert result.event_count == 3


def test_runner_rechecks_deadline_after_model_before_accepting_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [10.0]
    verification_calls = 0
    tool_calls = 0

    class SlowModel:
        def next_decision(
            self,
            _context: RunContext,
            _tool_specs: Sequence[Mapping[str, Any]],
        ) -> ModelDecision:
            clock[0] = 16.0
            return FinalAnswer("Too late")

    class CountingVerifier:
        def verify(
            self, _context: RunContext, _answer: FinalAnswer
        ) -> VerificationResult:
            nonlocal verification_calls
            verification_calls += 1
            return VerificationResult(True, "accepted")

    def count_tool(_arguments: Mapping[str, Any]) -> ToolResult:
        nonlocal tool_calls
        tool_calls += 1
        return ToolResult(ok=True)

    monkeypatch.setattr("tiny_harness.runner.monotonic", lambda: clock[0])
    events = MemoryEventSink(run_id="run-slow-model")
    runner = Runner(
        model=SlowModel(),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="unused",
                    description="Must not execute.",
                    input_schema={"type": "object"},
                    risk=Risk.READ,
                    handler=count_tool,
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=CountingVerifier(),
        config=RunConfig(timeout_seconds=5),
    )

    result = runner.run("Answer before timeout", ("Meet the deadline",))

    assert result.status is RunStatus.BUDGET_EXHAUSTED
    assert result.answer is None
    assert verification_calls == 0
    assert tool_calls == 0
    assert [event.kind for event in events.events] == [
        "run_started",
        "timeout",
        "run_finished",
    ]
    assert events.events[1].payload == {
        "boundary": "model",
        "call_may_still_be_running": False,
        "late_result_ignored": True,
    }


def test_runner_stops_waiting_for_a_slow_tool_and_ignores_its_late_result() -> None:
    tool_started = Event()
    release_tool = Event()
    tool_finished = Event()

    def slow_tool(_arguments: Mapping[str, Any]) -> ToolResult:
        tool_started.set()
        release_tool.wait(timeout=1)
        tool_finished.set()
        return ToolResult(ok=True, output="too late")

    events = MemoryEventSink(run_id="run-slow-tool")
    runner = Runner(
        model=ScriptedModel([ToolCall("slow", {})]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="slow",
                    description="Wait longer than the run budget.",
                    input_schema={"type": "object"},
                    risk=Risk.WRITE,
                    handler=slow_tool,
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=1, timeout_seconds=0.05),
    )

    started_at = wall_clock()
    try:
        result = runner.run("Run the slow tool", ("Finish before the deadline",))
        elapsed = wall_clock() - started_at

        assert tool_started.is_set()
        assert elapsed < 0.5
        assert not tool_finished.is_set()
        assert result.status is RunStatus.BUDGET_EXHAUSTED
        assert [event.kind for event in events.events] == [
            "run_started",
            "model_decision",
            "policy_decision",
            "timeout",
            "run_finished",
        ]
        assert events.events[-2].payload == {
            "boundary": "tool",
            "tool": "slow",
            "call_may_still_be_running": True,
            "late_result_ignored": True,
        }
        event_count_at_timeout = len(events.events)
    finally:
        release_tool.set()

    assert tool_finished.wait(timeout=1)
    assert len(events.events) == event_count_at_timeout


def test_runner_rejects_a_slow_verifiers_late_success() -> None:
    verification_started = Event()
    release_verification = Event()
    verification_finished = Event()

    class SlowAcceptingVerifier:
        def verify(
            self, _context: RunContext, _answer: FinalAnswer
        ) -> VerificationResult:
            verification_started.set()
            release_verification.wait(timeout=1)
            verification_finished.set()
            return VerificationResult(True, "accepted too late")

    events = MemoryEventSink(run_id="run-slow-verifier")
    runner = Runner(
        model=ScriptedModel([FinalAnswer("Unverified answer")]),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=SlowAcceptingVerifier(),
        config=RunConfig(timeout_seconds=0.05),
    )

    started_at = wall_clock()
    try:
        result = runner.run("Verify slowly", ("Finish before the deadline",))
        elapsed = wall_clock() - started_at

        assert verification_started.is_set()
        assert elapsed < 0.5
        assert not verification_finished.is_set()
        assert result.status is RunStatus.BUDGET_EXHAUSTED
        assert result.answer is None
        assert [event.kind for event in events.events] == [
            "run_started",
            "model_decision",
            "timeout",
            "run_finished",
        ]
        assert events.events[-2].payload == {
            "boundary": "verification",
            "call_may_still_be_running": True,
            "late_result_ignored": True,
        }
        event_count_at_timeout = len(events.events)
    finally:
        release_verification.set()

    assert verification_finished.wait(timeout=1)
    assert len(events.events) == event_count_at_timeout


def test_runner_rejects_blank_answer_before_accepting_verifier_can_approve() -> None:
    verification_calls = 0

    class AcceptEverything:
        def verify(
            self, _context: RunContext, _answer: FinalAnswer
        ) -> VerificationResult:
            nonlocal verification_calls
            verification_calls += 1
            return VerificationResult(True, "accepted")

    events = MemoryEventSink(run_id="run-blank-answer")
    runner = Runner(
        model=ScriptedModel([FinalAnswer("   ")]),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptEverything(),
    )

    result = runner.run("Return evidence", ("Answer must not be blank",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == "final answer is empty"
    assert verification_calls == 0
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "verification",
        "run_finished",
    ]


def test_runner_converts_verifier_exception_to_safe_failed_result() -> None:
    secret = "sensitive verifier detail"

    class RaisingVerifier:
        def verify(
            self, _context: RunContext, _answer: FinalAnswer
        ) -> VerificationResult:
            raise RuntimeError(secret)

    events = MemoryEventSink(run_id="run-verifier-error")
    runner = Runner(
        model=ScriptedModel([FinalAnswer("Evidence")]),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=RaisingVerifier(),
    )

    result = runner.run("Verify evidence", ("Evidence is valid",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == "verification error: RuntimeError"
    assert secret not in result.reason
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "verification_error",
        "run_finished",
    ]
    assert events.events[2].payload == {"type": "RuntimeError"}


def test_runner_rejects_malformed_verifier_acceptance_instead_of_succeeding() -> None:
    class MalformedVerifier:
        def verify(
            self, _context: RunContext, _answer: FinalAnswer
        ) -> VerificationResult:
            return VerificationResult(
                accepted=cast(bool, "false"),
                reason="malformed acceptance",
            )

    events = MemoryEventSink(run_id="run-malformed-verifier")
    runner = Runner(
        model=ScriptedModel([FinalAnswer("Unverified answer")]),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=MalformedVerifier(),
    )

    result = runner.run("Verify safely", ("Require a boolean decision",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == "verification error: TypeError"
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "verification_error",
        "run_finished",
    ]


@pytest.mark.parametrize(
    ("failure_source", "error_type"),
    [("policy", "PermissionError"), ("approval", "ConnectionError")],
)
def test_runner_converts_authorization_exception_to_safe_failed_result(
    failure_source: str,
    error_type: str,
) -> None:
    secret = "sensitive authorization detail"
    tool_calls = 0

    class RaisingPolicy:
        def evaluate(self, _tool: Tool, _call: ToolCall) -> PolicyDecision:
            raise PermissionError(secret)

    def raising_approval(_tool: Tool, _call: ToolCall) -> bool:
        raise ConnectionError(secret)

    def count_tool(_arguments: Mapping[str, Any]) -> ToolResult:
        nonlocal tool_calls
        tool_calls += 1
        return ToolResult(ok=True)

    events = MemoryEventSink(run_id=f"run-{failure_source}-error")
    runner = Runner(
        model=ScriptedModel([ToolCall("publish", {})]),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="publish",
                    description="Publish a value.",
                    input_schema={"type": "object"},
                    risk=Risk.CONSEQUENTIAL,
                    handler=count_tool,
                )
            ]
        ),
        policy=RaisingPolicy() if failure_source == "policy" else RiskPolicy(),
        approval=(
            raising_approval
            if failure_source == "approval"
            else lambda _tool, _call: False
        ),
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Publish safely", ("Respect authorization",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == f"{failure_source} error: {error_type}"
    assert secret not in result.reason
    assert tool_calls == 0
    if failure_source == "policy":
        assert [event.kind for event in events.events] == [
            "run_started",
            "model_decision",
            "policy_error",
            "run_finished",
        ]
    else:
        assert [event.kind for event in events.events] == [
            "run_started",
            "model_decision",
            "policy_decision",
            "approval_requested",
            "approval_error",
            "run_finished",
        ]
    assert events.events[-2].payload == {"type": error_type}


def test_runner_converts_malformed_model_decision_to_safe_failed_result() -> None:
    secret = "sensitive malformed output"

    class MalformedModel:
        def next_decision(
            self,
            _context: RunContext,
            _tool_specs: Sequence[Mapping[str, Any]],
        ) -> ModelDecision:
            return cast(ModelDecision, {"unexpected": secret})

    events = MemoryEventSink(run_id="run-malformed-model")
    runner = Runner(
        model=MalformedModel(),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Ask the model", ("Return a valid decision",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == "model error: TypeError"
    assert secret not in result.reason
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_error",
        "run_finished",
    ]
    assert events.events[1].payload == {"type": "TypeError"}


def test_runner_rejects_non_string_final_answer_before_serialization() -> None:
    secret = "sensitive malformed answer"

    class SensitiveText:
        def __repr__(self) -> str:
            return secret

    malformed_answer = FinalAnswer(cast(str, SensitiveText()))
    events = MemoryEventSink(run_id="run-malformed-answer")
    runner = Runner(
        model=ScriptedModel([malformed_answer]),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Ask the model", ("Return a valid answer",))

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == "model error: TypeError"
    assert secret not in result.reason
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_error",
        "run_finished",
    ]
    assert events.events[1].payload == {"type": "TypeError"}
    assert secret not in repr(events.events)


def test_runner_does_not_expose_model_exception_message() -> None:
    secret = "sensitive model detail"

    class RaisingModel:
        def next_decision(
            self,
            _context: RunContext,
            _tool_specs: Sequence[Mapping[str, Any]],
        ) -> ModelDecision:
            raise RuntimeError(secret)

    events = MemoryEventSink(run_id="run-safe-model-error")
    runner = Runner(
        model=RaisingModel(),
        tools=ToolRegistry(),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
    )

    result = runner.run("Ask the model", ("Return an answer",))

    assert result.status is RunStatus.FAILED
    assert result.reason == "model error: RuntimeError"
    assert secret not in result.reason
    assert events.events[1].payload == {"type": "RuntimeError"}
    assert events.events[-1].kind == "run_finished"


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
