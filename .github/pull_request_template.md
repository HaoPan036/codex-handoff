## Problem

Describe the concrete issue this change addresses.

## Changes

Describe the bounded implementation.

## Lifecycle and safety review

- [ ] `PostCompact` remains non-interrupting.
- [ ] Every successful `Stop` path emits valid JSON.
- [ ] `Stop` never dispatches a handoff, including when `stop_hook_active` is set.
- [ ] Reminders occur once at N, 2N, 3N; resume preserves the cadence and clear resets it.
- [ ] The Hook performs no network or repository mutation.
- [ ] The Skill preserves the working tree and its write boundary.

## Validation

- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `python3 scripts/validate_package.py`
- [ ] Relevant manual smoke test documented

## Documentation

- [ ] English and Chinese README behavior remains aligned.
- [ ] `CHANGELOG.md` updated for user-visible behavior.
