from typing import Any, Mapping

from labs.support_triage.tools import (
    ALLOWED_CATEGORIES,
    SentReply,
    TriageState,
    build_registry,
    build_tools,
)
from labs.support_triage.verification import TriageVerifier
from tiny_harness import FinalAnswer, Risk, RunContext, ToolCall, ToolResult

EXPECTED_RISKS = {
    "read_ticket": Risk.READ,
    "search_policy": Risk.READ,
    "set_category": Risk.WRITE,
    "draft_reply": Risk.WRITE,
    "send_reply": Risk.CONSEQUENTIAL,
}

DRAFT = "The duplicate charge for invoice INV-7781 is refunded in full."

CONTEXT = RunContext("Triage T-1042", ("Record a category.", "Draft a reply."))


def execute(state: TriageState, name: str, arguments: Mapping[str, Any]) -> ToolResult:
    return build_registry(state=state).execute(ToolCall(name, arguments))


def test_every_tool_declares_its_specified_risk_class() -> None:
    tools = build_tools(state=TriageState())

    assert {tool.name: tool.risk for tool in tools} == EXPECTED_RISKS


def test_send_reply_is_the_only_consequential_tool() -> None:
    tools = build_tools(state=TriageState())

    consequential = [
        tool.name for tool in tools if tool.risk is Risk.CONSEQUENTIAL
    ]
    assert consequential == ["send_reply"]


def test_allowed_categories_are_a_fixed_sorted_allow_list() -> None:
    assert ALLOWED_CATEGORIES == ("account_access", "billing", "bug", "how_to")


def test_read_ticket_returns_the_stored_ticket() -> None:
    result = execute(TriageState(), "read_ticket", {"ticket_id": "T-1044"})

    assert result.ok
    assert "CSV export" in result.output
    assert "Ingrid Sollers" in result.output


def test_read_ticket_reports_an_unknown_ticket_as_a_typed_failure() -> None:
    result = execute(TriageState(), "read_ticket", {"ticket_id": "T-9999"})

    assert result == ToolResult(ok=False, error="unknown ticket: T-9999")


def test_read_ticket_rejects_a_missing_argument() -> None:
    result = execute(TriageState(), "read_ticket", {})

    assert not result.ok
    assert result.error == "read_ticket requires a non-empty ticket_id string"


def test_search_policy_returns_matching_text_with_its_provenance() -> None:
    result = execute(TriageState(), "search_policy", {"keyword": "locked"})

    assert result.ok
    assert "[account-security.md]" in result.output
    assert "thirty minutes" in result.output


def test_search_policy_reports_an_empty_search_as_success() -> None:
    result = execute(TriageState(), "search_policy", {"keyword": "warp drive"})

    assert result.ok
    assert result.output == "no policy section matched the keyword: warp drive"


def test_set_category_records_an_allowed_category() -> None:
    state = TriageState()

    result = execute(state, "set_category", {"category": "billing"})

    assert result.ok
    assert state.category == "billing"


def test_set_category_rejects_a_category_outside_the_allow_list() -> None:
    state = TriageState()

    result = execute(state, "set_category", {"category": "refund_now"})

    assert not result.ok
    assert result.error is not None
    assert result.error.startswith("unknown category: refund_now")
    assert "account_access, billing, bug, how_to" in result.error
    assert state.category is None


def test_draft_reply_records_the_draft_on_run_local_state() -> None:
    state = TriageState()

    result = execute(state, "draft_reply", {"text": DRAFT})

    assert result.ok
    assert state.draft_reply == DRAFT


def test_draft_reply_rejects_blank_text() -> None:
    state = TriageState()

    result = execute(state, "draft_reply", {"text": "   "})

    assert not result.ok
    assert state.draft_reply is None


def test_send_reply_refuses_to_send_without_a_category_or_a_draft() -> None:
    state = TriageState()

    result = execute(state, "send_reply", {"ticket_id": "T-1042"})

    assert not result.ok
    assert result.error == "no category was recorded for this run"
    assert state.sent_replies == ()


def test_send_reply_refuses_to_send_a_categorised_ticket_without_a_draft() -> None:
    state = TriageState()
    execute(state, "set_category", {"category": "billing"})

    result = execute(state, "send_reply", {"ticket_id": "T-1042"})

    assert not result.ok
    assert result.error == "no reply was drafted for this run"
    assert state.sent_replies == ()


def test_send_reply_simulates_one_send_when_the_evidence_exists() -> None:
    state = TriageState()
    execute(state, "set_category", {"category": "billing"})
    execute(state, "draft_reply", {"text": DRAFT})

    result = execute(state, "send_reply", {"ticket_id": "T-1042"})

    assert result.ok
    assert "Dana Whitfield" in result.output
    assert state.sent_replies == (
        SentReply(ticket_id="T-1042", category="billing", body=DRAFT),
    )


def test_verifier_rejects_an_answer_when_no_category_was_recorded() -> None:
    state = TriageState()
    state.draft_reply = DRAFT

    result = TriageVerifier(state).verify(CONTEXT, FinalAnswer("Ticket triaged."))

    assert result.accepted is False
    assert result.reason == "no category was recorded by set_category"


def test_verifier_rejects_an_answer_when_no_reply_was_drafted() -> None:
    state = TriageState()
    state.category = "billing"

    result = TriageVerifier(state).verify(CONTEXT, FinalAnswer("Ticket triaged."))

    assert result.accepted is False
    assert result.reason == "no reply was drafted by draft_reply"


def test_verifier_accepts_only_when_lab_state_holds_both_pieces_of_evidence() -> None:
    state = TriageState()
    state.category = "billing"
    state.draft_reply = DRAFT

    result = TriageVerifier(state).verify(CONTEXT, FinalAnswer("Ticket triaged."))

    assert result.accepted is True
    assert "billing" in result.reason
