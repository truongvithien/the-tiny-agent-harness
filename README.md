# The Tiny Agent Harness

An agent harness is the ordinary software around an AI model that supplies context and tools, enforces policy, performs approved effects, records events, and verifies completion. This beginner course promises a small working Python harness you can understand, test, and extend through hands-on lessons rather than a hidden framework.

Coding agents are one application of a harness, not its definition. The same core boundaries can support research, support triage, and other tasks in which a model proposes intent while trusted software controls effects.

## Prerequisites

You need Git, a terminal, and Python 3.12. You should be comfortable running commands and reading basic Python functions, classes, dictionaries, lists, and exceptions; no machine-learning or agent-framework experience is required.

After cloning the repository, run the setup commands from its root (the directory containing `pyproject.toml`). Replace `<repository-url>` with the URL for your copy.

On macOS or Linux with a POSIX shell:

```bash
git clone <repository-url>
cd the-tiny-agent-harness
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -v
```

On Windows in PowerShell:

```powershell
git clone <repository-url>
cd the-tiny-agent-harness
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -v
```

The default test command uses strict marker checking and skips intentionally incomplete learner work and optional live tests. To run only the incomplete Part 2 learner contract while working on it, use:

```bash
python -m pytest -m learner tests/test_course_exercise.py -v
```

## Start here

Begin with [Part 1: Foundations](course/01-foundations/README.md). Its deterministic demonstration needs no network access or API key:

```bash
python -m examples.foundations_demo
```

It reports success and writes a seven-event JSON Lines trace to `.traces/foundations.jsonl`. Continue with [Part 2: The Tiny Core](course/02-tiny-core/README.md), complete its small risk-policy exercise, and check your work with:

```bash
python course/02-tiny-core/check_exercise.py
```

The starter is intentionally incomplete, so this command reports three failures until you implement it. You can check the supplied solution without changing the learner exercise:

```bash
python course/02-tiny-core/check_exercise.py --solution
```

That solution check reports three passes.

## Course map

1. [Foundations](course/01-foundations/README.md) — distinguish the model from the harness and inspect a complete deterministic trace.
2. [Build the tiny core](course/02-tiny-core/README.md) — follow the typed control loop and complete a policy puzzle.
3. [Support-triage laboratory](course/03-support-triage/README.md) — read tickets and policy text, then gate a simulated send behind human approval.
4. [Research laboratory](course/04-research-agent/README.md) — fetch documents from a local server and accept only claims backed by captured evidence.
5. [Software-development laboratory](course/05-coding-agent/README.md) — patch a throwaway copy of a repository inside an enforced filesystem and command scope.
6. [OpenAI integration](course/06-openai-integration/README.md) — replace the scripted model with the official SDK behind one adapter.
7. [Capstone](course/07-capstone/README.md) — add your own tool or policy, and prove its boundary with a denial test.

Each laboratory runs its own demonstration from the repository root:

```bash
python -m labs.support_triage.demo
python -m labs.research.demo
python -m labs.coding.demo
```

Every one is offline and deterministic. The research laboratory serves its
documents from a local HTTP server on an ephemeral port, and the
software-development laboratory works only inside a temporary directory that it
deletes afterwards.

Parts 1 to 5 and 7, their demonstrations, and the default test suite need no
network access and no credentials. Part 6 adds an optional lesson using the
official OpenAI SDK: its contract tests run offline with a fake client, and only
its `live`-marked test needs a key, which it skips when none is present.

Never commit API keys or put them in examples, traces, or test fixtures. The
live lesson reads credentials from the environment only.

Once you have worked through the parts, check the whole repository the way a new
learner meets it:

```bash
python scripts/verify_course.py
```

## Repository map

- `course/` contains the lessons, hints, and learner exercises.
- `tiny_harness/` contains the small reusable runtime shared by every part.
- `labs/` contains the case laboratories, their synthetic data, and their runnable demonstrations.
- `examples/` contains completed runnable demonstrations.
- `solutions/` mirrors exercises with reference implementations.
- `scripts/` contains `verify_course.py`, the whole-course consistency check.
- `tests/` contains deterministic runtime, scenario, configuration, and exercise-contract checks.
- `docs/superpowers/` contains the approved [course design specification](docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md) and implementation plans.
- `.traces/` is ignored local output created by demonstrations.

For the rationale behind the entire seven-part progression, read the [course design specification](docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md).
