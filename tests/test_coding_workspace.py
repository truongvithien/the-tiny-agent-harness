import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from labs.coding.workspace import (
    FIXTURE_REPO,
    WORKSPACE_PREFIX,
    PathEscapesWorkspace,
    Workspace,
    is_inside,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SOURCE = FIXTURE_REPO / "wordcount.py"
REPLACEMENT_SOURCE = "def count_words(text):\n    return 0\n"


@pytest.fixture
def workspace() -> Iterator[Workspace]:
    created = Workspace.from_fixture()
    try:
        yield created
    finally:
        created.cleanup()


def temporary_workspaces() -> list[Path]:
    return sorted(Path(tempfile.gettempdir()).glob(f"{WORKSPACE_PREFIX}*"))


def test_workspace_is_a_temporary_copy_outside_the_repository(
    workspace: Workspace,
) -> None:
    temporary_root = Path(tempfile.gettempdir()).resolve()

    assert workspace.root.is_relative_to(temporary_root)
    assert not workspace.root.is_relative_to(REPO_ROOT)
    assert workspace.root != REPO_ROOT
    assert workspace.list_files() == (
        "README.md",
        "test_wordcount.py",
        "wordcount.py",
    )


@pytest.mark.parametrize(
    "candidate",
    [
        "../../etc/passwd",
        "..",
        "a/../../..",
        "a/../../../etc/passwd",
        "wordcount.py/../../escaped.py",
    ],
)
def test_parent_traversal_is_rejected(workspace: Workspace, candidate: str) -> None:
    assert is_inside(workspace.root, candidate) is False

    with pytest.raises(PathEscapesWorkspace, match="escapes the workspace"):
        workspace.resolve(candidate)


@pytest.mark.parametrize(
    "candidate",
    [
        "/etc/passwd",
        "/",
        str(REPO_ROOT / "README.md"),
        str(FIXTURE_SOURCE),
    ],
)
def test_absolute_path_outside_the_workspace_is_rejected(
    workspace: Workspace, candidate: str
) -> None:
    assert is_inside(workspace.root, candidate) is False

    with pytest.raises(PathEscapesWorkspace, match="escapes the workspace"):
        workspace.resolve(candidate)


def test_symlink_pointing_outside_the_workspace_is_rejected(
    workspace: Workspace, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    (workspace.root / "escape").symlink_to(outside, target_is_directory=True)

    assert (workspace.root / "escape" / "secret.txt").read_text() == "secret"
    assert is_inside(workspace.root, "escape/secret.txt") is False
    assert is_inside(workspace.root, "escape") is False
    with pytest.raises(PathEscapesWorkspace, match="escapes the workspace"):
        workspace.read_file("escape/secret.txt")
    assert "escape/secret.txt" not in workspace.list_files()


def test_symlinked_file_inside_the_workspace_is_rejected_when_it_targets_outside(
    workspace: Workspace, tmp_path: Path
) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    (workspace.root / "linked.txt").symlink_to(secret)

    assert is_inside(workspace.root, "linked.txt") is False
    with pytest.raises(PathEscapesWorkspace, match="escapes the workspace"):
        workspace.write_file("linked.txt", "overwritten")
    assert secret.read_text(encoding="utf-8") == "secret"


def test_sibling_directory_with_a_shared_string_prefix_is_rejected(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "ws").resolve()
    root.mkdir()
    sibling = (tmp_path / "ws-evil").resolve()
    sibling.mkdir()
    secret = sibling / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    workspace = Workspace(root)

    assert str(secret).startswith(str(root))
    assert is_inside(root, secret) is False
    with pytest.raises(PathEscapesWorkspace, match="escapes the workspace"):
        workspace.resolve(secret)


@pytest.mark.parametrize(
    "candidate",
    [".", "wordcount.py", "./wordcount.py", "src/../wordcount.py", "new/nested.py"],
)
def test_paths_inside_the_workspace_are_accepted(
    workspace: Workspace, candidate: str
) -> None:
    assert is_inside(workspace.root, candidate) is True
    assert workspace.resolve(candidate).is_relative_to(workspace.root)


def test_write_lands_in_the_copy_and_leaves_the_repository_unchanged(
    workspace: Workspace,
) -> None:
    fixture_before = FIXTURE_SOURCE.read_text(encoding="utf-8")
    fixture_mtime_before = FIXTURE_SOURCE.stat().st_mtime_ns

    written = workspace.write_file("wordcount.py", REPLACEMENT_SOURCE)

    assert written == "wordcount.py"
    assert workspace.read_file("wordcount.py") == REPLACEMENT_SOURCE
    assert FIXTURE_SOURCE.read_text(encoding="utf-8") == fixture_before
    assert FIXTURE_SOURCE.stat().st_mtime_ns == fixture_mtime_before


def test_edits_are_reversible(workspace: Workspace) -> None:
    original = workspace.read_file("wordcount.py")
    workspace.write_file("wordcount.py", "broken\n")
    workspace.write_file("added.py", "new\n")

    assert [edit.path for edit in workspace.edits] == ["wordcount.py", "added.py"]
    assert workspace.revert_last() == "added.py"
    assert not (workspace.root / "added.py").exists()
    assert workspace.revert_last() == "wordcount.py"
    assert workspace.read_file("wordcount.py") == original
    assert workspace.revert_last() is None


def contents(workspace: Workspace) -> dict[str, str]:
    return {name: workspace.read_file(name) for name in workspace.list_files()}


def test_revert_all_restores_every_edit(workspace: Workspace) -> None:
    before = contents(workspace)
    workspace.write_file("wordcount.py", "broken\n")
    workspace.write_file("added.py", "new\n")

    workspace.revert_all()

    assert workspace.edits == ()
    assert contents(workspace) == before


def test_cleanup_removes_the_temporary_workspace() -> None:
    created = Workspace.from_fixture()
    root = created.root

    created.cleanup()

    assert not root.exists()
    assert root not in temporary_workspaces()


def test_context_manager_cleans_up_after_a_failure() -> None:
    root: Path | None = None

    with pytest.raises(RuntimeError, match="scripted failure"):
        with Workspace.from_fixture() as created:
            root = created.root
            raise RuntimeError("scripted failure")

    assert root is not None
    assert not root.exists()


def test_search_text_reports_matching_lines(workspace: Workspace) -> None:
    matches = workspace.search_text("text.split")

    assert matches == ('wordcount.py:2: return len(text.split(" "))',)
    assert workspace.search_text("no-such-token") == ()


def test_search_text_rejects_an_empty_pattern(workspace: Workspace) -> None:
    with pytest.raises(ValueError, match="pattern"):
        workspace.search_text("")


def test_read_file_reports_a_missing_workspace_file(workspace: Workspace) -> None:
    with pytest.raises(FileNotFoundError, match="not a workspace file"):
        workspace.read_file("absent.py")


def test_list_files_reports_a_path_that_is_not_a_directory(
    workspace: Workspace,
) -> None:
    with pytest.raises(NotADirectoryError, match="not a workspace directory"):
        workspace.list_files("wordcount.py")


def test_fixture_copy_excludes_bytecode_caches(workspace: Workspace) -> None:
    assert not any("__pycache__" in name for name in workspace.list_files())
