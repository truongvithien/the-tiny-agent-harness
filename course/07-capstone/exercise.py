from dataclasses import dataclass, field
from typing import Any, Mapping

from tiny_harness import (
    FunctionTool,
    PolicyDecision,
    Risk,
    Tool,
    ToolCall,
    ToolResult,
)

MAX_AUTOMATIC_REFUND = 100.0


@dataclass
class RefundLedger:
    issued: list[tuple[str, float]] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(amount for _ticket, amount in self.issued)


def build_refund_tool(ledger: RefundLedger) -> FunctionTool:
    def issue_refund(arguments: Mapping[str, Any]) -> ToolResult:
        ticket = str(arguments["ticket_id"])
        amount = float(arguments["amount"])
        ledger.issued.append((ticket, amount))
        return ToolResult(ok=True, output=f"refunded {amount:.2f} on {ticket}")

    return FunctionTool(
        name="issue_refund",
        description="Refund a customer for a billing error.",
        input_schema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["ticket_id", "amount"],
            "additionalProperties": False,
        },
        risk=Risk.CONSEQUENTIAL,
        handler=issue_refund,
    )


class RefundPolicy:
    """Authorize tool calls, inspecting refund amounts as well as risk.

    Unlike RiskPolicy, this policy reads the *arguments* of a call. Return:

    - PolicyDecision.ALLOW for any read or write tool;
    - PolicyDecision.DENY for an `issue_refund` call whose `amount` is missing,
      not a number, negative, or greater than MAX_AUTOMATIC_REFUND;
    - PolicyDecision.APPROVAL_REQUIRED for every other consequential call.

    A denial must never depend on the model choosing to behave.
    """

    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision:
        raise NotImplementedError("complete the refund policy from the capstone")
