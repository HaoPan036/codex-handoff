# Troubleshooting

## The Skill does not appear

Start a new Codex session after installation. Confirm that one of these paths exists:

```text
Plugin: plugins/codex-handoff/skills/codex-handoff/SKILL.md
Profile: ~/.agents/skills/codex-handoff/SKILL.md
```

For profile installation, rerun `bash install.sh 3` and inspect its printed paths.

## Automatic handoff reports `CODEX_HANDOFF_SKILL_UNAVAILABLE`

The Hook could not verify its own exact workflow file. Do not work around this by selecting another `handoff` Skill.

- Plugin mode: remove and reinstall `codex-handoff@codex-handoff`, start a new session, and review the refreshed hooks. The Hook resolves only `${PLUGIN_ROOT}/skills/codex-handoff/SKILL.md`.
- Profile mode: rerun `bash install.sh 3`. The installer rewrites `CODEX_HANDOFF_SKILL_PATH` in both Hook commands to the exact installed Skill.

The compact count is preserved. After repair, the next completed compaction can schedule another safe retry.

## Automatic handoff selected another `handoff` Skill

Version `0.1.0` continuation text could be treated as ordinary prompt text by the Host, allowing the model to choose a similarly named Skill. Reinstall a version containing the deterministic identity fix and start a new session. A fixed audit record named `handoff_requested_at_safe_stop` includes `skill_identity`, `skill_path`, `skill_sha256`, and `skill_resolver`; the continuation trace includes a successful `verify_identity.py` receipt. Absence of those fields means an older cached Hook is still active.

## Compact events are not counted

Review and trust the Hook in Codex. Plugin installation does not imply Hook trust.

Profile installation can be inspected in `~/.codex/config.toml`. It should contain `PostCompact` and `Stop` command hooks that reference `codex_handoff_hook.py`.

Inspect the local audit log:

```bash
tail -n 50 ~/.codex/codex-handoff/events.jsonl
```

Plugin installations store the log under the host-provided `PLUGIN_DATA` directory.

## An unexpected handoff was requested

Run the read-only doctor from a Codex Handoff checkout:

```bash
python3 scripts/doctor.py
```

It reports active Plugin, profile, project, and legacy sources plus possible duplicate execution risk. Codex loads matching hooks from every active source; one source does not override another.

Then inspect state and the bounded audit log. Plugin mode normally uses the host-provided `PLUGIN_DATA`; profile mode uses:

```bash
jq . ~/.codex/codex-handoff/state.json
tail -n 50 ~/.codex/codex-handoff/events.jsonl
```

Look for the same `generation_id`, unique `receipt_id` values, `duplicate`, `compact_count_since_handoff`, and the final Stop `action`. A fresh `startup`, `clear`, or `resume` generation must start with zero active receipts. `stale_pending_rejected` means Stop found a pending flag without enough current-generation evidence and safely ignored it.

## The handoff triggers only once

Versions before `0.1.0` could retain a lifetime counter and never establish a new threshold window. Reinstall `0.1.0` or newer. The current state uses `compact_count_since_handoff` and resets it after every handoff request.

## The handoff runs twice after Plugin installation

Codex loads matching hooks from every active source. Installing the Plugin does not disable hooks left in `~/.codex/config.toml` by an earlier profile-installed `codex-handoff-session` v4.

Open `/hooks` and check whether both the old profile Hook and the Plugin Hook are enabled. To migrate, run the current checkout's uninstaller before enabling the Plugin:

```bash
bash uninstall.sh
```

This removes the current and legacy profile Skill and Hook entries while retaining local counters and logs. It does not remove a separately installed Plugin. Restart Codex, review `/hooks` again, and trust only the Hook set you intend to use.

## Stop Hook reports invalid output

Versions before `0.1.0` could emit no output on a normal `Stop`. The current Hook emits `{"continue": true}` on every successful non-handoff `Stop` path.

## A new composer opened but the continuation did not start

This is the expected deep-link contract. `codex://new?...&prompt=...` opens a new local composer and sets its initial text; it does not submit the prompt. Press **Send** to start the continuation.

The helper reports these layers separately:

```text
deep_link_dispatched
thread_creation_verified
prompt_prefill_requested
prompt_prefilled
prompt_submission_verified
turn_started_verified
thread_name_verified
user_action_required
```

`deep_link_dispatched=true` means only that the operating system accepted the URL. It is not proof of thread creation, prompt submission, turn start, or title assignment. The helper does not set a title, so title behavior is `UNKNOWN` unless independently verified by the Host.

## A new composer does not open

Run the helper manually:

```bash
python3 ~/.agents/skills/codex-handoff/scripts/open_new_session.py \
  /absolute/path/to/workspace docs/CODEX_HANDOFF.md --json
```

When `deep_link_dispatched` is false, copy `startup_prompt` into a new Codex composer and press **Send**. The handoff file remains valid.

## The wrong threshold is used

Profile installation embeds the threshold into the Hook command. Rerun:

```bash
bash install.sh 5
```

Plugin installation reads `~/.codex/codex-handoff.json` unless an environment variable overrides it:

```json
{
  "compact_threshold": 5
}
```

## Remove everything

```bash
bash uninstall.sh --purge-state
```

The uninstaller backs up `~/.codex/config.toml` before removing its Hook entries.
