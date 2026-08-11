# Codex Handoff

Updated: `2026-08-11T13:30:00+08:00`
Workspace: `/Users/example/projects/sample-agent`
Branch: `feat/retry-policy`
HEAD: `8c13d9a`
Handoff reason: `third completed context compaction`

## 1. Objective and scope

### Objective

Add bounded retry behavior to the sample agent without changing its public response schema.

### In scope

Retry classification, retry limit configuration, focused unit tests, and user documentation.

### Out of scope

Provider migration, prompt redesign, deployment, and unrelated formatting changes.

## 2. Verified current state

### Completed

`src/retry.py:classify_error` classifies timeout and rate-limit failures. `tests/test_retry.py` covers two retryable and three terminal cases. The focused test file passed at handoff time.

### In progress

`src/agent.py:run` calls the classifier, but the retry delay remains fixed at one second. The intended bounded exponential delay has not been implemented.

### Remaining

Implement the delay calculation, add boundary tests for attempts 0 through 3, update the configuration example, and run the full test suite.

## 3. Architecture and data flow

`Agent.run` calls the provider. A provider exception passes through `classify_error`. Retryable errors enter the retry policy, which reads `max_attempts` and the delay settings from `AgentConfig`. Terminal errors preserve the existing response path.

## 4. Decisions, constraints, and rejected approaches

### Decisions and reasons

Keep retry classification deterministic and provider-independent. This allows focused tests and prevents model output from deciding operational control flow.

### Invariants and constraints

Preserve the public response schema. Retry attempts must never exceed `max_attempts`. Terminal authentication errors must fail immediately.

### Rejected approaches

Do not add an external retry dependency for this bounded implementation. Do not retry every exception because programming errors and invalid credentials require immediate visibility.

## 5. Relevant files and symbols

- `src/retry.py:classify_error`: completed classifier.
- `src/retry.py:retry_delay`: placeholder that still returns a fixed value.
- `src/agent.py:Agent.run`: partial integration.
- `src/config.py:AgentConfig`: retry limit exists; delay fields are missing.
- `tests/test_retry.py`: focused tests for classification.

## 6. Verification

### Commands run

`python -m pytest tests/test_retry.py -q` returned `5 passed`. `git diff --check` returned status zero.

### Checks not run

The full test suite and type checker were not run because delay configuration and boundary tests remain incomplete.

## 7. Working tree

### Staged changes

None.

### Unstaged changes

`src/retry.py`, `src/agent.py`, and `tests/test_retry.py` contain the partial retry implementation.

### Untracked files

`docs/retry-policy-notes.md` contains design notes and has not been reviewed for inclusion.

## 8. Known issues, risks, and unknowns

The desired maximum delay is `UNKNOWN`; confirm it from the issue or ask the user before choosing a value. Provider-specific exception subclasses may differ across the supported provider versions.

## 9. Next concrete task

Inspect the retry requirement, confirm the maximum delay, then implement `retry_delay` and its boundary tests without modifying the response schema. Completion requires focused tests, the full suite, and `git diff --check` to pass.

## 10. New-session startup checklist

1. Read all applicable `AGENTS.md` files.
2. Read this handoff completely.
3. Verify branch, HEAD, working tree, relevant code, and relevant tests.
4. Resolve conflicts in favor of repository evidence.
5. State the current status, planned files, validation plan, and main risk.
6. Continue only the task in section 9.

## 11. Handoff history

### `2026-08-11T13:30:00+08:00`

- Reason: third completed context compaction
- Branch / HEAD: `feat/retry-policy` / `8c13d9a`
- Key progress since previous handoff: added deterministic error classification, partial integration, and five focused tests
- Next task: confirm the maximum delay and implement bounded exponential delay with tests
