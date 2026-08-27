from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent / "data"
TICKETS_ROOT = DATA_ROOT / "tickets"
POLICIES_ROOT = DATA_ROOT / "policies"


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    customer: str
    channel: str
    received_at: str
    subject: str
    body: str


@dataclass(frozen=True)
class PolicyExcerpt:
    source: str
    heading: str
    text: str


def _load_ticket(path: Path) -> Ticket:
    record = json.loads(path.read_text(encoding="utf-8"))
    return Ticket(
        ticket_id=str(record["ticket_id"]),
        customer=str(record["customer"]),
        channel=str(record["channel"]),
        received_at=str(record["received_at"]),
        subject=str(record["subject"]),
        body=str(record["body"]),
    )


class TicketStore:
    def __init__(self, root: Path = TICKETS_ROOT) -> None:
        self._root = root

    def ticket_ids(self) -> tuple[str, ...]:
        return tuple(sorted(ticket.ticket_id for ticket in self._all()))

    def read(self, ticket_id: str) -> Ticket | None:
        wanted = ticket_id.strip().upper()
        for ticket in self._all():
            if ticket.ticket_id.upper() == wanted:
                return ticket
        return None

    def _all(self) -> tuple[Ticket, ...]:
        return tuple(_load_ticket(path) for path in sorted(self._root.glob("*.json")))


def _split_sections(source: str, text: str) -> tuple[PolicyExcerpt, ...]:
    excerpts: list[PolicyExcerpt] = []
    heading = ""
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading:
                excerpts.append(
                    PolicyExcerpt(source=source, heading=heading, text=_join(lines))
                )
            heading = line[3:].strip()
            lines = []
        elif heading:
            lines.append(line)
    if heading:
        excerpts.append(PolicyExcerpt(source=source, heading=heading, text=_join(lines)))
    return tuple(excerpts)


def _join(lines: list[str]) -> str:
    return " ".join(line.strip() for line in lines if line.strip())


class PolicyLibrary:
    def __init__(self, root: Path = POLICIES_ROOT) -> None:
        self._root = root

    def sources(self) -> tuple[str, ...]:
        return tuple(path.name for path in sorted(self._root.glob("*.md")))

    def excerpts(self) -> tuple[PolicyExcerpt, ...]:
        found: tuple[PolicyExcerpt, ...] = ()
        for path in sorted(self._root.glob("*.md")):
            found += _split_sections(path.name, path.read_text(encoding="utf-8"))
        return found

    def search(self, keyword: str, *, limit: int = 3) -> tuple[PolicyExcerpt, ...]:
        needle = keyword.strip().lower()
        if not needle:
            return ()
        matches = tuple(
            excerpt
            for excerpt in self.excerpts()
            if needle in excerpt.heading.lower() or needle in excerpt.text.lower()
        )
        return matches[:limit]
