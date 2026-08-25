from tiny_harness.types import PolicyDecision, Risk


def decide(risk: Risk) -> PolicyDecision:
    if risk is Risk.CONSEQUENTIAL:
        return PolicyDecision.APPROVAL_REQUIRED
    return PolicyDecision.ALLOW
