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
3. Support-triage laboratory — upcoming until its plan lands.
4. Research laboratory — upcoming until its plan lands.
5. Software-development laboratory — upcoming until its plan lands.
6. OpenAI integration — upcoming until its plan lands.
7. Capstone — upcoming until its plan lands.

Parts 1 and 2, their demonstrations, and the default test suite are offline and deterministic. Part 6 will later add an optional lesson using the official OpenAI SDK; its live run will be opt-in, while its default tests will remain offline.

Never commit API keys or put them in examples, traces, or test fixtures. The later live lesson will read credentials from the environment.

## Repository map

- `course/` contains the lessons, hints, and learner exercises.
- `tiny_harness/` contains the small reusable runtime.
- `examples/` contains completed runnable demonstrations.
- `solutions/` mirrors exercises with reference implementations.
- `tests/` contains deterministic runtime, scenario, configuration, and exercise-contract checks.
- `docs/superpowers/` contains the approved [course design specification](docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md) and implementation plans.
- `.traces/` is ignored local output created by demonstrations.

For the rationale behind the entire seven-part progression, read the [course design specification](docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md).
