## Problem

Describe the concrete issue this change addresses.

## Changes

Describe the bounded implementation.

## Lifecycle and safety review

- [ ] `PostCompact` remains non-interrupting.
- [ ] Every successful `Stop` path emits valid JSON.
- [ ] `stop_hook_active` cannot create a continuation loop.
- [ ] The recurring threshold still resets after a handoff request.
- [ ] The Hook performs no network or repository mutation.
- [ ] The Skill preserves the working tree and its write boundary.

## Validation

- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `python3 scripts/validate_package.py`
- [ ] Relevant manual smoke test documented

## Documentation

- [ ] English and Chinese README behavior remains aligned.
- [ ] `CHANGELOG.md` updated for user-visible behavior.
