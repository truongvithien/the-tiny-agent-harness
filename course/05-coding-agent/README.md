# Part 5: The Software-Development Laboratory

## Learning goals

By the end of this lesson, you can:

- explain why a **workspace** — the one directory tree an agent may touch — is
  enforced by Python code rather than by instructions in a prompt;
- resolve a proposed path and reject every escape from that workspace,
  including `..` traversal, absolute paths, symbolic links, and sibling
  directories whose names merely start with the same characters;
- describe why a command **allow-list** contains argument lists rather than
  shell strings, and why every command needs a timeout;
- explain what "reversible" means for an edit in this laboratory; and
- explain why a passing check is completion evidence while a model's claim of
  success is not.

Run every command below from the repository root, the directory containing
`pyproject.toml`.

This lesson assumes [Part 1: Foundations](../01-foundations/README.md) and
[Part 2: The Tiny Core](../02-tiny-core/README.md). It reuses that core without
changing it: the same `Runner`, the same `Risk` classes, and the same event
trace. Only the tools, the policy, and the verifier are new. The full rationale
for the seven parts is in the
[course design specification](../../docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md).

## The laboratory in one paragraph

A **fixture repository** is a deliberately tiny sample project used for
teaching. This laboratory's fixture is
[`labs/coding/fixture_repo/`](../../labs/coding/fixture_repo/): one function in
[`wordcount.py`](../../labs/coding/fixture_repo/wordcount.py), three tests in
[`test_wordcount.py`](../../labs/coding/fixture_repo/test_wordcount.py), and a
bug that makes two of those tests fail. Before a run,
[`labs/coding/workspace.py`](../../labs/coding/workspace.py) copies the fixture
into a fresh operating-system temporary directory. The agent reads, searches,
edits, and runs checks in that copy. It cannot reach the course repository, it
cannot run Git, and it cannot reach the network.

## Run the demonstration

```bash
python -m labs.coding.demo
```

Expected result: three printed lines — `succeeded`, the final answer, and
`.traces/coding.jsonl`. The run performs six tool actions and then one final
answer, so the trace holds twenty-two events:

```bash
python -c "import json,pathlib; [print(json.loads(l)['sequence'], json.loads(l)['kind']) for l in pathlib.Path('.traces/coding.jsonl').read_text().splitlines()]"
```

Expected result:

```text
1 run_started
2 model_decision
3 policy_decision
4 tool_result
5 model_decision
6 policy_decision
7 tool_result
8 model_decision
9 policy_decision
10 tool_result
11 model_decision
12 policy_decision
13 tool_result
14 model_decision
15 policy_decision
16 tool_result
17 model_decision
18 policy_decision
19 tool_result
20 model_decision
21 verification
22 run_finished
```

Read the two `run_check` results in the trace. Event 7 records
`check failed with exit code 1` before the edit, and event 19 records
`check passed with exit code 0` after it. Event 21 quotes event 19's outcome as
the reason for acceptance. Those two events are the point of the whole lesson:
the run succeeded because a command reported exit code 0, not because the model
said it had fixed the bug.

## The five tools and their risk classes

[`labs/coding/tools.py`](../../labs/coding/tools.py) defines the laboratory's
tools. Each declares one `Risk`, exactly as described in Part 2.

| Tool | Risk | What it may do |
| --- | --- | --- |
| `list_files` | `READ` | List files inside the workspace, skipping symlinks and bytecode caches. |
| `read_file` | `READ` | Read one text file inside the workspace. |
| `search_text` | `READ` | Search workspace text files for a literal substring. |
| `write_file` | `WRITE` | Replace one file inside the workspace, keeping its previous content. |
| `run_check` | `WRITE` | Run one allow-listed command inside the workspace, under a timeout. |

`run_check` is classified `WRITE` rather than `CONSEQUENTIAL`. It executes only
a fully specified argument list drawn from a Python allow-list, inside a
disposable temporary directory, with no network access and no Git; its worst
outcome is changing files in a directory that is deleted when the run ends, and
a timeout bounds how long it can take. That is the definition of a reversible
local change. Marking it `CONSEQUENTIAL` would demand a human keystroke before
every test run — the one action a learner repeats most — which trains people to
approve prompts without reading them, and approval fatigue is a real safety
loss. Approval is reserved for effects that leave the workspace.

That justification depends entirely on the contents of the allow-list. If the
allow-list ever admitted a command that published a package, wrote to a shared
cache, or opened a network connection, the risk class would have to become
`CONSEQUENTIAL`, because the effect would no longer be confined to a directory
the harness can throw away.

## Filesystem scope: containment in code, not in prose

You could write "only edit files under the workspace" in a prompt. That is a
request, not a boundary. The model may misread it, a tool argument may be
assembled from text the model does not control, and a future model may simply
behave differently. Prompt text has no enforcement mechanism; a function that
returns `False` does.

[`labs/coding/workspace.py`](../../labs/coding/workspace.py) centralizes that
function. Every tool that accepts a path calls `Workspace.resolve`, which calls
`is_inside` and raises `PathEscapesWorkspace` when a candidate escapes. There
is exactly one place to read, test, and fix.

`is_inside` resolves both sides of the comparison and then compares path
components:

- **Resolve the root, not just the candidate.** On macOS a temporary directory
  such as `/var/folders/...` is reached through a symbolic link to
  `/private/var/folders/...`. Comparing a resolved candidate against an
  unresolved root rejects legitimate paths and hides real bugs.
- **`..` is not text to be stripped.** Resolving the whole path collapses
  `a/../../../etc/passwd` to what the filesystem would actually open. Deleting
  the characters `..` from a string is not the same operation.
- **A symbolic link is part of the path.** Resolution follows links, so a link
  created inside the workspace that points outside resolves to an outside path
  and is rejected.
- **Compare components, never string prefixes.** `/tmp/ws-evil/secret.txt`
  starts with the characters `/tmp/ws`, but it is not inside `/tmp/ws`.
  `Path.is_relative_to` compares path parts, so it answers the question you
  actually meant to ask.

Containment is also cheap insurance: the workspace is a copy. Even a defect in
`is_inside` would damage a directory that is deleted at the end of the run
rather than your repository.

### What this proves, and what it does not

Be precise about the claim. The tests prove that these tools, given these
arguments, cannot read or write outside the workspace. Two limits are worth
naming:

- Resolution and the later `open` are separate operations. A process that could
  replace a directory with a symbolic link between them could defeat the check.
  Nothing else has a handle on this workspace, so the race is not reachable
  here, but a harness guarding a shared directory would need file descriptors
  rather than path comparisons.
- A command is trusted once it is on the allow-list. `run_check` starts the
  child in the workspace, but the operating system does not confine that child
  to it. The allow-list, not the workspace, is what bounds `run_check`; a
  sandbox, container, or separate user account is what would confine an
  arbitrary command.

## Command allow-listing and timeouts

[`labs/coding/tools.py`](../../labs/coding/tools.py) holds the allow-list:

```python
CHECK_COMMAND = ("python", "-m", "unittest", "discover", "-p", "test_*.py")
ALLOWED_COMMANDS = (CHECK_COMMAND,)
```

An **argument list** (or argv) is a sequence in which the first item is the
program and each later item is one separate argument. A **shell string** is one
line of text that a shell parses before running anything.

The allow-list holds argument lists because a shell string cannot be checked
safely. In a shell string, `;`, `&&`, `|`, backticks, `$(...)`, quotes, and
globs all change what runs, so validating the text means reimplementing the
shell's parser — and any mistake in that reimplementation is an arbitrary
command. `subprocess.run(argv, shell=False)` passes the list to the operating
system with no parsing step at all, so `is_allowed_command` can answer one
narrow question: is this exact tuple of strings a member of the allow-list?
`is_allowed_command` therefore rejects a `str` outright: a string is a sequence
of characters, not a program with arguments.

The allow-list is an allow-list, not a deny-list. Blocking `git`, `curl`, and
`rm` by name would still permit everything nobody thought to name. Only listed
commands run; `git status` is refused for the same reason as any other
unlisted command, not because Git appears on a list of dangers.

Two independent timeouts bound a check:

- `subprocess.run(..., timeout=CHECK_TIMEOUT_SECONDS)` inside the tool kills a
  check that hangs, and the tool returns a typed failure that names the
  timeout; and
- the runner's own wall-clock budget from Part 2 stops waiting on any boundary
  that misses the deadline, records a `timeout` event, and finishes with
  `budget_exhausted`.

The tool also strips `PYTHONPATH` from the child environment and sets
`PYTHONDONTWRITEBYTECODE=1`. Without the first, an inherited import path could
make the check import modules from the course repository instead of the
workspace copy, and the evidence would describe the wrong files. The second
keeps `__pycache__` directories out of the workspace so file listings stay
stable.

## Reversible edits

"Reversible" in this laboratory means two concrete things, not a promise of
good behavior.

1. The workspace itself is a disposable copy. `Workspace.cleanup` deletes the
   whole tree, and `run_demo` uses the workspace as a context manager, so the
   directory is removed even when a run raises.
2. Every `write_file` records an `Edit` holding the file's previous content, or
   `None` when the file did not exist. `Workspace.revert_last` and
   `Workspace.revert_all` restore those bytes, so an edit can be undone inside
   a run without discarding the whole workspace.

Nothing here is a Git commit. Part 5 performs no Git operation at all, in
either the workspace or the repository; the spec excludes automatic commits,
pushes, and merges from the entire course.

## Verification before completion

[`labs/coding/verification.py`](../../labs/coding/verification.py) defines a
`CheckLedger` and the `PassingCheckRequired` verifier. Only `run_check` writes
to the ledger, and it writes what actually happened: the command, its exit
code, and its captured output. The verifier then accepts a final answer only
when the most recent recorded check exists and exited 0. Nothing the model
writes in its answer can create or alter a ledger record.

This matters because the two failure modes it prevents are the common ones.
A model that declares "I fixed it" without running the check produces
`no allow-listed check ran in this run` and the run finishes `failed`. A model
that runs the check, sees failures, and declares them unrelated produces
`the last check exited with 1: ...` and also finishes `failed`. Evidence is
what a bounded action reported; a claim is what the model asserted about it.
Only the first can be replayed from the trace by someone who does not trust
either party.

Note one deliberate distinction in the trace. A failing check is recorded as a
*successful* tool result (`"ok": true`) whose output begins
`check failed with exit code 1`. The tool did its job — it ran the check and
captured the outcome. "The check failed" is evidence for the verifier, not a
tool malfunction. A tool result is `ok: false` only when the tool could not
perform its bounded action at all: a path escaped the workspace, a command was
not allow-listed, the check timed out, or an argument was invalid.

## Where a denial ends the run

[`labs/coding/policy.py`](../../labs/coding/policy.py) supplies
`WorkspacePolicy` because the core `RiskPolicy` is not strict enough here: it
allows every `WRITE` action, which would let `write_file` name any path on the
disk. `WorkspacePolicy` inspects the frozen arguments of the proposed
`ToolCall` before anything executes and returns `PolicyDecision.DENY` when

- a `path` or `directory` argument is missing, is not a string, or is not
  inside the workspace; or
- a `command` argument — including the default used when the model omits it —
  is not in the allow-list.

A `DENY` makes the runner finish immediately with `RunStatus.POLICY_DENIED`
after recording `policy_decision`, so the trace of a refused write is exactly
four events: `run_started`, `model_decision`, `policy_decision`,
`run_finished`. No `tool_result` appears, because nothing ran.

The tools repeat these checks themselves and return typed failures. That
duplication is intentional. Policy protects the run; the tool protects itself
against being called from anywhere else, including a future lesson, a test, or
a capstone extension that forgets to install the policy.

## Exercise: complete the containment check

Open [`exercise.py`](exercise.py). Its `is_inside` function receives a
workspace root and a candidate path and must return `True` only when the
candidate is the root itself or a path inside it. Relative candidates are
interpreted against the root. The starter raises `NotImplementedError` on
purpose.

With your virtual environment activated, run the checker from the repository
root:

```bash
python course/05-coding-agent/check_exercise.py
```

It builds a real temporary directory tree — a workspace, an outside directory,
a sibling directory named `ws-evil`, and a symbolic link pointing out of the
workspace — then prints one `✓` or `✗` per case and exits with status 1 until
every case passes. Before you write anything, it reports seven failures.

Keep the function to a few lines. This puzzle is about the boundary, not about
Python tricks.

### Hint 1

Two of the seven cases are relative paths and two are absolute. Decide what a
relative candidate is relative to, and join it to the root before you compare
anything.

### Hint 2

`Path.resolve()` collapses `.` and `..` and follows symbolic links. Ask
yourself which of the two paths you are comparing needs that treatment. The
`sibling with a shared prefix` case still fails if you resolve both and then
compare the results as strings.

### Hint 3

`pathlib` can answer "is this path within that path?" by comparing path
components rather than characters. Look for a `Path` method that takes another
path and returns a `bool`, and remember that it must also answer `True` when
the two paths are equal.

After your checker passes, compare your reasoning with the
[reference solution](../../solutions/05-coding-agent/exercise.py). To check the
reference without changing your learner file, run:

```bash
python course/05-coding-agent/check_exercise.py --solution
```

Expected result: seven passes and exit status 0.

The laboratory's own copy of this logic lives in
[`labs/coding/workspace.py`](../../labs/coding/workspace.py). Read it after you
finish, and notice that `Workspace.resolve` is the only place any tool converts
a proposed path into a real one.

## Run the laboratory's tests

```bash
python -m pytest tests/test_coding_workspace.py tests/test_coding_policy.py tests/test_coding_tools.py tests/test_coding_demo.py tests/test_coding_exercise.py -v
```

Expected result: every test passes, and three intentionally incomplete learner
tests are deselected. These files are worth reading as well as running: they
are the proof that the escapes described above are actually blocked, including
the symbolic link and the sibling-prefix cases, and that no temporary workspace
survives a run.

## Recap

The agent worked on a temporary copy, so the repository was never at risk. One
function decided which paths existed for it, and a list of argument lists
decided which commands existed for it. A policy turned both decisions into
`DENY` before any effect occurred, and a timeout bounded the one command that
could run. Completion required a recorded exit code of 0 — evidence produced by
a bounded action — rather than the model's own report of success.
