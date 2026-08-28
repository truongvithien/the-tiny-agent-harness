import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

LEARNER_EXERCISE = Path("course/05-coding-agent/exercise.py")
REFERENCE_SOLUTION = Path("solutions/05-coding-agent/exercise.py")
CHECKER = Path("course/05-coding-agent/check_exercise.py")
EXPECTED_SOLUTION_OUTPUT = [
    "✓ workspace file: accepted",
    "✓ workspace root: accepted",
    "✓ parent traversal: rejected",
    "✓ nested traversal: rejected",
    "✓ absolute path outside: rejected",
    "✓ sibling with a shared prefix: rejected",
    "✓ symlink to outside: rejected",
]
UNIMPLEMENTED_EXERCISE = """\
from pathlib import Path


def is_inside(workspace_root: Path | str, candidate: Path | str) -> bool:
    raise NotImplementedError("complete the containment check from Lesson 5")
"""

NAIVE_PREFIX_EXERCISE = """\
from pathlib import Path


def is_inside(workspace_root, candidate) -> bool:
    root = Path(workspace_root).resolve()
    target = Path(candidate)
    if not target.is_absolute():
        target = root / target
    return str(target.resolve()).startswith(str(root))
"""


def load_is_inside(path: Path) -> Callable[[Path | str, Path | str], bool]:
    spec = importlib.util.spec_from_file_location("coding_exercise", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.is_inside


def load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("coding_exercise_checker", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def containment_cases(tmp_path: Path) -> list[tuple[Path, str, bool]]:
    workspace = tmp_path / "ws"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "module.py").write_text("", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    sibling = tmp_path / "ws-evil"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret", encoding="utf-8")
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    return [
        (workspace, "src/module.py", True),
        (workspace, ".", True),
        (workspace, "../outside/secret.txt", False),
        (workspace, "src/../../outside/secret.txt", False),
        (workspace, str(outside / "secret.txt"), False),
        (workspace, str(sibling / "secret.txt"), False),
        (workspace, "escape/secret.txt", False),
    ]


@pytest.mark.learner
def test_learner_containment_contract(tmp_path: Path) -> None:
    is_inside = load_is_inside(LEARNER_EXERCISE)

    for root, candidate, expected in containment_cases(tmp_path):
        assert is_inside(root, candidate) is expected


def test_reference_solution_satisfies_containment_contract(tmp_path: Path) -> None:
    is_inside = load_is_inside(REFERENCE_SOLUTION)

    for root, candidate, expected in containment_cases(tmp_path):
        assert is_inside(root, candidate) is expected


def test_checker_reports_every_unimplemented_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(UNIMPLEMENTED_EXERCISE, encoding="utf-8")

    assert load_checker().check(exercise) is False
    printed = capsys.readouterr().out.splitlines()
    assert len(printed) == len(EXPECTED_SOLUTION_OUTPUT)
    assert all(
        line.startswith("✗")
        and line.endswith(
            "NotImplementedError: complete the containment check from Lesson 5"
        )
        for line in printed
    )


def test_checker_rejects_a_string_prefix_implementation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(NAIVE_PREFIX_EXERCISE, encoding="utf-8")

    assert load_checker().check(exercise) is False
    assert capsys.readouterr().out.splitlines() == [
        "✓ workspace file: accepted",
        "✓ workspace root: accepted",
        "✓ parent traversal: rejected",
        "✓ nested traversal: rejected",
        "✓ absolute path outside: rejected",
        "✗ sibling with a shared prefix: expected rejected, got accepted",
        "✓ symlink to outside: rejected",
    ]


def test_checker_rejects_a_non_boolean_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(
        "def is_inside(workspace_root, candidate):\n    return 'yes'\n",
        encoding="utf-8",
    )

    assert load_checker().check(exercise) is False
    assert capsys.readouterr().out.splitlines()[0] == (
        "✗ workspace file: expected accepted, got 'yes'"
    )


@pytest.mark.parametrize(
    ("source", "expected_message"),
    [
        ("def is_inside(:\n", "✗ exercise could not be loaded: SyntaxError"),
        (
            "import module_that_does_not_exist_for_the_course\n",
            "✗ exercise could not be loaded: ModuleNotFoundError",
        ),
        ("VALUE = 1\n", "✗ exercise could not be loaded: missing callable is_inside"),
    ],
)
def test_checker_reports_module_load_failures_without_a_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    source: str,
    expected_message: str,
) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(source, encoding="utf-8")

    assert load_checker().check(exercise) is False
    assert capsys.readouterr().out.splitlines() == [expected_message]


def test_checker_accepts_reference_solution() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--solution"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == EXPECTED_SOLUTION_OUTPUT


def test_checker_cli_rejects_an_unimplemented_exercise(tmp_path: Path) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(UNIMPLEMENTED_EXERCISE, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(CHECKER), "--exercise", str(exercise)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1


def test_checker_leaves_no_temporary_directory_behind(tmp_path: Path) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(NAIVE_PREFIX_EXERCISE, encoding="utf-8")
    checker = load_checker()

    checker.check(exercise)

    assert not list(Path(tempfile.gettempdir()).glob("tiny-harness-check-*"))
