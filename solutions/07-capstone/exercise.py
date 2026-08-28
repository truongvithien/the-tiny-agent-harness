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
    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision:
        if tool.risk is not Risk.CONSEQUENTIAL:
            return PolicyDecision.ALLOW
        if tool.name != "issue_refund":
            return PolicyDecision.APPROVAL_REQUIRED
        amount = call.arguments.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            return PolicyDecision.DENY
        if amount < 0 or amount > MAX_AUTOMATIC_REFUND:
            return PolicyDecision.DENY
        return PolicyDecision.APPROVAL_REQUIRED
