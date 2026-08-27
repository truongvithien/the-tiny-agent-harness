from typing import cast

from tiny_harness.tools import FunctionTool, ToolRegistry
from tiny_harness.types import Risk, ToolCall, ToolResult


def make_echo() -> FunctionTool:
    return FunctionTool(
        name="echo",
        description="Return supplied text.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        risk=Risk.READ,
        handler=lambda arguments: ToolResult(ok=True, output=str(arguments["text"])),
    )


def test_registry_lists_model_visible_specifications() -> None:
    registry = ToolRegistry([make_echo()])
    assert registry.specifications() == [
        {
            "name": "echo",
            "description": "Return supplied text.",
            "input_schema": make_echo().input_schema,
        }
    ]


def test_execute_returns_typed_unknown_tool_failure() -> None:
    result = ToolRegistry().execute(ToolCall("missing", {}))
    assert result == ToolResult(ok=False, error="unknown tool: missing")


def test_execute_converts_handler_exception_to_safe_failure() -> None:
    broken = FunctionTool(
        name="broken",
        description="Fail safely.",
        input_schema={"type": "object"},
        risk=Risk.READ,
        handler=lambda _: 1 / 0,  # type: ignore[arg-type,return-value]
    )
    result = ToolRegistry([broken]).execute(ToolCall("broken", {}))
    assert not result.ok
    assert result.error == "tool broken failed: ZeroDivisionError"


def test_registry_rejects_duplicate_tool_names() -> None:
    registry = ToolRegistry([make_echo()])
    try:
        registry.register(make_echo())
    except ValueError as error:
        assert str(error) == "duplicate tool: echo"
    else:
        raise AssertionError("duplicate registration should fail")


def test_execute_returns_handler_result() -> None:
    result = ToolRegistry([make_echo()]).execute(ToolCall("echo", {"text": "hello"}))
    assert result == ToolResult(ok=True, output="hello")


def test_execute_converts_malformed_handler_result_to_safe_failure() -> None:
    malformed = FunctionTool(
        name="malformed",
        description="Return the wrong runtime type.",
        input_schema={"type": "object"},
        risk=Risk.READ,
        handler=lambda _arguments: cast(ToolResult, "not a ToolResult"),
    )

    result = ToolRegistry([malformed]).execute(ToolCall("malformed", {}))

    assert result == ToolResult(
        ok=False,
        error="tool malformed returned an invalid result",
    )
