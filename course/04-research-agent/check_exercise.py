import argparse
import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from labs.research.tools import Claim  # noqa: E402


SURVEY = "marsh-survey-2024"
ATLAS = "regional-bird-atlas"
GHOST = "ghost-source"

CASES: tuple[tuple[str, tuple[Claim, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    ("no claims", (), (SURVEY,), ()),
    (
        "cited source was fetched",
        (Claim("128 nesting pairs were counted.", SURVEY),),
        (SURVEY,),
        (),
    ),
    (
        "cited source was never fetched",
        (Claim("The colony is growing.", GHOST),),
        (SURVEY,),
        (GHOST,),
    ),
    (
        "one missing citation is reported once",
        (
            Claim("The colony is growing.", GHOST),
            Claim("128 nesting pairs were counted.", SURVEY),
            Claim("The colony is the largest in the county.", GHOST),
        ),
        (SURVEY, ATLAS),
        (GHOST,),
    ),
    (
        "nothing was fetched at all",
        (
            Claim("The colony is growing.", GHOST),
            Claim("128 nesting pairs were counted.", SURVEY),
        ),
        (),
        (GHOST, SURVEY),
    ),
)


class _MissingCheck(Exception):
    pass


def format_ids(source_ids: Sequence[str]) -> str:
    return ", ".join(source_ids) if source_ids else "(none)"


def load_check(
    path: Path,
) -> Callable[[Sequence[Claim], Sequence[str]], tuple[str, ...]]:
    spec = importlib.util.spec_from_file_location("evidence_exercise", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load exercise: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    check = getattr(module, "unsupported_source_ids", None)
    if not callable(check):
        raise _MissingCheck
    return check


def check(path: Path) -> bool:
    try:
        unsupported = load_check(path)
    except _MissingCheck:
        print("✗ exercise could not be loaded: missing callable unsupported_source_ids")
        return False
    except Exception as error:
        print(f"✗ exercise could not be loaded: {type(error).__name__}")
        return False
    all_passed = True
    for label, claims, fetched, expected in CASES:
        try:
            actual = unsupported(claims, fetched)
        except Exception as error:
            print(f"✗ {label}: {type(error).__name__}: {error}")
            all_passed = False
            continue
        if isinstance(actual, tuple) and actual == expected:
            print(f"✓ {label}: {format_ids(actual)}")
            continue
        shown = format_ids(actual) if isinstance(actual, tuple) else repr(actual)
        print(f"✗ {label}: expected {format_ids(expected)}, got {shown}")
        all_passed = False
    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Lesson 4 evidence puzzle.")
    parser.add_argument(
        "--solution",
        action="store_true",
        help="check the reference solution instead of the learner exercise",
    )
    arguments = parser.parse_args()
    base = "solutions" if arguments.solution else "course"
    path = ROOT / base / "04-research-agent" / "exercise.py"
    return 0 if check(path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
