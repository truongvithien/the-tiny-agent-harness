# Task 4 Report: Enforce deterministic policy and approval

## Implementation

- Added `tiny_harness/policy.py` with the `Policy` protocol, `ApprovalCallback` type alias, deterministic `RiskPolicy.evaluate`, and `authorize` approval flow.
- `Risk.READ` and `Risk.WRITE` return `PolicyDecision.ALLOW`; `Risk.CONSEQUENTIAL` returns `PolicyDecision.APPROVAL_REQUIRED`.
- `authorize` invokes the callback only for approval-required decisions and maps approval to `ALLOW` or refusal to `DENY`; all other policy decisions pass through.
- Re-exported all policy interfaces from `tiny_harness`.

## Changed files

- `tiny_harness/policy.py` (created)
- `tests/test_policy.py` (created)
- `tiny_harness/__init__.py` (modified)

## RED/GREEN evidence

- RED: `.venv/bin/python3 -m pytest tests/test_policy.py -v` failed during collection with `ModuleNotFoundError: No module named 'tiny_harness.policy'` before the implementation existed.
- GREEN: `.venv/bin/python3 -m pytest tests/test_policy.py -v` passed, 5 tests.
- Full suite: `.venv/bin/python3 -m pytest -v` passed, 15 tests.
- `git diff --check` passed.

## Final output

The package now exposes `Policy`, `ApprovalCallback`, `RiskPolicy`, and `authorize`, with prompt-independent deterministic risk enforcement and explicit consequential-action approval.

## Self-review

The implementation matches the approved interface and exact risk/decision mapping, does not inspect prompts or mutate calls, and keeps callback invocation limited to consequential actions requiring approval. Tests cover all three risk classes plus approval refusal and acceptance.

## Concerns

No known concerns. The policy intentionally trusts the tool's declared `risk`, as specified by the approved protocol.
