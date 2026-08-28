import argparse
import importlib.util
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class Case:
    label: str
    root: Path
    candidate: str
    expected: bool


class _MissingIsInside(Exception):
    pass


def build_cases(base: Path) -> tuple[Case, ...]:
    workspace = base / "ws"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "module.py").write_text("", encoding="utf-8")
    outside = base / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    sibling = base / "ws-evil"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret", encoding="utf-8")
    cases = [
        Case("workspace file", workspace, "src/module.py", True),
        Case("workspace root", workspace, ".", True),
        Case("parent traversal", workspace, "../outside/secret.txt", False),
        Case("nested traversal", workspace, "src/../../outside/secret.txt", False),
        Case("absolute path outside", workspace, str(outside / "secret.txt"), False),
        Case(
            "sibling with a shared prefix",
            workspace,
            str(sibling / "secret.txt"),
            False,
        ),
    ]
    try:
        (workspace / "escape").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        print("⚠ symlink to outside: skipped, this system cannot create symlinks")
    else:
        cases.append(Case("symlink to outside", workspace, "escape/secret.txt", False))
    return tuple(cases)


def load_is_inside(path: Path) -> Callable[[Path | str, Path | str], bool]:
    spec = importlib.util.spec_from_file_location("containment_exercise", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load exercise: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    is_inside = getattr(module, "is_inside", None)
    if not callable(is_inside):
        raise _MissingIsInside
    return is_inside


def verdict(accepted: bool) -> str:
    return "accepted" if accepted else "rejected"


def check(path: Path) -> bool:
    try:
        is_inside = load_is_inside(path)
    except _MissingIsInside:
        print("✗ exercise could not be loaded: missing callable is_inside")
        return False
    except Exception as error:
        print(f"✗ exercise could not be loaded: {type(error).__name__}")
        return False
    all_passed = True
    with tempfile.TemporaryDirectory(prefix="tiny-harness-check-") as directory:
        for case in build_cases(Path(directory)):
            try:
                actual = is_inside(case.root, case.candidate)
            except Exception as error:
                print(f"✗ {case.label}: {type(error).__name__}: {error}")
                all_passed = False
                continue
            if actual is case.expected:
                print(f"✓ {case.label}: {verdict(case.expected)}")
            else:
                shown = verdict(actual) if type(actual) is bool else repr(actual)
                print(
                    f"✗ {case.label}: expected {verdict(case.expected)}, got {shown}"
                )
                all_passed = False
    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Lesson 5 scope puzzle.")
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
        path = ROOT / base / "05-coding-agent" / "exercise.py"
    return 0 if check(path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
