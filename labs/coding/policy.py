from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from labs.coding.tools import (
    ALLOWED_COMMANDS,
    CHECK_COMMAND,
    COMMAND_ARGUMENT,
    PATH_ARGUMENTS,
    is_allowed_command,
)
from labs.coding.workspace import Workspace, is_inside
from tiny_harness import PolicyDecision, Risk, Tool, ToolCall


class WorkspacePolicy:
    def __init__(
        self,
        workspace: Workspace,
        *,
        allowed_commands: Sequence[Sequence[str]] = ALLOWED_COMMANDS,
    ) -> None:
        self._workspace = workspace
        self._allowed_commands = allowed_commands

    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision:
        if not isinstance(tool.risk, Risk):
            raise TypeError("tool risk must be a Risk")
        properties = self._declared_properties(tool)
        for key in PATH_ARGUMENTS:
            if key in call.arguments and not self._in_scope(call.arguments[key]):
                return PolicyDecision.DENY
        if COMMAND_ARGUMENT in properties:
            command = call.arguments.get(COMMAND_ARGUMENT, CHECK_COMMAND)
            if not is_allowed_command(command, self._allowed_commands):
                return PolicyDecision.DENY
        if tool.risk is Risk.CONSEQUENTIAL:
            return PolicyDecision.APPROVAL_REQUIRED
        return PolicyDecision.ALLOW

    def _in_scope(self, candidate: Any) -> bool:
        if not isinstance(candidate, str) or not candidate:
            return False
        return is_inside(self._workspace.root, candidate)

    @staticmethod
    def _declared_properties(tool: Tool) -> dict[str, Any]:
        schema = tool.input_schema
        properties = schema.get("properties", {}) if hasattr(schema, "get") else {}
        return dict(properties) if isinstance(properties, dict) else {}
