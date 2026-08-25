# Foundations exercises: who owns this responsibility?

For each prompt, choose **model** or **harness**. Use **model** when the work is
about proposing meaning or intent. Use **harness** when ordinary code must
enforce a boundary, cause an effect, preserve evidence, or decide a terminal
status.

1. Interpret a user's request and propose that `lookup_habitat` should run.
2. Check that `lookup_habitat` is a registered tool before invoking it.
3. Decide which sentence best summarizes an observed tool result.
4. Refuse to publish a message when required approval was not granted.
5. Stop after the configured iteration budget is exhausted.
6. Replace an API token with `[REDACTED]` before writing a trace event.
7. Propose a final answer based on the observations in the current state.
8. Check that the final answer meets explicit acceptance criteria.
9. Convert a tool exception into a safe, typed failure result.
10. Choose the arguments to include in a structured `ToolCall`.

<details>
<summary>Answers and explanations</summary>

1. **Model.** Interpreting language and proposing the next intent is the
   model's role. The proposal is still data; it does not run the tool.
2. **Harness.** Registration is an enforceable allow-list boundary. The harness
   must prevent an invented tool name from becoming an effect.
3. **Model.** Producing a useful natural-language summary is a meaning-making
   decision. The harness still controls which observations the model receives.
4. **Harness.** Approval must be enforced by deterministic code before the
   action. A prompt reminder is not enforcement.
5. **Harness.** A budget is a stopping guarantee, so the runner owns it even if
   the model asks to continue.
6. **Harness.** Secrets must be removed before persistence. Safety cannot depend
   on the model noticing every sensitive value.
7. **Model.** The model proposes the answer. A separate verifier decides whether
   that proposal is acceptable.
8. **Harness.** Completion is an evidence boundary. The model's claim that it is
   done is not proof.
9. **Harness.** The tool executor catches raw exceptions so the loop receives a
   predictable `ToolResult` instead of crashing or leaking details.
10. **Model.** Choosing a tool and arguments is a proposal of intent. The
    harness still limits the request to registered tools, authorizes it, and
    executes it.

</details>
