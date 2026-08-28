import json
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from labs.coding import demo
from labs.coding.demo import ACCEPTANCE_CRITERIA, FIXED_SOURCE, TASK, run_demo
from labs.coding.policy import WorkspacePolicy
from labs.coding.tools import CHECK_COMMAND, build_tools
from labs.coding.verification import CheckLedger, PassingCheckRequired
from labs.coding.workspace import FIXTURE_REPO, WORKSPACE_PREFIX, Workspace
from tiny_harness import (
    FinalAnswer,
    JsonlEventSink,
    ModelDecision,
    RunConfig,
    RunResult,
    Runner,
    RunStatus,
    ScriptedModel,
    ToolCall,
)

FIXTURE_FILES = ("README.md", "test_wordcount.py", "wordcount.py")
BROKEN_SOURCE = "def count_words(text):\n    return 0\n"


@pytest.fixture
def workspace() -> Iterator[Workspace]:
    created = Workspace.from_fixture()
    try:
        yield created
    finally:
        created.cleanup()


def temporary_workspaces() -> set[Path]:
    return set(Path(tempfile.gettempdir()).glob(f"{WORKSPACE_PREFIX}*"))


def kinds(trace: Path) -> list[str]:
    return [json.loads(line)["kind"] for line in trace.read_text().splitlines()]


def payloads(trace: Path, kind: str) -> list[dict[str, object]]:
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    return [event["payload"] for event in events if event["kind"] == kind]


def run_scenario(
    workspace: Workspace,
    trace: Path,
    decisions: Sequence[ModelDecision],
) -> RunResult:
    ledger = CheckLedger()
    runner = Runner(
        model=ScriptedModel(decisions),
        tools=build_tools(workspace, ledger),
        policy=WorkspacePolicy(workspace),
        approval=lambda _tool, _call: False,
        events=JsonlEventSink(trace, run_id="coding-scenario"),
        verifier=PassingCheckRequired(ledger),
        config=RunConfig(max_iterations=len(decisions), timeout_seconds=60.0),
    )
    return runner.run(TASK, ACCEPTANCE_CRITERIA)


def test_demo_fixes_the_fixture_and_records_a_passing_check(tmp_path: Path) -> None:
    trace = tmp_path / "coding.jsonl"

    result = run_demo(trace)

    assert result.status is RunStatus.SUCCEEDED
    assert result.answer == demo.FINAL_ANSWER
    assert result.reason == (
        "the last check passed in this run with exit code 0: "
        "python -m unittest discover -p test_*.py"
    )
    assert kinds(trace) == [
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
    checks = [
        payload
        for payload in payloads(trace, "tool_result")
        if payload["tool"] == "run_check"
    ]
    assert len(checks) == 2
    assert str(checks[0]["output"]).startswith("check failed with exit code 1")
    assert str(checks[1]["output"]).startswith("check passed with exit code 0")
    assert payloads(trace, "verification") == [
        {
            "accepted": True,
            "reason": (
                "the last check passed in this run with exit code 0: "
                "python -m unittest discover -p test_*.py"
            ),
        }
    ]


def test_demo_leaves_no_temporary_workspace_behind(tmp_path: Path) -> None:
    before = temporary_workspaces()

    run_demo(tmp_path / "coding.jsonl")

    assert temporary_workspaces() == before


def test_demo_never_modifies_the_course_repository(tmp_path: Path) -> None:
    before = {
        path.name: (path.read_text(encoding="utf-8"), path.stat().st_mtime_ns)
        for path in sorted(FIXTURE_REPO.iterdir())
        if path.is_file()
    }

    run_demo(tmp_path / "coding.jsonl")

    after = {
        path.name: (path.read_text(encoding="utf-8"), path.stat().st_mtime_ns)
        for path in sorted(FIXTURE_REPO.iterdir())
        if path.is_file()
    }
    assert set(before) == set(FIXTURE_FILES)
    assert after == before


def test_demo_rewrites_its_trace_on_every_run(tmp_path: Path) -> None:
    trace = tmp_path / "coding.jsonl"

    run_demo(trace)
    first = kinds(trace)
    run_demo(trace)

    assert kinds(trace) == first


def test_main_prints_the_status_answer_and_trace_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = tmp_path / "coding.jsonl"
    monkeypatch.setattr(demo, "TRACE_PATH", trace)

    demo.main()

    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == "succeeded"
    assert printed[-1] == str(trace)


def test_an_out_of_scope_write_ends_the_run_with_policy_denied(
    workspace: Workspace, tmp_path: Path
) -> None:
    trace = tmp_path / "denied.jsonl"
    target = tmp_path / "escaped.py"

    result = run_scenario(
        workspace,
        trace,
        [
            ToolCall(
                "write_file", {"path": str(target), "content": "escaped = True\n"}
            ),
            FinalAnswer("I edited a file outside the workspace."),
        ],
    )

    assert result.status is RunStatus.POLICY_DENIED
    assert result.answer is None
    assert result.reason == "policy denied tool: write_file"
    assert kinds(trace) == [
        "run_started",
        "model_decision",
        "policy_decision",
        "run_finished",
    ]
    assert payloads(trace, "policy_decision") == [
        {"tool": "write_file", "decision": "deny"}
    ]
    assert not target.exists()


def test_a_command_outside_the_allow_list_ends_the_run_with_policy_denied(
    workspace: Workspace, tmp_path: Path
) -> None:
    trace = tmp_path / "denied-command.jsonl"

    result = run_scenario(
        workspace,
        trace,
        [
            ToolCall("run_check", {"command": ["git", "status"]}),
            FinalAnswer("I inspected the Git status."),
        ],
    )

    assert result.status is RunStatus.POLICY_DENIED
    assert result.reason == "policy denied tool: run_check"
    assert kinds(trace) == [
        "run_started",
        "model_decision",
        "policy_decision",
        "run_finished",
    ]


def test_a_declared_fix_without_any_check_fails_verification(
    workspace: Workspace, tmp_path: Path
) -> None:
    trace = tmp_path / "unverified.jsonl"

    result = run_scenario(
        workspace,
        trace,
        [
            ToolCall(
                "write_file", {"path": "wordcount.py", "content": FIXED_SOURCE}
            ),
            FinalAnswer("I fixed count_words, so the tests must pass now."),
        ],
    )

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == "no allow-listed check ran in this run"
    assert kinds(trace) == [
        "run_started",
        "model_decision",
        "policy_decision",
        "tool_result",
        "model_decision",
        "verification",
        "run_finished",
    ]
    assert payloads(trace, "verification") == [
        {"accepted": False, "reason": "no allow-listed check ran in this run"}
    ]


def test_a_declared_fix_after_a_failing_check_fails_verification(
    workspace: Workspace, tmp_path: Path
) -> None:
    trace = tmp_path / "failing-check.jsonl"

    result = run_scenario(
        workspace,
        trace,
        [
            ToolCall("run_check", {"command": list(CHECK_COMMAND)}),
            FinalAnswer("The remaining failures are unrelated, so I am done."),
        ],
    )

    assert result.status is RunStatus.FAILED
    assert result.answer is None
    assert result.reason == (
        "the last check exited with 1: python -m unittest discover -p test_*.py"
    )
    assert kinds(trace) == [
        "run_started",
        "model_decision",
        "policy_decision",
        "tool_result",
        "model_decision",
        "verification",
        "run_finished",
    ]


def test_an_edit_that_breaks_a_previously_passing_check_fails_verification(
    workspace: Workspace, tmp_path: Path
) -> None:
    trace = tmp_path / "regression.jsonl"

    result = run_scenario(
        workspace,
        trace,
        [
            ToolCall(
                "write_file", {"path": "wordcount.py", "content": FIXED_SOURCE}
            ),
            ToolCall("run_check", {"command": list(CHECK_COMMAND)}),
            ToolCall(
                "write_file",
                {"path": "wordcount.py", "content": BROKEN_SOURCE},
            ),
            ToolCall("run_check", {"command": list(CHECK_COMMAND)}),
            FinalAnswer("The check passed earlier in this run."),
        ],
    )

    assert result.status is RunStatus.FAILED
    assert result.reason.startswith("the last check exited with 1")
