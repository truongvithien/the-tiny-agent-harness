import json
from pathlib import Path

from labs.support_triage.demo import (
    ACCEPTANCE_CRITERIA,
    CATEGORY,
    DRAFT_REPLY,
    FINAL_ANSWER,
    TASK,
    TICKET_ID,
    run_demo,
    scripted_approval,
)
from labs.support_triage.tools import SentReply, TriageState, build_registry
from labs.support_triage.verification import TriageVerifier
from tiny_harness import (
    FinalAnswer,
    MemoryEventSink,
    RiskPolicy,
    RunConfig,
    Runner,
    RunStatus,
    ScriptedModel,
    ToolCall,
)

APPROVED_KINDS = [
    "run_started",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "policy_decision",
    "approval_requested",
    "approval_decision",
    "tool_result",
    "model_decision",
    "verification",
    "run_finished",
]

REFUSED_KINDS = [
    "run_started",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "policy_decision",
    "approval_requested",
    "approval_decision",
    "run_finished",
]


def trace_kinds(path: Path) -> list[str]:
    return [json.loads(line)["kind"] for line in path.read_text().splitlines()]


def test_approved_demo_succeeds_and_records_the_approval_gate(tmp_path: Path) -> None:
    state = TriageState()
    trace = tmp_path / "support_triage.jsonl"

    result = run_demo(trace, state=state, approve=True)

    assert result.status is RunStatus.SUCCEEDED
    assert result.answer == FINAL_ANSWER
    assert trace_kinds(trace) == APPROVED_KINDS
    assert state.category == CATEGORY
    assert state.draft_reply == DRAFT_REPLY
    assert state.sent_replies == (
        SentReply(ticket_id=TICKET_ID, category=CATEGORY, body=DRAFT_REPLY),
    )


def test_approved_demo_trace_carries_provenance_and_one_granted_approval(
    tmp_path: Path,
) -> None:
    trace = tmp_path / "support_triage.jsonl"

    run_demo(trace, approve=True)

    events = [json.loads(line) for line in trace.read_text().splitlines()]
    approvals = [event for event in events if event["kind"] == "approval_decision"]
    searches = [
        event
        for event in events
        if event["kind"] == "tool_result" and event["payload"]["tool"] == "search_policy"
    ]
    assert [event["payload"] for event in approvals] == [
        {"tool": "send_reply", "granted": True}
    ]
    assert "[billing-refunds.md]" in searches[0]["payload"]["output"]
    assert all(event["run_id"] == "support-triage-demo" for event in events)


def test_refused_approval_stops_the_run_before_the_send_handler(tmp_path: Path) -> None:
    state = TriageState()
    trace = tmp_path / "support_triage.jsonl"

    result = run_demo(trace, state=state, approve=False)

    assert result.status is RunStatus.APPROVAL_REFUSED
    assert result.answer is None
    assert result.reason == "approval refused for tool: send_reply"
    assert trace_kinds(trace) == REFUSED_KINDS
    assert state.send_calls == 0
    assert state.sent_replies == ()


def test_invalid_category_returns_a_typed_failure_and_the_run_does_not_succeed() -> None:
    state = TriageState()
    events = MemoryEventSink("invalid-category")
    runner = Runner(
        model=ScriptedModel(
            [
                ToolCall("set_category", {"category": "refund_now"}),
                FinalAnswer("Ticket T-1042 is categorised and answered."),
            ]
        ),
        tools=build_registry(state=state),
        policy=RiskPolicy(),
        approval=scripted_approval(True),
        events=events,
        verifier=TriageVerifier(state),
        config=RunConfig(max_iterations=2),
    )

    result = runner.run(TASK, ACCEPTANCE_CRITERIA)

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert state.category is None
    failures = [event for event in events.events if event.kind == "tool_result"]
    assert failures[0].payload["ok"] is False
    assert failures[0].payload["error"] == (
        "unknown category: refund_now; allowed categories are "
        "account_access, billing, bug, how_to"
    )


def test_a_final_answer_without_a_draft_is_rejected_by_the_verifier() -> None:
    state = TriageState()
    events = MemoryEventSink("no-draft")
    runner = Runner(
        model=ScriptedModel(
            [
                ToolCall("set_category", {"category": "billing"}),
                FinalAnswer("Ticket T-1042 is triaged and the customer was answered."),
            ]
        ),
        tools=build_registry(state=state),
        policy=RiskPolicy(),
        approval=scripted_approval(True),
        events=events,
        verifier=TriageVerifier(state),
        config=RunConfig(max_iterations=2),
    )

    result = runner.run(TASK, ACCEPTANCE_CRITERIA)

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == "no reply was drafted by draft_reply"
