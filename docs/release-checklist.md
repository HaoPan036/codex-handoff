# Release checklist

## Code and tests

- [ ] `python3 -m unittest discover -s tests -v` passes.
- [ ] `python3 scripts/validate_package.py` passes.
- [ ] `Stop` emits valid JSON on every successful path.
- [ ] The threshold triggers at the configured count.
- [ ] A handoff request resets the per-handoff counter.
- [ ] `stop_hook_active` does not create a continuation loop.
- [ ] State migration is covered by tests.

## Package

- [ ] `.codex-plugin/plugin.json` version matches `pyproject.toml` and `CHANGELOG.md`.
- [ ] Marketplace source points to `./plugins/codex-handoff`.
- [ ] Plugin paths begin with `./` and remain inside the plugin root.
- [ ] Hook command uses `${PLUGIN_ROOT}`.
- [ ] README installation instructions match the release tag.

## Manual smoke test

- [ ] Add the local marketplace with `codex plugin marketplace add ./`.
- [ ] Install the Plugin from `/plugins` or the desktop directory.
- [ ] Review and trust the Hook.
- [ ] Trigger three completed compactions in a disposable repository.
- [ ] Confirm the active task finishes before the handoff continuation begins.
- [ ] Confirm `docs/CODEX_HANDOFF.md` passes validation.
- [ ] Confirm another three compactions can trigger a second handoff.
- [ ] Confirm uninstall leaves unrelated Hook configuration unchanged.

## Publication

- [ ] Create a signed or annotated `vX.Y.Z` tag.
- [ ] Attach a source archive generated from the tag.
- [ ] Publish release notes from `CHANGELOG.md`.
- [ ] Create a minimal demonstration and community announcement.
- [ ] Monitor Issues and Discussions for installation failures.
