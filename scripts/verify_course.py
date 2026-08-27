import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
CREDENTIAL = re.compile(r"sk-[A-Za-z0-9]{16,}")
FORBIDDEN_SUFFIXES = (".jsonl", ".env")
FORBIDDEN_PARTS = (".venv", "__pycache__", ".pytest_cache", ".traces")


def tracked_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [ROOT / name for name in listing.stdout.split("\0") if name]


def report(passed: bool, message: str) -> bool:
    print(f"{'✓' if passed else '✗'} {message}")
    return passed


def check_markdown_links(files: list[Path]) -> bool:
    broken: list[str] = []
    for path in (item for item in files if item.suffix == ".md"):
        for _text, target in LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = (path.parent / target.split("#")[0]).resolve()
            if not resolved.exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    for entry in broken:
        print(f"    broken link: {entry}")
    return report(not broken, f"relative Markdown links resolve ({len(broken)} broken)")


def check_course_parts(files: list[Path]) -> bool:
    parts = sorted(path.name for path in (ROOT / "course").iterdir() if path.is_dir())
    missing = [name for name in parts if not (ROOT / "course" / name / "README.md").exists()]
    for name in missing:
        print(f"    missing lesson: course/{name}/README.md")
    return report(
        not missing and len(parts) == 7,
        f"every course part has a lesson ({len(parts)} parts found)",
    )


def check_exercise_pairs() -> bool:
    problems: list[str] = []
    for exercise in sorted((ROOT / "course").glob("*/exercise.py")):
        part = exercise.parent.name
        if not (exercise.parent / "check_exercise.py").exists():
            problems.append(f"course/{part} has no check_exercise.py")
        if not (ROOT / "solutions" / part / "exercise.py").exists():
            problems.append(f"solutions/{part}/exercise.py is missing")
    for entry in problems:
        print(f"    {entry}")
    return report(not problems, "each exercise has a checker and a reference solution")


def check_course_map() -> bool:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    targets = {target for _text, target in LINK.findall(readme)}
    missing = [
        part.name
        for part in sorted((ROOT / "course").iterdir())
        if part.is_dir()
        and not any(part.name in target for target in targets)
    ]
    for name in missing:
        print(f"    README does not link course/{name}")
    return report(not missing, "the README course map links every part")


def check_repository_hygiene(files: list[Path]) -> bool:
    offenders: list[str] = []
    for path in files:
        relative = path.relative_to(ROOT)
        if path.suffix in FORBIDDEN_SUFFIXES or set(relative.parts) & set(FORBIDDEN_PARTS):
            offenders.append(str(relative))
    for entry in offenders:
        print(f"    should not be tracked: {entry}")
    return report(not offenders, "no traces, environments, or caches are tracked")


def check_no_credentials(files: list[Path]) -> bool:
    offenders: list[str] = []
    for path in files:
        if path.suffix in {".png", ".jpg", ".gif", ".ico"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if CREDENTIAL.search(content):
            offenders.append(str(path.relative_to(ROOT)))
    for entry in offenders:
        print(f"    possible credential in: {entry}")
    return report(not offenders, "no tracked file contains an API-key pattern")


def main() -> int:
    files = tracked_files()
    results = [
        check_course_parts(files),
        check_exercise_pairs(),
        check_course_map(),
        check_markdown_links(files),
        check_repository_hygiene(files),
        check_no_credentials(files),
    ]
    passed = all(results)
    print(f"\n{'all course checks passed' if passed else 'course checks failed'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
