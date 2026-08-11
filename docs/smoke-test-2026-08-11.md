# Plugin smoke-test evidence, 2026-08-11

## Result

**Partial Plugin smoke test passed.**

Codex CLI discovered and installed the `codex-handoff` marketplace package from both the local checkout and the public GitHub shorthand in separate isolated `CODEX_HOME` directories. The hook was then executed from the locally installed Plugin cache, not from the source checkout. Threshold timing, safe `Stop` scheduling, the continuation-loop guard, recurring handoffs, local state, and the audit log behaved as expected.

This was not a complete host-driven end-to-end test. Codex did not emit the lifecycle events during a real long-running session, and the interactive Hook trust UI, Skill-authored handoff, and `codex://new` launch remain to be verified together.

## Environment

- Date: 2026-08-11
- Operating system: macOS 26.5.1, arm64
- Codex CLI: `0.147.0-alpha.6.5`
- Python: `3.14.5`
- Package: `codex-handoff@codex-handoff`, version `0.1.0`
- Installation targets: two isolated temporary `CODEX_HOME` directories
- Marketplace sources: local checkout and `HaoPan036/codex-handoff` at `main`
- Network access: used only for the public GitHub shorthand test

No user Plugin configuration, Hook trust state, repository, or existing v4 profile installation was changed.
The isolated `CODEX_HOME` directories had no login state, and no credential or token was copied into them. This is why the smoke test stopped before starting a model-backed Codex session.

## Marketplace and installation evidence

The local checkout commands used one temporary `CODEX_HOME`:

```bash
codex plugin marketplace add /path/to/codex-handoff --json
codex plugin list --available --json
codex plugin add codex-handoff@codex-handoff --json
codex plugin list --json
```

A second temporary `CODEX_HOME` exercised the public command shown in the README:

```bash
codex plugin marketplace add HaoPan036/codex-handoff --ref main --json
codex plugin list --available --json
codex plugin add codex-handoff@codex-handoff --json
codex plugin list --json
```

Observed results:

- Marketplace name resolved as `codex-handoff`.
- The available package resolved as `codex-handoff@codex-handoff`, version `0.1.0`.
- Installation completed with the Plugin enabled.
- The installed cache contained the manifest, `hooks.json`, Hook script, Skill, `openai.yaml`, handoff template, and all three helper scripts.
- The public shorthand resolved to `https://github.com/HaoPan036/codex-handoff.git`, exposed version `0.1.0`, and installed successfully.
- SHA-256 hashes for the public cached manifest, Hook definition, Hook script, Skill, and all three helpers matched the corresponding files in the current checkout.

## Installed-Hook lifecycle evidence

The cached Hook received six `PostCompact` payloads and three `Stop` payloads across two threshold cycles.

First cycle:

```text
PostCompact 1 recorded | count=1 | pending=false | stdout=empty
PostCompact 2 recorded | count=2 | pending=false | stdout=empty
PostCompact 3 recorded | count=3 | pending=true  | stdout=empty
Stop                  | decision=block | invokes $codex-handoff | safe boundary confirmed
```

Second cycle:

```text
PostCompact 4..6      | count reaches 3 again | pending=true
Stop, hook active     | continue=true | pending remains true
Next normal Stop      | decision=block | invokes $codex-handoff
```

Final state:

```json
{
  "compact_count_since_handoff": 0,
  "total_compactions": 6,
  "pending_handoff": false,
  "handoff_requests": 2
}
```

The local audit log contained nine records: six `PostCompact` events and three `Stop` events, including two `handoff_requested_at_safe_stop` actions.

## Installed-helper evidence

The helper scripts were run from the installed Plugin cache.

- `validate_handoff.py` accepted `examples/CODEX_HANDOFF.example.md` with one retained history entry.
- `collect_snapshot.py` resolved the Git repository, applicable `AGENTS.md`, branch, status, and a passing `git diff --check` result.
- `open_new_session.py --print-only --json` returned a startup prompt that referenced both `AGENTS.md` and `docs/CODEX_HANDOFF.md`.

Print-only mode deliberately avoided opening another application during this isolated test.

## Evidence not claimed

The following items remain open and must not be described as verified yet:

- interactive installation through `/plugins` or the desktop Plugins Directory
- Hook review and trust through the host UI
- lifecycle events emitted by Codex during a real long-running session
- Skill creation or update of `docs/CODEX_HANDOFF.md` from that continuation
- automatic `codex://new` handling by the operating system and Codex
- a second host-driven handoff after another real threshold cycle

Follow [demo.md](demo.md#host-driven-end-to-end-test) to close the remaining gap.

## Earlier v4 implementation

The earlier profile-installed `codex-handoff-session-v4` source was reviewed as implementation provenance. Its installed Skill, Hook, and helper hashes matched the v4 source directory. An available historical handoff artifact predates that v4 installation and lacks the required bounded-history section, so it was not used as proof for the current Plugin smoke test.
