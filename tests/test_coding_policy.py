from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from labs.coding.policy import WorkspacePolicy
from labs.coding.tools import CHECK_COMMAND, build_tools
from labs.coding.verification import CheckLedger
from labs.coding.workspace import FIXTURE_REPO, Workspace
from tiny_harness import (
    FunctionTool,
    PolicyDecision,
    Risk,
    Tool,
    ToolCall,
    ToolRegistry,
    ToolResult,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace() -> Iterator[Workspace]:
    created = Workspace.from_fixture()
    try:
        yield created
    finally:
        created.cleanup()


@pytest.fixture
def tools(workspace: Workspace) -> ToolRegistry:
    return build_tools(workspace, CheckLedger())


def decide(
    tools: ToolRegistry, workspace: Workspace, call: ToolCall
) -> PolicyDecision:
    tool = tools.get(call.name)
    assert tool is not None
    return WorkspacePolicy(workspace).evaluate(tool, call)


def consequential_tool() -> FunctionTool:
    return FunctionTool(
        name="notify_reviewer",
        description="Send a message outside the workspace.",
        input_schema={"type": "object", "properties": {}},
        risk=Risk.CONSEQUENTIAL,
        handler=lambda _arguments: ToolResult(ok=True),
    )


@pytest.mark.parametrize(
    "call",
    [
        ToolCall("list_files", {}),
        ToolCall("list_files", {"directory": "."}),
        ToolCall("read_file", {"path": "wordcount.py"}),
        ToolCall("search_text", {"pattern": "split"}),
        ToolCall("write_file", {"path": "wordcount.py", "content": "x = 1\n"}),
        ToolCall("write_file", {"path": "new/nested.py", "content": "x = 1\n"}),
        ToolCall("run_check", {}),
        ToolCall("run_check", {"command": list(CHECK_COMMAND)}),
    ],
)
def test_in_scope_actions_are_allowed(
    tools: ToolRegistry, workspace: Workspace, call: ToolCall
) -> None:
    assert decide(tools, workspace, call) is PolicyDecision.ALLOW


@pytest.mark.parametrize(
    "call",
    [
        ToolCall("write_file", {"path": "../escaped.py", "content": "x = 1\n"}),
        ToolCall("write_file", {"path": "a/../../../escaped.py", "content": "x\n"}),
        ToolCall("write_file", {"path": "/tmp/escaped.py", "content": "x = 1\n"}),
        ToolCall(
            "write_file",
            {"path": str(REPO_ROOT / "README.md"), "content": "overwritten\n"},
        ),
        ToolCall(
            "write_file",
            {"path": str(FIXTURE_REPO / "wordcount.py"), "content": "x = 1\n"},
        ),
        ToolCall("read_file", {"path": "../../etc/passwd"}),
        ToolCall("read_file", {"path": "/etc/passwd"}),
        ToolCall("list_files", {"directory": ".."}),
        ToolCall("write_file", {"path": "", "content": "x = 1\n"}),
    ],
)
def test_out_of_scope_paths_are_denied(
    tools: ToolRegistry, workspace: Workspace, call: ToolCall
) -> None:
    assert decide(tools, workspace, call) is PolicyDecision.DENY


def test_out_of_scope_write_to_a_sibling_prefix_directory_is_denied(
    tools: ToolRegistry, workspace: Workspace
) -> None:
    sibling = workspace.root.parent / f"{workspace.root.name}-evil"
    call = ToolCall(
        "write_file", {"path": str(sibling / "escaped.py"), "content": "x = 1\n"}
    )

    assert str(sibling).startswith(str(workspace.root))
    assert decide(tools, workspace, call) is PolicyDecision.DENY


def test_write_through_a_symlink_out_of_the_workspace_is_denied(
    tools: ToolRegistry, workspace: Workspace, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace.root / "escape").symlink_to(outside, target_is_directory=True)
    call = ToolCall(
        "write_file", {"path": "escape/escaped.py", "content": "x = 1\n"}
    )

    assert decide(tools, workspace, call) is PolicyDecision.DENY


def test_a_non_string_path_is_denied(
    tools: ToolRegistry, workspace: Workspace
) -> None:
    call = ToolCall("write_file", {"path": cast(Any, 17), "content": "x = 1\n"})

    assert decide(tools, workspace, call) is PolicyDecision.DENY


@pytest.mark.parametrize(
    "command",
    [
        ["git", "status"],
        ["git", "push", "origin", "main"],
        ["python", "-c", "import urllib.request"],
        ["python", "-m", "unittest"],
        ["curl", "https://example.com"],
        ["rm", "-rf", "."],
        "python -m unittest discover -p test_*.py",
        [],
        ["python", 3],
    ],
)
def test_commands_outside_the_allow_list_are_denied(
    tools: ToolRegistry, workspace: Workspace, command: object
) -> None:
    call = ToolCall("run_check", {"command": cast(Any, command)})

    assert decide(tools, workspace, call) is PolicyDecision.DENY


def test_a_consequential_tool_requires_approval(workspace: Workspace) -> None:
    tool = consequential_tool()

    decision = WorkspacePolicy(workspace).evaluate(
        tool, ToolCall("notify_reviewer", {})
    )

    assert decision is PolicyDecision.APPROVAL_REQUIRED


def test_an_invalid_runtime_risk_is_rejected(workspace: Workspace) -> None:
    tool = FunctionTool(
        name="broken",
        description="A tool with an invalid risk.",
        input_schema={"type": "object", "properties": {}},
        risk=cast(Risk, "write"),
        handler=lambda _arguments: ToolResult(ok=True),
    )

    with pytest.raises(TypeError, match="risk"):
        WorkspacePolicy(workspace).evaluate(tool, ToolCall("broken", {}))


def test_an_extended_allow_list_permits_only_its_own_entries(
    workspace: Workspace,
) -> None:
    extra = ("python", "-m", "unittest", "-v")
    policy = WorkspacePolicy(workspace, allowed_commands=(extra,))
    tool = cast(Tool, build_tools(workspace, CheckLedger()).get("run_check"))

    assert (
        policy.evaluate(tool, ToolCall("run_check", {"command": list(extra)}))
        is PolicyDecision.ALLOW
    )
    assert (
        policy.evaluate(tool, ToolCall("run_check", {"command": list(CHECK_COMMAND)}))
        is PolicyDecision.DENY
    )
