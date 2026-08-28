from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

FIXTURE_REPO = Path(__file__).resolve().parent / "fixture_repo"
WORKSPACE_PREFIX = "tiny-harness-coding-"
COPY_IGNORED = ("__pycache__", "*.pyc")
SEARCH_RESULT_LIMIT = 50


class PathEscapesWorkspace(Exception):
    pass


def is_inside(workspace_root: Path | str, candidate: Path | str) -> bool:
    root = Path(workspace_root).resolve()
    target = Path(candidate)
    if not target.is_absolute():
        target = root / target
    return target.resolve().is_relative_to(root)


@dataclass(frozen=True)
class Edit:
    path: str
    previous_content: str | None


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._edits: list[Edit] = []

    @classmethod
    def from_fixture(cls, fixture: Path = FIXTURE_REPO) -> Workspace:
        root = Path(tempfile.mkdtemp(prefix=WORKSPACE_PREFIX))
        shutil.copytree(
            fixture,
            root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*COPY_IGNORED),
        )
        return cls(root)

    def __enter__(self) -> Workspace:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.cleanup()

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def resolve(self, candidate: Path | str) -> Path:
        if not is_inside(self.root, candidate):
            raise PathEscapesWorkspace(f"path escapes the workspace: {candidate}")
        target = Path(candidate)
        if not target.is_absolute():
            target = self.root / target
        return target.resolve()

    def relative(self, target: Path) -> str:
        return str(target.resolve().relative_to(self.root))

    def list_files(self, directory: Path | str = ".") -> tuple[str, ...]:
        base = self.resolve(directory)
        if not base.is_dir():
            raise NotADirectoryError(f"not a workspace directory: {directory}")
        return tuple(sorted(self.relative(found) for found in self._walk(base)))

    def read_file(self, path: Path | str) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"not a workspace file: {path}")
        return target.read_text(encoding="utf-8")

    def write_file(self, path: Path | str, content: str) -> str:
        target = self.resolve(path)
        previous = target.read_text(encoding="utf-8") if target.is_file() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        relative = self.relative(target)
        self._edits.append(Edit(relative, previous))
        return relative

    def search_text(
        self, pattern: str, limit: int = SEARCH_RESULT_LIMIT
    ) -> tuple[str, ...]:
        if not pattern:
            raise ValueError("search pattern must not be empty")
        matches: list[str] = []
        for found in sorted(self._walk(self.root)):
            try:
                text = found.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = self.relative(found)
            for number, line in enumerate(text.splitlines(), start=1):
                if pattern in line:
                    matches.append(f"{relative}:{number}: {line.strip()}")
                    if len(matches) == limit:
                        return tuple(matches)
        return tuple(matches)

    @property
    def edits(self) -> tuple[Edit, ...]:
        return tuple(self._edits)

    def revert_last(self) -> str | None:
        if not self._edits:
            return None
        edit = self._edits.pop()
        target = self.resolve(edit.path)
        if edit.previous_content is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(edit.previous_content, encoding="utf-8")
        return edit.path

    def revert_all(self) -> None:
        while self._edits:
            self.revert_last()

    def _walk(self, base: Path) -> list[Path]:
        return [
            found
            for found in base.rglob("*")
            if found.is_file()
            and not found.is_symlink()
            and "__pycache__" not in found.parts
        ]
