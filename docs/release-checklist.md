# Release checklist

## Code and tests

- [x] `python3 -m unittest discover -s tests -v` passes.
- [x] `python3 scripts/validate_package.py` passes.
- [x] `Stop` emits valid JSON on every successful path.
- [x] The threshold triggers at the configured count.
- [x] A handoff request resets the per-handoff counter.
- [x] `stop_hook_active` does not create a continuation loop.
- [x] State migration is covered by tests.

## Package

- [x] `.codex-plugin/plugin.json` version matches `pyproject.toml` and `CHANGELOG.md`.
- [x] Marketplace source points to `./plugins/codex-handoff`.
- [x] Plugin paths begin with `./` and remain inside the plugin root.
- [x] Hook command uses `${PLUGIN_ROOT}`.
- [x] README installation instructions match the release tag.
- [x] `README.md` and `README.zh-CN.md` make the same behavior and status claims.
- [x] README badges resolve and correspond to the actual workflow, license, Python requirement, and target platforms.
- [x] README local links and the terminal demo resolve from the repository root.
- [x] Demo copy distinguishes the isolated smoke test, host-driven verification, and reviewed publication recording.

## Isolated CLI smoke test

Evidence is recorded in [smoke-test-2026-08-11.md](smoke-test-2026-08-11.md).

- [x] Add the local Marketplace in an isolated `CODEX_HOME`.
- [x] Add and install the public `HaoPan036/codex-handoff` Marketplace from `main` in a second isolated `CODEX_HOME`.
- [x] Discover and install `codex-handoff@codex-handoff` version `0.1.0`.
- [x] Execute the Hook from the installed Plugin cache for two threshold cycles.
- [x] Confirm safe `Stop`, `stop_hook_active`, recurring reset, state, and audit behavior.
- [x] Run the installed snapshot, handoff validator, and clean-session prompt helpers.

## Manual smoke test

Follow [demo.md](demo.md#host-driven-end-to-end-test) and record the Codex version, operating system, installation mode, threshold, and exact result.

- [x] Add the local marketplace with `codex plugin marketplace add ./`.
- [x] Confirm no earlier profile-installed v4 Hook remains enabled alongside the Plugin Hook.
- [x] Install the Plugin from `/plugins` or the desktop directory.
- [x] Review and trust the Hook.
- [x] Trigger three completed compactions in a disposable repository.
- [x] Confirm the active task finishes before the handoff continuation begins.
- [x] Confirm `docs/CODEX_HANDOFF.md` passes validation.
- [x] Confirm another three compactions can trigger a second handoff.
- [x] Confirm the clean-session helper either opens a verified session or returns the complete fallback prompt.
- [x] Confirm uninstall leaves unrelated Hook configuration unchanged.

## Publication

- [x] Create the annotated `v0.1.0` tag at commit `30a8ce2`.
- [x] Attach a source archive generated from the tag and its SHA-256 checksum.
- [x] Publish release notes from `CHANGELOG.md`.
- [x] Replace the conceptual flow with a reviewed terminal recording or keep the conceptual label explicit.
- [ ] Create a community announcement.
- [ ] Monitor Issues and Discussions for installation failures.
