import json

from examples.foundations_demo import run_demo
from tiny_harness.types import RunStatus


def test_foundations_demo_is_offline_and_inspectable(tmp_path) -> None:
    trace = tmp_path / "foundations.jsonl"

    result = run_demo(trace)

    assert result.status is RunStatus.SUCCEEDED
    assert result.answer == "The habitat guide says foxes are omnivores."
    kinds = [json.loads(line)["kind"] for line in trace.read_text().splitlines()]
    assert kinds == [
        "run_started",
        "model_decision",
        "policy_decision",
        "tool_result",
        "model_decision",
        "verification",
        "run_finished",
    ]
