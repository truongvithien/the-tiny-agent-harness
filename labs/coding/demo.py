from __future__ import annotations

from pathlib import Path

from labs.coding.policy import WorkspacePolicy
from labs.coding.tools import CHECK_COMMAND, build_tools
from labs.coding.verification import CheckLedger, PassingCheckRequired
from labs.coding.workspace import Workspace
from tiny_harness import (
    FinalAnswer,
    JsonlEventSink,
    RunConfig,
    RunResult,
    Runner,
    ScriptedModel,
    ToolCall,
)

TRACE_PATH = Path(".traces/coding.jsonl")
TASK = "Make the allow-listed check pass in the temporary workspace copy."
ACCEPTANCE_CRITERIA = (
    "count_words counts words separated by any whitespace.",
    "The allow-listed check command passes in this run.",
)
FIXED_SOURCE = """def count_words(text: str) -> int:
    return len(text.split())
"""
FINAL_ANSWER = (
    "count_words now splits on any run of whitespace, and the allow-listed "
    "check passed with exit code 0 after the edit."
)


def build_demo(trace_path: Path, workspace: Workspace) -> Runner:
    ledger = CheckLedger()
    return Runner(
        model=ScriptedModel(
            [
                ToolCall("list_files", {}),
                ToolCall("run_check", {"command": list(CHECK_COMMAND)}),
                ToolCall("read_file", {"path": "test_wordcount.py"}),
                ToolCall("search_text", {"pattern": "split"}),
                ToolCall(
                    "write_file",
                    {"path": "wordcount.py", "content": FIXED_SOURCE},
                ),
                ToolCall("run_check", {"command": list(CHECK_COMMAND)}),
                FinalAnswer(FINAL_ANSWER),
            ]
        ),
        tools=build_tools(workspace, ledger),
        policy=WorkspacePolicy(workspace),
        approval=lambda _tool, _call: False,
        events=JsonlEventSink(trace_path, run_id="coding-demo"),
        verifier=PassingCheckRequired(ledger),
        config=RunConfig(max_iterations=7, timeout_seconds=60.0),
    )


def run_demo(trace_path: Path) -> RunResult:
    trace_path.unlink(missing_ok=True)
    with Workspace.from_fixture() as workspace:
        return build_demo(trace_path, workspace).run(TASK, ACCEPTANCE_CRITERIA)


def main() -> None:
    result = run_demo(TRACE_PATH)
    print(result.status.value)
    print(result.answer)
    print(TRACE_PATH)


if __name__ == "__main__":
    main()
