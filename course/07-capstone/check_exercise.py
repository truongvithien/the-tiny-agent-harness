import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tiny_harness import (  # noqa: E402
    FunctionTool,
    PolicyDecision,
    Risk,
    ToolCall,
    ToolResult,
)


def _tool(name: str, risk: Risk) -> FunctionTool:
    return FunctionTool(
        name=name,
        description="Test action.",
        input_schema={"type": "object"},
        risk=risk,
        handler=lambda _: ToolResult(ok=True),
    )


def _refund(amount: object) -> ToolCall:
    return ToolCall("issue_refund", {"ticket_id": "T-1", "amount": amount})


CASES: tuple[tuple[str, FunctionTool, ToolCall, PolicyDecision], ...] = (
    (
        "a read tool is allowed",
        _tool("read_ticket", Risk.READ),
        ToolCall("read_ticket", {}),
        PolicyDecision.ALLOW,
    ),
    (
        "a write tool is allowed",
        _tool("set_category", Risk.WRITE),
        ToolCall("set_category", {}),
        PolicyDecision.ALLOW,
    ),
    (
        "a small refund needs approval",
        _tool("issue_refund", Risk.CONSEQUENTIAL),
        _refund(50),
        PolicyDecision.APPROVAL_REQUIRED,
    ),
    (
        "a refund exactly at the limit needs approval",
        _tool("issue_refund", Risk.CONSEQUENTIAL),
        _refund(100.0),
        PolicyDecision.APPROVAL_REQUIRED,
    ),
    (
        "a refund above the limit is denied",
        _tool("issue_refund", Risk.CONSEQUENTIAL),
        _refund(250.0),
        PolicyDecision.DENY,
    ),
    (
        "a negative refund is denied",
        _tool("issue_refund", Risk.CONSEQUENTIAL),
        _refund(-5.0),
        PolicyDecision.DENY,
    ),
    (
        "a missing amount is denied",
        _tool("issue_refund", Risk.CONSEQUENTIAL),
        ToolCall("issue_refund", {"ticket_id": "T-1"}),
        PolicyDecision.DENY,
    ),
    (
        "a non-numeric amount is denied",
        _tool("issue_refund", Risk.CONSEQUENTIAL),
        _refund("250"),
        PolicyDecision.DENY,
    ),
    (
        "another consequential tool still needs approval",
        _tool("send_reply", Risk.CONSEQUENTIAL),
        ToolCall("send_reply", {}),
        PolicyDecision.APPROVAL_REQUIRED,
    ),
)


class _MissingPolicy(Exception):
    pass


def load_policy(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("capstone_exercise", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load exercise: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy = getattr(module, "RefundPolicy", None)
    if policy is None:
        raise _MissingPolicy
    return policy()


def check(path: Path) -> bool:
    try:
        policy = load_policy(path)
    except _MissingPolicy:
        print("✗ exercise could not be loaded: missing class RefundPolicy")
        return False
    except Exception as error:
        print(f"✗ exercise could not be loaded: {type(error).__name__}")
        return False
    all_passed = True
    for label, tool, call, expected in CASES:
        try:
            actual = policy.evaluate(tool, call)
        except Exception as error:
            print(f"✗ {label}: {type(error).__name__}: {error}")
            all_passed = False
            continue
        if actual is expected:
            print(f"✓ {label}: {actual.value}")
        else:
            shown = actual.value if isinstance(actual, PolicyDecision) else repr(actual)
            print(f"✗ {label}: expected {expected.value}, got {shown}")
            all_passed = False
    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the capstone policy puzzle.")
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
        path = ROOT / base / "07-capstone" / "exercise.py"
    return 0 if check(path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
