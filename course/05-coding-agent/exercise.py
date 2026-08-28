from pathlib import Path


def is_inside(workspace_root: Path | str, candidate: Path | str) -> bool:
    """Return True only when candidate is the workspace root or a path inside it."""
    raise NotImplementedError("complete the containment check from Lesson 5")
