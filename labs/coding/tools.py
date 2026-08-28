from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from labs.coding.verification import CheckLedger
from labs.coding.workspace import PathEscapesWorkspace, Workspace
from tiny_harness import FunctionTool, Risk, ToolRegistry, ToolResult

CHECK_COMMAND: tuple[str, ...] = (
    "python",
    "-m",
    "unittest",
    "discover",
    "-p",
    "test_*.py",
)
ALLOWED_COMMANDS: tuple[tuple[str, ...], ...] = (CHECK_COMMAND,)
CHECK_TIMEOUT_SECONDS = 15.0
MAX_CHECK_OUTPUT = 2000
PATH_ARGUMENTS = ("path", "directory")
COMMAND_ARGUMENT = "command"


def is_allowed_command(
    command: object,
    allowed: Sequence[Sequence[str]] = ALLOWED_COMMANDS,
) -> bool:
    if isinstance(command, (str, bytes, bytearray)):
        return False
    if not isinstance(command, Sequence):
        return False
    if not all(isinstance(part, str) for part in command):
        return False
    return tuple(command) in {tuple(entry) for entry in allowed}


def resolve_program(command: Sequence[str]) -> list[str]:
    argv = list(command)
    if argv and argv[0] == "python":
        argv[0] = sys.executable
    return argv


def display_command(command: object) -> str:
    if isinstance(command, str):
        return command
    if isinstance(command, Sequence):
        return " ".join(str(part) for part in command)
    return repr(command)


def check_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if key != "PYTHONPATH"
    }
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _truncate(output: str) -> str:
    if len(output) <= MAX_CHECK_OUTPUT:
        return output
    return output[:MAX_CHECK_OUTPUT] + "…[TRUNCATED]"


def _require_string(arguments: Mapping[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def build_list_files(workspace: Workspace) -> FunctionTool:
    def list_files(arguments: Mapping[str, Any]) -> ToolResult:
        directory = arguments.get("directory", ".")
        if not isinstance(directory, str) or not directory:
            return ToolResult(ok=False, error="directory must be a non-empty string")
        try:
            found = workspace.list_files(directory)
        except PathEscapesWorkspace as error:
            return ToolResult(ok=False, error=str(error))
        except (NotADirectoryError, OSError) as error:
            return ToolResult(ok=False, error=f"{type(error).__name__}: {error}")
        return ToolResult(ok=True, output="\n".join(found))

    return FunctionTool(
        name="list_files",
        description="List files inside the temporary workspace.",
        input_schema={
            "type": "object",
            "properties": {"directory": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        risk=Risk.READ,
        handler=list_files,
    )


def build_read_file(workspace: Workspace) -> FunctionTool:
    def read_file(arguments: Mapping[str, Any]) -> ToolResult:
        try:
            path = _require_string(arguments, "path")
            content = workspace.read_file(path)
        except PathEscapesWorkspace as error:
            return ToolResult(ok=False, error=str(error))
        except ValueError as error:
            return ToolResult(ok=False, error=str(error))
        except (FileNotFoundError, UnicodeDecodeError, OSError) as error:
            return ToolResult(ok=False, error=f"{type(error).__name__}: {error}")
        return ToolResult(ok=True, output=content)

    return FunctionTool(
        name="read_file",
        description="Read one text file inside the temporary workspace.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        risk=Risk.READ,
        handler=read_file,
    )


def build_search_text(workspace: Workspace) -> FunctionTool:
    def search_text(arguments: Mapping[str, Any]) -> ToolResult:
        try:
            pattern = _require_string(arguments, "pattern")
            matches = workspace.search_text(pattern)
        except ValueError as error:
            return ToolResult(ok=False, error=str(error))
        except OSError as error:
            return ToolResult(ok=False, error=f"{type(error).__name__}: {error}")
        if not matches:
            return ToolResult(ok=True, output=f"no match for {pattern}")
        return ToolResult(ok=True, output="\n".join(matches))

    return FunctionTool(
        name="search_text",
        description="Search for a literal substring in workspace text files.",
        input_schema={
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
            "additionalProperties": False,
        },
        risk=Risk.READ,
        handler=search_text,
    )


def build_write_file(workspace: Workspace) -> FunctionTool:
    def write_file(arguments: Mapping[str, Any]) -> ToolResult:
        content = arguments.get("content")
        if not isinstance(content, str):
            return ToolResult(ok=False, error="content must be a string")
        try:
            path = _require_string(arguments, "path")
            written = workspace.write_file(path, content)
        except PathEscapesWorkspace as error:
            return ToolResult(ok=False, error=str(error))
        except ValueError as error:
            return ToolResult(ok=False, error=str(error))
        except OSError as error:
            return ToolResult(ok=False, error=f"{type(error).__name__}: {error}")
        return ToolResult(ok=True, output=f"wrote {written}")

    return FunctionTool(
        name="write_file",
        description="Replace one file inside the temporary workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        risk=Risk.WRITE,
        handler=write_file,
    )


def build_run_check(
    workspace: Workspace,
    ledger: CheckLedger,
    *,
    allowed_commands: Sequence[Sequence[str]] = ALLOWED_COMMANDS,
    timeout_seconds: float = CHECK_TIMEOUT_SECONDS,
) -> FunctionTool:
    def run_check(arguments: Mapping[str, Any]) -> ToolResult:
        command = arguments.get(COMMAND_ARGUMENT, CHECK_COMMAND)
        if not is_allowed_command(command, allowed_commands):
            return ToolResult(
                ok=False,
                error=f"command is not allow-listed: {display_command(command)}",
            )
        argv = resolve_program(command)
        try:
            completed = subprocess.run(
                argv,
                cwd=workspace.root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                env=check_environment(),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                ok=False,
                error=(
                    f"check timed out after {timeout_seconds} seconds: "
                    f"{display_command(command)}"
                ),
            )
        except OSError as error:
            return ToolResult(
                ok=False, error=f"{type(error).__name__}: {error}"
            )
        output = _truncate(f"{completed.stdout}{completed.stderr}".strip())
        record = ledger.record(command, completed.returncode, output)
        verdict = "passed" if record.passed else "failed"
        return ToolResult(
            ok=True,
            output=(
                f"check {verdict} with exit code {record.exit_code}\n"
                f"{record.display_command}\n{output}"
            ),
        )

    return FunctionTool(
        name="run_check",
        description="Run the allow-listed check command inside the workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
            "additionalProperties": False,
        },
        risk=Risk.WRITE,
        handler=run_check,
    )


def build_tools(
    workspace: Workspace,
    ledger: CheckLedger,
    *,
    allowed_commands: Sequence[Sequence[str]] = ALLOWED_COMMANDS,
    timeout_seconds: float = CHECK_TIMEOUT_SECONDS,
) -> ToolRegistry:
    return ToolRegistry(
        [
            build_list_files(workspace),
            build_read_file(workspace),
            build_search_text(workspace),
            build_write_file(workspace),
            build_run_check(
                workspace,
                ledger,
                allowed_commands=allowed_commands,
                timeout_seconds=timeout_seconds,
            ),
        ]
    )
