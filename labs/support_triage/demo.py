from __future__ import annotations

from pathlib import Path

from labs.support_triage.tools import TriageState, build_registry
from labs.support_triage.verification import TriageVerifier
from tiny_harness import (
    ApprovalCallback,
    FinalAnswer,
    JsonlEventSink,
    RiskPolicy,
    RunConfig,
    RunResult,
    Runner,
    ScriptedModel,
    Tool,
    ToolCall,
)

TRACE_PATH = Path(".traces/support_triage.jsonl")
TICKET_ID = "T-1042"
CATEGORY = "billing"
DRAFT_REPLY = (
    "You were charged twice for invoice INV-7781. We refund the duplicate "
    "charge of 49.00 in full; banks usually show it within five business days. "
    "No action is needed from you."
)
FINAL_ANSWER = (
    "Ticket T-1042 is categorised as billing and an approved refund reply was sent."
)
TASK = "Triage support ticket T-1042 and send a policy-grounded reply."
ACCEPTANCE_CRITERIA = (
    "Record one allowed category for the ticket.",
    "Draft a reply grounded in the policy knowledge base.",
    "Send the reply only after a person approves it.",
)


def scripted_approval(approve: bool) -> ApprovalCallback:
    def approval(tool: Tool, call: ToolCall) -> bool:
        del tool, call
        return approve

    return approval


def build_demo(
    trace_path: Path,
    *,
    state: TriageState | None = None,
    approve: bool = True,
) -> Runner:
    lab_state = state if state is not None else TriageState()
    return Runner(
        model=ScriptedModel(
            [
                ToolCall("read_ticket", {"ticket_id": TICKET_ID}),
                ToolCall("search_policy", {"keyword": "duplicate charge"}),
                ToolCall("set_category", {"category": CATEGORY}),
                ToolCall("draft_reply", {"text": DRAFT_REPLY}),
                ToolCall("send_reply", {"ticket_id": TICKET_ID}),
                FinalAnswer(FINAL_ANSWER),
            ]
        ),
        tools=build_registry(state=lab_state),
        policy=RiskPolicy(),
        approval=scripted_approval(approve),
        events=JsonlEventSink(trace_path, run_id="support-triage-demo"),
        verifier=TriageVerifier(lab_state),
        config=RunConfig(max_iterations=6),
    )


def run_demo(
    trace_path: Path,
    *,
    state: TriageState | None = None,
    approve: bool = True,
) -> RunResult:
    trace_path.unlink(missing_ok=True)
    runner = build_demo(trace_path, state=state, approve=approve)
    return runner.run(TASK, ACCEPTANCE_CRITERIA)


def main() -> None:
    result = run_demo(TRACE_PATH)
    print(result.status.value)
    print(result.answer)
    print(TRACE_PATH)


if __name__ == "__main__":
    main()
