from pathlib import Path
from typing import Any, Mapping

from tiny_harness import (
    AcceptFinalAnswer,
    FinalAnswer,
    FunctionTool,
    JsonlEventSink,
    Risk,
    RiskPolicy,
    RunConfig,
    RunResult,
    Runner,
    ScriptedModel,
    ToolCall,
    ToolRegistry,
    ToolResult,
)


def build_demo(trace_path: Path) -> Runner:
    habitats = {"fox": "Foxes are omnivores."}

    def lookup_habitat(arguments: Mapping[str, Any]) -> ToolResult:
        return ToolResult(ok=True, output=habitats[str(arguments["animal"])])

    tool = FunctionTool(
        name="lookup_habitat",
        description="Look up an animal's habitat guide entry.",
        input_schema={
            "type": "object",
            "properties": {"animal": {"type": "string"}},
            "required": ["animal"],
            "additionalProperties": False,
        },
        risk=Risk.READ,
        handler=lookup_habitat,
    )
    return Runner(
        model=ScriptedModel(
            [
                ToolCall("lookup_habitat", {"animal": "fox"}),
                FinalAnswer("The habitat guide says foxes are omnivores."),
            ]
        ),
        tools=ToolRegistry([tool]),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=JsonlEventSink(trace_path, run_id="foundations-demo"),
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=2),
    )


def run_demo(trace_path: Path) -> RunResult:
    trace_path.unlink(missing_ok=True)
    return build_demo(trace_path).run(
        "Use the habitat guide to answer the question.",
        ("State whether foxes are omnivores.",),
    )


def main() -> None:
    trace_path = Path(".traces/foundations.jsonl")
    result = run_demo(trace_path)
    print(result.status.value)
    print(result.answer)
    print(trace_path)


if __name__ == "__main__":
    main()
