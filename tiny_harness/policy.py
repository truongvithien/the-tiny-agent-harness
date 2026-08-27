from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from tiny_harness.tools import Tool
from tiny_harness.types import PolicyDecision, Risk, ToolCall


class Policy(Protocol):
    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision: ...


ApprovalCallback: TypeAlias = Callable[[Tool, ToolCall], bool]


@dataclass(frozen=True)
class AuthorizationResult:
    policy_decision: PolicyDecision
    approval_granted: bool | None = None

    @property
    def allowed(self) -> bool:
        if self.policy_decision is PolicyDecision.ALLOW:
            return True
        return (
            self.policy_decision is PolicyDecision.APPROVAL_REQUIRED
            and self.approval_granted is True
        )


def _require_policy_decision(value: object) -> PolicyDecision:
    if not isinstance(value, PolicyDecision):
        raise TypeError("policy decision must be a PolicyDecision")
    return value


def _require_approval_result(value: object) -> bool:
    if type(value) is not bool:
        raise TypeError("approval result must be a bool")
    return value


class RiskPolicy:
    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision:
        del call
        if not isinstance(tool.risk, Risk):
            raise TypeError("tool risk must be a Risk")
        if tool.risk is Risk.CONSEQUENTIAL:
            return PolicyDecision.APPROVAL_REQUIRED
        return PolicyDecision.ALLOW


def authorize(
    tool: Tool,
    call: ToolCall,
    policy: Policy,
    approval: ApprovalCallback,
) -> AuthorizationResult:
    decision = _require_policy_decision(policy.evaluate(tool, call))
    if decision is PolicyDecision.APPROVAL_REQUIRED:
        granted = _require_approval_result(approval(tool, call))
        return AuthorizationResult(decision, approval_granted=granted)
    return AuthorizationResult(decision)
