from typing import Protocol

from tiny_harness.types import FinalAnswer, RunContext, VerificationResult


class Verifier(Protocol):
    def verify(self, context: RunContext, answer: FinalAnswer) -> VerificationResult: ...


class AcceptFinalAnswer:
    def verify(self, context: RunContext, answer: FinalAnswer) -> VerificationResult:
        del context
        if not answer.text.strip():
            return VerificationResult(False, "final answer is empty")
        return VerificationResult(True, "a non-empty final answer was supplied")
