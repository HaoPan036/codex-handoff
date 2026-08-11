# Contributing to Codex Handoff

Thank you for helping improve reliable long-session continuation for Codex.

## Design constraints

Changes must preserve these properties:

1. `PostCompact` only records a completed compaction. It must not interrupt the active turn.
2. Automatic handoff begins at a later `Stop` boundary.
3. Every successful `Stop` hook execution emits valid JSON.
4. A handoff request resets the per-handoff counter so the threshold can recur.
5. The hook does not read transcripts, inspect repository content, call the network, or mutate project files.
6. The Skill treats repository and verification evidence as stronger than chat history.
7. The handoff workflow preserves staged, unstaged, and untracked work.
8. Sections 1 through 10 represent current state. Section 11 retains at most five history entries.

Read [docs/design.md](docs/design.md) before changing lifecycle behavior.

## Development setup

Python 3.11 or newer is recommended.

```bash
git clone https://github.com/haopan036/codex-handoff.git
cd codex-handoff
python3 -m unittest discover -s tests -v
python3 scripts/validate_package.py
```

No third-party runtime dependency is required.

## Pull requests

Keep each pull request focused. Include:

- the problem and expected behavior
- affected lifecycle events
- tests for every changed branch
- compatibility impact
- any migration required for existing state or configuration

Do not include credentials, private transcripts, proprietary repositories, or generated handoff files from real projects.

## Commit scope

Prefer small commits that separate lifecycle logic, tests, documentation, and packaging changes. Avoid drive-by formatting changes in unrelated files.
