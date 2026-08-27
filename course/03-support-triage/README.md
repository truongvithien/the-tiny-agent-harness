# Part 3: The Support-Triage Laboratory

## Learning goals

By the end of this lesson, you can:

- describe a tool's **input contract** and read its typed success or failure
  result instead of an exception;
- explain why reading a ticket and searching policy text are safe by default
  while sending a reply is not;
- follow one structured model decision at a time through a real event trace,
  including the approval request that guards the only consequential tool; and
- complete a small approval gate that refuses a consequential action when the
  run has no evidence to send.

This lesson assumes you finished [Part 2: The Tiny Core](../02-tiny-core/README.md)
and can name the five boundaries the runner crosses.

Run every command below from the repository root, the directory containing
`pyproject.toml`.

## The laboratory

A **laboratory** in this course is synthetic local infrastructure plus the tools
that reach it. Nothing in this laboratory touches a network, and no tool writes
outside the run's own memory.

[`labs/support_triage/store.py`](../../labs/support_triage/store.py) holds two
read-only sources:

- a **ticket store**: one JSON file per ticket, such as
  [`t-1042.json`](../../labs/support_triage/data/tickets/t-1042.json); and
- a **policy knowledge base**: Markdown files split into sections, such as
  [`billing-refunds.md`](../../labs/support_triage/data/policies/billing-refunds.md).

`TicketStore.read` returns `Ticket | None`. An unknown identifier is an ordinary
answer, not a crash, so the tool above it can turn `None` into a typed failure.
`PolicyLibrary.search` returns `PolicyExcerpt` values, each carrying the
`source` filename it came from. That filename is **provenance**: the record of
where a piece of text originated. A reply grounded in policy is only checkable
when its source travels with it.

[`labs/support_triage/tools.py`](../../labs/support_triage/tools.py) holds
**run-local state**: a `TriageState` object created for one run and thrown away
afterwards. The category and the draft live there, not in the model's prose.

## The five tools and their risk classes

| Tool | Risk | What it does | Why that risk |
| --- | --- | --- | --- |
| `read_ticket` | `READ` | Loads one ticket from the JSON store. | Observes local data and changes nothing. |
| `search_policy` | `READ` | Returns policy excerpts with their source filename. | Observes local data and changes nothing. |
| `set_category` | `WRITE` | Records one category from a fixed allow-list. | Changes run-local state, and the next call can overwrite it. |
| `draft_reply` | `WRITE` | Stores the draft reply text. | Changes run-local state, and the next call can overwrite it. |
| `send_reply` | `CONSEQUENTIAL` | Simulates sending the draft to the customer. | Communicates outward; a delivered message cannot be recalled. |

### Why `send_reply` is consequential and `search_policy` is not

`search_policy` reads text that already exists. Run it ten times and the
laboratory is identical afterwards; run it on the wrong keyword and the only
cost is a useless observation. Nothing leaves the process, so a mistake is
recoverable by trying again.

`send_reply` is the only tool whose effect a person outside the run would see.
In this laboratory the send is simulated — it appends a `SentReply` to
run-local state and performs no real I/O — but its **risk class describes the
real action it stands for**. A wrong category can be corrected by calling
`set_category` again. A wrong message that has reached a customer cannot be
unsent. That asymmetry, not the size of the code, is what
`Risk.CONSEQUENTIAL` records.

Because `RiskPolicy` in
[`tiny_harness/policy.py`](../../tiny_harness/policy.py) returns
`APPROVAL_REQUIRED` for exactly that class, `send_reply` is the laboratory's
**approval gate**: the one point where the run stops and asks a person before
an effect happens.

## Verification by evidence, not assertion

[`labs/support_triage/verification.py`](../../labs/support_triage/verification.py)
replaces Part 2's `AcceptFinalAnswer`. `TriageVerifier` reads `TriageState` and
accepts a final answer only when a category was recorded **and** a reply was
drafted. A model that writes "I have categorised and answered the ticket"
without calling the tools produces `RunStatus.FAILED`, because the verifier
never reads the answer text at all.

## Run the demonstration

[`labs/support_triage/demo.py`](../../labs/support_triage/demo.py) scripts six
model decisions for ticket T-1042 and approves the send:

```bash
python -m labs.support_triage.demo
```

Expected output, three lines:

```text
succeeded
Ticket T-1042 is categorised as billing and an approved refund reply was sent.
.traces/support_triage.jsonl
```

Now inspect the trace. **A trace** is the append-only JSON Lines history of one
run:

```bash
python -c 'import json; [print(json.loads(l)["kind"]) for l in open(".traces/support_triage.jsonl")]'
```

Expected: twenty-one event kinds in this order.

```text
run_started
model_decision  policy_decision  tool_result          # read_ticket
model_decision  policy_decision  tool_result          # search_policy
model_decision  policy_decision  tool_result          # set_category
model_decision  policy_decision  tool_result          # draft_reply
model_decision  policy_decision  approval_requested  approval_decision  tool_result   # send_reply
model_decision  verification
run_finished
```

Four iterations record three events each. The fifth records five: the policy
decision, the request put to a person, that person's answer, and only then the
result of the send. Read the trace in a text editor and notice that
`approval_requested` is written *before* the handler could run. That ordering is
what the trace exists to prove.

Refusal is the interesting half. This run refuses the same send:

```bash
python -c 'from pathlib import Path; from labs.support_triage.demo import run_demo; from labs.support_triage.tools import TriageState; s = TriageState(); r = run_demo(Path(".traces/support_triage_refused.jsonl"), state=s, approve=False); print(r.status.value, r.reason, s.sent_replies)'
```

Expected:

```text
approval_refused approval refused for tool: send_reply ()
```

Eighteen events are recorded and there is no `tool_result` for `send_reply`,
because the run ends between `approval_decision` and execution. The empty tuple
is the laboratory's own side-effect log: nothing was sent.

To watch the whole scenario suite instead, run:

```bash
python -m pytest tests/test_support_triage_demo.py -v
```

Expected: five passing scenario tests.

## Exercise: gate the consequential action on its evidence

`RiskPolicy` asks a person about every consequential call, even one that has
nothing to send. A support desk wants something stricter: never interrupt a
person for a send that would fail anyway.

Open [`exercise.py`](exercise.py). Its `decide` function receives a `Risk`, the
category recorded so far (or `None`), and the draft reply so far (or `None`),
and must return a `PolicyDecision`. The starter raises `NotImplementedError` on
purpose.

The seven cases the checker uses are:

| Risk | Category | Draft | Expected |
| --- | --- | --- | --- |
| `READ` | none | none | `ALLOW` |
| `WRITE` | none | none | `ALLOW` |
| `CONSEQUENTIAL` | `billing` | present | `APPROVAL_REQUIRED` |
| `CONSEQUENTIAL` | none | present | `DENY` |
| `CONSEQUENTIAL` | `refund_now` | present | `DENY` |
| `CONSEQUENTIAL` | `billing` | blank | `DENY` |
| `CONSEQUENTIAL` | `billing` | none | `DENY` |

Check your work from the repository root:

```bash
python course/03-support-triage/check_exercise.py
```

It prints one `✓` or `✗` per case and exits with status 1 until every case
passes. Keep the function small; this puzzle is about the approval boundary,
not Python tricks.

### Hint 1

Two of the seven cases never involve a person at all. Handle those first and
you have five cases left, all of the same risk class.

### Hint 2

`ALLOWED_CATEGORIES` is already imported for you from the laboratory's tools
module. Membership testing with `in` treats `None` as simply absent from the
tuple, so an unknown category and a missing category can share one branch.

### Hint 3

A draft of `"   "` is not a draft. `str.strip()` tells you whether text carries
content, and `None` must be excluded before you call a string method on it.
`DENY` and `APPROVAL_REQUIRED` are different answers: the first never asks a
person, the second always does.

After your checker passes, compare your reasoning with the
[reference solution](../../solutions/03-support-triage/exercise.py). To check
the reference without changing your learner file, run:

```bash
python course/03-support-triage/check_exercise.py --solution
```

That solution check reports seven passes and exits with status 0.

To watch the same contract fail as a test while you work on it, run:

```bash
python -m pytest -m learner tests/test_support_triage_exercise.py -v
```

Expected before solving: seven failures naming the learner message. These tests
carry the `learner` marker, so the default suite skips them and a fresh clone
stays green.

## Recap

The laboratory adds nothing to the runner from Part 2; it adds tools, data, and
a verifier. Reads are allowed by default because they change nothing.
Writes touch only run-local state, so a later call can correct them.
`send_reply` is the single consequential tool, so it is the single approval
gate, and the trace records the request and the answer before any effect. The
verifier accepts a final answer only on evidence found in lab state, and the
exercise makes the gate refuse a consequential action that has no evidence to
send.

Related reading: [Part 1: Foundations](../01-foundations/README.md), the
[bounded runner](../../tiny_harness/runner.py), the
[implementation plan](../../docs/superpowers/plans/2026-08-27-support-triage-lab.md),
and the [course design specification](../../docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md).

Continue to [Part 4: Research laboratory](../04-research-agent/README.md), where
every tool is read-only and completion must be backed by captured evidence
rather than an approval.
