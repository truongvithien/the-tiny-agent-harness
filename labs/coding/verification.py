from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tiny_harness import FinalAnswer, RunContext, VerificationResult


@dataclass(frozen=True)
class CheckRecord:
    command: tuple[str, ...]
    exit_code: int
    output: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    @property
    def display_command(self) -> str:
        return " ".join(self.command)


class CheckLedger:
    def __init__(self) -> None:
        self._records: list[CheckRecord] = []

    @property
    def records(self) -> tuple[CheckRecord, ...]:
        return tuple(self._records)

    @property
    def latest(self) -> CheckRecord | None:
        return self._records[-1] if self._records else None

    def record(
        self, command: Sequence[str], exit_code: int, output: str
    ) -> CheckRecord:
        record = CheckRecord(tuple(command), exit_code, output)
        self._records.append(record)
        return record


class PassingCheckRequired:
    def __init__(self, ledger: CheckLedger) -> None:
        self._ledger = ledger

    def verify(
        self, context: RunContext, answer: FinalAnswer
    ) -> VerificationResult:
        del context, answer
        latest = self._ledger.latest
        if latest is None:
            return VerificationResult(
                False, "no allow-listed check ran in this run"
            )
        if not latest.passed:
            return VerificationResult(
                False,
                f"the last check exited with {latest.exit_code}: "
                f"{latest.display_command}",
            )
        return VerificationResult(
            True,
            f"the last check passed in this run with exit code 0: "
            f"{latest.display_command}",
        )
