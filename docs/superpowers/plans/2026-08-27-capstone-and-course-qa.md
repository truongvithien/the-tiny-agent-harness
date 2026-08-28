# Capstone and Course QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the course. Add a capstone that proves the harness can be extended without editing the runner, connect all seven parts into one navigable path, and add a single command that checks the repository the way a new learner meets it.

**Architecture:** The capstone introduces an argument-aware policy — the first policy in the course to read a call's arguments rather than only its tool's risk class — governing a new consequential `issue_refund` tool. Scenario tests drive it through the real `Runner` to show deny, refuse, and approve paths, and one test reads the runner's source to prove it was not modified. A standard-library `scripts/verify_course.py` performs whole-course consistency checks, and `tests/test_course_navigation.py` makes those checks part of the default suite.

**Tech Stack:** Python 3.12, standard library, pytest 8, Markdown

**Spec:** `docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md`

## Global Constraints

- Python 3.12 is the documented baseline.
- The capstone must be completable by extending an existing tool or policy without changing `tiny_harness/runner.py`.
- The rubric rewards clear contracts and evidence rather than feature count.
- Denial must be proved by absence of effect, not by a returned decision object.
- The default suite stays offline, deterministic, and green on a fresh clone.
- Course directory names follow the specification's repository organization.
- No credential, trace, temporary workspace, or learner-local file becomes tracked.

## Planned file map

```text
course/07-capstone/README.md                    rubric, warm-up, and extension guide
course/07-capstone/exercise.py                  learner argument-aware policy puzzle
course/07-capstone/check_exercise.py            standalone learner feedback command
solutions/07-capstone/exercise.py               reference implementation
tests/test_capstone_exercise.py                 learner, solution, and scenario contracts
scripts/verify_course.py                        whole-course consistency gate
tests/test_course_navigation.py                 makes the gate and navigation enforceable
README.md                                       complete seven-part course map
course/02-tiny-core/README.md                   forward link to Part 3
course/03-support-triage/README.md              forward link to Part 4
course/04-research-agent/README.md              forward link to Part 5
course/05-coding-agent/README.md                forward link to Part 6
course/06-openai-integration/README.md          forward link to Part 7
```

---

### Task 1: Add the capstone extension and its evidence

**Files:**
- Create: `course/07-capstone/exercise.py`
- Create: `solutions/07-capstone/exercise.py`
- Create: `course/07-capstone/check_exercise.py`
- Create: `tests/test_capstone_exercise.py`

**Interfaces:**
- Consumes: `FunctionTool`, `Policy`, `PolicyDecision`, `Risk`, `Tool`, `ToolCall`, `ToolResult`, and the public `Runner`.
- Produces: `MAX_AUTOMATIC_REFUND`, `RefundLedger`, `build_refund_tool(ledger)`, and `RefundPolicy.evaluate(tool, call)`.

- [x] **Step 1: Choose an extension that needs a new kind of decision**

`RiskPolicy` discards the call with `del call`, so nothing in Parts 1 to 6 inspects arguments. Refund size is a property of the call, not of the tool, which makes an argument-aware policy the smallest extension that teaches something genuinely new while remaining additive.

- [x] **Step 2: Define the contract**

`issue_refund` is `CONSEQUENTIAL` with a closed `input_schema` over `ticket_id` and `amount`. `RefundPolicy` allows any read or write, denies an `issue_refund` whose `amount` is missing, non-numeric, negative, or above `MAX_AUTOMATIC_REFUND`, and requires approval for every other consequential call.

- [x] **Step 3: Guard the argument checks against untrusted input**

Arguments originate from a model, so the reference implementation rejects rather than coerces, and excludes `bool` explicitly because `isinstance(True, int)` is `True` in Python.

- [x] **Step 4: Prove the boundary by absence of effect**

Three scenario tests drive the policy through the real `Runner` with a `RefundLedger` as the effect witness: an over-limit refund ends `POLICY_DENIED` with an empty ledger and a trace stopping at `policy_decision`; a within-limit refund with approval refused ends `APPROVAL_REFUSED` with an empty ledger; an approved within-limit refund ends `SUCCEEDED` with one ledger entry. Event-kind sequences are asserted, not assumed.

- [x] **Step 5: Prove the runner did not change**

One test reads `tiny_harness/runner.py` with `inspect.getsource` and asserts it mentions neither the new tool, the new policy, nor its constant, satisfying the specification's tenth acceptance criterion.

- [x] **Step 6: Split learner and contributor suites**

Three incomplete-learner tests carry `@pytest.mark.learner`; ten parametrized solution-contract cases and the scenario tests stay in the default suite. The checker mirrors Part 2, supports `--solution`, and exits 1 unless all nine cases pass.

### Task 2: Write the capstone lesson and rubric

**Files:**
- Create: `course/07-capstone/README.md`

- [x] **Step 1: State the purpose and the deliverables**

The lesson defines *risk classification*, *denial test*, and *argument-aware policy* at first use, and asks for five deliverables: a contract, a justified risk classification, a success test and a denial test, one scenario run with its trace, and a written boundary statement including limits.

- [x] **Step 2: Write the rubric as observable criteria**

Six criteria — contract clarity, risk justification, denial evidence, trace reading, honest limits, and runner untouched — each with a strong and a weak description. Marks reward contracts and evidence rather than feature count.

- [x] **Step 3: Name the two failure modes explicitly**

Enforcing a rule in the prompt instead of in a policy, and claiming completion without evidence. Both are mistakes the earlier parts exist to prevent.

- [x] **Step 4: Supply hints without revealing the answer**

Three progressive hints move from the trivial non-consequential case, to checking the tool name before its arguments, to the untrusted-input and `bool` pitfalls.

### Task 3: Add the whole-course quality gate

**Files:**
- Create: `scripts/verify_course.py`
- Create: `tests/test_course_navigation.py`

- [x] **Step 1: Check what a new learner would hit first**

The script enumerates tracked files with `git ls-files` and checks: all seven parts have a lesson; every exercise has a checker and a reference solution; the README course map links every part; every relative Markdown link resolves; no trace, environment, or cache is tracked; and no tracked file contains an API-key pattern. It prints one ✓ or ✗ per check and exits non-zero on any failure.

- [x] **Step 2: Make the gate enforceable rather than advisory**

`tests/test_course_navigation.py` runs the script as a subprocess and asserts exit status 0, asserts the seven part directories, asserts each lesson links to the next, asserts every part after the first has an exercise/checker/solution trio, and asserts the README documents all four demonstration commands.

- [x] **Step 3: Note the gate's own boundary**

The script only sees tracked files, so it must be run after staging new work; otherwise new files are silently skipped. Staging before verification is part of Task 5.

### Task 4: Connect the course into one path

**Files:**
- Modify: `README.md`
- Modify: `course/02-tiny-core/README.md`
- Modify: `course/03-support-triage/README.md`
- Modify: `course/04-research-agent/README.md`
- Modify: `course/05-coding-agent/README.md`
- Modify: `course/06-openai-integration/README.md`

- [x] **Step 1: Replace the placeholder course map**

Parts 3 to 7 were listed as "upcoming until its plan lands" because each laboratory was built on its own branch and forbidden from editing shared files. Each entry now links its lesson with a one-line description, and the three laboratory demonstration commands are documented together.

- [x] **Step 2: Correct the offline and credential wording**

The README no longer describes Part 6 in the future tense. It states that Parts 1 to 5 and 7 need no network or credentials, that Part 6's contract tests run offline with a fake client, and that only its `live`-marked test needs a key and skips without one.

- [x] **Step 3: Extend the repository map**

Add `labs/` and `scripts/`, and describe `tiny_harness/` as shared by every part.

- [x] **Step 4: Wire forward navigation**

Each laboratory branch could only link backwards, because its successor's directory did not exist on that branch. Add the 2→3, 3→4, 4→5, 5→6, and 6→7 links, completing a path a learner can follow without returning to the README.

### Task 5: Verify the finished course

- [x] **Step 1: Stage the new work before verifying**

Because the gate reads `git ls-files`, run `git add` first so new lessons, scripts, and solutions are actually inspected.

- [x] **Step 2: Run every gate**

Run: `python scripts/verify_course.py` — expected: six passing checks, exit 0.

Run: `python -m pytest -q` — expected: the whole default suite passes.

Run: `python -m pytest -m learner -q` — expected: only intentionally incomplete learner contracts fail.

Run each of the four demonstrations and each of the six checkers in both modes.

- [x] **Step 3: Confirm the specification's acceptance criteria**

All ten first-release criteria are satisfied: documented setup, a demonstration and a checked exercise in every part, one shared core across all three cases, an offline default suite, a JSON Lines trace per run, policy tests covering allow/deny/approval, proven workspace containment, deterministic adapter tests plus one opt-in live run, no tracked credentials or generated output, and a capstone completable without changing the runner.
