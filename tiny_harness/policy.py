from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias

from tiny_harness.tools import Tool
from tiny_harness.types import PolicyDecision, Risk, ToolCall


class Policy(Protocol):
    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision: ...


ApprovalCallback: TypeAlias = Callable[[Tool, ToolCall], bool]


class RiskPolicy:
    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision:
        del call
        if tool.risk is Risk.CONSEQUENTIAL:
            return PolicyDecision.APPROVAL_REQUIRED
        return PolicyDecision.ALLOW


def authorize(
    tool: Tool,
    call: ToolCall,
    policy: Policy,
    approval: ApprovalCallback,
) -> PolicyDecision:
    decision = policy.evaluate(tool, call)
    if decision is PolicyDecision.APPROVAL_REQUIRED:
        return PolicyDecision.ALLOW if approval(tool, call) else PolicyDecision.DENY
    return decision
