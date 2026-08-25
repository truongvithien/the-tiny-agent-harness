from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from tiny_harness.types import Risk, ToolCall, ToolResult


class Tool(Protocol):
    name: str
    description: str
    input_schema: Mapping[str, Any]
    risk: Risk

    def invoke(self, arguments: Mapping[str, Any]) -> ToolResult: ...


@dataclass(frozen=True)
class FunctionTool:
    name: str
    description: str
    input_schema: Mapping[str, Any]
    risk: Risk
    handler: Callable[[Mapping[str, Any]], ToolResult]

    def invoke(self, arguments: Mapping[str, Any]) -> ToolResult:
        return self.handler(arguments)


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specifications(self) -> list[dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in self._tools.values()
        ]

    def execute(self, call: ToolCall) -> ToolResult:
        tool = self.get(call.name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool: {call.name}")
        try:
            return tool.invoke(call.arguments)
        except Exception as error:
            return ToolResult(ok=False, error=f"tool {call.name} failed: {type(error).__name__}")
