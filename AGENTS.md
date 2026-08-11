# Repository instructions

## Source of truth

Treat the source under `plugins/codex-handoff/`, the tests, and the public Codex documentation linked from the README as authoritative. Generated archives are release artifacts and must not be edited directly.

## Required checks

Run both commands after any functional or packaging change:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_package.py
```

## Lifecycle invariants

- `PostCompact` records state and emits no steering decision.
- `Stop` always emits valid JSON when the hook exits with status 0.
- `decision: block` is used only to schedule one safe continuation.
- `stop_hook_active` prevents a continuation loop.
- The per-handoff compact counter resets after a handoff request.
- The hook performs no network call and no repository mutation.
- The Skill updates only `docs/CODEX_HANDOFF.md` during handoff preparation.

## Documentation

Keep `README.md` and `README.zh-CN.md` behaviorally aligned. Update `CHANGELOG.md` when user-visible behavior changes.
