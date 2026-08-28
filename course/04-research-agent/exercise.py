from collections.abc import Sequence

from labs.research.tools import Claim


def unsupported_source_ids(
    claims: Sequence[Claim],
    fetched_source_ids: Sequence[str],
) -> tuple[str, ...]:
    """Return the cited source ids that were never fetched in this run."""
    raise NotImplementedError("complete the evidence check from Lesson 4")
