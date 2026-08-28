import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tiny_harness.types import PolicyDecision, Risk  # noqa: E402


CASES = (
    (Risk.READ, PolicyDecision.ALLOW),
    (Risk.WRITE, PolicyDecision.ALLOW),
    (Risk.CONSEQUENTIAL, PolicyDecision.APPROVAL_REQUIRED),
)


class _MissingDecide(Exception):
    pass


def load_decide(path: Path) -> Callable[[Risk], PolicyDecision]:
    spec = importlib.util.spec_from_file_location("policy_exercise", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load exercise: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    decide = getattr(module, "decide", None)
    if not callable(decide):
        raise _MissingDecide
    return decide


def check(path: Path) -> bool:
    try:
        decide = load_decide(path)
    except _MissingDecide:
        print("✗ exercise could not be loaded: missing callable decide")
        return False
    except Exception as error:
        print(f"✗ exercise could not be loaded: {type(error).__name__}")
        return False
    all_passed = True
    for risk, expected in CASES:
        try:
            actual = decide(risk)
        except Exception as error:
            print(f"✗ {risk.value}: {type(error).__name__}: {error}")
            all_passed = False
            continue
        if actual is expected:
            print(f"✓ {risk.value}: {actual.value}")
        else:
            shown = actual.value if isinstance(actual, PolicyDecision) else repr(actual)
            print(f"✗ {risk.value}: expected {expected.value}, got {shown}")
            all_passed = False
    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Lesson 2 policy puzzle.")
    parser.add_argument(
        "--solution",
        action="store_true",
        help="check the reference solution instead of the learner exercise",
    )
    parser.add_argument(
        "--exercise",
        type=Path,
        default=None,
        help="check this file instead of the course or solution exercise",
    )
    arguments = parser.parse_args()
    if arguments.exercise is not None:
        path = arguments.exercise
    else:
        base = "solutions" if arguments.solution else "course"
        path = ROOT / base / "02-tiny-core" / "exercise.py"
    return 0 if check(path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
