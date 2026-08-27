from collections.abc import Sequence

from labs.research.tools import Claim


def unsupported_source_ids(
    claims: Sequence[Claim],
    fetched_source_ids: Sequence[str],
) -> tuple[str, ...]:
    """Report each missing citation once, in the order the claims raised it."""
    fetched = set(fetched_source_ids)
    missing: list[str] = []
    for claim in claims:
        if claim.source_id not in fetched and claim.source_id not in missing:
            missing.append(claim.source_id)
    return tuple(missing)
