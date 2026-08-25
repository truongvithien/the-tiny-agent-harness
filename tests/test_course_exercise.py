import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

from tiny_harness.types import PolicyDecision, Risk


def load_decide(path: Path) -> Callable[[Risk], PolicyDecision]:
    spec = importlib.util.spec_from_file_location("course_exercise", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decide


def load_checker() -> ModuleType:
    path = Path("course/02-tiny-core/check_exercise.py")
    spec = importlib.util.spec_from_file_location("course_exercise_checker", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        (Risk.READ, PolicyDecision.ALLOW),
        (Risk.WRITE, PolicyDecision.ALLOW),
        (Risk.CONSEQUENTIAL, PolicyDecision.APPROVAL_REQUIRED),
    ],
)
@pytest.mark.learner
def test_learner_policy_contract(risk: Risk, expected: PolicyDecision) -> None:
    decide = load_decide(Path("course/02-tiny-core/exercise.py"))
    assert decide(risk) is expected


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        (Risk.READ, PolicyDecision.ALLOW),
        (Risk.WRITE, PolicyDecision.ALLOW),
        (Risk.CONSEQUENTIAL, PolicyDecision.APPROVAL_REQUIRED),
    ],
)
def test_reference_solution_satisfies_policy_contract(
    risk: Risk, expected: PolicyDecision
) -> None:
    decide = load_decide(Path("solutions/02-tiny-core/exercise.py"))
    assert decide(risk) is expected


@pytest.mark.learner
def test_checker_reports_all_incomplete_learner_cases(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(
        """\
from tiny_harness.types import PolicyDecision, Risk

def decide(risk: Risk) -> PolicyDecision:
    raise NotImplementedError("complete the three risk decisions from Lesson 2")
""",
        encoding="utf-8",
    )

    assert load_checker().check(exercise) is False
    assert capsys.readouterr().out.splitlines() == [
        "✗ read: NotImplementedError: complete the three risk decisions from Lesson 2",
        "✗ write: NotImplementedError: complete the three risk decisions from Lesson 2",
        "✗ consequential: NotImplementedError: complete the three risk decisions from Lesson 2",
    ]


@pytest.mark.parametrize(
    ("source", "expected_message"),
    [
        ("def decide(:\n", "✗ exercise could not be loaded: SyntaxError"),
        (
            "import module_that_does_not_exist_for_the_course\n",
            "✗ exercise could not be loaded: ModuleNotFoundError",
        ),
        ("VALUE = 1\n", "✗ exercise could not be loaded: missing callable decide"),
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
        [sys.executable, "course/02-tiny-core/check_exercise.py", "--solution"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "✓ read: allow",
        "✓ write: allow",
        "✓ consequential: approval_required",
    ]
