from typing import cast

import pytest

from tiny_harness.policy import RiskPolicy, authorize
from tiny_harness.tools import FunctionTool
from tiny_harness.types import PolicyDecision, Risk, ToolCall, ToolResult


def tool(risk: Risk) -> FunctionTool:
    return FunctionTool(
        name="action",
        description="Test action.",
        input_schema={"type": "object"},
        risk=risk,
        handler=lambda _: ToolResult(ok=True),
    )


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        (Risk.READ, PolicyDecision.ALLOW),
        (Risk.WRITE, PolicyDecision.ALLOW),
        (Risk.CONSEQUENTIAL, PolicyDecision.APPROVAL_REQUIRED),
    ],
)
def test_risk_policy_classifies_actions(risk: Risk, expected: PolicyDecision) -> None:
    assert RiskPolicy().evaluate(tool(risk), ToolCall("action", {})) is expected


def test_authorize_denies_consequential_action_when_approval_is_refused() -> None:
    authorization = authorize(
        tool(Risk.CONSEQUENTIAL),
        ToolCall("action", {}),
        RiskPolicy(),
        approval=lambda _tool, _call: False,
    )
    assert authorization.policy_decision is PolicyDecision.APPROVAL_REQUIRED
    assert authorization.approval_granted is False
    assert not authorization.allowed


def test_authorize_allows_consequential_action_when_approval_is_granted() -> None:
    authorization = authorize(
        tool(Risk.CONSEQUENTIAL),
        ToolCall("action", {}),
        RiskPolicy(),
        approval=lambda _tool, _call: True,
    )
    assert authorization.policy_decision is PolicyDecision.APPROVAL_REQUIRED
    assert authorization.approval_granted is True
    assert authorization.allowed


def test_risk_policy_rejects_an_invalid_runtime_risk() -> None:
    invalid = tool(cast(Risk, "consequential"))

    with pytest.raises(TypeError, match="risk"):
        RiskPolicy().evaluate(invalid, ToolCall("action", {}))


def test_authorize_rejects_a_non_boolean_approval() -> None:
    with pytest.raises(TypeError, match="approval"):
        authorize(
            tool(Risk.CONSEQUENTIAL),
            ToolCall("action", {}),
            RiskPolicy(),
            approval=lambda _tool, _call: cast(bool, "no"),
        )


def test_authorize_rejects_an_invalid_policy_decision() -> None:
    class InvalidPolicy:
        def evaluate(
            self, _tool: FunctionTool, _call: ToolCall
        ) -> PolicyDecision:
            return cast(PolicyDecision, "allow")

    with pytest.raises(TypeError, match="policy decision"):
        authorize(
            tool(Risk.READ),
            ToolCall("action", {}),
            InvalidPolicy(),
            approval=lambda _tool, _call: False,
        )
