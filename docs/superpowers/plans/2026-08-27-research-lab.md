# Research Laboratory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Part 4 of the course, in which the shared harness runs against a local HTTP document server holding conflicting and incomplete synthetic sources, and completion is granted only when every recorded claim cites a source the run actually fetched.

**Architecture:** The Part 2 core is reused unchanged. A standard-library `HTTPServer` bound to an ephemeral loopback port serves parsed Markdown sources as JSON. Three read-only tools list, fetch, and cite those sources, keeping fetch provenance and recorded claims in a run-local `ResearchNotebook`. A `CitedClaims` verifier reads that notebook rather than the model's prose, so evidence — not assertion — decides success. A scripted demonstration and a checked learner puzzle teach the same evidence boundary.

**Tech Stack:** Python 3.12, standard library (`http.server`, `urllib`, `json`, `threading`), pytest 8, JSON Lines, Markdown

**Spec:** `docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md` — "Part 4: Research laboratory", "Local mock infrastructure", "State and event model", "Testing strategy"

## Global Constraints

- Python 3.12 is the documented baseline.
- Standard-library features only; no new dependency is introduced.
- No network access beyond loopback, and no credentials.
- The document server binds `127.0.0.1` on port 0 and is never given a fixed port.
- One command or context manager starts the server and cleans it up, including on failure.
- No test may leave a serving thread or a listening socket behind.
- `tiny_harness/`, `README.md`, `pyproject.toml`, `.gitignore`, `examples/`, Parts 1-2, and existing tests are not modified.
- `labs/` stays an implicit namespace package: no `labs/__init__.py`, so parallel laboratory branches cannot conflict over one file.
- Every tool in this laboratory is `Risk.READ`; the lab has no consequential action and no approval gate.
- Failures and budget exhaustion can never be reported as success.
- Learner work is marked `learner` and excluded from the default suite; a separate reference-solution test stays in it.

## Planned file map

```text
docs/superpowers/plans/2026-08-27-research-lab.md   this plan
labs/research/__init__.py                           lab public surface
labs/research/data/marsh-survey-2024.md             128 pairs; conflicts with the atlas; long enough to truncate
labs/research/data/regional-bird-atlas.md           96 pairs; conflicts with the survey
labs/research/data/warden-field-notes.md            incomplete source: no season total
labs/research/data/survey-method-manual.md          method background
labs/research/data/marsh-habitat-guide.md           habitat background, no counts
labs/research/data/visitor-leaflet.md               confident prose with no evidence
labs/research/server.py                             ephemeral-port loopback document server
labs/research/tools.py                              list_sources, fetch_source, record_claim, notebook
labs/research/verification.py                       unsupported_source_ids and CitedClaims
labs/research/demo.py                               scripted demonstration and main()
course/04-research-agent/README.md                        lesson prose, commands, hints
course/04-research-agent/exercise.py                      learner evidence puzzle
course/04-research-agent/check_exercise.py                standalone learner feedback command
solutions/04-research-agent/exercise.py                   explained reference implementation
tests/test_research_server.py                       binding, routing, 404, and cleanup tests
tests/test_research_tools.py                        tool contract, truncation, and verifier tests
tests/test_research_demo.py                         end-to-end scenario and trace assertions
tests/test_research_exercise.py                     learner exercise contract tests
```

---

### Task 1: Serve synthetic sources from an ephemeral loopback port

**Files:**
- Create: `labs/research/data/*.md`
- Create: `labs/research/server.py`
- Create: `tests/test_research_server.py`

**Interfaces:**
- Consumes: `http.server.HTTPServer`, `pathlib`, `threading`.
- Produces: `Document`, `parse_document(source_id, raw)`, `load_documents(directory)`, `DocumentServer` with `.port`/`.base_url`/`.start()`/`.stop()` and the context-manager protocol, and `serve_documents(directory, *, host)`.

- [x] **Step 1: Write six synthetic sources including a conflicting pair and an incomplete source**

`marsh-survey-2024` reports 128 nesting pairs and declares `Conflicts-With: regional-bird-atlas`; `regional-bird-atlas` reports 96 and declares the reverse. `warden-field-notes` is about the same survey but holds no total. `survey-method-manual`, `marsh-habitat-guide`, and `visitor-leaflet` supply method, background, and confident-but-unsourced prose. `marsh-survey-2024` is written longer than the fetch character limit so truncation is observable in a real trace.

- [x] **Step 2: Write the server tests first**

Assert that the data set has at least five documents with a symmetric declared conflict and an incomplete source; that `parse_document` splits title, `Conflicts-With:`, and prose; that the server binds `127.0.0.1` on a non-zero port; that two servers get different ports; that `/sources` and `/sources/<id>` serve fixtures; that an unknown id is HTTP 404; and that after the `with` block — including one exited by an exception — no new thread remains and the port refuses a connection.

Expected before implementation: FAIL, because `labs.research.server` does not exist.

- [x] **Step 3: Implement parsing and the server**

Metadata is declared in the document, not in code, so conflicts are data. The handler serves JSON, logs nothing, and sends `Content-Length`. A plain `HTTPServer` (not the threading variant) is used so exactly one serving thread exists and `stop()` can join it. `serve_forever` polls at 0.02 s so shutdown is prompt in tests.

- [x] **Step 4: Confirm no leaked thread or socket**

Run: `python -m pytest tests/test_research_server.py -q`

Expected: PASS, and the suite exits without hanging.

### Task 2: Add read-only research tools with an explicit context limit

**Files:**
- Create: `labs/research/tools.py`
- Create: `tests/test_research_tools.py`

**Interfaces:**
- Consumes: `FunctionTool`, `Risk`, `ToolRegistry`, `ToolResult` from `tiny_harness`; the server's route constants.
- Produces: `MAX_SOURCE_CHARACTERS`, `TRUNCATION_NOTICE`, `truncate_source_text`, `Claim`, `FetchedSource`, `ResearchNotebook`, `make_list_sources`, `make_fetch_source`, `make_record_claim`, `build_research_tools(base_url, notebook)`.

- [x] **Step 1: Write the tool contract tests**

Assert that all three tools are `Risk.READ`; that `fetch_source` returns the source id and URL alongside the text; that an unknown id becomes `ToolResult(ok=False, error="unknown source: …")` rather than an exception; that a long document is cut at `MAX_SOURCE_CHARACTERS` and ends with the marker naming that limit; that a short document is untouched; and that `record_claim` refuses a citation for a source not fetched in this run.

- [x] **Step 2: Implement the notebook and the three tools**

The notebook holds fetch provenance and claims for one run only. `conflicting_fetched_sources` is symmetric and returns only sources fetched in this run, so a conflict is invisible until both sides have been read. `fetch_source` maps HTTP 404 to a plain failure and every other `OSError` to a retryable failure; it never raises at the tool boundary.

- [x] **Step 3: Classify every tool `READ` and justify it**

`record_claim` mutates only run-local memory, so `READ` is honest and the laboratory has no approval gate. The lesson states what would make it `WRITE`.

- [x] **Step 4: Run the tool tests**

Run: `python -m pytest tests/test_research_tools.py -q`

Expected: PASS.

### Task 3: Verify completion from captured evidence

**Files:**
- Create: `labs/research/verification.py`
- Modify: `tests/test_research_tools.py`

**Interfaces:**
- Consumes: `FinalAnswer`, `RunContext`, `VerificationResult`, `Claim`, `ResearchNotebook`.
- Produces: `unsupported_source_ids(claims, fetched_source_ids)` and `CitedClaims(notebook).verify(context, answer)`.

- [x] **Step 1: Write verifier tests for every rejection and the acceptance**

Reject zero claims; reject a claim citing an unfetched source; reject a contradicted claim that is not marked `disputed`; reject a disputed claim whose report does not name the contradicting source; accept a properly cited set.

- [x] **Step 2: Implement the four ordered rules**

In order: at least one claim; every citation fetched; every contradicted claim marked `disputed`; the report text names every source behind its claims, including each contradicting source. Rule 3 is the uncertainty rule and rule 4 stops a conflict from being admitted privately and hidden from the reader.

- [x] **Step 3: Record the uncertainty design decision**

Chosen: `record_claim` carries a `disputed` flag and the verifier enforces it. Documented simplifications: conflicts are declared between whole documents rather than individual figures, and a conflict only exists once both sources are in the notebook.

- [x] **Step 4: Run the verifier tests**

Run: `python -m pytest tests/test_research_tools.py -q`

Expected: PASS.

### Task 4: Publish the deterministic demonstration

**Files:**
- Create: `labs/research/demo.py`
- Create: `labs/research/__init__.py`
- Create: `tests/test_research_demo.py`

**Interfaces:**
- Consumes: the public `tiny_harness` API, the server, the tools, and the verifier.
- Produces: `DEMO_DECISIONS`, `build_demo(trace_path, base_url, decisions)`, `run_with_decisions(trace_path, decisions)`, `run_demo(trace_path)`, `main()`, and the command `python -m labs.research.demo`.

- [x] **Step 1: Script one run that selects part of the context and reports a dispute**

Six tool calls then a final answer: list all six sources, fetch three of them, record a disputed count claim citing `marsh-survey-2024`, record an undisputed method claim citing `survey-method-manual`, then report both figures with all three source ids.

- [x] **Step 2: Write the end-to-end tests**

Assert the exact 22-event kind sequence read from the real JSONL trace; assert the trace carries `source_id`, the `/sources/<id>` URL, the character limit, the declared conflict, and the truncation marker; assert three of six sources were fetched.

- [x] **Step 3: Add the failure scenarios**

A hidden conflict finishes `failed` naming the contradicting source; a disputed claim whose report omits that source finishes `failed`; a claim citing an unfetched source is refused at the tool and the run finishes `failed` with no evidence; a confident answer with no claims at all finishes `failed`.

- [x] **Step 4: Guarantee shutdown around every run**

`run_with_decisions` owns the `with serve_documents()` block, so the demo and every scenario test stop the server even when the run raises.

- [x] **Step 5: Run the demonstration and read its trace**

Run: `python -m labs.research.demo`

Expected: prints `succeeded`, a report naming `marsh-survey-2024`, `regional-bird-atlas`, and `survey-method-manual`, then `.traces/research.jsonl`.

Run: `python -c 'import json; print([json.loads(line)["kind"] for line in open(".traces/research.jsonl")])'`

Expected: the 22 kinds asserted by the test.

### Task 5: Create Part 4 with a checked evidence puzzle

**Files:**
- Create: `course/04-research-agent/exercise.py`
- Create: `course/04-research-agent/check_exercise.py`
- Create: `solutions/04-research-agent/exercise.py`
- Create: `tests/test_research_exercise.py`
- Create: `course/04-research-agent/README.md`

**Interfaces:**
- Consumes: `Claim` from `labs.research.tools`.
- Produces: learner function `unsupported_source_ids(claims, fetched_source_ids) -> tuple[str, ...]`; a standalone checker runnable from the repository root.

- [x] **Step 1: Write the learner and reference contract tests**

Five cases: no claims; a supported claim; an unsupported claim; a repeated missing id reported once in claim order; nothing fetched at all. The learner test carries `@pytest.mark.learner`; a separate reference-solution test over the same cases stays in the default suite. Both load their exercise file by path with `importlib.util`, because hyphenated course directories are not importable.

- [x] **Step 2: Add the deliberately incomplete starter**

`course/04-research-agent/exercise.py` raises `NotImplementedError("complete the evidence check from Lesson 4")`.

Run: `python -m pytest -m learner tests/test_research_exercise.py -q`

Expected: FAIL with that learner-facing message.

- [x] **Step 3: Add the checker and the reference solution**

`check_exercise.py` mirrors `course/02-tiny-core/check_exercise.py`: `ROOT` from `Path(__file__).resolve().parents[2]`, `sys.path.insert`, one `✓`/`✗` per case, a `--solution` flag, and exit 1 unless every case passes. Tests cover the incomplete output, three module-load failures reported without a traceback, and a subprocess run in each mode.

- [x] **Step 4: Write the lesson**

`course/04-research-agent/README.md` opens with learning goals; defines mock infrastructure, context, and provenance at first use; tabulates the six sources and the tool-to-risk mapping; explains why every tool is `READ` yet verification is still required, and how provenance differs from confident prose; gives the exact demo, trace, and checker commands with expected results; offers three progressive hints that describe the shape of the solution without writing it; links the reference solution afterwards; and ends with a recap.

- [x] **Step 5: Verify both learner and contributor experiences**

Run: `python course/04-research-agent/check_exercise.py`

Expected: five readable failures and exit status 1.

Run: `python course/04-research-agent/check_exercise.py --solution`

Expected: five passes and exit status 0.

Run: `python -m pytest -q`

Expected: PASS, with the original 72 tests still green.

### Task 6: Close out the laboratory

**Files:**
- Modify: `docs/superpowers/plans/2026-08-27-research-lab.md`

**Interfaces:**
- Consumes: every file created above.
- Produces: a verified, committed Part 4.

- [x] **Step 1: Confirm `labs` remains a namespace package**

Assert `labs.__file__ is None` and that `from labs.research... import ...` works with no `labs/__init__.py`.

- [x] **Step 2: Check every relative Markdown link**

A standard-library link check over all tracked Markdown extracts relative links and asserts each target exists. 34 links resolve; none broken.

- [x] **Step 3: Run the full suite and confirm it exits cleanly**

Run: `python -m pytest -q`

Expected: 117 passed, 10 deselected, no hang.

- [x] **Step 4: Commit the laboratory**

```bash
git add docs/superpowers/plans labs course/04-research-agent solutions/04-research-agent tests
git commit -m "feat: add research laboratory"
```

- [ ] **Step 5: Fold Part 4 into the course entry point**

`README.md` still lists Part 4 as upcoming and does not link the lesson, and Part 3 exists only on its own branch. Updating the shared course map and its cross-links belongs to the branch that integrates the laboratories, not to this one.
