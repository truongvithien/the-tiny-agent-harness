from tiny_harness.types import PolicyDecision, Risk


def decide(risk: Risk) -> PolicyDecision:
    """Require approval only when an action is difficult to reverse or external."""
    if risk is Risk.CONSEQUENTIAL:
        return PolicyDecision.APPROVAL_REQUIRED
    return PolicyDecision.ALLOW
