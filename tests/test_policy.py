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
    decision = authorize(
        tool(Risk.CONSEQUENTIAL),
        ToolCall("action", {}),
        RiskPolicy(),
        approval=lambda _tool, _call: False,
    )
    assert decision is PolicyDecision.DENY


def test_authorize_allows_consequential_action_when_approval_is_granted() -> None:
    decision = authorize(
        tool(Risk.CONSEQUENTIAL),
        ToolCall("action", {}),
        RiskPolicy(),
        approval=lambda _tool, _call: True,
    )
    assert decision is PolicyDecision.ALLOW
