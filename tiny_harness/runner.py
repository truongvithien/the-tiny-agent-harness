from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from threading import Event, Thread
from time import monotonic
from typing import Generic, TypeVar, cast

from tiny_harness.events import EventSink
from tiny_harness.models import ModelAdapter
from tiny_harness.policy import (
    ApprovalCallback,
    Policy,
    _require_approval_result,
    _require_policy_decision,
)
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
    VerificationResult,
)
from tiny_harness.verification import Verifier


_T = TypeVar("_T")


class _DeadlineExceeded(Exception):
    def __init__(
        self,
        *,
        call_started: bool,
        call_may_still_be_running: bool,
    ) -> None:
        super().__init__("time budget exhausted")
        self.call_started = call_started
        self.call_may_still_be_running = call_may_still_be_running


@dataclass(frozen=True)
class _CallOutcome(Generic[_T]):
    completed_at: float
    value: _T | None = None
    error: BaseException | None = None


def _call_before_deadline(operation: Callable[[], _T], deadline: float) -> _T:
    """Bound the runner's wait; a timed-out synchronous call may keep running."""
    if monotonic() >= deadline:
        raise _DeadlineExceeded(
            call_started=False,
            call_may_still_be_running=False,
        )

    completed = Event()
    outcomes: list[_CallOutcome[_T]] = []

    def invoke() -> None:
        try:
            value = operation()
        except BaseException as error:
            outcomes.append(_CallOutcome(completed_at=monotonic(), error=error))
        else:
            outcomes.append(_CallOutcome(completed_at=monotonic(), value=value))
        finally:
            completed.set()

    worker = Thread(target=invoke, daemon=True)
    worker.start()
    remaining = deadline - monotonic()
    if remaining > 0:
        completed.wait(remaining)
    if not completed.is_set():
        raise _DeadlineExceeded(
            call_started=True,
            call_may_still_be_running=True,
        )

    outcome = outcomes[0]
    if outcome.completed_at >= deadline:
        raise _DeadlineExceeded(
            call_started=True,
            call_may_still_be_running=False,
        )
    if outcome.error is not None:
        raise outcome.error
    return cast(_T, outcome.value)


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
                return self._finish_timeout(
                    started.run_id,
                    "run",
                    _DeadlineExceeded(
                        call_started=False,
                        call_may_still_be_running=False,
                    ),
                )
            context = RunContext(
                task,
                criteria,
                observations,
                self.config.max_iterations - iteration,
            )
            try:
                decision = _call_before_deadline(
                    lambda: self.model.next_decision(
                        context, self.tools.specifications()
                    ),
                    deadline,
                )
            except _DeadlineExceeded as timeout:
                return self._finish_timeout(started.run_id, "model", timeout)
            except Exception as error:
                return self._fail_boundary(started.run_id, "model", error)
            try:
                _validate_decision(decision)
                serialized_decision = _serialize_decision(decision)
            except Exception as error:
                return self._fail_boundary(started.run_id, "model", error)
            self.events.record("model_decision", serialized_decision)
            if isinstance(decision, FinalAnswer):
                if not decision.text.strip():
                    verification = VerificationResult(False, "final answer is empty")
                else:
                    try:
                        verification = _call_before_deadline(
                            lambda: _require_verification_result(
                                self.verifier.verify(context, decision)
                            ),
                            deadline,
                        )
                    except _DeadlineExceeded as timeout:
                        return self._finish_timeout(
                            started.run_id,
                            "verification",
                            timeout,
                        )
                    except Exception as error:
                        return self._fail_boundary(
                            started.run_id, "verification", error
                        )
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
                try:
                    policy_decision = _call_before_deadline(
                        lambda: _require_policy_decision(
                            self.policy.evaluate(tool, decision)
                        ),
                        deadline,
                    )
                except _DeadlineExceeded as timeout:
                    return self._finish_timeout(
                        started.run_id,
                        "policy",
                        timeout,
                        tool=decision.name,
                    )
                except Exception as error:
                    return self._fail_boundary(started.run_id, "policy", error)
                self.events.record(
                    "policy_decision",
                    {"tool": decision.name, "decision": policy_decision.value},
                )
                if policy_decision is PolicyDecision.DENY:
                    return self._finish(
                        started.run_id,
                        RunStatus.POLICY_DENIED,
                        None,
                        f"policy denied tool: {decision.name}",
                    )
                if policy_decision is PolicyDecision.APPROVAL_REQUIRED:
                    self.events.record("approval_requested", {"tool": decision.name})
                    try:
                        approval_granted = _call_before_deadline(
                            lambda: _require_approval_result(
                                self.approval(tool, decision)
                            ),
                            deadline,
                        )
                    except _DeadlineExceeded as timeout:
                        return self._finish_timeout(
                            started.run_id,
                            "approval",
                            timeout,
                            tool=decision.name,
                        )
                    except Exception as error:
                        return self._fail_boundary(
                            started.run_id, "approval", error
                        )
                    self.events.record(
                        "approval_decision",
                        {"tool": decision.name, "granted": approval_granted},
                    )
                    if not approval_granted:
                        return self._finish(
                            started.run_id,
                            RunStatus.APPROVAL_REFUSED,
                            None,
                            f"approval refused for tool: {decision.name}",
                        )
                try:
                    result = _call_before_deadline(
                        lambda: self.tools.execute(decision),
                        deadline,
                    )
                except _DeadlineExceeded as timeout:
                    return self._finish_timeout(
                        started.run_id,
                        "tool",
                        timeout,
                        tool=decision.name,
                    )
                except Exception as error:
                    return self._fail_boundary(started.run_id, "tool", error)
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

    def _fail_boundary(
        self,
        run_id: str,
        boundary: str,
        error: Exception,
    ) -> RunResult:
        error_type = type(error).__name__
        self.events.record(f"{boundary}_error", {"type": error_type})
        return self._finish(
            run_id,
            RunStatus.FAILED,
            None,
            f"{boundary} error: {error_type}",
        )

    def _finish_timeout(
        self,
        run_id: str,
        boundary: str,
        timeout: _DeadlineExceeded,
        *,
        tool: str | None = None,
    ) -> RunResult:
        payload: dict[str, object] = {
            "boundary": boundary,
            "call_may_still_be_running": timeout.call_may_still_be_running,
            "late_result_ignored": timeout.call_started,
        }
        if tool is not None:
            payload["tool"] = tool
        self.events.record("timeout", payload)
        reason = (
            "time budget exhausted"
            if boundary == "run"
            else f"time budget exhausted during {boundary}"
        )
        if timeout.call_may_still_be_running:
            reason += "; the timed-out call may still be running"
        return self._finish(
            run_id,
            RunStatus.BUDGET_EXHAUSTED,
            None,
            reason,
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


def _validate_decision(decision: object) -> None:
    if isinstance(decision, FinalAnswer):
        if not isinstance(decision.text, str):
            raise TypeError("final answer text must be a string")
        return
    if isinstance(decision, ToolCall):
        return
    raise TypeError("model returned an invalid decision")


def _require_verification_result(value: object) -> VerificationResult:
    if not isinstance(value, VerificationResult):
        raise TypeError("verifier must return a VerificationResult")
    if type(value.accepted) is not bool:
        raise TypeError("verification acceptance must be a bool")
    if not isinstance(value.reason, str):
        raise TypeError("verification reason must be a string")
    return value


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
