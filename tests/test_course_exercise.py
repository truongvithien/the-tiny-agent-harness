import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

from tiny_harness.types import PolicyDecision, Risk


def load_decide(path: Path) -> Callable[[Risk], PolicyDecision]:
    spec = importlib.util.spec_from_file_location("course_exercise", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decide


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
def test_checker_reports_all_incomplete_learner_cases() -> None:
    result = subprocess.run(
        [sys.executable, "course/02-tiny-core/check_exercise.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "✗ read: NotImplementedError: complete the three risk decisions from Lesson 2",
        "✗ write: NotImplementedError: complete the three risk decisions from Lesson 2",
        "✗ consequential: NotImplementedError: complete the three risk decisions from Lesson 2",
    ]


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
