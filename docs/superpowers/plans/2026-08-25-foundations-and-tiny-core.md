# Foundations and Tiny Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an offline, deterministic first course stage in which beginner Python programmers learn the agent/model boundary and build a tested observe-decide-authorize-execute-record-verify loop.

**Architecture:** A dependency-light `tiny_harness` package owns typed decisions, tools, policy, events, verification, and a single-action runner. A scripted model and a read-only local demonstration make every foundational run reproducible; course prose and a checked learner exercise teach the same interfaces without requiring an API key.

**Tech Stack:** Python 3.12, standard library, pytest 8, JSON Lines, Markdown

**Spec:** `docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md`

## Global Constraints

- Python 3.12 is the documented baseline.
- Standard-library features are preferred for the core and mock services.
- `pytest` provides tests and exercise checks.
- The official `openai` package is not introduced in this plan; it belongs to Part 6.
- Packaging follows a standard `pyproject.toml` layout.
- Setup uses `python -m venv` and `python -m pip`.
- Default demonstrations and tests require no network access or credentials.
- The runner executes at most one tool action per iteration.
- Prompt text can describe policy, but deterministic Python code enforces it.
- Failures and budget exhaustion can never be reported as success.
- Do not add multi-agent orchestration, vector storage, browser automation, deployment, or a UI.

## Planned file map

```text
README.md                                      course entry point and setup
pyproject.toml                                 package metadata and pytest settings
.gitignore                                     local environments, traces, and caches
tiny_harness/__init__.py                       public beginner-facing imports
tiny_harness/types.py                          shared immutable contracts
tiny_harness/models.py                         model adapter protocol and scripted model
tiny_harness/tools.py                          tool protocol, registry, and safe execution
tiny_harness/policy.py                         deterministic authorization decisions
tiny_harness/events.py                         in-memory and JSON Lines event sinks
tiny_harness/verification.py                   verification protocol and basic verifier
tiny_harness/runner.py                         bounded agent control loop
examples/foundations_demo.py                   deterministic completed demonstration
course/01-foundations/README.md                model-versus-harness theory lesson
course/01-foundations/exercises.md             responsibility-classification exercise
course/02-tiny-core/README.md                  guided core walkthrough
course/02-tiny-core/exercise.py                learner policy puzzle
course/02-tiny-core/check_exercise.py           standalone learner feedback command
solutions/02-tiny-core/exercise.py             explained reference implementation
tests/test_types.py                            contract tests
tests/test_tools.py                            registry and executor tests
tests/test_policy.py                           authorization tests
tests/test_events.py                           trace and redaction tests
tests/test_runner.py                           loop, limits, and terminal-state tests
tests/test_foundations_demo.py                 end-to-end deterministic scenario
tests/test_course_exercise.py                  learner exercise contract tests
```

---

### Task 1: Establish the runnable Python course skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `tiny_harness/__init__.py`
- Create: `tests/test_package.py`

**Interfaces:**
- Consumes: Python 3.12 and `python -m pip`.
- Produces: importable package `tiny_harness`; command `python -m pytest`.

- [ ] **Step 1: Write the failing package test**

```python
# tests/test_package.py
import tiny_harness


def test_package_exposes_a_version() -> None:
    assert tiny_harness.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify the package is absent**

Run: `python -m pytest tests/test_package.py -v`

Expected: FAIL during collection because `tiny_harness` or `__version__` does not exist.

- [ ] **Step 3: Add minimal packaging and package metadata**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "the-tiny-agent-harness"
version = "0.1.0"
description = "A beginner course for building a tiny, observable agent harness."
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8,<9"]

[tool.pytest.ini_options]
addopts = "-ra"
testpaths = ["tests"]
```

```python
# tiny_harness/__init__.py
"""Small, explicit building blocks for an educational agent harness."""

__version__ = "0.1.0"
```

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
*.egg-info/
dist/
build/
.env
*.jsonl
```

- [ ] **Step 4: Install the editable development package and run the test**

Run: `python -m pip install -e '.[dev]'`

Expected: installation succeeds.

Run: `python -m pytest tests/test_package.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the skeleton**

```bash
git add pyproject.toml .gitignore tiny_harness/__init__.py tests/test_package.py
git commit -m "build: add Python course skeleton"
```

### Task 2: Define the harness contracts

**Files:**
- Create: `tiny_harness/types.py`
- Create: `tests/test_types.py`
- Modify: `tiny_harness/__init__.py`

**Interfaces:**
- Consumes: only standard-library `dataclasses`, `enum`, and typing primitives.
- Produces: `Risk`, `PolicyDecision`, `RunStatus`, `ToolCall`, `FinalAnswer`, `ToolResult`, `Observation`, `RunContext`, `VerificationResult`, and `RunResult`.

- [ ] **Step 1: Write contract tests**

```python
# tests/test_types.py
from dataclasses import FrozenInstanceError

import pytest

from tiny_harness.types import Risk, RunContext, ToolCall, ToolResult


def test_tool_call_copies_mutable_arguments() -> None:
    raw = {"ticket_id": "T-1"}
    call = ToolCall(name="read_ticket", arguments=raw)
    raw["ticket_id"] = "changed"
    assert call.arguments == {"ticket_id": "T-1"}


def test_tool_result_requires_an_error_when_unsuccessful() -> None:
    with pytest.raises(ValueError, match="error"):
        ToolResult(ok=False)


def test_context_is_immutable_at_its_boundary() -> None:
    context = RunContext(task="inspect", acceptance_criteria=("evidence",))
    with pytest.raises(FrozenInstanceError):
        context.task = "changed"  # type: ignore[misc]


def test_risk_values_are_stable_for_serialization() -> None:
    assert [risk.value for risk in Risk] == ["read", "write", "consequential"]
```

- [ ] **Step 2: Run the contract tests and confirm they fail**

Run: `python -m pytest tests/test_types.py -v`

Expected: FAIL because `tiny_harness.types` does not exist.

- [ ] **Step 3: Implement immutable shared types**

```python
# tiny_harness/types.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class Risk(StrEnum):
    READ = "read"
    WRITE = "write"
    CONSEQUENTIAL = "consequential"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    APPROVAL_REFUSED = "approval_refused"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class FinalAnswer:
    text: str


type ModelDecision = ToolCall | FinalAnswer


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str = ""
    error: str | None = None
    retryable: bool = False

    def __post_init__(self) -> None:
        if not self.ok and not self.error:
            raise ValueError("an unsuccessful tool result requires an error")


@dataclass(frozen=True)
class Observation:
    source: str
    content: str


@dataclass(frozen=True)
class RunContext:
    task: str
    acceptance_criteria: tuple[str, ...]
    observations: tuple[Observation, ...] = ()
    remaining_iterations: int = 0


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    answer: str | None
    reason: str
    run_id: str
    event_count: int = field(default=0)
```

- [ ] **Step 4: Re-export the public contracts and run their tests**

Add explicit imports and `__all__` entries in `tiny_harness/__init__.py` for the types above while retaining `__version__`.

Run: `python -m pytest tests/test_types.py tests/test_package.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the contracts**

```bash
git add tiny_harness/types.py tiny_harness/__init__.py tests/test_types.py
git commit -m "feat: define harness contracts"
```

### Task 3: Add typed tools and safe execution

**Files:**
- Create: `tiny_harness/tools.py`
- Create: `tests/test_tools.py`
- Modify: `tiny_harness/__init__.py`

**Interfaces:**
- Consumes: `Risk`, `ToolCall`, and `ToolResult` from `tiny_harness.types`.
- Produces: `Tool` protocol, `FunctionTool`, `ToolRegistry.register(tool)`, `ToolRegistry.specifications()`, and `ToolRegistry.execute(call)`.

- [ ] **Step 1: Write registry and executor tests**

```python
# tests/test_tools.py
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
```

- [ ] **Step 2: Run tool tests and confirm they fail**

Run: `python -m pytest tests/test_tools.py -v`

Expected: FAIL because `tiny_harness.tools` does not exist.

- [ ] **Step 3: Implement the tool protocol, function adapter, and registry**

```python
# tiny_harness/tools.py
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
```

- [ ] **Step 4: Add duplicate-registration and ordinary-success tests, then run the file**

Add tests proving duplicate names raise `ValueError` and `echo` returns `ToolResult(ok=True, output="hello")`.

Run: `python -m pytest tests/test_tools.py -v`

Expected: PASS.

- [ ] **Step 5: Re-export tool interfaces and commit**

```bash
git add tiny_harness/tools.py tiny_harness/__init__.py tests/test_tools.py
git commit -m "feat: add typed tool registry"
```

### Task 4: Enforce deterministic policy and approval

**Files:**
- Create: `tiny_harness/policy.py`
- Create: `tests/test_policy.py`
- Modify: `tiny_harness/__init__.py`

**Interfaces:**
- Consumes: `Tool`, `ToolCall`, and `PolicyDecision`.
- Produces: `Policy` protocol, `RiskPolicy.evaluate(tool, call)`, `ApprovalCallback`, and `authorize(tool, call, policy, approval)`.

- [ ] **Step 1: Write policy tests for all three risk classes**

```python
# tests/test_policy.py
import pytest

from tiny_harness.policy import RiskPolicy, authorize
from tiny_harness.tools import FunctionTool
from tiny_harness.types import PolicyDecision, Risk, ToolCall, ToolResult


def tool(risk: Risk) -> FunctionTool:
    return FunctionTool(
        name="action",
        description="Test action.",
        input_schema={"type": "object"},
        risk=risk,
        handler=lambda _: ToolResult(ok=True),
    )


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        (Risk.READ, PolicyDecision.ALLOW),
        (Risk.WRITE, PolicyDecision.ALLOW),
        (Risk.CONSEQUENTIAL, PolicyDecision.APPROVAL_REQUIRED),
    ],
)
def test_risk_policy_classifies_actions(risk: Risk, expected: PolicyDecision) -> None:
    assert RiskPolicy().evaluate(tool(risk), ToolCall("action", {})) is expected


def test_authorize_denies_consequential_action_when_approval_is_refused() -> None:
    decision = authorize(
        tool(Risk.CONSEQUENTIAL),
        ToolCall("action", {}),
        RiskPolicy(),
        approval=lambda _tool, _call: False,
    )
    assert decision is PolicyDecision.DENY
```

- [ ] **Step 2: Run policy tests and confirm they fail**

Run: `python -m pytest tests/test_policy.py -v`

Expected: FAIL because `tiny_harness.policy` does not exist.

- [ ] **Step 3: Implement policy as code, independent of prompts**

```python
# tiny_harness/policy.py
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias

from tiny_harness.tools import Tool
from tiny_harness.types import PolicyDecision, Risk, ToolCall


class Policy(Protocol):
    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision: ...


ApprovalCallback: TypeAlias = Callable[[Tool, ToolCall], bool]


class RiskPolicy:
    def evaluate(self, tool: Tool, call: ToolCall) -> PolicyDecision:
        del call
        if tool.risk is Risk.CONSEQUENTIAL:
            return PolicyDecision.APPROVAL_REQUIRED
        return PolicyDecision.ALLOW


def authorize(
    tool: Tool,
    call: ToolCall,
    policy: Policy,
    approval: ApprovalCallback,
) -> PolicyDecision:
    decision = policy.evaluate(tool, call)
    if decision is PolicyDecision.APPROVAL_REQUIRED:
        return PolicyDecision.ALLOW if approval(tool, call) else PolicyDecision.DENY
    return decision
```

- [ ] **Step 4: Test approval acceptance and run policy tests**

Add a test where the callback returns `True` and assert `PolicyDecision.ALLOW`.

Run: `python -m pytest tests/test_policy.py -v`

Expected: PASS.

- [ ] **Step 5: Re-export policy interfaces and commit**

```bash
git add tiny_harness/policy.py tiny_harness/__init__.py tests/test_policy.py
git commit -m "feat: enforce tool risk policy"
```

### Task 5: Record inspectable and redacted event traces

**Files:**
- Create: `tiny_harness/events.py`
- Create: `tests/test_events.py`
- Modify: `tiny_harness/__init__.py`

**Interfaces:**
- Consumes: JSON-serializable event payloads.
- Produces: immutable `Event`, `EventSink` protocol, `MemoryEventSink.record(kind, payload)`, `JsonlEventSink.record(kind, payload)`, `.count`, and `.events` for the memory sink.

- [ ] **Step 1: Write event-order, truncation, redaction, and persistence tests**

```python
# tests/test_events.py
import json

from tiny_harness.events import JsonlEventSink, MemoryEventSink


def test_memory_sink_assigns_monotonic_sequence_numbers() -> None:
    sink = MemoryEventSink(run_id="run-1")
    sink.record("run_started", {"task": "demo"})
    sink.record("run_finished", {"status": "succeeded"})
    assert [event.sequence for event in sink.events] == [1, 2]


def test_sink_redacts_secrets_and_truncates_long_strings() -> None:
    sink = MemoryEventSink(run_id="run-1", secrets=("secret-value",), max_string_length=8)
    sink.record("tool_result", {"token": "secret-value", "output": "abcdefghijk"})
    assert sink.events[0].payload == {"token": "[REDACTED]", "output": "abcdefgh…[TRUNCATED]"}


def test_jsonl_sink_writes_one_json_object_per_event(tmp_path) -> None:
    path = tmp_path / "trace.jsonl"
    sink = JsonlEventSink(path=path, run_id="run-1")
    sink.record("run_started", {"task": "demo"})
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["kind"] == "run_started"
    assert rows[0]["run_id"] == "run-1"
```

- [ ] **Step 2: Run event tests and confirm they fail**

Run: `python -m pytest tests/test_events.py -v`

Expected: FAIL because `tiny_harness.events` does not exist.

- [ ] **Step 3: Implement event normalization and the memory sink**

Implement `Event` as a frozen dataclass with `sequence`, ISO-8601 UTC `timestamp`, `run_id`, `kind`, and a copied payload. Add a private recursive normalizer that:

```python
def normalize(value: object, secrets: tuple[str, ...], limit: int) -> object:
    if isinstance(value, str):
        cleaned = value
        for secret in secrets:
            cleaned = cleaned.replace(secret, "[REDACTED]")
        return cleaned if len(cleaned) <= limit else cleaned[:limit] + "…[TRUNCATED]"
    if isinstance(value, dict):
        return {str(key): normalize(item, secrets, limit) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item, secrets, limit) for item in value]
    return value
```

`MemoryEventSink.record()` increments the sequence, normalizes the payload, creates the event, stores it, and returns it.

- [ ] **Step 4: Implement JSON Lines persistence and run event tests**

`JsonlEventSink` composes a `MemoryEventSink`, creates the parent directory, and appends `json.dumps(dataclasses.asdict(event), sort_keys=True) + "\n"` using UTF-8 after every record.

Run: `python -m pytest tests/test_events.py -v`

Expected: PASS.

- [ ] **Step 5: Re-export event interfaces and commit**

```bash
git add tiny_harness/events.py tiny_harness/__init__.py tests/test_events.py
git commit -m "feat: add inspectable event traces"
```

### Task 6: Build the bounded single-action runner

**Files:**
- Create: `tiny_harness/models.py`
- Create: `tiny_harness/verification.py`
- Create: `tiny_harness/runner.py`
- Create: `tests/test_runner.py`
- Modify: `tiny_harness/__init__.py`

**Interfaces:**
- Consumes: all contracts, `ToolRegistry`, `Policy`, approval callback, and `EventSink`.
- Produces: `ModelAdapter.next_decision(context, tool_specs)`, `ScriptedModel`, `Verifier.verify(context, answer)`, `AcceptFinalAnswer`, `RunConfig`, and `Runner.run(task, acceptance_criteria)`.

- [ ] **Step 1: Write a successful two-iteration runner test**

```python
# tests/test_runner.py
from tiny_harness.events import MemoryEventSink
from tiny_harness.models import ScriptedModel
from tiny_harness.policy import RiskPolicy
from tiny_harness.runner import RunConfig, Runner
from tiny_harness.tools import FunctionTool, ToolRegistry
from tiny_harness.types import FinalAnswer, Risk, RunStatus, ToolCall, ToolResult
from tiny_harness.verification import AcceptFinalAnswer


def test_runner_executes_one_tool_then_verifies_final_answer() -> None:
    events = MemoryEventSink(run_id="run-1")
    runner = Runner(
        model=ScriptedModel(
            [ToolCall("lookup", {"key": "answer"}), FinalAnswer("The value is 42.")]
        ),
        tools=ToolRegistry(
            [
                FunctionTool(
                    name="lookup",
                    description="Read a value.",
                    input_schema={"type": "object"},
                    risk=Risk.READ,
                    handler=lambda _: ToolResult(ok=True, output="42"),
                )
            ]
        ),
        policy=RiskPolicy(),
        approval=lambda _tool, _call: False,
        events=events,
        verifier=AcceptFinalAnswer(),
        config=RunConfig(max_iterations=4, timeout_seconds=5),
    )
    result = runner.run("Find the value", ("State the retrieved value",))
    assert result.status is RunStatus.SUCCEEDED
    assert result.answer == "The value is 42."
    assert [event.kind for event in events.events] == [
        "run_started",
        "model_decision",
        "policy_decision",
        "tool_result",
        "model_decision",
        "verification",
        "run_finished",
    ]
```

- [ ] **Step 2: Add failing tests for refusal, exhaustion, and false completion**

Add tests asserting:

- a refused consequential call returns `RunStatus.APPROVAL_REFUSED` without invoking its handler;
- a model that never returns a final answer stops at exactly `max_iterations` with `RunStatus.BUDGET_EXHAUSTED`;
- `VerificationResult(accepted=False, reason="missing evidence")` returns `RunStatus.FAILED`, never success; and
- an unknown tool produces a `tool_result` event and can be observed by the next model iteration.

Run: `python -m pytest tests/test_runner.py -v`

Expected: FAIL because the model, verification, and runner modules do not exist.

- [ ] **Step 3: Implement the model and verifier boundaries**

```python
# tiny_harness/models.py
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
```

```python
# tiny_harness/verification.py
from typing import Protocol

from tiny_harness.types import FinalAnswer, RunContext, VerificationResult


class Verifier(Protocol):
    def verify(self, context: RunContext, answer: FinalAnswer) -> VerificationResult: ...


class AcceptFinalAnswer:
    def verify(self, context: RunContext, answer: FinalAnswer) -> VerificationResult:
        del context
        if not answer.text.strip():
            return VerificationResult(False, "final answer is empty")
        return VerificationResult(True, "a non-empty final answer was supplied")
```

- [ ] **Step 4: Implement the runner state machine**

Create frozen `RunConfig(max_iterations: int = 8, timeout_seconds: float = 30.0, retry_limit: int = 2)` and validate positive values. In `Runner.run`:

```python
deadline = monotonic() + self.config.timeout_seconds
observations: tuple[Observation, ...] = ()
self.events.record("run_started", {"task": task, "acceptance_criteria": acceptance_criteria})
for iteration in range(1, self.config.max_iterations + 1):
    if monotonic() >= deadline:
        return self._finish(RunStatus.BUDGET_EXHAUSTED, None, "time budget exhausted")
    context = RunContext(task, acceptance_criteria, observations, self.config.max_iterations - iteration)
    decision = self.model.next_decision(context, self.tools.specifications())
    self.events.record("model_decision", serialize_decision(decision))
    if isinstance(decision, FinalAnswer):
        verification = self.verifier.verify(context, decision)
        self.events.record("verification", dataclasses.asdict(verification))
        status = RunStatus.SUCCEEDED if verification.accepted else RunStatus.FAILED
        return self._finish(status, decision.text if verification.accepted else None, verification.reason)
    tool = self.tools.get(decision.name)
    if tool is None:
        result = self.tools.execute(decision)
    else:
        policy_decision = authorize(tool, decision, self.policy, self.approval)
        self.events.record("policy_decision", {"tool": decision.name, "decision": policy_decision.value})
        if policy_decision is PolicyDecision.DENY:
            return self._finish(RunStatus.APPROVAL_REFUSED, None, "approval refused")
        result = self.tools.execute(decision)
    self.events.record("tool_result", serialize_tool_result(decision, result))
    observations += (Observation(source=decision.name, content=result.output if result.ok else result.error or "error"),)
return self._finish(RunStatus.BUDGET_EXHAUSTED, None, "iteration budget exhausted")
```

Add focused private serialization helpers and `_finish`, which always records `run_finished` and returns `RunResult` with `event_count=self.events.count`. Catch model exceptions at the model boundary, emit `model_error`, and return `RunStatus.FAILED`. Count equivalent retryable failures by `(tool name, error)` and fail once the count exceeds `retry_limit`.

- [ ] **Step 5: Run runner tests and the full suite**

Run: `python -m pytest tests/test_runner.py -v`

Expected: PASS.

Run: `python -m pytest -v`

Expected: PASS.

- [ ] **Step 6: Re-export runtime interfaces and commit**

```bash
git add tiny_harness tests/test_runner.py
git commit -m "feat: add bounded agent runner"
```

### Task 7: Publish a deterministic completed demonstration

**Files:**
- Create: `examples/foundations_demo.py`
- Create: `tests/test_foundations_demo.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the public `tiny_harness` API from Tasks 2-6.
- Produces: `examples.foundations_demo.build_demo(trace_path)` and CLI command `python -m examples.foundations_demo`.

- [ ] **Step 1: Write the end-to-end demonstration test**

```python
# tests/test_foundations_demo.py
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
```

- [ ] **Step 2: Run the demonstration test and confirm it fails**

Run: `python -m pytest tests/test_foundations_demo.py -v`

Expected: FAIL because the example does not exist.

- [ ] **Step 3: Implement the local demonstration**

Define one read-only `lookup_habitat` tool backed by an in-memory mapping, a `ScriptedModel` with exactly one tool call and one final answer, a `JsonlEventSink`, and a `run_demo(trace_path: Path) -> RunResult`. The CLI writes to `.traces/foundations.jsonl`, prints the final status and answer, and prints the trace path.

Use this scripted sequence:

```python
[
    ToolCall("lookup_habitat", {"animal": "fox"}),
    FinalAnswer("The habitat guide says foxes are omnivores."),
]
```

Add `.traces/` to `.gitignore`.

- [ ] **Step 4: Run the scenario and inspect its trace**

Run: `python -m pytest tests/test_foundations_demo.py -v`

Expected: PASS.

Run: `python -m examples.foundations_demo`

Expected: prints `succeeded`, the fox answer, and `.traces/foundations.jsonl`.

Run: `python -c 'import json; print([json.loads(line)["kind"] for line in open(".traces/foundations.jsonl")])'`

Expected: the seven event kinds asserted in the test.

- [ ] **Step 5: Commit the demonstration**

```bash
git add .gitignore examples/foundations_demo.py tests/test_foundations_demo.py
git commit -m "feat: add deterministic foundations demo"
```

### Task 8: Create Parts 1 and 2 with a checked policy puzzle

**Files:**
- Create: `course/01-foundations/README.md`
- Create: `course/01-foundations/exercises.md`
- Create: `course/02-tiny-core/README.md`
- Create: `course/02-tiny-core/exercise.py`
- Create: `course/02-tiny-core/check_exercise.py`
- Create: `solutions/02-tiny-core/exercise.py`
- Create: `tests/test_course_exercise.py`

**Interfaces:**
- Consumes: `Risk`, `PolicyDecision`, `Tool`, and `ToolCall`.
- Produces: learner function `decide(risk: Risk) -> PolicyDecision`; standalone checker runnable from the repository root.

- [ ] **Step 1: Write the learner-exercise contract test**

```python
# tests/test_course_exercise.py
import importlib.util
from pathlib import Path

import pytest

from tiny_harness.types import PolicyDecision, Risk


def load_decide(path: Path):
    spec = importlib.util.spec_from_file_location("course_exercise", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decide


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        (Risk.READ, PolicyDecision.ALLOW),
        (Risk.WRITE, PolicyDecision.ALLOW),
        (Risk.CONSEQUENTIAL, PolicyDecision.APPROVAL_REQUIRED),
    ],
)
@pytest.mark.learner
def test_learner_policy_contract(risk: Risk, expected: PolicyDecision) -> None:
    decide = load_decide(Path("course/02-tiny-core/exercise.py"))
    assert decide(risk) is expected
```

Keep the path loader in the test because hyphenated course directories are not import packages; do not add a runtime abstraction solely for test imports.

- [ ] **Step 2: Create a deliberately incomplete learner function and confirm the check fails**

```python
# course/02-tiny-core/exercise.py
from tiny_harness.types import PolicyDecision, Risk


def decide(risk: Risk) -> PolicyDecision:
    """Return the policy decision appropriate for a tool risk."""
    raise NotImplementedError("complete the three risk decisions from Lesson 2")
```

Run: `python -m pytest tests/test_course_exercise.py -v`

Expected: FAIL with the learner-facing `NotImplementedError` message. This test is excluded from the default suite using a `learner` marker so a fresh clone still has a green contributor suite; the standalone checker includes it explicitly.

- [ ] **Step 3: Add the standalone checker and reference solution**

`course/02-tiny-core/check_exercise.py` imports the learner file by path, evaluates all three risks, prints one checkmark or cross per case, and exits with status 1 unless all cases pass.

```python
# solutions/02-tiny-core/exercise.py
from tiny_harness.types import PolicyDecision, Risk


def decide(risk: Risk) -> PolicyDecision:
    if risk is Risk.CONSEQUENTIAL:
        return PolicyDecision.APPROVAL_REQUIRED
    return PolicyDecision.ALLOW
```

Add a separate test that loads the solution and proves it satisfies all three cases.

- [ ] **Step 4: Write the two lessons and exercises**

`course/01-foundations/README.md` must define model, agent, harness, tool, policy, state, event trace, verifier, and evaluation; show the six-stage control loop; explain why effects belong to the harness; and link to `examples/foundations_demo.py` with exact run and trace-inspection commands.

`course/01-foundations/exercises.md` must present at least eight responsibility-classification prompts, followed by a collapsed answer section explaining each model-versus-harness choice.

`course/02-tiny-core/README.md` must walk through each core file in execution order, explain the three risk classes, link each event to its producing boundary, and instruct learners to run:

```bash
python course/02-tiny-core/check_exercise.py
```

It must give three progressive hints without displaying the final function before linking to `solutions/02-tiny-core/exercise.py`.

- [ ] **Step 5: Verify both learner and contributor experiences**

Run: `python course/02-tiny-core/check_exercise.py`

Expected before solving: three readable failures and exit status 1.

Run the checker against the solution using its documented `--solution` flag.

Expected: three passes and exit status 0.

Run: `python -m pytest -m 'not learner' -v`

Expected: PASS.

- [ ] **Step 6: Commit Parts 1 and 2**

```bash
git add course solutions tests/test_course_exercise.py pyproject.toml
git commit -m "docs: add foundations and tiny core lessons"
```

### Task 9: Finish the course entry point and foundation quality gate

**Files:**
- Create: `README.md`
- Modify: `pyproject.toml`
- Modify: files found by the checks below only when required to make documented commands accurate.

**Interfaces:**
- Consumes: all foundation/core files and commands from Tasks 1-8.
- Produces: a beginner setup path from clone to first successful demonstration and exercise.

- [ ] **Step 1: Write the top-level README**

Include:

- a two-sentence definition and course promise;
- an explicit statement that coding agents are one harness application;
- prerequisites and Python 3.12 setup commands for POSIX shells and PowerShell;
- a seven-part course map, marking Parts 3-7 as upcoming until their plans land;
- the exact foundations demonstration command;
- the exact Part 2 exercise-check command;
- a brief repository map;
- the distinction between offline deterministic lessons and the later optional OpenAI lesson;
- a warning never to commit API keys; and
- links to the design spec, Part 1, and Part 2.

- [ ] **Step 2: Add strict pytest marker configuration**

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-ra --strict-markers -m 'not learner and not live'"
testpaths = ["tests"]
markers = [
  "learner: intentionally incomplete learner exercise contract",
  "live: opt-in tests that require external services",
]
```

Ensure the incomplete learner test has `@pytest.mark.learner` and the solution-contract test remains in the default suite. A learner can override the configured selection with `python -m pytest -m learner tests/test_course_exercise.py -v`.

- [ ] **Step 3: Verify every documented command from a clean environment**

Create a temporary virtual environment outside the repository and run, in order:

```bash
python -m pip install -e '.[dev]'
python -m pytest -m 'not learner and not live' -v
python -m examples.foundations_demo
python course/02-tiny-core/check_exercise.py --solution
```

Expected: installation succeeds; default tests pass; the demo succeeds and writes a seven-event trace; the solution checker reports three passes.

- [ ] **Step 4: Inspect repository hygiene and documentation links**

Run: `git status --short --ignored`

Expected: `.venv`, caches, build metadata, and `.traces` are ignored; no trace or credential file is tracked.

Run a small standard-library link checker from the repository root that extracts relative Markdown links from `README.md` and the two lesson READMEs and asserts every referenced path exists. If this check reveals a bad link, correct the link rather than adding a permanent dependency.

- [ ] **Step 5: Commit the foundation milestone**

```bash
git add README.md pyproject.toml course tiny_harness examples solutions tests .gitignore
git commit -m "docs: publish foundations course milestone"
```

- [ ] **Step 6: Record the next-plan boundaries**

After this plan passes, write separate plans in this order:

1. `support-triage-lab` — synthetic ticket store, policy knowledge base, approval puzzle.
2. `research-lab` — local HTTP documents, citations, uncertainty, and context limits.
3. `coding-lab` — temporary fixture repository, scoped files, command allow-list, and verification.
4. `openai-integration` — official SDK adapter, deterministic contract tests, and one opt-in live run.
5. `capstone-and-course-qa` — extension rubric, cross-platform verification, and complete course navigation.

Each subsequent plan must read the committed interfaces produced here and retain an offline green default suite.
