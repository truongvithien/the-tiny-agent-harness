import os

import pytest

from tiny_harness import (
    AcceptFinalAnswer,
    FunctionTool,
    MemoryEventSink,
    Risk,
    RiskPolicy,
    RunConfig,
    Runner,
    RunStatus,
    ToolRegistry,
    ToolResult,
)
from tiny_harness.openai_adapter import OpenAIModel, client_from_environment

LIVE_MODEL = os.environ.get("TINY_HARNESS_LIVE_MODEL", "gpt-4o-mini")

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY is not set",
    ),
]


def test_live_model_completes_a_bounded_tool_run() -> None:
    events = MemoryEventSink(run_id="openai-live")
    runner = Runner(
        model=OpenAIModel(client=client_from_environment(), model=LIVE_MODEL),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="lookup_launch_year",
                    description="Return the launch year of the named mission.",
                    input_schema={
                        "type": "object",
                        "properties": {"mission": {"type": "string"}},
                        "required": ["mission"],
                        "additionalProperties": False,
                    },
                    risk=Risk.READ,
                    handler=lambda _: ToolResult(ok=True, output="1977"),
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=4, timeout_seconds=60.0),
    )

    result = runner.run(
        "Use the tool to find the launch year of Voyager 1, then state it.",
        ("State the launch year returned by the tool",),
    )

    assert result.status is RunStatus.SUCCEEDED
    kinds = [event.kind for event in events.events]
    assert "tool_result" in kinds
    assert kinds[0] == "run_started"
    assert kinds[-1] == "run_finished"
