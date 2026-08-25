from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class Risk(StrEnum):
    READ = "read"
    WRITE = "write"
    CONSEQUENTIAL = "consequential"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    APPROVAL_REFUSED = "approval_refused"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class FinalAnswer:
    text: str


type ModelDecision = ToolCall | FinalAnswer


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str = ""
    error: str | None = None
    retryable: bool = False

    def __post_init__(self) -> None:
        if not self.ok and not self.error:
            raise ValueError("an unsuccessful tool result requires an error")


@dataclass(frozen=True)
class Observation:
    source: str
    content: str


@dataclass(frozen=True)
class RunContext:
    task: str
    acceptance_criteria: tuple[str, ...]
    observations: tuple[Observation, ...] = ()
    remaining_iterations: int = 0


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    answer: str | None
    reason: str
    run_id: str
    event_count: int = field(default=0)
