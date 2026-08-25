# Part 1: Foundations

## Learning goals

By the end of this lesson, you can:

- distinguish a model from the software that makes it an agent;
- name the six stages in a small agent control loop;
- explain why the harness, rather than the model, owns effects; and
- run a deterministic example and inspect its event trace.

Run every command in this lesson from the repository root, the directory that
contains `pyproject.toml`.

## The pieces and their responsibilities

A **model** is a component that receives context and proposes a response. In
this course, a proposal is either a final answer or a structured request to use
a tool. A model proposes intent; it does not perform an action by itself.

An **agent** is a model inside a program that can repeatedly gather
information, choose a next step, and act toward a task. The surrounding program
is an **agent harness** (or simply **harness**): ordinary software that prepares
context, offers tools, enforces rules, performs approved actions, records what
happened, and decides when the work is complete.

A **tool** is a named, bounded operation that the harness can perform. It has a
description, an input contract, a risk class, and an execution function. A file
reader and a message sender can both be tools, but their risks differ.

A **policy** is deterministic code that decides whether a requested tool action
is allowed, denied, or needs human approval. Describing a rule in a prompt may
help the model choose well, but only a policy boundary can enforce the rule.

**State** is the compact information needed for the next decision: the task,
acceptance criteria, observations, and remaining budget. An **event trace** is
the append-only history of a run. Each event says what happened, in what order,
and with which safe-to-record details. State helps the next step; the trace
helps a person understand the steps already taken.

A **verifier** is code that checks a proposed final answer against explicit
completion conditions and available evidence. An **evaluation** is a repeatable
measurement across one or more runs, such as how often the verifier accepts a
correct answer. Verification is part of a run; evaluation tells us how the
system performs across runs.

## The six-stage control loop

The small loop used throughout this course is:

```text
1. observe   -> build compact state from the task and earlier results
2. decide    -> ask the model for one final answer or one ToolCall
3. authorize -> apply deterministic policy to the requested tool
4. execute   -> invoke at most one approved tool action
5. record    -> append decisions and results to the event trace
6. verify    -> check completion evidence, then stop or continue
```

A `ToolCall` is structured data containing a tool name and its arguments. It is
a request, not an effect. This boundary matters: untrusted or mistaken model
output remains harmless data until the harness validates it, checks policy, and
chooses to execute it.

Effects belong to the harness because the harness can apply guarantees the
model cannot. This harness restricts available tools, requests approval before
consequential work, enforces time and iteration limits, turns exceptions into
safe results, redacts secrets, and preserves a trace. The same boundary is
where later lessons can add argument validation. Keeping the effect boundary in
ordinary Python makes the safety rules testable and independent of prompt
wording.

## Run the completed example

The [foundations demonstration](../../examples/foundations_demo.py) uses a
scripted model and a local dictionary, so it needs neither network access nor
an API key. Run it from the repository root:

```bash
.venv/bin/python3 -m examples.foundations_demo
```

The three output lines show a `succeeded` status, the final answer, and the
trace path `.traces/foundations.jsonl`.

JSON Lines stores one JSON object on each line. Pretty-print the trace from the
repository root with:

```bash
.venv/bin/python3 -m json.tool --json-lines .traces/foundations.jsonl
```

Follow the sequence numbers. The scripted model requests `lookup_habitat`; the
policy allows its read-only risk; the harness executes the lookup; and the tool
result becomes an observation for the next decision. The model then proposes a
final answer, and the verifier accepts it before the harness reports success.

Next, practice deciding which component owns a responsibility in
[the foundations exercises](exercises.md), then continue to
[Part 2: Tiny Core](../02-tiny-core/README.md).

## Recap

The model proposes intent. The harness owns authorization, effects, records,
budgets, and verified completion. That separation turns a model response into
an observable and controllable agent run.
