# Changelog

All notable changes are documented here.

## 0.2.0, 2026-09-08

### Changed

- Replaced automatic Stop handoffs with non-blocking PostCompact reminders at N, 2N, 3N completed compactions; the default interval is five.
- Handoffs now start only when the user explicitly invokes `$codex-handoff`. Ignoring a reminder never dispatches work, writes a handoff, or opens a task.
- Preserve counts and reminder milestones when the same session resumes or restarts; clear/new sessions start a fresh cadence. A manual handoff does not reset that cadence.
- State schema 3 removes automatic-dispatch flags. Verified schema-2 receipts may seed the cadence; unverifiable legacy totals remain diagnostic only, and already-reached milestones do not replay.
- Aligned plugin, profile, and shell defaults at five. The profile installer preserves unrelated configuration and warns about duplicate Plugin + profile hooks.
- Replaced the homepage's old automatic-handoff recording with an explicitly labeled reminder workflow illustration and current walkthrough. Historical test records remain separate.

### Fixed

- Corrected portable continuation results: OS deep-link dispatch does not verify task creation, prompt submission, turn start, or naming. A prefilled composer requires **Send**.
- The desktop Skill uses native titled task creation when available; portable hosts retain a transparent workspace-name fallback.
- Build source ZIPs from a resolved Git revision, including its committed file modes, instead of scanning the working directory. Local edits and untracked files cannot enter the archive.

### Verification and upgrades

- The [September 8 acceptance record](docs/smoke-test-2026-09-08.md) documents current host behavior and its verification limits.
- Added release archive regression tests and validation of the current changelog and bilingual README version links.
- Added a read-only installation diagnostic, `scripts/doctor.py`.
- Upgrade one installation path at a time, restart the session, and review the updated hooks. Existing pending automatic handoffs will not run.
- Python 3.11+ is required. If `python3` resolves to an older macOS system interpreter, use `python3.11 scripts/install_profile.py --threshold 5`.

## 0.1.1, 2026-08-12

### Fixed

- Bound automatic handoff continuations to the current installation's exact `codex-handoff/SKILL.md` path and SHA-256, with a verifier receipt and clear failure instead of silently substituting another `handoff` Skill.
- Pinned profile-installed Hook commands to the exact installed Skill path while retaining explicit-only manual invocation.

### Changed

- Corrected the 2026-08-11 smoke-test claim: its continuation text and generated artifacts did not by themselves prove which Skill file the Host loaded.
- Added competing-Skill, unavailable-Skill, recurring identity, loop-prevention, profile-path, audit-provenance, and real Host regression evidence.

## 0.1.0, 2026-08-11

### Added

- Codex plugin package with `PostCompact` and `Stop` lifecycle hooks.
- Explicit `$codex-handoff` Skill with evidence-first safety rules.
- Recurring compact threshold with safe `Stop` continuation.
- Valid JSON output for every successful `Stop` hook path.
- Current-state plus five-entry handoff history contract.
- Repository snapshot, handoff validation, and clean-session helpers.
- Plugin marketplace metadata and profile installation fallback.
- Migration from compatible v3 compact counters.
- Standard-library test suite and package validator.
- English and Chinese documentation.

### Changed

- Reworked both README homepages around a concise value proposition, early profile-installer quick start, and a clearly labeled conceptual workflow visual.
- Recorded the verified isolated CLI installation and installed-Hook lifecycle smoke test as the first stage of release verification.
- Extended package validation and the release checklist to protect the bilingual homepage assets and status claims.
- Documented the migration guard that prevents profile-installed v4 hooks and Plugin hooks from running together.
- Recorded a model-backed macOS host test covering interactive Hook trust, six host-emitted compactions, two recurring handoffs, validated bounded history, continuation-loop prevention, launch fallback, and clean-session verification.
- Verified that Plugin removal and reinstallation preserve all unrelated Codex configuration and restore the enabled Plugin with its Hook trust state.
- Verified local Marketplace installation through the Codex `/plugins` interface and confirmed the installed version, enabled state, and retained Hook trust entries.
- Replaced the README hero workflow illustration with a reviewed 18-second GIF from a real host-driven Codex run covering three compactions, safe `Stop`, explicit handoff invocation, validation, and clean-session fallback.

### Fixed

- Kept the test suite syntactically compatible with the documented Python 3.11 minimum.
