# Part 7: Capstone

## Learning goals

By the end of this part, you can:

- extend the harness with one new tool or policy without editing the runner;
- justify a **risk classification** and defend it against a plausible objection;
- write both a success test and a **denial test** for a boundary you added;
- run a scenario and read its trace as the evidence for your claim; and
- describe the safety boundary your extension creates, and its limits.

Run every command in this part from the repository root, the directory that
contains `pyproject.toml`.

## What a capstone is for

The previous five parts each handed you a boundary that already existed. This
part asks you to add one. The measure of success is not how much you build. It
is whether someone else can read your contract, your tests, and one trace, and
then trust the boundary without reading your implementation.

This part has two pieces: a small checked warm-up that everyone completes, and
an open extension assessed against the rubric below.

## Warm-up: an argument-aware policy

Every policy so far has looked only at a tool's risk class.
[`RiskPolicy`](../../tiny_harness/policy.py) even discards the call with
`del call`. But risk is not always a property of the tool alone. Refunding two
pounds and refunding two thousand pounds use the same tool.

An **argument-aware policy** reads the arguments of a call, not just the tool
that would run it. Open [`exercise.py`](exercise.py) and implement
`RefundPolicy.evaluate` so that:

- any read or write tool is allowed;
- an `issue_refund` call is **denied** when its `amount` is missing, is not a
  number, is negative, or exceeds `MAX_AUTOMATIC_REFUND`; and
- every other consequential call still requires approval.

Check your work:

```bash
python course/07-capstone/check_exercise.py
```

The starter is intentionally incomplete, so this reports nine failures and exits
with status 1 until you finish it.

### Hints

1. Handle the easy case first. If the tool's risk is not
   `Risk.CONSEQUENTIAL`, the decision is `ALLOW` and nothing else matters.
2. Only `issue_refund` has an amount to inspect. Any other consequential tool
   should keep the Part 2 behaviour of `APPROVAL_REQUIRED`, so check the tool's
   name before you reach for its arguments.
3. Arguments arrive from a model, so treat them as untrusted. `arguments.get`
   avoids a `KeyError` on a missing amount, and a missing or non-numeric value
   should be denied rather than coerced. Watch out for `bool`: in Python
   `isinstance(True, int)` is `True`, and `True` is not an amount.

Then compare with
[`solutions/07-capstone/exercise.py`](../../solutions/07-capstone/exercise.py):

```bash
python course/07-capstone/check_exercise.py --solution
```

That reports nine passes and exits with status 0.

### Why this proves the design

`tests/test_capstone_exercise.py` runs the same policy through the real
`Runner` three times and asserts the traces:

| Scenario | Status | Ledger | Trace shape |
| --- | --- | --- | --- |
| Refund of 250 | `POLICY_DENIED` | empty | stops at `policy_decision` |
| Refund of 50, approval refused | `APPROVAL_REFUSED` | empty | stops at `approval_decision` |
| Refund of 50, approval granted | `SUCCEEDED` | one entry | reaches `tool_result` |

In the denied run the refund handler is never reached, so no effect occurs.
A final test reads the runner's own source and asserts it mentions neither the
new tool nor the new policy: the extension is additive, and the control loop you
built in Part 2 did not change.

## The open extension

Add **one** tool or **one** policy to any existing case — the
[support-triage lab](../03-support-triage/README.md), the
[research lab](../04-research-agent/README.md), or the
[coding lab](../05-coding-agent/README.md). One is enough. A second adds no
marks.

Deliver five things:

1. **A contract.** The tool's name, description, `input_schema`, and risk class,
   or the policy's decision rule stated as a sentence per outcome.
2. **A risk classification with a justification.** Say why it is `read`,
   `write`, or `consequential`, and name the condition that would change it.
3. **A success test and a denial test.** The denial test matters more. It must
   prove that the effect did not happen, not merely that a decision object said
   `deny`.
4. **One scenario run and its trace.** Point at the event kinds that show your
   boundary working.
5. **A written boundary statement.** Two or three sentences: what your extension
   prevents, and what it does not.

### Rubric

Marks reward clear contracts and evidence, not feature count.

| Criterion | Strong | Weak |
| --- | --- | --- |
| Contract clarity | Input schema and risk class are explicit; the name says what it does | Arguments are undocumented or the risk class is unstated |
| Risk justification | Names the specific irreversible or external effect, and the condition that would reclassify it | Asserts a class without reasoning, or copies another tool's class |
| Denial evidence | A test proves no effect occurred, using a spy, ledger, or filesystem check | Only asserts a returned `PolicyDecision`, or asserts nothing |
| Trace reading | Cites the event kinds that prove the boundary held | Describes intent without pointing at a trace |
| Honest limits | States what the boundary does not cover | Claims the extension makes the agent safe |
| Runner untouched | `tiny_harness/runner.py` is unchanged | The loop was edited to special-case the extension |

### Two failure modes to avoid

**Enforcing in the prompt.** Telling the model "never refund more than 100" is
not a boundary. Prompt text describes a rule; a policy enforces one. If your
extension can be defeated by the model choosing differently, it is not done.

**Claiming completion without evidence.** A verifier that accepts because the
model said it finished repeats the mistake Part 5 exists to prevent. Accept only
on evidence a tool actually produced.

## Verify the whole course

One command checks the repository the way a new learner meets it:

```bash
python scripts/verify_course.py
```

It confirms every part has a lesson, every exercise has a checker and a
reference solution, the README course map links every part, every relative
Markdown link resolves, no trace or environment is tracked, and no file contains
an API-key pattern. It exits 0 when the course is consistent.

## Recap

A harness earns trust boundary by boundary. You added one: a policy that reads
arguments, denies before any effect, and is proved by a test showing the effect
did not occur. The runner did not change, which is the point — a small, typed
core with clear seams is what makes an extension safe to add.

You have now built the whole course: contracts and a control loop in
[Part 2](../02-tiny-core/README.md), approval gates in
[Part 3](../03-support-triage/README.md), evidence and provenance in
[Part 4](../04-research-agent/README.md), filesystem and command scope in
[Part 5](../05-coding-agent/README.md), and a live provider behind one adapter in
[Part 6](../06-openai-integration/README.md). The reasoning behind the whole
progression is in the
[course design specification](../../docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md).
