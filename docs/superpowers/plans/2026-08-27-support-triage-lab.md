# Support-Triage Laboratory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Implemented in one pass on 2026-08-27. Every step below is checked
and describes what was actually built.

**Goal:** Give Part 3 an offline, deterministic support-triage laboratory in which the existing `tiny_harness` runner reads a synthetic ticket, retrieves policy text with provenance, records a category, drafts a reply, and reaches a simulated send that a person must approve.

**Architecture:** `labs/support_triage` adds data, tools, and a verifier around the unchanged core. A read-only store serves JSON tickets and Markdown policy sections; five `FunctionTool` values expose it with typed arguments and typed results; one mutable `TriageState` object holds the run's category, draft, and simulated sends; a `TriageVerifier` accepts a final answer only on that state's evidence. A scripted model and a scripted approval callback keep the demonstration and every test reproducible. Course prose and a checked approval-gate puzzle teach the same boundary without an API key.

**Tech Stack:** Python 3.12, standard library, pytest 8, JSON, JSON Lines, Markdown

**Spec:** `docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md` (Part 3: Support-triage laboratory)

## Global Constraints

- `tiny_harness/`, `README.md`, `pyproject.toml`, `.gitignore`, `examples/`, `course/01-*`, `course/02-*`, and existing tests are not modified by this plan.
- `labs` stays an implicit namespace package: no `labs/__init__.py`, so parallel laboratory branches cannot collide on a shared file.
- Tools bind to the committed core interfaces exactly; no core signature is inferred or changed.
- No network access, no credentials, and no filesystem writes outside run-local state and the ignored `.traces/` directory.
- `send_reply` performs a simulated send only; its risk class describes the real action it stands for.
- Deterministic Python code, not prompt text, enforces the approval gate.
- Verification uses evidence recorded in lab state, never a model assertion.
- The default pytest selection stays green; the intentionally incomplete learner contract carries the `learner` marker.
- Trace assertions check event kinds and payload fields, never timestamps.

## Planned file map

```text
docs/superpowers/plans/2026-08-27-support-triage-lab.md   this plan
labs/support_triage/__init__.py                          laboratory public names
labs/support_triage/data/tickets/*.json                  five synthetic tickets
labs/support_triage/data/policies/*.md                   four synthetic policy documents
labs/support_triage/store.py                             read-only ticket and policy access
labs/support_triage/tools.py                             run-local state and the five typed tools
labs/support_triage/verification.py                      evidence-based verifier
labs/support_triage/demo.py                              deterministic scripted demonstration
course/03-support-triage/README.md                       lesson prose, hints, and commands
course/03-support-triage/exercise.py                     learner approval-gate puzzle
course/03-support-triage/check_exercise.py               standalone learner feedback command
solutions/03-support-triage/exercise.py                  explained reference implementation
tests/test_support_triage_store.py                       fixture and search tests
tests/test_support_triage_tools.py                       risk-class, tool-contract, and verifier tests
tests/test_support_triage_demo.py                        approved, refused, and rejected scenarios
tests/test_support_triage_exercise.py                    learner and reference exercise contracts
```

---

### Task 1: Publish the synthetic laboratory data and its read-only store

**Files:**
- Create: `labs/support_triage/data/tickets/t-1042.json` … `t-1046.json`
- Create: `labs/support_triage/data/policies/billing-refunds.md`, `account-security.md`, `product-support.md`, `reply-style.md`
- Create: `labs/support_triage/store.py`
- Create: `tests/test_support_triage_store.py`

**Interfaces:**
- Consumes: `json` and `pathlib` only.
- Produces: `Ticket`, `PolicyExcerpt`, `TicketStore.ticket_ids()`, `TicketStore.read(ticket_id) -> Ticket | None`, `PolicyLibrary.sources()`, `PolicyLibrary.excerpts()`, and `PolicyLibrary.search(keyword, limit=3)`.

- [x] **Step 1: Write five tickets spanning the four triage categories**

`T-1042` duplicate billing charge, `T-1043` locked account, `T-1044` empty CSV export defect, `T-1045` how-to question about invitations, `T-1046` cancellation with a final-amount question. Each record carries `ticket_id`, `customer`, `channel`, `received_at`, `subject`, and `body`.

- [x] **Step 2: Write four policy documents with `##` sections**

Each document opens with a `#` title, states that it is synthetic, and then carries two to three `##` sections. Sections are the unit of retrieval, so the title is never returned as an excerpt.

- [x] **Step 3: Implement the store**

`TicketStore.read` trims and case-folds the requested identifier and returns `None` when nothing matches, so an unknown identifier is data rather than an exception. `PolicyLibrary` splits each document on `## ` headings and returns `PolicyExcerpt(source, heading, text)`, where `source` is the filename that supplies provenance. `search` matches a case-folded keyword against heading and body and caps its result at `limit`.

- [x] **Step 4: Test the fixtures, the missing-ticket answer, and provenance**

Run: `python -m pytest tests/test_support_triage_store.py -q`

Expected: PASS, ten tests. They cover a real fixture read, at least four sorted identifiers, `None` for an unknown identifier, trimmed and case-folded matching, an isolated empty root, single-match provenance, at least three Markdown sources, a bounded case-insensitive search, empty searches, and the excluded document title.

### Task 2: Add the five typed tools over run-local state

**Files:**
- Create: `labs/support_triage/tools.py`
- Create: `labs/support_triage/verification.py`
- Create: `labs/support_triage/__init__.py`
- Create: `tests/test_support_triage_tools.py`

**Interfaces:**
- Consumes: `FunctionTool`, `Risk`, `ToolRegistry`, `ToolResult`, `FinalAnswer`, `RunContext`, and `VerificationResult` from `tiny_harness`, plus the Task 1 store.
- Produces: `ALLOWED_CATEGORIES`, `SentReply`, `TriageState`, `build_tools(state=..., tickets=None, policies=None)`, `build_registry(...)`, and `TriageVerifier(state)`.

- [x] **Step 1: Define run-local state and the category allow-list**

`TriageState` holds `category`, `draft_reply`, `sent_replies`, and a `send_calls` counter that the send handler increments on entry. The counter is the laboratory's own spy: a refused run must leave it at zero. `ALLOWED_CATEGORIES` is the fixed tuple `("account_access", "billing", "bug", "how_to")`.

- [x] **Step 2: Build the tools with typed arguments and typed failures**

Every handler validates its arguments through one `_text_argument` helper and returns `ToolResult(ok=False, error=...)` rather than raising. Risk classes are `read_ticket` READ, `search_policy` READ, `set_category` WRITE, `draft_reply` WRITE, and `send_reply` CONSEQUENTIAL. `set_category` rejects any category outside the allow-list and names the allowed values in its error. `send_reply` refuses to send without a known ticket, a category, and a non-blank draft, and otherwise appends one `SentReply` to run-local state without performing real I/O.

- [x] **Step 3: Implement the evidence-based verifier**

`TriageVerifier.verify` ignores the answer text. It returns `VerificationResult(False, ...)` when no category was recorded, `VerificationResult(False, ...)` when no reply was drafted, and only then accepts, naming the recorded category as its reason.

- [x] **Step 4: Test the safety contract and the tool contracts**

Run: `python -m pytest tests/test_support_triage_tools.py -q`

Expected: PASS, eighteen tests. The first asserts the exact `{name: Risk}` mapping, which is the laboratory's safety contract; another asserts `send_reply` is the only consequential tool. The rest cover typed argument rejection, the unknown-ticket failure, provenance in the search output, an empty search reported as success, the category allow-list leaving state untouched on rejection, draft recording, all three `send_reply` refusals and its single success, and the three verifier outcomes.

### Task 3: Script the deterministic demonstration

**Files:**
- Create: `labs/support_triage/demo.py`
- Create: `tests/test_support_triage_demo.py`

**Interfaces:**
- Consumes: `Runner`, `RunConfig`, `RiskPolicy`, `ScriptedModel`, `JsonlEventSink`, `ToolCall`, `FinalAnswer`, `ApprovalCallback`, and the Task 2 laboratory.
- Produces: `scripted_approval(approve)`, `build_demo(trace_path, state=None, approve=True) -> Runner`, `run_demo(trace_path, state=None, approve=True) -> RunResult`, `main()`, and the command `python -m labs.support_triage.demo`.

- [x] **Step 1: Mirror the conventions of `examples/foundations_demo.py`**

`run_demo` removes any previous trace, builds the runner, and runs the task. `main` prints the terminal status, the answer, and the trace path, and writes to `.traces/support_triage.jsonl`. `build_demo` scripts six decisions: `read_ticket`, `search_policy`, `set_category`, `draft_reply`, `send_reply`, then a `FinalAnswer`, under `RunConfig(max_iterations=6)`. The approval callback is a closure over a boolean, so approval is deterministic and the happy path approves.

- [x] **Step 2: Run the demonstration and read the real trace**

Run: `python -m labs.support_triage.demo`

Expected: prints `succeeded`, the T-1042 answer, and `.traces/support_triage.jsonl`.

Run: `python -c 'import json; [print(json.loads(l)["kind"]) for l in open(".traces/support_triage.jsonl")]'`

Expected, twenty-one kinds: `run_started`; then `model_decision`, `policy_decision`, `tool_result` four times; then `model_decision`, `policy_decision`, `approval_requested`, `approval_decision`, `tool_result`; then `model_decision`, `verification`; then `run_finished`.

- [x] **Step 3: Assert both approval outcomes and the failure scenarios**

Run: `python -m pytest tests/test_support_triage_demo.py -q`

Expected: PASS, five tests. They assert the twenty-one-kind approved sequence read from the JSON Lines file plus the sent reply in state; the granted approval payload, search provenance, and run identifier; the refused run ending `APPROVAL_REFUSED` after eighteen kinds with `send_calls == 0` and no sent reply; an invalid category producing `ToolResult(ok=False, ...)` and a run that does not succeed; and a final answer without a draft failing verification.

### Task 4: Add the checked approval-gate exercise

**Files:**
- Create: `course/03-support-triage/exercise.py`
- Create: `course/03-support-triage/check_exercise.py`
- Create: `solutions/03-support-triage/exercise.py`
- Create: `tests/test_support_triage_exercise.py`

**Interfaces:**
- Consumes: `Risk`, `PolicyDecision`, and `ALLOWED_CATEGORIES`.
- Produces: learner function `decide(risk, category, draft) -> PolicyDecision` and a checker runnable from the repository root.

- [x] **Step 1: State the puzzle at the approval boundary**

`decide` receives a risk plus the evidence recorded so far. Non-consequential risks return `ALLOW`. A consequential call with an allow-listed category and a non-blank draft returns `APPROVAL_REQUIRED`. A consequential call missing either piece of evidence returns `DENY`, so a person is never interrupted for a send that would fail. The starter raises `NotImplementedError` with a learner-facing message naming Lesson 3.

- [x] **Step 2: Mirror the Part 2 checker exactly**

`ROOT = Path(__file__).resolve().parents[2]` with `sys.path.insert`, a private `_MissingDecide`, `load_decide` by path with `importlib.util`, one `✓`/`✗` line per case, a `--solution` flag selecting `solutions/` over `course/`, and exit status 1 unless every case passes.

- [x] **Step 3: Verify both learner and contributor experiences**

Run: `python course/03-support-triage/check_exercise.py`

Expected: seven readable `NotImplementedError` lines and exit status 1.

Run: `python course/03-support-triage/check_exercise.py --solution`

Expected: seven `✓` lines and exit status 0.

- [x] **Step 4: Follow the Part 2 exercise-test pattern**

Run: `python -m pytest tests/test_support_triage_exercise.py -q`

Expected: PASS, thirteen selected and eight deselected. The seven-case learner contract and the checker's incomplete-exercise output carry `@pytest.mark.learner`; a separate parametrized test proving the reference solution satisfies the same seven cases runs in the default suite, alongside checker tests for module load failures, a wrong decision, the accepted reference solution, and the rejected learner starter.

Run: `python -m pytest -m learner tests/test_support_triage_exercise.py -q`

Expected: seven failures naming the learner message; this is the intended state of the starter file.

### Task 5: Write the lesson and close the milestone

**Files:**
- Create: `course/03-support-triage/README.md`
- Create: `docs/superpowers/plans/2026-08-27-support-triage-lab.md`

**Interfaces:**
- Consumes: every command and file produced by Tasks 1-4.
- Produces: a learner path from the demonstration through the trace to a passing checker.

- [x] **Step 1: Write the lesson prose**

Open with learning goals; define laboratory, ticket store, policy knowledge base, provenance, run-local state, trace, and approval gate at first use; give the tool-to-risk table; explain why `send_reply` is consequential while `search_policy` is not; give the exact demonstration, trace-inspection, refusal, checker, and solution-checker commands with their expected results; give three progressive hints that do not reveal the final function; link the reference solution; and end with a recap.

- [x] **Step 2: Verify every documented command and relative link**

Ran each command from the repository root and confirmed the printed results, then confirmed every relative Markdown link in the lesson resolves to a real file.

- [x] **Step 3: Run the whole suite**

Run: `python -m pytest -q`

Expected: 118 passed, 12 deselected. The 72 tests from the foundations milestone stay green.

- [x] **Step 4: Commit the laboratory**

```bash
git add docs/superpowers/plans/2026-08-27-support-triage-lab.md labs course/03-support-triage solutions/03-support-triage tests
git commit -m "feat: add support-triage laboratory"
```

- [x] **Step 5: Record what this plan deliberately leaves to a later plan**

The top-level `README.md` still lists Part 3 as upcoming and its course map is unchanged, because this plan may not modify `README.md`. The plan that lands after the remaining laboratories should update the course map, the repository map's description of `labs/`, and the learner-marker note so they name Part 3.
