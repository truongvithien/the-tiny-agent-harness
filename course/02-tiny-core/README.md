# Part 2: The Tiny Core

## Learning goals

By the end of this lesson, you can:

- follow one run through the core files in execution order;
- explain the boundary around each model decision, policy decision, tool
  effect, trace event, and verification result; and
- complete a small policy function for three tool risk classes.

Run every command below from the repository root, the directory containing
`pyproject.toml`.

## Before the loop: the shared contracts

A **contract** describes the shape and meaning of data passed across a boundary.
The core starts in [`tiny_harness/types.py`](../../tiny_harness/types.py), which
defines immutable contracts. `ToolCall` carries a requested tool name and
arguments, recursively freezing nested mappings and sequences so policy or
approval code cannot change what will execute after the proposal is recorded.
`ToolResult` carries success or failure as data. `RunContext` is the compact
state supplied for a decision, while `RunResult` is the terminal result.

[`tiny_harness/tools.py`](../../tiny_harness/tools.py) defines `Tool`, the
contract for a bounded operation, and `ToolRegistry`, the allow-list that finds
and executes registered tools. `FunctionTool` adapts an ordinary Python
function to that contract. This boundary prevents an arbitrary model-proposed
name from becoming an arbitrary function call, and it converts tool exceptions
into safe `ToolResult` failures.

Every tool declares one `Risk`:

- `READ` observes data without changing it and is allowed by default within the
  tool's scope.
- `WRITE` makes a reversible local change and is allowed in this course's lab
  workspace. The tool boundary must still limit where and what it can change.
- `CONSEQUENTIAL` communicates externally or performs a difficult-to-reverse
  action, so it requires explicit approval.

[`tiny_harness/policy.py`](../../tiny_harness/policy.py) defines the `Policy`
contract and `RiskPolicy`. Its `evaluate` method returns a `PolicyDecision`:
`ALLOW`, `DENY`, or `APPROVAL_REQUIRED`. The separate `authorize` function asks
the approval callback when necessary. Policy runs before execution so a denied
action cannot cause its effect first.

`authorize` preserves both pieces of authorization evidence: the policy's
original decision and, only when that decision is `APPROVAL_REQUIRED`, the
callback's boolean response. The runner records the policy decision before it
requests approval. A direct `DENY` ends with `policy_denied`; a person refusing
an approval request ends with `approval_refused`.

[`tiny_harness/events.py`](../../tiny_harness/events.py) defines an `EventSink`,
which records ordered events. `MemoryEventSink` supports tests and
`JsonlEventSink` persists one JSON object per line. The sink copies payloads,
redacts configured secrets, and truncates large strings at the recording
boundary so later mutation or unsafe output cannot rewrite history.

## During the loop: decide, act, and verify

[`tiny_harness/models.py`](../../tiny_harness/models.py) defines
`ModelAdapter.next_decision`. The adapter receives `RunContext` plus safe tool
descriptions, then returns one `ToolCall` or `FinalAnswer`. `ScriptedModel` makes
the lessons deterministic by returning decisions supplied in advance. The
model boundary proposes exactly one next step; it never executes the step.

[`tiny_harness/runner.py`](../../tiny_harness/runner.py) coordinates the run.
In execution order it:

1. records the task and acceptance criteria;
2. builds the current context and asks the model for one decision;
3. validates and records that decision;
4. for a known tool, records the policy decision, then records any approval
   request and its strictly boolean response before asking `ToolRegistry` to
   execute it;
5. records the `ToolResult` and adds it to the next context as an observation;
6. for a final answer, rejects blank text itself or calls the verifier, records
   the verification result, and returns a terminal result; and
7. stops early if a time, iteration, retry, approval, or error boundary says it
   must stop.

At most one tool executes per iteration. This keeps every effect next to its
policy decision and result in the trace.

### What the wall-clock limit guarantees

The runner gives each synchronous model, policy, approval, tool, and verifier
call only the time remaining in the run budget. If a call misses the deadline,
the runner records `timeout`, ignores any result that arrives later, finishes
with `budget_exhausted`, and does not wait indefinitely. A verifier result that
arrives after the deadline can therefore never produce success.

An ordinary Python function cannot be force-cancelled safely once it is
running. In particular, a timed-out tool may still finish an external side
effect after the runner returns. The timeout event states whether the call may
still be running and that a late result will be ignored; it never claims the
call or side effect was cancelled. Real tools should also use their own I/O
timeouts and, when risk warrants it, operations designed to be safely retried
or cancelled.

[`tiny_harness/verification.py`](../../tiny_harness/verification.py) defines
`Verifier.verify`. A verifier turns a proposed `FinalAnswer` and its context
into a `VerificationResult`. The included `AcceptFinalAnswer` is deliberately
small: it accepts non-empty text. Later lessons can replace it with checks tied
to stronger evidence. This boundary exists because a model saying "done" does
not itself prove completion.

Finally, [`tiny_harness/__init__.py`](../../tiny_harness/__init__.py) re-exports
the beginner-facing names. It changes import convenience, not ownership: the
implementations remain in the focused files above.

## Which boundary produces each event?

| Event kind | Producing boundary | Why it is recorded |
| --- | --- | --- |
| `run_started` | `Runner.run` | Captures the task and acceptance criteria before work begins. |
| `model_decision` | Runner, immediately after `ModelAdapter` | Preserves the validated proposal before policy or execution. |
| `policy_decision` | Runner, immediately after `Policy.evaluate` | Preserves `ALLOW`, `DENY`, or `APPROVAL_REQUIRED` without collapsing it into a later outcome. |
| `approval_requested` | Runner, before the approval callback | Proves a person was asked before a consequential effect. |
| `approval_decision` | Runner, after the approval callback | Records whether that request was granted. |
| `tool_result` | Runner, immediately after `ToolRegistry.execute` | Records success or safe failure before it becomes an observation. |
| `verification` | Runner, after either rejecting a blank answer itself or calling `Verifier.verify` | Preserves the decision behind acceptance or rejection. |
| `timeout` | Runner's wall-clock boundary | Names the timed-out boundary, whether its call may still run, and that a late result is ignored. |
| `model_error`, `policy_error`, `approval_error`, `tool_error`, or `verification_error` | Runner's matching exception boundary | Records the safe exception type without leaking raw details. |
| `run_finished` | `Runner._finish` | Records the terminal status, answer, and reason. |

An unknown tool has no tool object to authorize, so it produces a failed
`tool_result` but no `policy_decision`. A refused consequential action produces
`policy_decision`, `approval_requested`, and `approval_decision` before
`run_finished`; execution never occurs. A direct policy denial has no approval
events because no person was asked.

## Exercise: complete the risk policy

Open [`exercise.py`](exercise.py). Its `decide` function receives a `Risk` and
must return the corresponding `PolicyDecision`. The starter raises
`NotImplementedError` on purpose.

With your virtual environment activated, run the checker from the repository
root:

```bash
python course/02-tiny-core/check_exercise.py
```

It checks all three risks, prints one `✓` or `✗` for each case, and exits with
status 1 until every case passes. Keep the function small; this puzzle is about
the policy boundary, not Python tricks.

### Hint 1

List the three `Risk` members and decide which one cannot be allowed without a
person's approval.

### Hint 2

Compare enum members with `is`, for example `risk is Risk.READ`. Return enum
members such as `PolicyDecision.ALLOW`, not strings such as `"allow"`.

### Hint 3

Two risk classes share the same result. Handle the one exceptional class first,
then use one return for the remaining classes.

After your checker passes, compare your reasoning with the
[reference solution](../../solutions/02-tiny-core/exercise.py). To check the
reference without changing your learner file, run:

```bash
python course/02-tiny-core/check_exercise.py --solution
```

## Recap

The tiny core passes explicit data across narrow boundaries: the model proposes
a `ToolCall`, policy authorizes it, the registry executes one bounded tool, the
event sink records the result, and the verifier controls successful completion.
The risk puzzle practices the boundary that must run before an effect.

Continue to [Part 3: Support-triage laboratory](../03-support-triage/README.md),
which puts these boundaries to work on a synthetic ticket store and adds a
human approval gate before a consequential action.
