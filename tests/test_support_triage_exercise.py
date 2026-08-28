import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

from tiny_harness.types import PolicyDecision, Risk

Decide = Callable[[Risk, str | None, str | None], PolicyDecision]

DRAFT = "You were charged twice for invoice INV-7781; the duplicate is refunded."

CONTRACT = [
    (Risk.READ, None, None, PolicyDecision.ALLOW),
    (Risk.WRITE, None, None, PolicyDecision.ALLOW),
    (Risk.CONSEQUENTIAL, "billing", DRAFT, PolicyDecision.APPROVAL_REQUIRED),
    (Risk.CONSEQUENTIAL, None, DRAFT, PolicyDecision.DENY),
    (Risk.CONSEQUENTIAL, "refund_now", DRAFT, PolicyDecision.DENY),
    (Risk.CONSEQUENTIAL, "billing", "   ", PolicyDecision.DENY),
    (Risk.CONSEQUENTIAL, "billing", None, PolicyDecision.DENY),
]

EXPECTED_SOLUTION_OUTPUT = [
    "✓ read without evidence: allow",
    "✓ write without evidence: allow",
    "✓ consequential with a category and a draft: approval_required",
    "✓ consequential without a category: deny",
    "✓ consequential with an unknown category: deny",
    "✓ consequential with a blank draft: deny",
    "✓ consequential without a draft: deny",
]


def load_decide(path: Path) -> Decide:
    spec = importlib.util.spec_from_file_location("triage_exercise", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decide


def load_checker() -> ModuleType:
    path = Path("course/03-support-triage/check_exercise.py")
    spec = importlib.util.spec_from_file_location("triage_exercise_checker", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("risk", "category", "draft", "expected"), CONTRACT)
@pytest.mark.learner
def test_learner_approval_gate_contract(
    risk: Risk, category: str | None, draft: str | None, expected: PolicyDecision
) -> None:
    decide = load_decide(Path("course/03-support-triage/exercise.py"))

    assert decide(risk, category, draft) is expected


@pytest.mark.parametrize(("risk", "category", "draft", "expected"), CONTRACT)
def test_reference_solution_satisfies_approval_gate_contract(
    risk: Risk, category: str | None, draft: str | None, expected: PolicyDecision
) -> None:
    decide = load_decide(Path("solutions/03-support-triage/exercise.py"))

    assert decide(risk, category, draft) is expected


@pytest.mark.learner
def test_checker_reports_every_incomplete_learner_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(
        """\
from tiny_harness.types import PolicyDecision, Risk

def decide(risk, category, draft) -> PolicyDecision:
    raise NotImplementedError("complete the evidence-aware approval gate from Lesson 3")
""",
        encoding="utf-8",
    )

    assert load_checker().check(exercise) is False
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(CONTRACT)
    assert all(
        line.endswith(
            "NotImplementedError: complete the evidence-aware approval gate from Lesson 3"
        )
        for line in lines
    )


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


def test_checker_reports_a_wrong_decision_readably(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(
        """\
from tiny_harness.types import PolicyDecision, Risk

def decide(risk, category, draft) -> PolicyDecision:
    return PolicyDecision.ALLOW
""",
        encoding="utf-8",
    )

    assert load_checker().check(exercise) is False
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "✓ read without evidence: allow"
    assert lines[2] == (
        "✗ consequential with a category and a draft: "
        "expected approval_required, got allow"
    )


def test_checker_accepts_the_reference_solution() -> None:
    result = subprocess.run(
        [sys.executable, "course/03-support-triage/check_exercise.py", "--solution"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == EXPECTED_SOLUTION_OUTPUT


def test_checker_rejects_the_incomplete_learner_exercise() -> None:
    result = subprocess.run(
        [sys.executable, "course/03-support-triage/check_exercise.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert len(result.stdout.splitlines()) == len(CONTRACT)
    assert "NotImplementedError" in result.stdout
