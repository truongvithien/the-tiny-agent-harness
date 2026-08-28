from pathlib import Path


def is_inside(workspace_root: Path | str, candidate: Path | str) -> bool:
    """Compare fully resolved paths so traversal and symlinks cannot escape."""
    root = Path(workspace_root).resolve()
    target = Path(candidate)
    if not target.is_absolute():
        target = root / target
    return target.resolve().is_relative_to(root)
