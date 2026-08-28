from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from tiny_harness import (
    FinalAnswer,
    JsonlEventSink,
    ModelDecision,
    RiskPolicy,
    RunConfig,
    RunResult,
    Runner,
    ScriptedModel,
    ToolCall,
)

from labs.research.server import serve_documents
from labs.research.tools import ResearchNotebook, build_research_tools
from labs.research.verification import CitedClaims

RESEARCH_TASK = (
    "Report how many grey heron nesting pairs the Blackwater Marsh survey found,"
    " citing the sources you read."
)

ACCEPTANCE_CRITERIA = (
    "Every claim cites a source fetched in this run.",
    "Sources that disagree are reported as disputed instead of settled.",
    "The report names each source it relies on.",
)

DEMO_ANSWER = (
    "marsh-survey-2024 reports 128 active grey heron nesting pairs from the"
    " April 2024 dawn count, while regional-bird-atlas reports 96 pairs from a"
    " 2019 return that excludes the willow scrub heronry. The two fetched"
    " sources disagree, so this report gives both figures with their sources"
    " rather than one settled total. survey-method-manual describes the dawn"
    " flush count the 2024 total was produced with."
)

DEMO_DECISIONS: tuple[ModelDecision, ...] = (
    ToolCall("list_sources", {}),
    ToolCall("fetch_source", {"source_id": "marsh-survey-2024"}),
    ToolCall("fetch_source", {"source_id": "regional-bird-atlas"}),
    ToolCall("fetch_source", {"source_id": "survey-method-manual"}),
    ToolCall(
        "record_claim",
        {
            "claim": "The April 2024 dawn count recorded 128 active grey heron"
            " nesting pairs.",
            "source_id": "marsh-survey-2024",
            "disputed": True,
        },
    ),
    ToolCall(
        "record_claim",
        {
            "claim": "A dawn flush count uses two independent observers for each"
            " colony.",
            "source_id": "survey-method-manual",
        },
    ),
    FinalAnswer(DEMO_ANSWER),
)


def build_demo(
    trace_path: Path,
    base_url: str,
    decisions: Sequence[ModelDecision] = DEMO_DECISIONS,
) -> Runner:
    notebook = ResearchNotebook()
    return Runner(
        model=ScriptedModel(decisions),
        tools=build_research_tools(base_url, notebook),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=JsonlEventSink(trace_path, run_id="research-demo"),
        verifier=CitedClaims(notebook),
        config=RunConfig(max_iterations=8, timeout_seconds=15.0),
    )


def run_with_decisions(
    trace_path: Path,
    decisions: Sequence[ModelDecision],
) -> RunResult:
    trace_path.unlink(missing_ok=True)
    with serve_documents() as server:
        runner = build_demo(trace_path, server.base_url, decisions)
        return runner.run(RESEARCH_TASK, ACCEPTANCE_CRITERIA)


def run_demo(trace_path: Path) -> RunResult:
    return run_with_decisions(trace_path, DEMO_DECISIONS)


def main() -> None:
    trace_path = Path(".traces/research.jsonl")
    result = run_demo(trace_path)
    print(result.status.value)
    print(result.answer)
    print(trace_path)


if __name__ == "__main__":
    main()
