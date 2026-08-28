from labs.support_triage.tools import ALLOWED_CATEGORIES
from tiny_harness.types import PolicyDecision, Risk


def decide(risk: Risk, category: str | None, draft: str | None) -> PolicyDecision:
    """Ask a person only about a consequential action whose evidence already exists."""
    if risk is not Risk.CONSEQUENTIAL:
        return PolicyDecision.ALLOW
    if category not in ALLOWED_CATEGORIES:
        return PolicyDecision.DENY
    if draft is None or not draft.strip():
        return PolicyDecision.DENY
    return PolicyDecision.APPROVAL_REQUIRED
