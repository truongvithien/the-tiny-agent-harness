import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tiny_harness.types import FinalAnswer, ModelDecision, ToolCall  # noqa: E402


def _tool_message(name: str, arguments: object) -> dict[str, Any]:
    return {
        "content": None,
        "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
    }


CASES: tuple[tuple[str, Mapping[str, Any], object], ...] = (
    (
        "tool call with JSON arguments",
        _tool_message("lookup", '{"key": "answer"}'),
        ToolCall("lookup", {"key": "answer"}),
    ),
    (
        "tool call without arguments",
        _tool_message("ping", ""),
        ToolCall("ping", {}),
    ),
    (
        "final answer text",
        {"content": "The value is 42.", "tool_calls": []},
        FinalAnswer("The value is 42."),
    ),
    (
        "tool call wins over accompanying text",
        {
            "content": "I will look it up.",
            "tool_calls": [{"function": {"name": "lookup", "arguments": "{}"}}],
        },
        ToolCall("lookup", {}),
    ),
    (
        "malformed JSON arguments are rejected",
        _tool_message("lookup", "{oops"),
        ValueError,
    ),
    (
        "arguments that are not an object are rejected",
        _tool_message("lookup", "[1, 2]"),
        ValueError,
    ),
    ("an empty message is rejected", {"content": "   "}, ValueError),
)


class _MissingDecode(Exception):
    pass


def load_decode(path: Path) -> Callable[[Mapping[str, Any]], ModelDecision]:
    spec = importlib.util.spec_from_file_location("openai_exercise", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load exercise: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    decode = getattr(module, "decode_decision", None)
    if not callable(decode):
        raise _MissingDecode
    return decode


def check(path: Path) -> bool:
    try:
        decode = load_decode(path)
    except _MissingDecode:
        print("✗ exercise could not be loaded: missing callable decode_decision")
        return False
    except Exception as error:
        print(f"✗ exercise could not be loaded: {type(error).__name__}")
        return False
    all_passed = True
    for label, message, expected in CASES:
        expects_error = isinstance(expected, type) and issubclass(expected, Exception)
        try:
            actual: object = decode(message)
        except Exception as error:
            if expects_error and isinstance(error, expected):
                print(f"✓ {label}: raised {type(error).__name__}")
            else:
                print(f"✗ {label}: {type(error).__name__}: {error}")
                all_passed = False
            continue
        if expects_error:
            print(f"✗ {label}: expected {expected.__name__}, got {actual!r}")
            all_passed = False
        elif actual == expected:
            print(f"✓ {label}: {actual!r}")
        else:
            print(f"✗ {label}: expected {expected!r}, got {actual!r}")
            all_passed = False
    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Lesson 6 adapter puzzle.")
    parser.add_argument(
        "--solution",
        action="store_true",
        help="check the reference solution instead of the learner exercise",
    )
    parser.add_argument(
        "--exercise",
        type=Path,
        default=None,
        help="check this file instead of the course or solution exercise",
    )
    arguments = parser.parse_args()
    if arguments.exercise is not None:
        path = arguments.exercise
    else:
        base = "solutions" if arguments.solution else "course"
        path = ROOT / base / "06-openai-integration" / "exercise.py"
    return 0 if check(path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
