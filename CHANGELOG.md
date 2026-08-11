# Changelog

All notable changes are documented here.

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
- Recorded the verified isolated CLI installation and installed-Hook lifecycle smoke test while keeping the remaining host-driven end-to-end boundary explicit.
- Extended package validation and the release checklist to protect the bilingual homepage assets and status claims.
- Documented the migration guard that prevents profile-installed v4 hooks and Plugin hooks from running together.
