import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARTS = (
    "01-foundations",
    "02-tiny-core",
    "03-support-triage",
    "04-research-agent",
    "05-coding-agent",
    "06-openai-integration",
    "07-capstone",
)


def test_the_course_verification_script_passes() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_course.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_every_documented_part_exists_in_order() -> None:
    found = sorted(path.name for path in (ROOT / "course").iterdir() if path.is_dir())

    assert found == sorted(PARTS)


@pytest.mark.parametrize(("part", "following"), list(zip(PARTS, PARTS[1:])))
def test_each_lesson_links_to_the_next(part: str, following: str) -> None:
    lesson = (ROOT / "course" / part / "README.md").read_text(encoding="utf-8")

    assert f"../{following}/README.md" in lesson


@pytest.mark.parametrize("part", PARTS[1:])
def test_every_part_after_the_first_has_a_checked_exercise(part: str) -> None:
    assert (ROOT / "course" / part / "exercise.py").is_file()
    assert (ROOT / "course" / part / "check_exercise.py").is_file()
    assert (ROOT / "solutions" / part / "exercise.py").is_file()


def test_the_readme_documents_every_laboratory_demonstration() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for module in (
        "examples.foundations_demo",
        "labs.support_triage.demo",
        "labs.research.demo",
        "labs.coding.demo",
    ):
        assert module in readme
