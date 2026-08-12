# Automatic Skill-identity smoke-test evidence, 2026-08-12

## Result

**PASS.** A real Codex Host completed the default three-compaction lifecycle and loaded the current Plugin's exact `codex-handoff` workflow in a disposable repository containing a competing `handoff` Skill. The Host trace contains the deterministic dispatch, successful identity receipt, and exact Skill read. The negative-control marker never appeared, the handoff validator passed, state reset correctly, and the continuation stopped without a loop.

An accelerated one-compaction configuration also completed two recurring cycles with the same Skill path and SHA-256. This second run verifies recurrence independently of the default-threshold timing test.

## Evidence scope

This test addresses the identity gap documented in `smoke-test-2026-08-11.md`. Existence of `docs/CODEX_HANDOFF.md` is not treated as identity proof. Provenance instead comes from three independent signals:

1. The Hook audit event records `skill_identity`, the exact installed `skill_path`, its SHA-256, and `skill_resolver`.
2. The Host trace records a successful `verify_identity.py` JSON receipt for the same path and hash.
3. The Host trace records the exact `codex-handoff` `SKILL.md` read, while the competing Skill's marker and side-effect file remain absent.

## Environment

- Date: 2026-08-12
- Operating system: macOS 26.5.1 (build 25F80), arm64
- Codex CLI: `0.147.0-alpha.6.5`
- Python: `3.14.5`
- Installation mode: authenticated profile with `codex-handoff@codex-handoff` installed from the local Marketplace checkout
- Package version: manifest version `0.1.0` plus the uncommitted identity fix under test
- Workspace: disposable Git repository under `/private/tmp`, with no remote or credentials
- Baseline HEAD: `4cdb975d53b039286652bd9cc7b0990c48f2a1df`

The first attempted Host run exposed a stale Plugin cache that lacked the new identity fields. That run was rejected as evidence. The Plugin was removed and reinstalled, a new session was started, and the installed cache was checked for the new Hook and verifier before the passing runs below. This confirms that an already installed development version must be refreshed before testing changed package contents.

## Competing-Skill fixture

The disposable repository advertised a repository-local Skill named `handoff`. Its description identified it as a negative control, its file contained `WRONG_HANDOFF_SKILL_USED`, and executing it would have created `WRONG_HANDOFF_SKILL_USED.txt`. Repository instructions prohibited reading or running that Skill.

The Host's available-Skills context included this competing `handoff` entry. After all automatic cycles:

```text
WRONG_HANDOFF_SKILL_USED in execution trace: absent
Read of competing handoff/SKILL.md: absent
WRONG_HANDOFF_SKILL_USED.txt: absent
```

## Default-threshold Host lifecycle

Session `019ff49e-3311-7883-a0f0-7697a2447903` ran with `CODEX_HANDOFF_COMPACT_THRESHOLD=3`:

```text
PostCompact #1 | count=1 | pending=false | total=1
PostCompact #2 | count=2 | pending=false | total=2
PostCompact #3 | count=3 | pending=true  | total=3
Normal Stop    | decision=block | handoff_requests=1
Continuation   | exact Skill identity verified and exact SKILL.md read
Validator      | passed | history=3/5
Continuation Stop | action=continuation_stop | no second dispatch
```

The `handoff_requested_at_safe_stop` audit record contained:

```json
{
  "compact_count_since_handoff": 3,
  "handoff_requests": 1,
  "skill_identity": "codex-handoff",
  "skill_path": "<CODEX_HOME>/plugins/cache/codex-handoff/codex-handoff/0.1.0/skills/codex-handoff/SKILL.md",
  "skill_resolver": "plugin_root",
  "skill_sha256": "ec2912faac5a915e687a19ef0df2d2ab98f7654311f766a6afc70bd430101f12",
  "threshold": 3,
  "total_compactions": 3
}
```

The Host trace contained a successful receipt with `name: codex-handoff`, the same exact path and SHA-256, and `verified: true` before the Skill workflow was followed. The generated `docs/CODEX_HANDOFF.md` separately recorded that identity-verifier command and passed the installed `validate_handoff.py`:

```text
Handoff validation passed
History entries retained: 3/5
```

Final lifecycle state:

```json
{
  "compact_count_since_handoff": 0,
  "total_compactions": 3,
  "pending_handoff": false,
  "handoff_requests": 1
}
```

## Recurring automatic Host lifecycle

A separate session, `019ff493-f903-7852-96f1-2b6824971c33`, used threshold 1 to make a two-cycle real-Host regression affordable. Both normal Stops recorded the same exact path and SHA-256 shown above. Both continuations produced successful identity receipts, read the exact Skill, validated the handoff, and ended with `continuation_stop`.

Final recurring state:

```json
{
  "compact_count_since_handoff": 0,
  "total_compactions": 2,
  "pending_handoff": false,
  "handoff_requests": 2
}
```

This accelerated recurrence complements unit coverage that performs two complete threshold-three cycles.

## Manual invocation compatibility

The Skill identity remains `codex-handoff`, `agents/openai.yaml` still contains `allow_implicit_invocation: false`, and the default composer prompt remains present. Automated tests verify those contracts. The automatic path no longer relies on a `$codex-handoff` mention or implicit discovery, so the explicit-only manual boundary is unchanged.

The user's pre-fix real-host observation established that manual `$codex-handoff` discovery worked. This run did not repeat a separate manual composer invocation; it verifies that the files and metadata supporting it were not changed incompatibly.

## Safety and limitations

- During each handoff, only `docs/CODEX_HANDOFF.md` was created or updated by the workflow. Existing staged, unstaged, and untracked work was preserved.
- The Hook handled lifecycle metadata and local state only; it did not read the repository or transcript, make network requests, or modify the repository.
- The `codex://new` deep link had no compatible handler in this environment. The documented manual startup-prompt fallback was returned; this did not affect Skill identity or handoff validation.
- Absolute cache paths are deliberately normalized above. The audit and Host trace remain local and contain no credentials.
