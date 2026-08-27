# Software-Development Laboratory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Part 5 of the course: an offline laboratory in which the shared harness edits a temporary copy of a tiny fixture repository, proves in tests that neither file access nor command execution can leave that copy, and accepts completion only when an allow-listed check actually passed.

**Architecture:** `labs/coding/` supplies case-specific tools, a stricter policy, and an evidence-backed verifier to the unmodified `tiny_harness` core. `workspace.py` copies the fixture into an operating-system temporary directory and owns the single containment function every tool must call; `policy.py` denies out-of-scope paths and non-allow-listed commands before any effect; `tools.py` exposes three read tools, one reversible write tool, and one allow-listed command runner with a timeout; `verification.py` accepts a final answer only from a recorded passing check. A scripted model makes the demonstration and every test deterministic, and the learner exercise isolates the containment predicate.

**Tech Stack:** Python 3.12, standard library (`pathlib`, `shutil`, `tempfile`, `subprocess`, `unittest`), pytest 8, JSON Lines, Markdown

**Spec:** `docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md` — "Part 5: Software-development laboratory", the policy and approval model, error handling and stopping conditions, and the testing strategy.

## Global Constraints

- Python 3.12 is the documented baseline; standard-library features only.
- `tiny_harness/`, `README.md`, `pyproject.toml`, `.gitignore`, `examples/`, `course/01-*`, `course/02-*`, and all existing tests are unchanged.
- `labs` is an implicit namespace package: no `labs/__init__.py`, so parallel laboratory branches cannot conflict.
- The default suite stays offline and deterministic: no network, no Git, no credentials, no clock or ordering assumptions.
- The agent works only on a temporary copy; the course repository is never modified by a run or a test.
- Commands are executed as argument lists with `shell=False`, from a Python allow-list, under a timeout.
- Policy is enforced by Python code, not by prompt text; a `DENY` ends the run before any effect.
- Verification requires captured evidence; a model's claim of success can never produce `RunStatus.SUCCEEDED`.
- Every temporary workspace is removed even when a run raises.
- The learner contract is marked `learner` and excluded from the default selection; a separate default-suite test proves the reference solution satisfies the same contract.

## Planned file map

```text
docs/superpowers/plans/2026-08-27-coding-lab.md   this plan
labs/coding/__init__.py                           laboratory package marker
labs/coding/fixture_repo/README.md                fixture description and check command
labs/coding/fixture_repo/wordcount.py             one function with one deliberate bug
labs/coding/fixture_repo/test_wordcount.py        three stdlib tests, two failing
labs/coding/workspace.py                          temporary copy, path resolution, containment
labs/coding/policy.py                             WorkspacePolicy: scope and allow-list denials
labs/coding/tools.py                              read, write, and allow-listed check tools
labs/coding/verification.py                       check ledger and evidence-backed verifier
labs/coding/demo.py                               deterministic scripted demonstration
course/05-coding-agent/README.md                        Part 5 lesson, hints, and commands
course/05-coding-agent/exercise.py                      learner containment puzzle
course/05-coding-agent/check_exercise.py                standalone learner feedback command
solutions/05-coding-agent/exercise.py                   explained reference implementation
tests/test_coding_workspace.py                    containment and lifecycle tests
tests/test_coding_policy.py                       scope and allow-list decision tests
tests/test_coding_tools.py                        tool contract, refusal, and timeout tests
tests/test_coding_demo.py                         scenario and trace-sequence tests
tests/test_coding_exercise.py                     learner and reference contract tests
```

---

### Task 1: Read the committed interfaces and record the baseline

**Files:**
- Read only.

**Interfaces:**
- Consumes: the spec, `tiny_harness/*.py`, `examples/foundations_demo.py`, `course/02-tiny-core/*`, `solutions/02-tiny-core/exercise.py`, `tests/test_foundations_demo.py`, `tests/test_course_exercise.py`, `pyproject.toml`.
- Produces: the exact signatures and event kinds this laboratory must bind to.

- [x] **Step 1: Read the Part 5 section, policy model, error handling, and testing strategy in the spec**

- [x] **Step 2: Read every core module for real signatures**

Confirmed keyword-only `Runner`, `RunConfig` validation, the five `RunStatus` members, `FunctionTool`/`ToolRegistry` behavior, `ToolResult`'s error requirement, `RiskPolicy` allowing `WRITE`, and the `Policy`/`Verifier` protocols.

- [x] **Step 3: Record the baseline suite result**

Run: `python -m pytest -q`

Expected: `72 passed, 4 deselected`. Observed: `72 passed, 4 deselected`.

### Task 2: Add the fixture repository

**Files:**
- Create: `labs/coding/__init__.py`
- Create: `labs/coding/fixture_repo/README.md`
- Create: `labs/coding/fixture_repo/wordcount.py`
- Create: `labs/coding/fixture_repo/test_wordcount.py`

**Interfaces:**
- Consumes: the standard-library `unittest` runner.
- Produces: a project whose documented check command fails before an edit and passes after one.

- [x] **Step 1: Write one buggy function and three tests**

`count_words` splits on the single-space string, so it miscounts repeated, tabbed, and blank whitespace. Two of three tests fail.

- [x] **Step 2: Choose a standard-library check command**

`python -m unittest discover -p 'test_*.py'` needs no third-party runner, no configuration file, and no rootdir discovery, so it cannot interact with the course's own pytest configuration. The fixture stays flat so `discover` puts the workspace root on the child's import path.

- [x] **Step 3: Confirm the fixture fails before any edit**

Run the check command inside the fixture directory.

Expected: `FAILED (failures=2)` and exit status 1. Observed exactly that, and the resulting `__pycache__` directory was removed from the source tree.

### Task 3: Build the workspace and its containment function

**Files:**
- Create: `labs/coding/workspace.py`
- Create: `tests/test_coding_workspace.py`

**Interfaces:**
- Consumes: `pathlib`, `shutil`, `tempfile`.
- Produces: `is_inside`, `PathEscapesWorkspace`, `Edit`, and `Workspace` with `from_fixture`, `resolve`, `relative`, `list_files`, `read_file`, `write_file`, `search_text`, `edits`, `revert_last`, `revert_all`, `cleanup`, and context-manager support.

- [x] **Step 1: Implement one containment predicate**

`is_inside` resolves the root, joins a relative candidate to that resolved root, resolves the candidate, and returns `Path.is_relative_to`. Resolving both sides is required because a macOS temporary directory is reached through a symbolic link; comparing components rather than string prefixes is required because `/tmp/ws-evil` starts with `/tmp/ws`.

- [x] **Step 2: Route every path through `Workspace.resolve`**

`resolve` raises `PathEscapesWorkspace` for any candidate `is_inside` rejects, and it is the only place a proposed path becomes a real path. Listings skip symbolic links and `__pycache__` so a link created inside the workspace cannot be offered to a later read.

- [x] **Step 3: Make edits reversible and the workspace disposable**

`write_file` records the previous content, or `None` for a new file. `revert_last` and `revert_all` restore those bytes. `cleanup` removes the tree, and `__exit__` calls it so a raising run still cleans up.

- [x] **Step 4: Write the containment tests**

Covers `..` traversal including `a/../../..`, absolute paths outside (including a real repository file), a directory symlink escape, a file symlink escape that must not overwrite its target, the `ws` versus `ws-evil` sibling case with an explicit assertion that a string prefix would have accepted it, accepted in-scope paths, writes landing in the copy while the fixture's content and mtime are unchanged, reversible edits, cleanup, context-manager cleanup after a failure, search behavior, and typed errors for a missing file and a non-directory.

Run: `python -m pytest tests/test_coding_workspace.py -q`

Expected: PASS. Observed: `28 passed`.

### Task 4: Add the evidence ledger and verifier

**Files:**
- Create: `labs/coding/verification.py`

**Interfaces:**
- Consumes: `FinalAnswer`, `RunContext`, `VerificationResult`.
- Produces: `CheckRecord`, `CheckLedger`, `PassingCheckRequired`.

- [x] **Step 1: Record only what a command reported**

`CheckRecord` holds the command, exit code, and captured output; `passed` means exit code 0. Only `run_check` writes records, so nothing in a model's answer can create one.

- [x] **Step 2: Accept a final answer only from a passing latest record**

`PassingCheckRequired.verify` returns `no allow-listed check ran in this run` when the ledger is empty and `the last check exited with N: ...` when the latest record failed, so a later regression cannot be excused by an earlier pass.

### Task 5: Build the laboratory tools

**Files:**
- Create: `labs/coding/tools.py`
- Create: `tests/test_coding_tools.py`

**Interfaces:**
- Consumes: `Workspace`, `CheckLedger`, `FunctionTool`, `Risk`, `ToolRegistry`, `ToolResult`, `subprocess`.
- Produces: `CHECK_COMMAND`, `ALLOWED_COMMANDS`, `is_allowed_command`, `resolve_program`, `check_environment`, `build_list_files`, `build_read_file`, `build_search_text`, `build_write_file`, `build_run_check`, `build_tools`.

- [x] **Step 1: Declare the allow-list as data**

`ALLOWED_COMMANDS` holds complete argument tuples. `is_allowed_command` rejects `str` and `bytes` outright, rejects non-string members, and otherwise tests exact tuple membership. `resolve_program` substitutes the running interpreter for the leading `python` so the allow-list can stay a literal.

- [x] **Step 2: Implement the three read tools and the write tool**

Each converts `PathEscapesWorkspace`, invalid arguments, and `OSError` into `ToolResult(ok=False, ...)` with a readable message rather than raising.

- [x] **Step 3: Implement `run_check` with a timeout and a clean environment**

`subprocess.run(argv, cwd=workspace.root, shell=False, timeout=...)` with `PYTHONPATH` removed and `PYTHONDONTWRITEBYTECODE=1` set. A non-allow-listed command and a timeout are typed failures that write nothing to the ledger. A completed check is a successful tool result whose output states `check passed with exit code 0` or `check failed with exit code 1`, because the tool performed its bounded action either way.

- [x] **Step 4: Classify `run_check` as `WRITE` and justify it in the lesson**

It runs one fully specified allow-listed command inside a disposable directory with no network and no Git, under a timeout, so its worst outcome is a change inside a tree that is deleted. Requiring approval for the most repeated action in the laboratory would train approval fatigue. The lesson states that the classification depends on the allow-list's contents.

- [x] **Step 5: Write the tool tests**

Covers the risk table, read outputs, refusals for out-of-scope paths with no file created outside, typed failures for invalid arguments, a reversible write, a captured failing check, a captured passing check after the fix, refusals for `git`, `curl`, unlisted `python` commands, shell strings and an empty list, an enforced 0.3-second timeout against an injected sleeping command, no bytecode cache left in the workspace, `is_allowed_command` truth table, `resolve_program`, and `check_environment`.

Run: `python -m pytest tests/test_coding_tools.py -q`

Expected: PASS. Observed: `40 passed`.

### Task 6: Add the workspace policy

**Files:**
- Create: `labs/coding/policy.py`
- Create: `tests/test_coding_policy.py`

**Interfaces:**
- Consumes: `Workspace`, `is_inside`, `ALLOWED_COMMANDS`, `is_allowed_command`, `PolicyDecision`, `Risk`, `Tool`, `ToolCall`.
- Produces: `WorkspacePolicy` satisfying the core `Policy` protocol.

- [x] **Step 1: Deny out-of-scope paths and non-allow-listed commands**

`RiskPolicy` allows every `WRITE`, so the laboratory supplies its own policy. `WorkspacePolicy.evaluate` inspects the frozen `ToolCall` arguments: a `path` or `directory` that is missing, non-string, or outside the workspace yields `DENY`, and a `command` — including the default used when the model omits it — that is not allow-listed yields `DENY`. Command validation is keyed on the tool's declared input schema rather than its name.

- [x] **Step 2: Keep the approval branch for consequential tools**

A `CONSEQUENTIAL` tool still yields `APPROVAL_REQUIRED`, and a non-`Risk` value still raises `TypeError`, so the laboratory policy remains a drop-in replacement for `RiskPolicy`.

- [x] **Step 3: Write the policy tests**

Covers allowed in-scope calls including `run_check` with and without an explicit command; denials for relative traversal, absolute paths, a real repository file, the fixture source, an empty path, a non-string path, a sibling-prefix directory, and a symlink escape; denials for `git status`, `git push`, `curl`, unlisted `python` commands, a shell string, an empty list, and a non-string member; `APPROVAL_REQUIRED` for a consequential tool; `TypeError` for an invalid risk; and an injected allow-list permitting only its own entries.

Run: `python -m pytest tests/test_coding_policy.py -q`

Expected: PASS. Observed: `32 passed`.

### Task 7: Write the deterministic demonstration

**Files:**
- Create: `labs/coding/demo.py`
- Create: `tests/test_coding_demo.py`

**Interfaces:**
- Consumes: everything above plus `JsonlEventSink`, `RunConfig`, `Runner`, `ScriptedModel`, `ToolCall`, `FinalAnswer`.
- Produces: `build_demo(trace_path, workspace)`, `run_demo(trace_path)`, `main()`, and `.traces/coding.jsonl`.

- [x] **Step 1: Script a run that earns its success**

Six tool actions — `list_files`, a failing `run_check`, `read_file`, `search_text`, `write_file`, a passing `run_check` — then a final answer, under `RunConfig(max_iterations=7, timeout_seconds=60.0)`. `run_demo` truncates the trace and uses `Workspace.from_fixture()` as a context manager so the temporary directory is removed even on failure.

- [x] **Step 2: Verify the demonstration and its trace**

Run: `python -m labs.coding.demo`

Expected: `succeeded`, the final answer, and `.traces/coding.jsonl`. Observed exactly that, with the twenty-two-event sequence recorded in the lesson, `check failed with exit code 1` at event 7, and `check passed with exit code 0` at event 19.

- [x] **Step 3: Write the scenario tests**

Covers the happy path with the exact event-kind list and both check outputs, no leaked temporary workspace, the fixture files unchanged by content and mtime, a repeatable trace, `main()`'s printed lines, `POLICY_DENIED` with the four-event trace for an out-of-scope write that creates no file, `POLICY_DENIED` for `git status`, `FAILED` with `no allow-listed check ran in this run` for a declared fix with no check, `FAILED` for a declared fix after a failing check, and `FAILED` when a later edit breaks a check that passed earlier in the same run.

Run: `python -m pytest tests/test_coding_demo.py -q`

Expected: PASS. Observed: `10 passed`.

### Task 8: Add the learner exercise, solution, and checker

**Files:**
- Create: `course/05-coding-agent/exercise.py`
- Create: `solutions/05-coding-agent/exercise.py`
- Create: `course/05-coding-agent/check_exercise.py`
- Create: `tests/test_coding_exercise.py`

**Interfaces:**
- Consumes: `pathlib` only, so the puzzle is independent of the harness.
- Produces: `is_inside(workspace_root, candidate) -> bool` and a standalone checker mirroring `course/02-tiny-core/check_exercise.py`.

- [x] **Step 1: Isolate the containment predicate as the puzzle**

The starter raises `NotImplementedError("complete the containment check from Lesson 5")`. The reference solution resolves both sides and returns `Path.is_relative_to`.

- [x] **Step 2: Build checker cases that defeat a string-prefix implementation**

`ROOT = Path(__file__).resolve().parents[2]`, `sys.path.insert`, `--solution`, `✓`/`✗` per case, exit 1 unless all pass. Cases are built in a real temporary tree: an in-workspace file, the root itself, parent traversal, nested traversal, an absolute outside path, a `ws-evil` sibling, and a symbolic link out of the workspace. Symlink creation is attempted and the case is skipped with a printed note on systems that forbid it.

- [x] **Step 3: Verify both checker modes and both wrong implementations**

Run: `python course/05-coding-agent/check_exercise.py`

Expected before solving: seven readable failures and exit status 1. Observed exactly that.

Run: `python course/05-coding-agent/check_exercise.py --solution`

Expected: seven passes and exit status 0. Observed exactly that.

A naive `startswith` implementation fails four cases; a resolve-then-`startswith` implementation still fails the sibling-prefix case. Both were executed against the checker.

- [x] **Step 4: Write the exercise contract tests**

`@pytest.mark.learner` covers the incomplete learner contract, the checker's per-case failure output, and the checker's exit status 1. The default suite covers the reference solution against the same seven cases, the rejection of a resolve-then-`startswith` implementation with its exact output, the rejection of a non-boolean result, the three module-load failures, the `--solution` subprocess output and exit status, and the absence of a leaked checker temporary directory.

Run: `python -m pytest tests/test_coding_exercise.py -q`

Expected: PASS with three deselected. Observed: `8 passed, 3 deselected`.

### Task 9: Write the lesson

**Files:**
- Create: `course/05-coding-agent/README.md`

**Interfaces:**
- Consumes: the verified demonstration output, trace, and checker output.
- Produces: Part 5 prose following the documented conventions.

- [x] **Step 1: Write the lesson**

Learning goals first; workspace, fixture repository, argument list, and shell string defined at first use; the tool-to-risk table with the `run_check` justification; why containment is Python and not prompting; why the allow-list holds argument lists rather than shell strings, and why it is an allow-list rather than a deny-list; the two independent timeouts; what reversible means here; why a passing check is evidence and a claim is not; why a failing check is still a successful tool result; where a `DENY` ends the run; three progressive hints that name no final function; a link to the solution; and a short recap.

- [x] **Step 2: Verify every documented command and link**

Ran the demonstration command, the trace one-liner, both checker modes, and the laboratory test command; all produced the documented output. All fifteen relative Markdown links were resolved against the filesystem and exist.

### Task 10: Prove the whole suite and repository hygiene

**Files:**
- No new files.

**Interfaces:**
- Consumes: the complete repository.
- Produces: a green default suite and an unmodified course repository.

- [x] **Step 1: Run the full default suite**

Run: `python -m pytest -q`

Expected: the 72 baseline tests still pass plus the new laboratory tests. Observed: `190 passed, 7 deselected`, and the nine pre-existing test files still report `72 passed, 4 deselected` on their own.

- [x] **Step 2: Confirm no temporary workspace leaks and nothing else changed**

Expected: no `tiny-harness-coding-*` or `tiny-harness-check-*` directory in the temporary directory after the suite, and `git status --short` listing only the new files. Observed exactly that.

- [x] **Step 3: Confirm `labs` needs no package file**

Expected: `import labs.coding.demo` succeeds with `labs` as an implicit namespace package. Observed `_NamespacePath`, so parallel laboratory branches will not conflict over a shared `labs/__init__.py`.

- [x] **Step 4: Commit the laboratory**

```bash
git add docs/superpowers/plans/2026-08-27-coding-lab.md labs course/05-coding-agent solutions/05-coding-agent tests/test_coding_workspace.py tests/test_coding_policy.py tests/test_coding_tools.py tests/test_coding_demo.py tests/test_coding_exercise.py
git commit -m "feat: add software-development laboratory"
```

### Task 11: Follow-up work left for later plans

**Files:**
- None in this plan.

**Interfaces:**
- Consumes: this laboratory's committed interfaces.
- Produces: a record of what Part 5 deliberately did not do.

- [ ] **Step 1: Link Part 5 from the course map**

`README.md` still lists Part 5 as "upcoming until its plan lands", and `pyproject.toml` still ships only `tiny_harness` in the wheel. Both files are out of scope for this plan; the plan that owns course navigation should update them together with the other laboratories.

- [ ] **Step 2: Reuse the laboratory in the capstone**

The capstone can add one tool or one policy here — for example a second allow-listed check or a `revert_last` tool — without changing `tiny_harness` or the runner.
