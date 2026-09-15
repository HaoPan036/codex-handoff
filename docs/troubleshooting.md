# Troubleshooting

## The Skill does not appear

Start a new Codex session after installation. Confirm that one of these paths exists:

```text
Plugin: plugins/codex-handoff/skills/codex-handoff/SKILL.md
Profile: ~/.agents/skills/codex-handoff/SKILL.md
```

For profile installation, rerun `bash install.sh 5` and inspect its printed paths.

## An automatic handoff still starts

The reminder-only hook never invokes a Skill or returns a blocking decision. An automatic handoff indicates an older installation or another hook. Run `python3 scripts/doctor.py` and review `/hooks`; do not assume this source checkout is already installed. Historical automatic-dispatch identity diagnostics remain in the dated smoke-test records.

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

Look for `compact_count`, `last_reminded_count`, `reminder_shown`, and `duplicate_compact_ignored`. Counts persist across resume/startup of the same session. Clear starts at zero. `Stop` never creates a handoff; reminders recur at N, 2N, 3N only. Legacy totals do not seed new reminders without verifiable receipts.

## The hook runs twice after Plugin installation

Codex loads matching hooks from every active source. Installing the Plugin does not disable hooks left in `~/.codex/config.toml` by an earlier profile-installed `codex-handoff-session` v4.

Open `/hooks` and check whether both the old profile Hook and the Plugin Hook are enabled. To migrate, run the current checkout's uninstaller before enabling the Plugin:

```bash
bash uninstall.sh
```

This removes the current and legacy profile Skill and Hook entries while retaining local counters and logs. It does not remove a separately installed Plugin. Restart Codex, review `/hooks` again, and trust only the Hook set you intend to use.

## Stop Hook reports invalid output

Versions before `0.1.0` could emit no output on a normal `Stop`. The current Hook emits `{"continue": true}` on every successful `Stop` path.

## A new composer opened but the continuation did not start

Version 0.2.0 used an unsent deep-link composer when native task controls could not match a saved project. Version 0.2.1 automatically creates and starts the task in the exact workspace through App Server. Refresh the marketplace and reinstall the plugin; verify its installed version. A composer requiring Send is now only expected with explicit `--manual`.

The automatic receipt separates `thread_creation_verified`, `thread_name_verified`, `prompt_submission_verified`, and `turn_started_verified`, and includes `thread_id`, `turn_id`, and `launch_stage` when known. An uncertain result is not safe to repeat blindly: inspect the reported task and recent tasks first. Startup success confirms submission, not completion of the new task's work.

## CLI startup fails

The helper prefers the desktop-bundled CLI when available. An incompatible global npm CLI can fail or hang even when desktop works. Pass `--codex-bin /absolute/path/to/codex` or set `CODEX_HANDOFF_CODEX_BIN` to select a working executable. `--print-only --json --source-thread-id <id>` can verify title lookup without creating a task.

The worker keeps its private server alive until the first turn completes. If that turn requests interactive input or approval, it is interrupted; continue in the created task. The helper cannot approve requests on the user's behalf.

## The next task did not inherit my numbered title

The desktop workflow matches the exact source task id, treats its title as untrusted data, and increments only a trailing integer that is not part of a dotted or hyphenated version. Examples: `KB` becomes `KB2`, `KB2` becomes `KB3`, while `release-v0.1.0` becomes `release-v0.1.02` only when explicitly supplied as a task title; a workspace-name fallback simply appends `2`.

In a restricted CLI or App Server continuation, nested App Server startup may be unable to initialize the Codex SQLite state. The helper reports this in `name_lookup_message` and falls back to the workspace name. Use `--source-thread-name "My Task2"` to supply an explicit portable title manually.

## Explicit manual preparation

Only when you want a prefilled composer instead of automatic startup, run:

```bash
python3 ~/.agents/skills/codex-handoff/scripts/open_new_session.py \
  /absolute/path/to/workspace docs/CODEX_HANDOFF.md --manual --json
```

`deep_link_dispatched` confirms only OS dispatch. Press Send in the composer. If dispatch fails, use the returned `startup_prompt` manually. Do not switch to this mode after an uncertain automatic submission until you have checked for an existing task.

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
