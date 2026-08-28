import json
from pathlib import Path

from labs.research.demo import run_demo, run_with_decisions
from labs.research.server import load_documents
from labs.research.tools import MAX_SOURCE_CHARACTERS, TRUNCATION_NOTICE
from tiny_harness import FinalAnswer, RunStatus, ToolCall

EXPECTED_KINDS = [
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
    "tool_result",
    "model_decision",
    "policy_decision",
    "tool_result",
    "model_decision",
    "verification",
    "run_finished",
]

HIDDEN_CONFLICT_DECISIONS = (
    ToolCall("fetch_source", {"source_id": "marsh-survey-2024"}),
    ToolCall("fetch_source", {"source_id": "regional-bird-atlas"}),
    ToolCall(
        "record_claim",
        {
            "claim": "Blackwater Marsh holds 128 grey heron nesting pairs.",
            "source_id": "marsh-survey-2024",
        },
    ),
    FinalAnswer(
        "Blackwater Marsh holds 128 grey heron nesting pairs, per marsh-survey-2024."
    ),
)

UNCITED_CONFLICT_DECISIONS = (
    ToolCall("fetch_source", {"source_id": "marsh-survey-2024"}),
    ToolCall("fetch_source", {"source_id": "regional-bird-atlas"}),
    ToolCall(
        "record_claim",
        {
            "claim": "Blackwater Marsh holds 128 grey heron nesting pairs.",
            "source_id": "marsh-survey-2024",
            "disputed": True,
        },
    ),
    FinalAnswer(
        "marsh-survey-2024 reports 128 nesting pairs, but the figure is disputed."
    ),
)

UNCITED_SOURCE_DECISIONS = (
    ToolCall("fetch_source", {"source_id": "survey-method-manual"}),
    ToolCall(
        "record_claim",
        {
            "claim": "Blackwater Marsh holds 128 grey heron nesting pairs.",
            "source_id": "marsh-survey-2024",
        },
    ),
    FinalAnswer("Blackwater Marsh holds 128 grey heron nesting pairs."),
)

NO_EVIDENCE_DECISIONS = (
    ToolCall("list_sources", {}),
    FinalAnswer("Blackwater Marsh holds about 128 grey heron nesting pairs."),
)


def trace_events(trace: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]


def test_research_demo_succeeds_on_cited_evidence(tmp_path: Path) -> None:
    trace = tmp_path / "research.jsonl"

    result = run_demo(trace)

    assert result.status is RunStatus.SUCCEEDED
    assert result.reason == (
        "2 recorded claims cite fetched sources, 1 of them marked disputed"
    )
    assert result.answer is not None
    assert "regional-bird-atlas" in result.answer
    assert [event["kind"] for event in trace_events(trace)] == EXPECTED_KINDS


def test_research_demo_trace_records_source_provenance(tmp_path: Path) -> None:
    trace = tmp_path / "research.jsonl"

    run_demo(trace)

    fetches = [
        event["payload"]
        for event in trace_events(trace)
        if event["kind"] == "tool_result" and event["payload"]["tool"] == "fetch_source"
    ]
    assert len(fetches) == 3
    outputs = [str(payload["output"]) for payload in fetches]
    assert "source_id: marsh-survey-2024" in outputs[0]
    assert "/sources/marsh-survey-2024" in outputs[0]
    assert f"character_limit: {MAX_SOURCE_CHARACTERS}" in outputs[0]
    assert TRUNCATION_NOTICE in outputs[0]
    assert "conflicts_with: regional-bird-atlas" in outputs[0]


def test_research_demo_selects_only_part_of_the_available_context(
    tmp_path: Path,
) -> None:
    trace = tmp_path / "research.jsonl"

    run_demo(trace)

    events = trace_events(trace)
    listings = [
        str(event["payload"]["output"])
        for event in events
        if event["kind"] == "tool_result"
        and event["payload"]["tool"] == "list_sources"
    ]
    fetched = {
        str(event["payload"]["arguments"]["source_id"])
        for event in events
        if event["kind"] == "model_decision"
        and event["payload"].get("tool") == "fetch_source"
    }
    available = len(load_documents())
    assert len(listings[0].splitlines()) == available
    assert len(fetched) == 3
    assert len(fetched) < available


def test_hiding_a_conflict_between_sources_fails_verification(tmp_path: Path) -> None:
    trace = tmp_path / "hidden.jsonl"

    result = run_with_decisions(trace, HIDDEN_CONFLICT_DECISIONS)

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == (
        "claims contradicted by another fetched source were not recorded as"
        " disputed: marsh-survey-2024 (contradicted by regional-bird-atlas)"
    )


def test_a_disputed_claim_must_still_name_the_contradicting_source(
    tmp_path: Path,
) -> None:
    trace = tmp_path / "uncited.jsonl"

    result = run_with_decisions(trace, UNCITED_CONFLICT_DECISIONS)

    assert result.status is RunStatus.FAILED
    assert result.reason == (
        "the report does not name every source behind its claims:"
        " regional-bird-atlas"
    )


def test_a_claim_citing_an_unfetched_source_is_refused_by_the_tool(
    tmp_path: Path,
) -> None:
    trace = tmp_path / "unfetched.jsonl"

    result = run_with_decisions(trace, UNCITED_SOURCE_DECISIONS)

    assert result.status is RunStatus.FAILED
    assert result.reason == (
        "no claim was recorded, so the report carries no captured evidence"
    )
    refusals = [
        event["payload"]
        for event in trace_events(trace)
        if event["kind"] == "tool_result" and not event["payload"]["ok"]
    ]
    assert refusals[0]["error"] == (
        "cannot cite a source that was not fetched in this run: marsh-survey-2024"
    )


def test_a_confident_report_without_evidence_cannot_succeed(tmp_path: Path) -> None:
    trace = tmp_path / "no-evidence.jsonl"

    result = run_with_decisions(trace, NO_EVIDENCE_DECISIONS)

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == (
        "no claim was recorded, so the report carries no captured evidence"
    )
