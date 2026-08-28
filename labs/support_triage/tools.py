from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from labs.support_triage.store import PolicyExcerpt, PolicyLibrary, Ticket, TicketStore
from tiny_harness import FunctionTool, Risk, ToolRegistry, ToolResult

ALLOWED_CATEGORIES: tuple[str, ...] = (
    "account_access",
    "billing",
    "bug",
    "how_to",
)


@dataclass(frozen=True)
class SentReply:
    ticket_id: str
    category: str
    body: str


class TriageState:
    def __init__(self) -> None:
        self.category: str | None = None
        self.draft_reply: str | None = None
        self.sent_replies: tuple[SentReply, ...] = ()
        self.send_calls: int = 0

    @property
    def has_evidence(self) -> bool:
        return self.category is not None and bool((self.draft_reply or "").strip())


def _text_argument(arguments: Mapping[str, Any], key: str) -> str | None:
    value = arguments.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _format_ticket(ticket: Ticket) -> str:
    return (
        f"{ticket.ticket_id} | {ticket.channel} | {ticket.received_at}\n"
        f"customer: {ticket.customer}\n"
        f"subject: {ticket.subject}\n"
        f"body: {ticket.body}"
    )


def _format_excerpts(excerpts: tuple[PolicyExcerpt, ...]) -> str:
    return "\n\n".join(
        f"[{excerpt.source}] {excerpt.heading}\n{excerpt.text}" for excerpt in excerpts
    )


def build_tools(
    *,
    state: TriageState,
    tickets: TicketStore | None = None,
    policies: PolicyLibrary | None = None,
) -> tuple[FunctionTool, ...]:
    ticket_store = tickets if tickets is not None else TicketStore()
    policy_library = policies if policies is not None else PolicyLibrary()

    def read_ticket(arguments: Mapping[str, Any]) -> ToolResult:
        ticket_id = _text_argument(arguments, "ticket_id")
        if ticket_id is None:
            return ToolResult(
                ok=False, error="read_ticket requires a non-empty ticket_id string"
            )
        ticket = ticket_store.read(ticket_id)
        if ticket is None:
            return ToolResult(ok=False, error=f"unknown ticket: {ticket_id}")
        return ToolResult(ok=True, output=_format_ticket(ticket))

    def search_policy(arguments: Mapping[str, Any]) -> ToolResult:
        keyword = _text_argument(arguments, "keyword")
        if keyword is None:
            return ToolResult(
                ok=False, error="search_policy requires a non-empty keyword string"
            )
        excerpts = policy_library.search(keyword)
        if not excerpts:
            return ToolResult(
                ok=True, output=f"no policy section matched the keyword: {keyword}"
            )
        return ToolResult(ok=True, output=_format_excerpts(excerpts))

    def set_category(arguments: Mapping[str, Any]) -> ToolResult:
        category = _text_argument(arguments, "category")
        if category is None:
            return ToolResult(
                ok=False, error="set_category requires a non-empty category string"
            )
        if category not in ALLOWED_CATEGORIES:
            allowed = ", ".join(ALLOWED_CATEGORIES)
            return ToolResult(
                ok=False,
                error=f"unknown category: {category}; allowed categories are {allowed}",
            )
        state.category = category
        return ToolResult(ok=True, output=f"category recorded: {category}")

    def draft_reply(arguments: Mapping[str, Any]) -> ToolResult:
        text = _text_argument(arguments, "text")
        if text is None:
            return ToolResult(
                ok=False, error="draft_reply requires a non-empty text string"
            )
        state.draft_reply = text
        return ToolResult(ok=True, output=f"draft recorded ({len(text)} characters)")

    def send_reply(arguments: Mapping[str, Any]) -> ToolResult:
        state.send_calls += 1
        ticket_id = _text_argument(arguments, "ticket_id")
        if ticket_id is None:
            return ToolResult(
                ok=False, error="send_reply requires a non-empty ticket_id string"
            )
        ticket = ticket_store.read(ticket_id)
        if ticket is None:
            return ToolResult(ok=False, error=f"unknown ticket: {ticket_id}")
        if state.category is None:
            return ToolResult(ok=False, error="no category was recorded for this run")
        draft = (state.draft_reply or "").strip()
        if not draft:
            return ToolResult(ok=False, error="no reply was drafted for this run")
        state.sent_replies += (
            SentReply(
                ticket_id=ticket.ticket_id, category=state.category, body=draft
            ),
        )
        return ToolResult(
            ok=True,
            output=(
                f"simulated send to {ticket.customer} for {ticket.ticket_id} "
                f"as {state.category}"
            ),
        )

    return (
        FunctionTool(
            name="read_ticket",
            description="Read one support ticket from the local ticket store.",
            input_schema={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
                "additionalProperties": False,
            },
            risk=Risk.READ,
            handler=read_ticket,
        ),
        FunctionTool(
            name="search_policy",
            description="Search the policy knowledge base and return excerpts with their source file.",
            input_schema={
                "type": "object",
                "properties": {"keyword": {"type": "string"}},
                "required": ["keyword"],
                "additionalProperties": False,
            },
            risk=Risk.READ,
            handler=search_policy,
        ),
        FunctionTool(
            name="set_category",
            description=(
                "Record one triage category on run-local state. "
                f"Allowed categories: {', '.join(ALLOWED_CATEGORIES)}."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": list(ALLOWED_CATEGORIES)}
                },
                "required": ["category"],
                "additionalProperties": False,
            },
            risk=Risk.WRITE,
            handler=set_category,
        ),
        FunctionTool(
            name="draft_reply",
            description="Store a draft customer reply on run-local state.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            risk=Risk.WRITE,
            handler=draft_reply,
        ),
        FunctionTool(
            name="send_reply",
            description="Simulate sending the drafted reply to the customer. Requires approval.",
            input_schema={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
                "additionalProperties": False,
            },
            risk=Risk.CONSEQUENTIAL,
            handler=send_reply,
        ),
    )


def build_registry(
    *,
    state: TriageState,
    tickets: TicketStore | None = None,
    policies: PolicyLibrary | None = None,
) -> ToolRegistry:
    return ToolRegistry(
        build_tools(state=state, tickets=tickets, policies=policies)
    )
