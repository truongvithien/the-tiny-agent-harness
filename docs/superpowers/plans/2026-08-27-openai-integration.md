# OpenAI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the deterministic scripted model with the official OpenAI SDK through one adapter, without changing any other harness boundary, and without making the default suite depend on a network or a credential.

**Architecture:** A single module, `tiny_harness/openai_adapter.py`, owns both translation directions as small pure functions plus one thin `ModelAdapter` implementation. The SDK client is injected rather than imported, so deterministic tests use a fake client and the default install stays dependency-free. `openai` is an optional extra used only by a lazily-imported environment helper and one opt-in live test.

**Tech Stack:** Python 3.12, standard library, pytest 8, optional `openai>=1.40`, Markdown

**Spec:** `docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md`

## Global Constraints

- Python 3.12 is the documented baseline.
- The default test suite must pass with no network access, no API key, and without the `openai` package installed.
- Credentials are read from the environment only, and never committed, printed, logged, or written into run state or traces.
- The adapter translates contracts; it never authorizes, executes, or verifies.
- Harness-owned types remain the boundary: provider output becomes `ToolCall` or `FinalAnswer`, or is rejected.
- No other `tiny_harness` module changes; the runner, policy, events, and verifier are untouched.
- Live tests are marked `live`, are excluded by the default addopts, and skip when credentials are absent.
- Live assertions check the contract, not exact natural-language wording.

## Planned file map

```text
tiny_harness/openai_adapter.py                 both translation directions and OpenAIModel
course/06-openai-integration/README.md         adapter lesson, credentials, hints
course/06-openai-integration/exercise.py       learner response-translation puzzle
course/06-openai-integration/check_exercise.py standalone learner feedback command
solutions/06-openai-integration/exercise.py    explained reference implementation
tests/test_openai_adapter.py                   deterministic contract tests with a fake client
tests/test_openai_exercise.py                  learner and solution contract tests
tests/test_openai_live.py                      opt-in live run, skipped without a key
pyproject.toml                                 openai optional dependency
```

---

### Task 1: Add the adapter module

**Files:**
- Create: `tiny_harness/openai_adapter.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `RunContext`, `Observation`, `ToolCall`, `FinalAnswer`, `ModelDecision`.
- Produces: `openai_tools`, `openai_messages`, `decode_decision`, `OpenAIModel`, `client_from_environment`, `DEFAULT_SYSTEM_PROMPT`.

- [x] **Step 1: Decide the dependency boundary**

The adapter accepts a duck-typed `client` and imports nothing from `openai` at module scope. This keeps the default install dependency-free and makes the deterministic tests possible. `openai` is imported lazily inside `client_from_environment` only.

- [x] **Step 2: Implement the harness-to-provider direction**

`openai_tools` maps each specification's `input_schema` onto `parameters` inside OpenAI's function shape, and returns `[]` for no tools so the caller can omit the field entirely (OpenAI rejects an empty `tools` list).

`openai_messages` emits one system message containing the instructions, acceptance criteria, and remaining iterations; one user message with the task; then one user message per observation, preserving order and naming its source.

- [x] **Step 3: Implement the provider-to-harness direction**

`decode_decision` accepts a plain mapping so the safety-critical logic is pure and testable. It prefers a tool call over accompanying text because the runner executes at most one action per iteration. It raises `ValueError` for a nameless tool call, arguments that are not valid JSON, arguments that do not decode to an object, and a message with neither a tool call nor usable text. Absent or empty arguments decode to `{}`.

`_response_message` normalizes an SDK response into that mapping, tolerating both attribute-style and mapping-style objects, and raises `ValueError` when there are no choices.

- [x] **Step 4: Add the environment helper**

`client_from_environment` raises `RuntimeError` when `OPENAI_API_KEY` is absent, and a helpful `RuntimeError` when the optional package is missing. It never returns, prints, or embeds the key; the SDK client reads it directly.

- [x] **Step 5: Declare the optional dependency**

Add `openai = ["openai>=1.40"]` to `[project.optional-dependencies]`. Do not add it to `dev`.

### Task 2: Prove the contracts deterministically

**Files:**
- Create: `tests/test_openai_adapter.py`
- Create: `tests/test_openai_live.py`

**Interfaces:**
- Consumes: the adapter, plus the public `Runner`, `RiskPolicy`, `ToolRegistry`, and `JsonlEventSink`.
- Produces: a fake client shaped like the SDK response, and one opt-in live scenario.

- [x] **Step 1: Build the fake client**

Small frozen dataclasses mirror the SDK shape (`choices[0].message.tool_calls[].function.{name,arguments}`) and record every outgoing request so translation can be asserted.

- [x] **Step 2: Cover both directions and every rejection**

Tests assert the translated tool shape, the empty-tools case, message ordering with observations, a custom system prompt, and each `decode_decision` outcome: JSON arguments, pre-decoded arguments, absent arguments, malformed JSON, non-object arguments, a nameless call, final answer text, tool-call precedence over text, empty messages, and a non-mapping message.

- [x] **Step 3: Prove harness compatibility end to end**

One test drives a real `Runner` with `OpenAIModel` and the fake client and asserts the seven canonical event kinds from the written JSON Lines trace, confirming the adapter satisfies the same contract as `ScriptedModel`.

- [x] **Step 4: Prove credentials cannot reach a trace**

One test runs with a fake secret in the task and a sink configured to redact it, then asserts the secret does not appear anywhere in the trace file. Another asserts `client_from_environment` raises when the key is absent.

- [x] **Step 5: Add the opt-in live test**

`tests/test_openai_live.py` carries `pytest.mark.live` plus a skip when `OPENAI_API_KEY` is absent. It asserts the run succeeded and a tool actually executed, never exact wording, and allows model override via `TINY_HARNESS_LIVE_MODEL`.

Run: `python -m pytest tests/test_openai_adapter.py -v`

Expected: PASS with no key, no network, and no `openai` package.

Run: `python -m pytest -m live -v`

Expected: one SKIPPED entry when no key is set.

### Task 3: Write the lesson and the learner puzzle

**Files:**
- Create: `course/06-openai-integration/README.md`
- Create: `course/06-openai-integration/exercise.py`
- Create: `course/06-openai-integration/check_exercise.py`
- Create: `solutions/06-openai-integration/exercise.py`
- Create: `tests/test_openai_exercise.py`

**Interfaces:**
- Consumes: `ToolCall`, `FinalAnswer`, `ModelDecision`.
- Produces: learner function `decode_decision(message) -> ModelDecision`; a standalone checker runnable from the repository root.

- [x] **Step 1: Choose the puzzle at the risk-bearing boundary**

The learner implements the provider-to-harness direction, because that is where untrusted output becomes harness data. The starter raises `NotImplementedError` with a lesson-facing message and documents both input shapes in its docstring.

- [x] **Step 2: Mirror the Part 2 checker**

`check_exercise.py` resolves `ROOT` via `parents[2]`, inserts it on `sys.path`, prints one ✓ or ✗ per case, supports `--solution`, and exits 1 unless every case passes. Cases include the two success shapes, tool-call precedence, and three rejections, so a partial implementation cannot pass.

- [x] **Step 3: Split learner and contributor suites**

The three incomplete-learner tests carry `@pytest.mark.learner` and are excluded by the default addopts. Separate solution-contract tests stay in the default suite, so a fresh clone is green. Both load exercise files by path with `importlib.util`, because hyphenated course directories are not importable packages.

- [x] **Step 4: Write the lesson**

The lesson states learning goals, defines *model adapter* and *credential* at first use, shows both translation directions, explains why a returned `ToolCall` is still only a request, gives exact commands with expected results, supplies three progressive hints that do not reveal the function, then links the solution and ends with a recap.

- [x] **Step 5: Verify both learner and contributor experiences**

Run: `python course/06-openai-integration/check_exercise.py`

Expected before solving: seven readable failures and exit status 1.

Run: `python course/06-openai-integration/check_exercise.py --solution`

Expected: seven passes and exit status 0.

Run: `python -m pytest -q`

Expected: PASS, with the learner and live tests deselected.

### Task 4: Record the remaining boundary

- [x] **Step 1: Note what this plan deliberately leaves out**

Multiple live providers, streaming, retries with backoff, token accounting, and structured-output modes are out of scope. The next and final plan is `capstone-and-course-qa`, which adds the extension rubric, the whole-course navigation pass (including the Part 6 to Part 7 link this plan intentionally omits), and cross-platform command verification.
