from __future__ import annotations

from collections.abc import Sequence

from tiny_harness import FinalAnswer, RunContext, VerificationResult

from labs.research.tools import Claim, ResearchNotebook


def unsupported_source_ids(
    claims: Sequence[Claim],
    fetched_source_ids: Sequence[str],
) -> tuple[str, ...]:
    fetched = set(fetched_source_ids)
    missing: list[str] = []
    for claim in claims:
        if claim.source_id not in fetched and claim.source_id not in missing:
            missing.append(claim.source_id)
    return tuple(missing)


class CitedClaims:
    def __init__(self, notebook: ResearchNotebook) -> None:
        self._notebook = notebook

    def verify(self, context: RunContext, answer: FinalAnswer) -> VerificationResult:
        del context
        claims = self._notebook.claims
        if not claims:
            return VerificationResult(
                False,
                "no claim was recorded, so the report carries no captured evidence",
            )
        missing = unsupported_source_ids(claims, self._notebook.fetched_source_ids)
        if missing:
            return VerificationResult(
                False,
                "claims cite sources that were never fetched in this run: "
                + ", ".join(missing),
            )
        hidden: list[str] = []
        required: list[str] = []
        for claim in claims:
            conflicts = self._notebook.conflicting_fetched_sources(claim.source_id)
            if conflicts and not claim.disputed:
                hidden.append(
                    f"{claim.source_id} (contradicted by {', '.join(conflicts)})"
                )
            for source_id in (claim.source_id, *conflicts):
                if source_id not in required:
                    required.append(source_id)
        if hidden:
            return VerificationResult(
                False,
                "claims contradicted by another fetched source were not recorded "
                "as disputed: " + "; ".join(hidden),
            )
        uncited = [source_id for source_id in required if source_id not in answer.text]
        if uncited:
            return VerificationResult(
                False,
                "the report does not name every source behind its claims: "
                + ", ".join(uncited),
            )
        disputed = sum(1 for claim in claims if claim.disputed)
        return VerificationResult(
            True,
            f"{len(claims)} recorded claims cite fetched sources, "
            f"{disputed} of them marked disputed",
        )
