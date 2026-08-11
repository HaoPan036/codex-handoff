# Plugin smoke-test evidence, 2026-08-11

## Result

**Plugin smoke test and two-cycle host-driven end-to-end test passed.**

Codex CLI discovered and installed the `codex-handoff` marketplace package from both the local checkout and the public GitHub shorthand in separate isolated `CODEX_HOME` directories. The hook was then executed from the locally installed Plugin cache, not from the source checkout. Threshold timing, safe `Stop` scheduling, the continuation-loop guard, recurring handoffs, local state, and the audit log behaved as expected.

After the isolated test, the Plugin was installed in the authenticated user profile and exercised by a model-backed Codex CLI session. Codex emitted six real manual `PostCompact` events, scheduled two safe handoff continuations, invoked the Skill twice, validated the two-entry handoff history, prevented continuation loops, and opened a clean session that independently reconciled the second handoff with Git.

## Environment

- Date: 2026-08-11
- Operating system: macOS 26.5.1, arm64
- Codex CLI: `0.147.0-alpha.6.5`
- Python: `3.14.5`
- Package: `codex-handoff@codex-handoff`, version `0.1.0`
- Installation targets: two isolated temporary `CODEX_HOME` directories, followed by the authenticated user profile for the host-driven run
- Marketplace sources: local checkout and `HaoPan036/codex-handoff` at `main`
- Network access: used only for the public GitHub shorthand test

The isolated `CODEX_HOME` directories had no login state, and no credential or token was copied into them. Those checks therefore stopped before starting a model-backed Codex session. The later host-driven run intentionally used the authenticated profile, after backing up and removing the earlier v4 profile Hook so that only the Plugin Hook was active.

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

## Host-driven end-to-end evidence

The host-driven test used the local Marketplace checkout, an authenticated Codex CLI session, a disposable Git repository with no remote or credentials, and `CODEX_HANDOFF_COMPACT_THRESHOLD=3`.

Observed setup and trust flow:

- The earlier profile-installed `codex-handoff-session-v4` configuration was backed up and uninstalled before the Plugin was enabled.
- `codex plugin marketplace add ./` and `codex plugin add codex-handoff@codex-handoff --json` installed version `0.1.0` from the current checkout.
- The bundled `PostCompact` and `Stop` hooks were reviewed and trusted through `/hooks`; unrelated hooks were not granted trust as part of this test.

Observed first cycle:

```text
PostCompact 1..3      | count=1,2,3 | pending becomes true at 3
Normal Stop           | action=handoff_requested_at_safe_stop | requests=1
Continuation          | invokes $codex-handoff | counter resets to 0
Handoff validator     | passes | history=1/5
Continuation Stop     | action=continuation_stop | no loop
```

The first clean-session launch attempt returned `opened: false` after macOS reported `kLSExecutableIncorrectFormat`. The helper returned the complete manual startup prompt, demonstrating the documented non-critical fallback.

Observed second cycle:

```text
PostCompact 4..6      | count=1,2,3 | pending becomes true at 6 total
Normal Stop           | action=handoff_requested_at_safe_stop | requests=2
Continuation          | invokes $codex-handoff | counter resets to 0
Handoff validator     | passes | history=2/5
Clean-session helper  | opened=true
Continuation Stop     | action=continuation_stop | no loop
```

The clean session created by the second `codex://new` launch read the complete handoff, inspected all available Git history, checked branch, HEAD, staged, unstaged, and untracked state, ran `git diff --check` and `git fsck --no-dangling`, and reported no conflict with repository-verifiable handoff claims. It made no repository change.

Final source-session state:

```json
{
  "compact_count_since_handoff": 0,
  "total_compactions": 6,
  "pending_handoff": false,
  "handoff_requests": 2
}
```

The disposable fixture's `docs/CODEX_HANDOFF.md` was the only file changed by either continuation and retained two of five allowed history entries. Each completed handoff update was committed only after its Skill turn had stopped, outside the handoff continuation itself.

The Plugin was then removed with `codex plugin remove codex-handoff@codex-handoff --json`. A structural comparison of `config.toml` before and after removal, excluding only the Plugin's own install and trust entries, found every unrelated setting unchanged. Reinstalling version `0.1.0` produced the same result, restored the Plugin to `enabled: true`, and retained its two Hook trust entries.

## Remaining evidence boundaries

The following items remain open and must not be described as verified yet:

- interactive installation through `/plugins` or the desktop Plugins Directory
- a reviewed, publishable terminal recording of the verified flow

Follow [demo.md](demo.md#recording-the-verified-flow) to produce the publication artifact without overstating the remaining installation and uninstall checks.

## Earlier v4 implementation

The earlier profile-installed `codex-handoff-session-v4` source was reviewed as implementation provenance. Its installed Skill, Hook, and helper hashes matched the v4 source directory. An available historical handoff artifact predates that v4 installation and lacks the required bounded-history section, so it was not used as proof for the current Plugin smoke test.
