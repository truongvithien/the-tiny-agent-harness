# The Tiny Agent Harness: Course Design

## Status

Approved course architecture, pending final review before implementation planning.

## Purpose

The Tiny Agent Harness is a beginner-oriented, hands-on course about the software that surrounds an AI model and turns it into a controlled agent. Learners build a small reusable harness, examine it in several domains, and complete puzzle-sized exercises against local mock infrastructure.

The course treats software development as one agent use case rather than the definition of an agent harness. Its examples progress from low-risk information processing to higher-risk environment modification.

## Audience and prerequisites

The primary audience is beginner Python programmers. A learner should be able to:

- run commands in a terminal;
- read basic Python functions and classes;
- create and activate a virtual environment; and
- understand files, dictionaries, lists, and exceptions.

No prior agent-framework, distributed-systems, or machine-learning experience is required.

## Learning outcomes

By the end of the course, a learner can:

1. Explain the boundary between a model and an agent harness.
2. Implement an observe-decide-authorize-execute-record-verify loop.
3. Define typed tools and return explicit success or failure results.
4. Keep compact run state and an append-only event trace.
5. Apply permission policies before side effects occur.
6. Add iteration, time, and retry limits.
7. Verify completion using evidence instead of model assertion.
8. Reuse the same harness across support, research, and coding cases.
9. Replace a deterministic mock model with the OpenAI API through an adapter.
10. Extend the harness with a new tool or policy and test its boundary.

## Scope

### Included

- A small Python harness implemented during the course.
- Deterministic mock-model execution for all foundational lessons.
- Synthetic local infrastructure and data for three case laboratories.
- Runnable demonstrations, incomplete learner exercises, automated checks, hints, and explained solutions.
- An opt-in OpenAI integration lesson.
- A capstone that extends the shared harness.

### Excluded from the first release

- Multi-agent orchestration.
- Long-term memory or vector databases.
- Browser automation and live web research.
- Production deployment, queues, or distributed workers.
- Automatic Git commits, pushes, merges, or deployments.
- A graphical interface.
- Support for multiple live model providers.
- Evaluation dashboards or hosted observability systems.

These exclusions keep the course focused on the irreducible responsibilities of a harness.

## Teaching approach

The course is concept-first and case-driven. It introduces one harness responsibility at a time, demonstrates it with deterministic behavior, and then asks the learner to complete a small implementation puzzle.

Every lab follows the same cycle:

1. Read a short concept lesson.
2. Run a completed miniature demonstration.
3. Inspect its human-readable event trace.
4. Open a starter exercise containing focused `TODO` gaps.
5. Implement one harness responsibility.
6. Run automated checks for immediate feedback.
7. Use progressive hints if blocked.
8. Compare the result with an explained reference solution.

Exercises test understanding at harness boundaries, not memorization of large code blocks. Each exercise should normally require changing one or two small functions.

## Course progression

### Part 1: Foundations

Introduces models, agents, harnesses, tools, state, policies, traces, verification, and evaluations. A paper exercise asks learners to classify responsibilities as model-owned or harness-owned.

### Part 2: Build the tiny core

Builds the shared harness using a scripted mock model. Lessons add typed messages, tools, the execution loop, event recording, limits, policy decisions, and verification in that order.

### Part 3: Support-triage laboratory

Runs against a synthetic local ticket store and policy knowledge base. The agent reads a ticket, retrieves relevant policy text, assigns a category, and drafts a response. Sending is simulated and requires human approval.

Primary concepts:

- typed tool arguments and results;
- separating read operations from consequential actions;
- structured model decisions; and
- approval gates.

### Part 4: Research laboratory

Runs against a local HTTP document server containing synthetic sources. The agent retrieves a small set of documents and produces a report whose claims cite captured evidence. The lab includes incomplete and conflicting sources.

Primary concepts:

- context selection and limits;
- source provenance;
- evidence-backed completion; and
- graceful handling of uncertainty.

### Part 5: Software-development laboratory

Runs against a temporary copy of a deliberately small sample repository. The agent can inspect files, search text, propose patches, and run allow-listed checks. It cannot modify the course repository or perform Git/network operations.

Primary concepts:

- filesystem scope;
- command allow-listing and timeouts;
- reversible edits; and
- verification before completion.

### Part 6: OpenAI integration

Introduces one adapter for the official OpenAI Python SDK. The adapter translates the shared harness message and tool contracts to the current OpenAI tool-calling interface, then translates responses back into harness-owned types.

The lesson makes live execution optional. API credentials are read from the environment, never committed, logged, or included in traces. Deterministic tests use a fake adapter and require neither network access nor an API key.

### Part 7: Capstone

The learner adds one tool or one policy to an existing case, defines its risk classification, writes success and denial tests, runs a scenario, and explains the resulting safety boundary. The capstone rubric rewards clear contracts and evidence rather than feature count.

## System architecture

The model proposes intent; the harness owns effects. The core runtime implements this control flow:

```text
task and state
    -> model adapter proposes a response or tool call
    -> policy authorizes, denies, or requests approval
    -> tool executor performs one bounded action
    -> event recorder captures inputs and results
    -> verifier checks progress and completion evidence
    -> loop continues or returns a terminal run result
```

Only one tool action is executed per loop iteration. This makes traces easy to follow and prevents a batch of unreviewed side effects.

### Core boundaries

- `ModelAdapter`: accepts compact harness context and returns a structured model decision.
- `Tool`: declares a name, description, input contract, risk class, and execution function.
- `ToolResult`: represents success or failure as data rather than exposing raw exceptions to the model.
- `Policy`: returns allow, deny, or approval-required before tool execution.
- `EventSink`: records append-only run events and redacts configured secrets.
- `Verifier`: evaluates explicit completion conditions against run state and evidence.
- `Runner`: coordinates the loop and enforces iteration and time budgets.

These interfaces remain intentionally small. Cases add tools and policies without subclass hierarchies or a plugin framework.

## State and event model

Run state contains only information needed for the next decision:

- task objective and acceptance criteria;
- relevant observations;
- tool results;
- decisions and approvals;
- remaining budgets; and
- verification status.

The event log is append-only history. Each event records a sequence number, timestamp, run identifier, event type, and typed payload. Large tool output is truncated with an explicit marker. Secrets are redacted before persistence. JSON Lines is used so traces are both machine-readable and easy to inspect locally.

## Policy and approval model

Each tool declares one of three risk classes:

- `read`: observes local state and is allowed by default within scope;
- `write`: performs a reversible local change and is allowed only in the lab workspace; or
- `consequential`: communicates externally or performs a difficult-to-reverse action and requires explicit approval.

Policy is evaluated by deterministic Python code. Prompt instructions may describe the policy to the model, but they are not the enforcement mechanism.

The initial course uses a terminal approval callback. Mock scenarios supply scripted approvals so automated tests remain deterministic.

## Local mock infrastructure

All foundational and case exercises run on a local machine without Docker:

- support data is stored as synthetic JSON and Markdown files;
- research sources are served by a standard-library local HTTP server on an ephemeral port; and
- coding tasks copy fixture repositories into operating-system temporary directories.

Each service has a single command that starts the demonstration and cleans up temporary resources on exit. Fixed random seeds and scripted model responses make expected traces reproducible.

## Error handling and stopping conditions

Tool exceptions are caught at the executor boundary and converted into typed failures containing a safe message and retryability flag. Unknown tools, invalid arguments, denied policies, approval refusal, timeouts, and verification failure each have distinct event types.

The runner stops when any of these conditions occurs:

- verification confirms all acceptance criteria;
- the model returns a final response and verification accepts it;
- the iteration or wall-clock budget is exhausted;
- an unrecoverable tool or model error occurs;
- approval is refused; or
- repeated equivalent failures exceed the configured retry limit.

The terminal result states the reason and includes references to supporting events. The harness never silently converts budget exhaustion or partial work into success.

## Testing strategy

The default suite is offline and deterministic:

- unit tests cover tool validation, policy decisions, state transitions, event redaction, limits, and verification;
- scenario tests run scripted model decisions through complete case flows;
- lab checks target the contract learners are asked to implement;
- trace assertions check important event sequences without snapshotting timestamps or irrelevant formatting; and
- coding-lab tests confirm that paths and commands cannot escape the temporary workspace.

Live OpenAI tests are opt-in, marked separately, and skip when credentials are absent. They verify adapter compatibility rather than exact natural-language output.

## Repository organization

```text
the-tiny-agent-harness/
├── README.md
├── course/
│   ├── 01-foundations/
│   ├── 02-tiny-core/
│   ├── 03-support-triage/
│   ├── 04-research-agent/
│   ├── 05-coding-agent/
│   ├── 06-openai-integration/
│   └── 07-capstone/
├── tiny_harness/
├── labs/
│   ├── support_triage/
│   ├── research/
│   └── coding/
├── solutions/
├── tests/
├── scripts/
├── docs/superpowers/specs/
└── pyproject.toml
```

Course lesson directories contain prose and exercise instructions. Reusable runtime code lives in `tiny_harness`. Lab data and runnable case adapters live in `labs`. Reference implementations mirror exercise identifiers under `solutions` rather than replacing the learner workspace.

## Technology and dependency policy

- Python 3.12 is the documented baseline.
- Standard-library features are preferred for the core and mock services.
- `pytest` provides tests and exercise checks.
- The official `openai` package is introduced only in Part 6.
- Packaging follows a standard `pyproject.toml` layout.
- Setup instructions use `python -m venv` and `python -m pip` so learners do not need an additional package manager.
- Commands are documented for macOS, Linux, and PowerShell where syntax differs.

## Documentation conventions

Every lesson begins with learning goals and ends with a short recap. New terms are defined at first use. Commands state the expected working directory and show a brief expected result. Hints are progressive, and solutions explain design reasoning as well as code.

The main README provides the course map, prerequisites, setup, estimated progression, and links to the first lesson. It distinguishes deterministic exercises from optional API-backed execution before asking learners to configure credentials.

## Acceptance criteria for the first release

The first release is complete when:

1. A new learner can set up the repository using only the documented prerequisites.
2. Every part contains a runnable demonstration and at least one checked exercise.
3. All three cases use the same core harness interfaces.
4. Default demonstrations and tests pass without network access or credentials.
5. Each run produces an inspectable JSON Lines trace.
6. Policy tests demonstrate allowed, denied, and approval-required actions.
7. The coding lab proves that file and command access stay inside its temporary workspace.
8. The OpenAI adapter has deterministic contract tests and one documented opt-in live run.
9. No credential, generated trace, temporary workspace, or learner-local configuration is tracked by Git.
10. The capstone can be completed by extending an existing tool or policy without changing the runner.

