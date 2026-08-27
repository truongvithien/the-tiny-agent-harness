import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "pyproject.toml"


def run_pytest(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(CONFIG), str(path), "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_default_pytest_selection_skips_learner_and_live_tests(tmp_path: Path) -> None:
    test_file = tmp_path / "test_markers.py"
    test_file.write_text(
        """\
import pytest

def test_offline_default():
    pass

@pytest.mark.learner
def test_learner_opt_in():
    pass

@pytest.mark.live
def test_live_opt_in():
    pass
""",
        encoding="utf-8",
    )

    result = run_pytest(test_file)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 2 deselected" in result.stdout


def test_pytest_rejects_unregistered_markers(tmp_path: Path) -> None:
    test_file = tmp_path / "test_unknown_marker.py"
    test_file.write_text(
        """\
import pytest

@pytest.mark.unregistered_course_marker
def test_unknown_marker():
    pass
""",
        encoding="utf-8",
    )

    result = run_pytest(test_file)

    assert result.returncode != 0
    assert "not found in `markers` configuration option" in result.stdout
