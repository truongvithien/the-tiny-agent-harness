# Part 4: The Research Laboratory

## Learning goals

By the end of this lesson, you can:

- explain why a harness gives a model a *selection* of context rather than all
  of it, and how a character limit makes that selection visible;
- trace a claim back to the source it came from through a run's event log;
- describe why a run made only of read-only tools still needs verification; and
- complete the evidence check that decides whether a report is backed by
  sources the run actually fetched.

Run every command below from the repository root, the directory containing
`pyproject.toml`, with your virtual environment activated. If you have not set
one up, follow the setup steps in the [main README](../../README.md).

This lesson builds on [Part 1: Foundations](../01-foundations/README.md) and
[Part 2: The Tiny Core](../02-tiny-core/README.md). It reuses their `Runner`,
`RiskPolicy`, event sinks, and `Verifier` contract without changing them; the
whole laboratory is new tools, new data, and a new verifier.

## The case

The laboratory serves six synthetic Markdown documents about a fictional heron
colony at Blackwater Marsh. The agent has to report how many nesting pairs the
2024 survey found.

The documents are not a tidy set. Two of them disagree:

| Source id | What it says |
| --- | --- |
| [`marsh-survey-2024`](../../labs/research/data/marsh-survey-2024.md) | 128 nesting pairs, counted April 2024 |
| [`regional-bird-atlas`](../../labs/research/data/regional-bird-atlas.md) | 96 nesting pairs, from a 2019 return |
| [`warden-field-notes`](../../labs/research/data/warden-field-notes.md) | the count sheet was lost; no total at all |
| [`survey-method-manual`](../../labs/research/data/survey-method-manual.md) | how a dawn flush count is performed |
| [`marsh-habitat-guide`](../../labs/research/data/marsh-habitat-guide.md) | habitat background, no counts |
| [`visitor-leaflet`](../../labs/research/data/visitor-leaflet.md) | "hundreds of herons", no count, no method |

`marsh-survey-2024` and `regional-bird-atlas` are the **conflicting pair**: they
give different figures for the same quantity. `warden-field-notes` is the
**incomplete source**: it is about the right survey but holds no total.
`visitor-leaflet` is the confident source with nothing behind it.

A source declares a conflict in its own text with one metadata line:

```text
Conflicts-With: regional-bird-atlas
```

[`labs/research/server.py`](../../labs/research/server.py) reads that line, keeps
it out of the document's prose, and serves it as a separate field. Declaring
conflicts in the data keeps the lab deterministic: the harness never has to
judge meaning, and you can add a conflicting source without touching code.

## The local document server

**Mock infrastructure** is a small local stand-in for a real service, used so a
lesson runs offline. Here it is one standard-library `HTTPServer` bound to
`127.0.0.1` on **port 0**, which asks the operating system for any free port.
The chosen port is then readable as `server.port`.

Two rules matter more than the routing:

- it binds loopback only, so nothing outside your machine can reach it; and
- it starts and stops through one context manager, so no test or failed demo
  leaves a thread or a socket behind.

```python
with serve_documents() as server:
    print(server.base_url)  # http://127.0.0.1:<ephemeral port>
```

Leaving the `with` block calls `shutdown()`, closes the socket, and joins the
serving thread. `tests/test_research_server.py` asserts exactly that, including
the case where the block raises.

Two routes exist:

- `GET /sources` returns every document's id and title; and
- `GET /sources/<id>` returns one document's id, title, declared conflicts, and
  text, or HTTP 404 with a JSON error for an unknown id.

## The three tools

[`labs/research/tools.py`](../../labs/research/tools.py) defines them, and every
one is `Risk.READ`:

| Tool | Risk | What it does |
| --- | --- | --- |
| `list_sources` | `READ` | Lists the ids and titles the server offers. |
| `fetch_source` | `READ` | Retrieves one document over HTTP and returns its provenance header plus a capped slice of its text. |
| `record_claim` | `READ` | Records one claim and the source id that supports it in run-local state. |

### Why is `record_claim` read-only?

Recall the three risk classes from Part 2: `READ` observes, `WRITE` makes a
reversible local change, and `CONSEQUENTIAL` reaches outside or is hard to
undo. `record_claim` writes only to a `ResearchNotebook` object that is created
when the run starts and discarded when it ends. Nothing on disk, on the
network, or in anyone's inbox changes. So `READ` is the honest classification,
and this laboratory has no approval gate at all — you will not see a single
`approval_requested` event in its trace.

If the notebook were saved to a file, `record_claim` would become `WRITE`, and
the tool boundary would then have to constrain *where* it may write. Part 5
does exactly that with a temporary workspace.

### Why a read-only run still needs verification

A run that cannot change anything can still be wrong, and this is the point of
the laboratory. Policy asks "may this action happen?"; verification asks "is
the result supported?" No amount of read-only safety answers the second
question. A model can fetch nothing and still write a fluent paragraph
containing a number. Only the verifier, holding the notebook, can tell that
paragraph apart from a report built on captured evidence.

### Context selection and the character limit

The **context** is what the harness puts in front of the model for its next
decision. It is a budget, not an archive. `fetch_source` enforces that budget
with one named constant:

```python
MAX_SOURCE_CHARACTERS = 600
```

Anything longer is cut at 600 characters and the cut is announced in the text
the model receives:

```text
…[TRUNCATED AT 600 CHARACTERS]
```

The marker matters as much as the cut. Silent truncation invites a model to
reason about a document it only partly saw and to state the missing part with
the same confidence as the rest. The demo shows both halves of selection: the
agent lists all six sources, then fetches three of them, and one of those three
comes back truncated.

### Provenance versus confidence

**Provenance** is the record of where a piece of text came from. Every
`fetch_source` result begins with it:

```text
source_id: marsh-survey-2024
url: http://127.0.0.1:53219/sources/marsh-survey-2024
title: Blackwater Marsh Heron Survey 2024
character_limit: 600
conflicts_with: regional-bird-atlas
text:
The 2024 dawn survey counted 128 active grey heron nesting pairs across …
```

Confidence is a property of prose: `visitor-leaflet` says "hundreds of herons"
and sounds certain. Provenance is a property of the run: an id, a URL, and a
`tool_result` event recorded at the moment the bytes arrived. The first can be
produced by a model with no evidence at all. The second cannot — it exists only
if a tool actually fetched something, and it stays in the trace where you can
check it afterwards.

## How this lab reports uncertainty

`record_claim` accepts an optional `disputed` flag, and the verifier
[`CitedClaims`](../../labs/research/verification.py) enforces its use. In order,
`verify` rejects a report when:

1. no claim was recorded at all;
2. a claim cites a source id that was never fetched in this run;
3. a claim's cited source is contradicted by *another source fetched in the
   same run*, but the claim was not recorded as `disputed`; or
4. the report text does not name every source behind its claims, including each
   contradicting source of a disputed claim.

Rule 3 is the uncertainty rule, and rule 4 is what stops the agent from
admitting the conflict privately and hiding it from the reader. Together they
mean an agent cannot quietly pick 128 over 96: either it marks the claim
disputed and names both sources, or the run finishes `failed`.

Two deliberate simplifications are worth naming. A conflict is declared between
whole documents, not between individual figures, so *any* claim citing
`marsh-survey-2024` must be marked disputed once `regional-bird-atlas` has been
fetched. And a conflict is invisible until both sources are in the notebook —
an agent that reads only `marsh-survey-2024` faces no dispute, because from
inside that run there is nothing to disagree with. Reading widely is what
surfaces the disagreement; the harness only makes sure a surfaced disagreement
cannot be dropped.

## Run the demonstration

```bash
python -m labs.research.demo
```

Expected: it prints `succeeded`, then a report naming `marsh-survey-2024`,
`regional-bird-atlas`, and `survey-method-manual`, then the path
`.traces/research.jsonl`. The server starts and stops inside that one command,
and no network access beyond loopback is used.

Now read the trace:

```bash
python -c 'import json; print([json.loads(line)["kind"] for line in open(".traces/research.jsonl")])'
```

Expected: 22 event kinds — `run_started`, then `model_decision`,
`policy_decision`, `tool_result` six times over, then a final
`model_decision`, `verification`, and `run_finished`. Every `policy_decision`
reads `allow`, because every tool is `READ`. There are no approval events.

To see one fetch with its provenance and its truncation marker:

```bash
python -c 'import json; print([json.loads(l)["payload"]["output"] for l in open(".traces/research.jsonl") if json.loads(l)["kind"] == "tool_result"][1])'
```

Expected: the provenance header shown earlier, followed by the first 600
characters of the survey report and `…[TRUNCATED AT 600 CHARACTERS]`.

## Exercise: complete the evidence check

Open [`exercise.py`](exercise.py). Its `unsupported_source_ids` function
receives the run's claims and the ids of the sources that were fetched, and
must return the cited ids that were never fetched. This is rule 2 of the
verifier — the check that separates a citation from a captured source. The
starter raises `NotImplementedError` on purpose.

The contract:

- return a `tuple` of source ids;
- report a missing id once, even when several claims cite it;
- keep the order in which the claims raised each missing id; and
- return an empty tuple when every claim is supported, and also when there are
  no claims.

Check your work:

```bash
python course/04-research-agent/check_exercise.py
```

Expected before you solve it: five `✗` lines and exit status 1. Expected once
it is right: five `✓` lines and exit status 0. You can also run the same
contract through pytest, which excludes this intentionally incomplete work from
the default suite:

```bash
python -m pytest -m learner tests/test_research_exercise.py -v
```

### Hint 1

You need two things a claim knows nothing about on its own: which ids were
fetched, and which ids you have already reported. Decide how you will hold each
one before you write the loop.

### Hint 2

`fetched_source_ids` is a sequence, so `in` on it scans. Building a `set` from
it first makes each lookup direct, and the set is the natural place to ask "was
this fetched?"

### Hint 3

The order rule and the once-only rule are the same rule seen twice: append to a
list only when the id is not already in it, then convert that list to a tuple
at the end. A `set` alone cannot do this, because a set has no order.

When your checker passes, compare your reasoning with the
[reference solution](../../solutions/04-research-agent/exercise.py). To check that
solution without touching your own file:

```bash
python course/04-research-agent/check_exercise.py --solution
```

Expected: five `✓` lines and exit status 0.

## Recap

The research laboratory reuses the Part 2 core unchanged and adds a local
document server on an ephemeral port, three read-only tools, and a verifier
that reads a notebook instead of prose. Context is a budget, so `fetch_source`
caps a document at `MAX_SOURCE_CHARACTERS` and says so in the text. Provenance
is recorded per fetch, so a claim can be traced to the bytes that supported it.
Because every tool is `READ`, policy never blocks anything here — and the run
can still fail, which is exactly why verification is a separate boundary from
policy. When two fetched sources disagree, the harness insists the report say
so.

Continue to [Part 5: Software-development laboratory](../05-coding-agent/README.md),
which moves from reading to changing files and reintroduces the risk classes
this lab did not need. For the full
seven-part plan, read the
[course design specification](../../docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md).
