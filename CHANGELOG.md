# Changelog

All notable changes are documented here.

## Unreleased

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
