from labs.support_triage.tools import ALLOWED_CATEGORIES
from tiny_harness.types import PolicyDecision, Risk


def decide(risk: Risk, category: str | None, draft: str | None) -> PolicyDecision:
    """Return the decision for one triage tool call, given the evidence so far."""
    raise NotImplementedError("complete the evidence-aware approval gate from Lesson 3")
