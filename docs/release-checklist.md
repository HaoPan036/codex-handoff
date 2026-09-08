# v0.2.0 release checklist

This checklist applies to the reminder-only release. Evidence is recorded in [smoke-test-2026-09-08.md](smoke-test-2026-09-08.md). The August automatic-handoff results remain in their dated records and do not satisfy a current host check.

## Code and package

- [x] Run `python3 -m unittest discover -s tests -v` using Python 3.11+ (Python 3.11.14: 42 tests passed).
- [x] Run `python3 scripts/validate_package.py` and `git diff --check`.
- [x] Confirm manifest, project, client diagnostic version, changelog, and both README release links say 0.2.0.
- [x] Confirm current homepages display the reminder workflow; historical automatic-handoff footage is labeled and linked separately.
- [x] Confirm installer guidance accounts for a system `python3` older than 3.11.
- [x] Confirm release archives use a resolved Git commit and Git file modes, excluding working-tree changes and untracked files (four archive regression tests).

## Real host acceptance

- [x] Observe real host compactions and reminders at 5/10/15 only.
- [x] Correlate non-blocking reminder messages with host UI or event-stream output (App Server warning entries).
- [x] Ignore reminders and verify normal work completes without automatic handoff.
- [x] Resume the same session and verify count persistence.
- [x] Verify a new session starts a fresh cadence; report clear-path coverage separately.
- [x] Explicitly request `handoff only`, verify Skill identity and validate the generated document.
- [x] Verify existing staged, unstaged, and untracked fixture work is preserved.
- [x] State actual continuation coverage separately from composer or URL dispatch.

## Publication procedure

Completion evidence for these post-commit steps belongs in the [GitHub Release](https://github.com/HaoPan036/codex-handoff/releases/tag/v0.2.0), so the tagged checklist does not claim publication before it happens.

1. Review the final diff and commit all intended release files.
2. Wait for the source commit's GitHub CI matrix to pass.
3. Create annotated tag `v0.2.0` at that exact commit.
4. Build with `python3 scripts/create_release.py --ref v0.2.0`.
5. Build twice and compare checksums; inspect the archive and validate its extracted package.
6. Publish the GitHub Release with source ZIP, SHA256SUMS, upgrade notes, and acceptance link.
7. Read back the remote tag, release metadata, and downloadable asset hashes.

Community announcements and external adoption are separate follow-up work.
