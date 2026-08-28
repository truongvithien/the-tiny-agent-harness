import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from labs.coding.tools import (
    ALLOWED_COMMANDS,
    CHECK_COMMAND,
    build_run_check,
    build_tools,
    check_environment,
    is_allowed_command,
    resolve_program,
)
from labs.coding.verification import CheckLedger
from labs.coding.workspace import FIXTURE_REPO, Workspace
from tiny_harness import Risk, Tool, ToolCall, ToolRegistry, ToolResult

REPO_ROOT = Path(__file__).resolve().parents[1]
SLEEP_COMMAND = ("python", "-c", "import time; time.sleep(5)")
BUGGY_SOURCE = 'def count_words(text: str) -> int:\n    return len(text.split(" "))\n'
FIXED_SOURCE = "def count_words(text: str) -> int:\n    return len(text.split())\n"


@pytest.fixture
def workspace() -> Iterator[Workspace]:
    created = Workspace.from_fixture()
    try:
        yield created
    finally:
        created.cleanup()


@pytest.fixture
def ledger() -> CheckLedger:
    return CheckLedger()


@pytest.fixture
def tools(workspace: Workspace, ledger: CheckLedger) -> ToolRegistry:
    return build_tools(workspace, ledger)


def invoke(tools: ToolRegistry, name: str, arguments: dict[str, Any]) -> ToolResult:
    return tools.execute(ToolCall(name, arguments))


def test_tools_declare_the_documented_risk_classes(tools: ToolRegistry) -> None:
    risks = {
        specification["name"]: cast(Tool, tools.get(specification["name"])).risk
        for specification in tools.specifications()
    }

    assert risks == {
        "list_files": Risk.READ,
        "read_file": Risk.READ,
        "search_text": Risk.READ,
        "write_file": Risk.WRITE,
        "run_check": Risk.WRITE,
    }


def test_read_tools_report_workspace_contents(tools: ToolRegistry) -> None:
    listed = invoke(tools, "list_files", {})
    read = invoke(tools, "read_file", {"path": "wordcount.py"})
    searched = invoke(tools, "search_text", {"pattern": "text.split"})

    assert listed.ok and listed.output.splitlines() == [
        "README.md",
        "test_wordcount.py",
        "wordcount.py",
    ]
    assert read.ok and read.output == BUGGY_SOURCE
    assert searched.ok
    assert searched.output == 'wordcount.py:2: return len(text.split(" "))'


def test_search_text_reports_an_empty_result_as_success(tools: ToolRegistry) -> None:
    result = invoke(tools, "search_text", {"pattern": "no-such-token"})

    assert result.ok
    assert result.output == "no match for no-such-token"


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("read_file", {"path": "../../etc/passwd"}),
        ("read_file", {"path": "/etc/passwd"}),
        ("read_file", {"path": str(FIXTURE_REPO / "wordcount.py")}),
        ("list_files", {"directory": ".."}),
        ("write_file", {"path": "../escaped.py", "content": "x = 1\n"}),
        ("write_file", {"path": str(REPO_ROOT / "README.md"), "content": "x\n"}),
    ],
)
def test_tools_refuse_paths_outside_the_workspace(
    tools: ToolRegistry, name: str, arguments: dict[str, Any]
) -> None:
    result = invoke(tools, name, arguments)

    assert result.ok is False
    assert result.error is not None
    assert "escapes the workspace" in result.error
    assert result.retryable is False


def test_a_refused_write_creates_no_file_outside_the_workspace(
    tools: ToolRegistry, tmp_path: Path
) -> None:
    target = tmp_path / "escaped.py"

    result = invoke(tools, "write_file", {"path": str(target), "content": "x = 1\n"})

    assert result.ok is False
    assert not target.exists()


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("read_file", {"path": "absent.py"}, "FileNotFoundError"),
        ("read_file", {}, "path must be a non-empty string"),
        ("write_file", {"path": "a.py"}, "content must be a string"),
        ("write_file", {"path": "a.py", "content": 7}, "content must be a string"),
        ("search_text", {"pattern": ""}, "pattern must be a non-empty string"),
        ("list_files", {"directory": ""}, "directory must be a non-empty string"),
        ("list_files", {"directory": "wordcount.py"}, "NotADirectoryError"),
    ],
)
def test_tools_convert_invalid_arguments_into_typed_failures(
    tools: ToolRegistry, name: str, arguments: dict[str, Any], expected: str
) -> None:
    result = invoke(tools, name, arguments)

    assert result.ok is False
    assert result.error is not None
    assert expected in result.error


def test_write_file_records_a_reversible_edit(
    tools: ToolRegistry, workspace: Workspace
) -> None:
    original = workspace.read_file("wordcount.py")

    result = invoke(
        tools, "write_file", {"path": "wordcount.py", "content": "fixed\n"}
    )

    assert result.ok and result.output == "wrote wordcount.py"
    assert workspace.read_file("wordcount.py") == "fixed\n"
    assert workspace.edits[-1].previous_content == original
    workspace.revert_last()
    assert workspace.read_file("wordcount.py") == original


def test_run_check_captures_a_failing_check_as_evidence(
    tools: ToolRegistry, ledger: CheckLedger
) -> None:
    result = invoke(tools, "run_check", {"command": list(CHECK_COMMAND)})

    assert result.ok
    assert result.output.startswith("check failed with exit code 1")
    assert ledger.latest is not None
    assert ledger.latest.command == CHECK_COMMAND
    assert ledger.latest.exit_code == 1
    assert ledger.latest.passed is False


def test_run_check_captures_a_passing_check_after_a_fix(
    tools: ToolRegistry, ledger: CheckLedger
) -> None:
    invoke(tools, "write_file", {"path": "wordcount.py", "content": FIXED_SOURCE})

    result = invoke(tools, "run_check", {})

    assert result.ok
    assert result.output.startswith("check passed with exit code 0")
    assert ledger.latest is not None
    assert ledger.latest.passed is True


@pytest.mark.parametrize(
    "command",
    [
        ["git", "status"],
        ["git", "commit", "-m", "fix"],
        ["curl", "https://example.com"],
        ["python", "-c", "print(1)"],
        ["python", "-m", "unittest"],
        "git status",
        "python -m unittest discover -p test_*.py",
        [],
    ],
)
def test_run_check_refuses_a_command_outside_the_allow_list(
    tools: ToolRegistry, ledger: CheckLedger, command: object
) -> None:
    result = invoke(tools, "run_check", {"command": cast(Any, command)})

    assert result.ok is False
    assert result.error is not None
    assert result.error.startswith("command is not allow-listed:")
    assert result.retryable is False
    assert ledger.records == ()


def test_run_check_enforces_its_timeout(
    workspace: Workspace, ledger: CheckLedger
) -> None:
    tool = build_run_check(
        workspace,
        ledger,
        allowed_commands=(SLEEP_COMMAND,),
        timeout_seconds=0.3,
    )

    result = tool.invoke({"command": list(SLEEP_COMMAND)})

    assert result.ok is False
    assert result.error is not None
    assert result.error.startswith("check timed out after 0.3 seconds")
    assert ledger.records == ()


def test_run_check_leaves_no_bytecode_cache_in_the_workspace(
    tools: ToolRegistry, workspace: Workspace
) -> None:
    invoke(tools, "run_check", {})

    assert not list(workspace.root.rglob("__pycache__"))


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (list(CHECK_COMMAND), True),
        (CHECK_COMMAND, True),
        (["git", "status"], False),
        ("python -m unittest discover -p test_*.py", False),
        (b"python", False),
        (None, False),
        (17, False),
        (["python", 3], False),
    ],
)
def test_is_allowed_command_accepts_only_allow_listed_argument_lists(
    command: object, expected: bool
) -> None:
    assert is_allowed_command(command, ALLOWED_COMMANDS) is expected


def test_resolve_program_uses_the_running_interpreter() -> None:
    assert resolve_program(CHECK_COMMAND)[0] == sys.executable
    assert resolve_program(CHECK_COMMAND)[1:] == list(CHECK_COMMAND[1:])
    assert resolve_program(("unittest",)) == ["unittest"]


def test_check_environment_drops_the_inherited_import_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))

    environment = check_environment()

    assert "PYTHONPATH" not in environment
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
