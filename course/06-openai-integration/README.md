# Part 6: OpenAI integration

## Learning goals

By the end of this lesson, you can:

- explain what a **model adapter** is and why the harness keeps its own types;
- translate harness tool specifications into the OpenAI tool-calling format;
- translate an OpenAI assistant message back into a `ToolCall` or
  `FinalAnswer`, rejecting output the harness cannot use;
- keep credentials out of your code, your traces, and your repository; and
- run the deterministic adapter tests without a key, and one live run with one.

Run every command in this lesson from the repository root, the directory that
contains `pyproject.toml`.

## The adapter boundary

Every earlier part used [`ScriptedModel`](../../tiny_harness/models.py), which
returns decisions from a fixed list. That is why the first five parts are
reproducible. A real provider replaces only that one component.

A **model adapter** is the single piece of code that speaks a provider's
dialect. It implements the `ModelAdapter` protocol — one method,
`next_decision(context, tool_specs)` — and does exactly two translations:

```text
harness -> provider :  RunContext + tool specifications -> messages + tools
provider -> harness :  assistant message -> ToolCall | FinalAnswer
```

Everything else in the harness stays unchanged. The runner, policy, event sink,
and verifier never learn that a network call happened. This is the payoff of
owning your own types: swapping providers is one file, not a rewrite.

[`tiny_harness/openai_adapter.py`](../../tiny_harness/openai_adapter.py) keeps
the two directions in small pure functions and one thin class:

- `openai_tools(tool_specs)` maps each harness specification
  (`name`, `description`, `input_schema`) onto OpenAI's function shape, where
  `input_schema` becomes `parameters`.
- `openai_messages(context, system_prompt=...)` turns run state into a message
  list: one system message carrying the instructions, acceptance criteria, and
  remaining iterations, one user message with the task, then one message per
  observation so earlier tool results stay visible.
- `decode_decision(message)` converts the assistant's reply into harness data.
- `OpenAIModel` calls the client and joins those three together.

Pure functions matter here. Translation is where malformed provider output
meets your program, so it is the part you most want to test without a network.

### Untrusted output stops at the boundary

A provider can return a tool call whose arguments are not valid JSON, a name
that is missing, or nothing at all. `decode_decision` raises a `ValueError` for
each of those instead of guessing. The runner catches the failure at its model
boundary, records a `model_error` event, and reports `RunStatus.FAILED`.

Note also what the adapter does *not* decide. It never authorizes a tool, and a
returned `ToolCall` is still only a request — policy runs afterwards, exactly as
in Part 2. A model that asks to send a message has not sent one.

When a reply contains both text and a tool call, the adapter takes the tool
call, because the runner executes at most one action per iteration. Any
remaining text becomes visible on the next turn.

## The client is injected, not imported

`OpenAIModel` accepts a `client` object rather than importing the SDK itself:

```python
OpenAIModel(client=client_from_environment(), model="gpt-4o-mini")
```

That keeps the default install dependency-free, and it means the deterministic
tests can pass a small fake object with the same shape. `openai` appears only in
`client_from_environment`, which imports it lazily and reads the key from the
environment.

Install the optional dependency only when you want a live run:

```bash
python -m pip install -e '.[openai]'
```

## Credentials

A **credential** is a secret that proves who is calling an API. Treat it the way
you would a password:

- keep the key in the environment, never in source, fixtures, or examples;
- never print it, log it, or place it in run state;
- never commit it — `.env` is already ignored by this repository; and
- pass it to nothing that writes to disk.

The adapter never receives the key as an argument; the SDK client reads
`OPENAI_API_KEY` itself. Event sinks also accept a `secrets` tuple and replace
any occurrence with `[REDACTED]` before writing, which
`tests/test_openai_adapter.py` proves for a full run.

Set the key for one shell session. On macOS or Linux:

```bash
export OPENAI_API_KEY='your-key-here'
```

In PowerShell:

```powershell
$env:OPENAI_API_KEY = 'your-key-here'
```

## Run the deterministic tests

These need no key, no network, and not even the `openai` package:

```bash
python -m pytest tests/test_openai_adapter.py -v
```

Every test passes. They cover both translation directions, each rejection case,
and one complete `Runner` run driven by a fake client — the same seven event
kinds you first saw in Part 1.

## Run the optional live test

The live test is marked `live`, so the default suite skips it. With a key set
and `openai` installed:

```bash
python -m pytest -m live -v
```

Without a key it reports `SKIPPED [1] ... OPENAI_API_KEY is not set`, which is
the expected result and not a failure. Override the model with
`TINY_HARNESS_LIVE_MODEL` if you prefer another one.

The live test asserts that the run succeeded and that a tool was actually
executed. It deliberately does not assert exact wording: a live model's prose
varies, so pinning it would make the suite flaky. Check the contract, not the
sentence.

## Exercise

Open [`exercise.py`](exercise.py) and implement `decode_decision`, the
provider-to-harness direction. Check your work:

```bash
python course/06-openai-integration/check_exercise.py
```

The starter is intentionally incomplete, so this reports seven failures and
exits with status 1 until you finish it.

### Hints

1. There are two success shapes and one failure shape. Look for a non-empty
   `tool_calls` list first, fall back to `content`, and raise `ValueError` when
   neither is usable. Remember that `"   "` is not usable text.
2. `arguments` arrives as a JSON *string*, so it needs `json.loads`. Absent or
   empty arguments should become `{}` rather than an error, because a tool can
   legitimately take none.
3. Two things can go wrong while decoding: the string may not parse, and it may
   parse into something that is not an object (`"[1, 2]"` is valid JSON but not
   arguments). `ToolCall` needs a mapping, so reject both with `ValueError` and
   name the tool in the message.

When you are finished, compare with the explained reference in
[`solutions/06-openai-integration/exercise.py`](../../solutions/06-openai-integration/exercise.py),
and confirm it satisfies the same contract:

```bash
python course/06-openai-integration/check_exercise.py --solution
```

That reports seven passes and exits with status 0.

## Recap

An adapter is a translator, not a new authority. It converts run state into a
provider request and a provider reply into harness types, rejecting anything it
cannot represent. Because the harness owns the types, one small file swaps a
scripted model for a live one while policy, traces, budgets, and verification
stay exactly as they were.

Part 7, the capstone, asks you to extend this harness with one tool or policy of
your own. Revisit [Part 2: The Tiny Core](../02-tiny-core/README.md) to see the
contracts this adapter satisfies. The full progression is described in the
[course design specification](../../docs/superpowers/specs/2026-08-25-tiny-agent-harness-course-design.md).
