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
- No hook emits a blocking decision or invokes the Skill; `PostCompact` may emit a non-blocking `systemMessage` reminder.
- Remind at counts N, 2N, 3N (default N=5), once per milestone; `Stop` never dispatches work.
- Keep counts and reminder state across resume/startup of the same session; clear/new sessions start a new cadence.
- The hook performs no network call and no repository mutation.
- The Skill updates only `docs/CODEX_HANDOFF.md` during handoff preparation.

## Documentation

Keep `README.md` and `README.zh-CN.md` behaviorally aligned. Update `CHANGELOG.md` when user-visible behavior changes.
