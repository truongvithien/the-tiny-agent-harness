from __future__ import annotations

from labs.support_triage.tools import TriageState
from tiny_harness import FinalAnswer, RunContext, VerificationResult


class TriageVerifier:
    def __init__(self, state: TriageState) -> None:
        self._state = state

    def verify(self, context: RunContext, answer: FinalAnswer) -> VerificationResult:
        del context, answer
        if self._state.category is None:
            return VerificationResult(False, "no category was recorded by set_category")
        draft = (self._state.draft_reply or "").strip()
        if not draft:
            return VerificationResult(False, "no reply was drafted by draft_reply")
        return VerificationResult(
            True,
            f"lab state holds category {self._state.category} and a drafted reply",
        )
