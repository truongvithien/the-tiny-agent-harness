import importlib.util
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

from labs.research.tools import Claim

SURVEY = "marsh-survey-2024"
ATLAS = "regional-bird-atlas"
GHOST = "ghost-source"

CASES = (
    ((), (SURVEY,), ()),
    ((Claim("128 nesting pairs were counted.", SURVEY),), (SURVEY,), ()),
    ((Claim("The colony is growing.", GHOST),), (SURVEY,), (GHOST,)),
    (
        (
            Claim("The colony is growing.", GHOST),
            Claim("128 nesting pairs were counted.", SURVEY),
            Claim("The colony is the largest in the county.", GHOST),
        ),
        (SURVEY, ATLAS),
        (GHOST,),
    ),
    (
        (
            Claim("The colony is growing.", GHOST),
            Claim("128 nesting pairs were counted.", SURVEY),
        ),
        (),
        (GHOST, SURVEY),
    ),
)

INCOMPLETE_EXERCISE = """\
from collections.abc import Sequence

from labs.research.tools import Claim


def unsupported_source_ids(
    claims: Sequence[Claim],
    fetched_source_ids: Sequence[str],
) -> tuple[str, ...]:
    raise NotImplementedError("complete the evidence check from Lesson 4")
"""


def load_check(
    path: Path,
) -> Callable[[Sequence[Claim], Sequence[str]], tuple[str, ...]]:
    spec = importlib.util.spec_from_file_location("research_exercise", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.unsupported_source_ids


def load_checker() -> ModuleType:
    path = Path("course/04-research-agent/check_exercise.py")
    spec = importlib.util.spec_from_file_location("research_exercise_checker", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("claims", "fetched", "expected"), CASES)
@pytest.mark.learner
def test_learner_evidence_contract(
    claims: tuple[Claim, ...],
    fetched: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    unsupported = load_check(Path("course/04-research-agent/exercise.py"))

    assert unsupported(claims, fetched) == expected


@pytest.mark.parametrize(("claims", "fetched", "expected"), CASES)
def test_reference_solution_satisfies_evidence_contract(
    claims: tuple[Claim, ...],
    fetched: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    unsupported = load_check(Path("solutions/04-research-agent/exercise.py"))

    assert unsupported(claims, fetched) == expected


@pytest.mark.learner
def test_checker_reports_all_incomplete_learner_cases(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exercise = tmp_path / "exercise.py"
    exercise.write_text(INCOMPLETE_EXERCISE, encoding="utf-8")

    assert load_checker().check(exercise) is False
    assert capsys.readouterr().out.splitlines() == [
        "✗ no claims: NotImplementedError: complete the evidence check from Lesson 4",
        "✗ cited source was fetched: NotImplementedError: complete the evidence check"
        " from Lesson 4",
        "✗ cited source was never fetched: NotImplementedError: complete the evidence"
        " check from Lesson 4",
        "✗ one missing citation is reported once: NotImplementedError: complete the"
        " evidence check from Lesson 4",
        "✗ nothing was fetched at all: NotImplementedError: complete the evidence"
        " check from Lesson 4",
    ]


@pytest.mark.parametrize(
    ("source", "expected_message"),
    [
        (
            "def unsupported_source_ids(:\n",
            "✗ exercise could not be loaded: SyntaxError",
        ),
        (
            "import module_that_does_not_exist_for_the_course\n",
            "✗ exercise could not be loaded: ModuleNotFoundError",
        ),
        (
            "VALUE = 1\n",
            "✗ exercise could not be loaded: missing callable unsupported_source_ids",
        ),
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


def test_checker_formats_source_id_lists_for_the_learner() -> None:
    module = load_checker()

    assert module.format_ids(()) == "(none)"
    assert module.format_ids(("a", "b")) == "a, b"


def test_checker_accepts_reference_solution() -> None:
    result = subprocess.run(
        [sys.executable, "course/04-research-agent/check_exercise.py", "--solution"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "✓ no claims: (none)",
        "✓ cited source was fetched: (none)",
        "✓ cited source was never fetched: ghost-source",
        "✓ one missing citation is reported once: ghost-source",
        "✓ nothing was fetched at all: ghost-source, marsh-survey-2024",
    ]


def test_checker_rejects_the_incomplete_learner_exercise() -> None:
    result = subprocess.run(
        [sys.executable, "course/04-research-agent/check_exercise.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert all(line.startswith("✗") for line in result.stdout.splitlines())
