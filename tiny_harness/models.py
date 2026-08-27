from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol

from tiny_harness.types import ModelDecision, RunContext


class ModelAdapter(Protocol):
    def next_decision(
        self, context: RunContext, tool_specs: Sequence[Mapping[str, Any]]
    ) -> ModelDecision: ...


class ScriptedModel:
    def __init__(self, decisions: Iterable[ModelDecision]) -> None:
        self._decisions = iter(decisions)

    def next_decision(
        self, context: RunContext, tool_specs: Sequence[Mapping[str, Any]]
    ) -> ModelDecision:
        del context, tool_specs
        try:
            return next(self._decisions)
        except StopIteration as error:
            raise RuntimeError("scripted model has no remaining decisions") from error
