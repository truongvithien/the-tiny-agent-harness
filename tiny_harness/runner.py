from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from time import monotonic

from tiny_harness.events import EventSink
from tiny_harness.models import ModelAdapter
from tiny_harness.policy import ApprovalCallback, Policy, authorize
from tiny_harness.tools import ToolRegistry
from tiny_harness.types import (
    FinalAnswer,
    Observation,
    PolicyDecision,
    RunContext,
    RunResult,
    RunStatus,
    ToolCall,
    ToolResult,
)
from tiny_harness.verification import Verifier


@dataclass(frozen=True)
class RunConfig:
    max_iterations: int = 8
    timeout_seconds: float = 30.0
    retry_limit: int = 2

    def __post_init__(self) -> None:
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry_limit <= 0:
            raise ValueError("retry_limit must be positive")


class Runner:
    def __init__(
        self,
        *,
        model: ModelAdapter,
        tools: ToolRegistry,
        policy: Policy,
        approval: ApprovalCallback,
        events: EventSink,
        verifier: Verifier,
        config: RunConfig = RunConfig(),
    ) -> None:
        self.model = model
        self.tools = tools
        self.policy = policy
        self.approval = approval
        self.events = events
        self.verifier = verifier
        self.config = config

    def run(self, task: str, acceptance_criteria: Sequence[str]) -> RunResult:
        deadline = monotonic() + self.config.timeout_seconds
        criteria = tuple(acceptance_criteria)
        observations: tuple[Observation, ...] = ()
        retryable_failures: dict[tuple[str, str], int] = {}
        started = self.events.record(
            "run_started", {"task": task, "acceptance_criteria": criteria}
        )
        for iteration in range(1, self.config.max_iterations + 1):
            if monotonic() >= deadline:
                return self._finish(
                    started.run_id,
                    RunStatus.BUDGET_EXHAUSTED,
                    None,
                    "time budget exhausted",
                )
            context = RunContext(
                task,
                criteria,
                observations,
                self.config.max_iterations - iteration,
            )
            try:
                decision = self.model.next_decision(
                    context, self.tools.specifications()
                )
            except Exception as error:
                self.events.record(
                    "model_error",
                    {"type": type(error).__name__, "message": str(error)},
                )
                return self._finish(
                    started.run_id,
                    RunStatus.FAILED,
                    None,
                    f"model error: {error}",
                )
            self.events.record("model_decision", _serialize_decision(decision))
            if isinstance(decision, FinalAnswer):
                verification = self.verifier.verify(context, decision)
                self.events.record("verification", asdict(verification))
                status = (
                    RunStatus.SUCCEEDED if verification.accepted else RunStatus.FAILED
                )
                return self._finish(
                    started.run_id,
                    status,
                    decision.text if verification.accepted else None,
                    verification.reason,
                )
            tool = self.tools.get(decision.name)
            if tool is None:
                result = self.tools.execute(decision)
            else:
                policy_decision = authorize(tool, decision, self.policy, self.approval)
                self.events.record(
                    "policy_decision",
                    {"tool": decision.name, "decision": policy_decision.value},
                )
                if policy_decision is PolicyDecision.DENY:
                    return self._finish(
                        started.run_id,
                        RunStatus.APPROVAL_REFUSED,
                        None,
                        "approval refused",
                    )
                result = self.tools.execute(decision)
            self.events.record("tool_result", _serialize_tool_result(decision, result))
            if not result.ok and result.retryable:
                error = result.error or "error"
                failure = (decision.name, error)
                retryable_failures[failure] = retryable_failures.get(failure, 0) + 1
                if retryable_failures[failure] > self.config.retry_limit:
                    return self._finish(
                        started.run_id,
                        RunStatus.FAILED,
                        None,
                        f"retry limit exceeded for {decision.name}: {error}",
                    )
            observations += (
                Observation(
                    source=decision.name,
                    content=result.output if result.ok else result.error or "error",
                ),
            )
        return self._finish(
            started.run_id,
            RunStatus.BUDGET_EXHAUSTED,
            None,
            "iteration budget exhausted",
        )

    def _finish(
        self,
        run_id: str,
        status: RunStatus,
        answer: str | None,
        reason: str,
    ) -> RunResult:
        self.events.record(
            "run_finished",
            {"status": status.value, "answer": answer, "reason": reason},
        )
        return RunResult(status, answer, reason, run_id, self.events.count)


def _serialize_decision(decision: ToolCall | FinalAnswer) -> dict[str, object]:
    if isinstance(decision, FinalAnswer):
        return {"type": "final_answer", "text": decision.text}
    return {
        "type": "tool_call",
        "tool": decision.name,
        "arguments": dict(decision.arguments),
    }


def _serialize_tool_result(call: ToolCall, result: ToolResult) -> dict[str, object]:
    return {
        "tool": call.name,
        "ok": result.ok,
        "output": result.output,
        "error": result.error,
        "retryable": result.retryable,
    }
