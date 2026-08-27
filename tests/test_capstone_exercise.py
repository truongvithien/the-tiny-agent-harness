import importlib.util
from pathlib import Path
from typing import Any

import pytest

from tiny_harness import (
    AcceptFinalAnswer,
    FinalAnswer,
    FunctionTool,
    MemoryEventSink,
    PolicyDecision,
    Risk,
    RunConfig,
    Runner,
    RunStatus,
    ScriptedModel,
    ToolCall,
    ToolRegistry,
    ToolResult,
)

EXERCISE = Path("course/07-capstone/exercise.py")
SOLUTION = Path("solutions/07-capstone/exercise.py")


def load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"capstone_{path.parts[0]}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tool(name: str, risk: Risk) -> FunctionTool:
    return FunctionTool(
        name=name,
        description="Test action.",
        input_schema={"type": "object"},
        risk=risk,
        handler=lambda _: ToolResult(ok=True),
    )


def refund_call(amount: object) -> ToolCall:
    return ToolCall("issue_refund", {"ticket_id": "T-1", "amount": amount})


@pytest.mark.learner
def test_learner_allows_a_read_tool() -> None:
    policy = load(EXERCISE).RefundPolicy()

    decision = policy.evaluate(tool("read_ticket", Risk.READ), ToolCall("read_ticket", {}))

    assert decision is PolicyDecision.ALLOW


@pytest.mark.learner
def test_learner_denies_a_refund_above_the_limit() -> None:
    policy = load(EXERCISE).RefundPolicy()

    decision = policy.evaluate(tool("issue_refund", Risk.CONSEQUENTIAL), refund_call(250.0))

    assert decision is PolicyDecision.DENY


@pytest.mark.learner
def test_learner_requires_approval_within_the_limit() -> None:
    policy = load(EXERCISE).RefundPolicy()

    decision = policy.evaluate(tool("issue_refund", Risk.CONSEQUENTIAL), refund_call(50.0))

    assert decision is PolicyDecision.APPROVAL_REQUIRED


@pytest.mark.parametrize(
    ("name", "risk", "call", "expected"),
    [
        ("read_ticket", Risk.READ, ToolCall("read_ticket", {}), PolicyDecision.ALLOW),
        ("set_category", Risk.WRITE, ToolCall("set_category", {}), PolicyDecision.ALLOW),
        (
            "issue_refund",
            Risk.CONSEQUENTIAL,
            refund_call(50),
            PolicyDecision.APPROVAL_REQUIRED,
        ),
        (
            "issue_refund",
            Risk.CONSEQUENTIAL,
            refund_call(100.0),
            PolicyDecision.APPROVAL_REQUIRED,
        ),
        ("issue_refund", Risk.CONSEQUENTIAL, refund_call(250.0), PolicyDecision.DENY),
        ("issue_refund", Risk.CONSEQUENTIAL, refund_call(-5.0), PolicyDecision.DENY),
        ("issue_refund", Risk.CONSEQUENTIAL, refund_call("250"), PolicyDecision.DENY),
        ("issue_refund", Risk.CONSEQUENTIAL, refund_call(True), PolicyDecision.DENY),
        (
            "issue_refund",
            Risk.CONSEQUENTIAL,
            ToolCall("issue_refund", {"ticket_id": "T-1"}),
            PolicyDecision.DENY,
        ),
        (
            "send_reply",
            Risk.CONSEQUENTIAL,
            ToolCall("send_reply", {}),
            PolicyDecision.APPROVAL_REQUIRED,
        ),
    ],
)
def test_solution_policy_contract(
    name: str,
    risk: Risk,
    call: ToolCall,
    expected: PolicyDecision,
) -> None:
    policy = load(SOLUTION).RefundPolicy()

    assert policy.evaluate(tool(name, risk), call) is expected


def build_runner(amount: float, *, approve: bool, events: MemoryEventSink) -> tuple[Runner, Any]:
    module = load(SOLUTION)
    ledger = module.RefundLedger()
    runner = Runner(
        model=ScriptedModel(
            [
                ToolCall("issue_refund", {"ticket_id": "T-1", "amount": amount}),
                FinalAnswer(f"Refunded {amount:.2f} on T-1."),
            ]
        ),
        tools=ToolRegistry([module.build_refund_tool(ledger)]),
        policy=module.RefundPolicy(),
        approval=lambda _tool, _call: approve,
        events=events,
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=4),
    )
    return runner, ledger


def test_an_over_limit_refund_is_denied_before_any_effect() -> None:
    events = MemoryEventSink(run_id="capstone-denied")
    runner, ledger = build_runner(250.0, approve=True, events=events)

    result = runner.run("Refund the customer", ("Refund only within policy",))

    assert result.status is RunStatus.POLICY_DENIED
    assert result.answer is None
    assert ledger.issued == []
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "run_finished",
    ]


def test_a_within_limit_refund_still_requires_approval() -> None:
    events = MemoryEventSink(run_id="capstone-refused")
    runner, ledger = build_runner(50.0, approve=False, events=events)

    result = runner.run("Refund the customer", ("Refund only within policy",))

    assert result.status is RunStatus.APPROVAL_REFUSED
    assert ledger.issued == []
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "approval_requested",
        "approval_decision",
        "run_finished",
    ]


def test_an_approved_refund_within_the_limit_succeeds() -> None:
    events = MemoryEventSink(run_id="capstone-approved")
    runner, ledger = build_runner(50.0, approve=True, events=events)

    result = runner.run("Refund the customer", ("Refund only within policy",))

    assert result.status is RunStatus.SUCCEEDED
    assert ledger.issued == [("T-1", 50.0)]
    assert ledger.total == 50.0
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


def test_the_capstone_extends_the_harness_without_changing_the_runner() -> None:
    import inspect

    import tiny_harness.runner as runner_module

    source = inspect.getsource(runner_module)

    assert "issue_refund" not in source
    assert "RefundPolicy" not in source
    assert "MAX_AUTOMATIC_REFUND" not in source
