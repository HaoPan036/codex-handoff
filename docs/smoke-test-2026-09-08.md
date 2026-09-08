# Real-host reminder and manual-handoff acceptance — 2026-09-08

## Result and scope

**PASS:** fifteen real, model-backed App Server compactions produced exactly three reminder warnings, at counts **5, 10, and 15**. Normal turns continued after every compaction. Restarting the App Server and resuming the same thread preserved the count. A new thread with the `clear` start source began at zero. An explicit `$codex-handoff handoff only` invocation then created and validated the handoff document.

The first run used a clean disposable Git repository. A second explicit handoff also **passed** preservation checks with staged, unstaged, and untracked changes present. It retained those contents and the Git index while updating only the handoff document.

The [public evidence summary](assets/host-evidence-summary-2026-09-08.json) contains the completed compaction item IDs, exact warning text, counters, source hashes, and selected validation results. It excludes private paths, credentials, and full conversation logs.

## Environment and isolation

| Item | Observed value |
| --- | --- |
| First run | 2026-09-08, 18:54:52–19:07:14, UTC+08:00 |
| Source base commit | `7ee30b0cff9afa9b6b9fc8f65a9173763703f0b5` |
| Codex CLI | `0.153.4`, the existing desktop-bundled executable |
| Operating system | macOS `15.7.3` (`24G419`) |
| Python | `3.11.14` |
| Model | Existing default `gpt-6-astra`, low reasoning effort |
| Reminder threshold | `5` |
| Hook installation mode | Project-local Hook definitions invoking current repository source |
| Other enabled Plugins / MCP servers | `0 / 0` in the test process |
| Hook state | Dedicated disposable `PLUGIN_DATA` directory |

The fixture had no remote and contained only simple public test data. The four matcher groups and event types came from the source `hooks/hooks.json`; their commands were adapted to an explicit Python 3.11 executable, source path, and isolated state directory. `hooks/list` reported exactly four enabled, trusted project Hooks, with no additional sources or discovery errors.

The exact reviewed Hook hashes and fixture trust were supplied through process-scoped configuration overrides. This did not persist Hook trust or change the user's configuration. The user `config.toml` SHA-256 was identical before and after the run. `HOME` and `CODEX_HOME` were not redefined, and the existing Codex login was used in place without copying or printing credentials.

This is a **current-source project-Hook integration test**, not proof of marketplace discovery, installation of the release archive, or interaction with the native `/hooks` trust screen.

Source fingerprints, unchanged at the end of the first run:

```text
hooks/codex_handoff_hook.py
02bc4db6cc6332a9096f29cdb133d5cc9b745ed64927b2494fa83f35121eb888

skills/codex-handoff/SKILL.md
6fba5bb0508c82281ff9ff045c3759e45f25597aa473bebc1505ca8c8a430320
```

## Scenario 1 — fifteen genuine compactions

Thread `01a080a8-0d16-7a41-8a63-cf7190089c52` first completed a short `READY` turn. The test client then issued fifteen sequential [`thread/compact/start`](https://developers.openai.com/codex/app-server/) requests. For each request it waited for a completed `contextCompaction` item and `turn/completed`, inspected the Hook's persisted count, and sent a normal user turn requesting `OK1` through `OK15`.

Every counter receipt originated from a completed host compaction. All fifteen post-compaction user turns completed successfully. Before the explicit handoff invocation there were no tool executions or handoff files.

| Completed count | Total reminders | Host observation |
| --- | --- | --- |
| 1–4 | 0 | No reminder warning |
| 5 | 1 | Warning; next reminder 10 |
| 6–9 | 1 | No additional reminder warning |
| 10 | 2 | Warning; next reminder 15 |
| 11–14 | 2 | No additional reminder warning |
| 15 | 3 | Warning; next reminder 20 |

The exact first warning was:

```text
本会话已累计压缩 5 次。需要交接时手动调用 $codex-handoff；当前任务照常继续。下次提醒：10 次。
```

All three messages arrived as `kind: "warning"` entries in **`hook/completed.run.entries`**. This is evidence from the real App Server event stream consumed by clients. It is not a native desktop or terminal screenshot, and the run does not establish how each client visually renders that warning. See the official [Hook output contract](https://developers.openai.com/codex/hooks).

The first phase completed 31 planned turns: one initial turn, fifteen compaction turns, and fifteen normal replies. The sixteen normal `Stop` Hooks completed without starting handoff work. The fixture still had no `docs/CODEX_HANDOFF.md` after `OK15`.

## Scenario 2 — resume and a new clear-sourced thread

The test client shut down its App Server process, started another, and called `thread/resume` on the same thread ID. The resumed normal turn completed with `RESUMED`. Observed state remained:

```text
compact_count        15
reminder_count        3
last_reminded_count  15
```

No extra reminder or automatic handoff appeared on resume.

The client then called `thread/start` with the protocol's `sessionStartSource: "clear"`. New thread `01a080b0-b599-7552-ba54-acd807ee0aa7` completed a normal `FRESH` turn with `generation_source: "clear"`, zero compactions, and zero reminders.

This verifies a real new thread with the clear start source. It does **not** test clearing the original populated thread through a native UI. Same-session synthetic clear handling belongs to the isolated Hook tests, a separate evidence category.

## Scenario 3 — explicit handoff in a clean fixture

Only after the cadence and resume checks did the client submit `$codex-handoff handoff only` with the exact source Skill path. The model read that `SKILL.md`, executed its identity helper, collected repository evidence, and wrote `docs/CODEX_HANDOFF.md`. The identity receipt reported:

```json
{
  "name": "codex-handoff",
  "sha256": "6fba5bb0508c82281ff9ff045c3759e45f25597aa473bebc1505ca8c8a430320",
  "verified": true
}
```

The fixture's `add` helper passed three small baseline assertions. The proposed future `subtract(a, b)` task remained unimplemented. The only new repository file was the handoff document; the initial fixture had no staged, unstaged, or untracked user changes to preserve.

The model ran the bundled validator successfully. An independent invocation after the model turn also exited `0` and reported:

```text
Handoff validation passed: <fixture>/docs/CODEX_HANDOFF.md
History entries retained: 1/5
```

The document path is normalized here for privacy. The original file's SHA-256 is in the evidence summary. Document validation checks its structural contract; this result alone does not independently establish every semantic claim in a handoff.

No composer or continuation thread was opened by the handoff workflow. Both fixture threads were archived after the first run.

## Scenario 4 — staged, unstaged, and untracked preservation

**PASS:** the same disposable fixture and existing thread were reused for a second explicit `handoff only` invocation. Before that invocation, the fixture received an added, staged `staged-sentinel.txt`, an unstaged edit to tracked `README.md`, and a separate untracked `untracked-sentinel.txt`.

Turn `01a080b5-42b8-78d1-8c6a-e466425e4150` verified the same Skill identity and updated the existing document. Independent before/after snapshots showed identical content SHA-256 values for the fixture source and sentinel files, identical `git ls-files --stage` output, identical staged diffs and unstaged README diffs, and identical status entries outside the handoff path:

```text
 M README.md
A  staged-sentinel.txt
?? untracked-sentinel.txt
```

The host also captured content-hash maps of every fixture file except the handoff document before and after its update. Independently parsing the two command results confirmed that those maps matched, including `.git/index`. Git inspection in that host turn used `GIT_OPTIONAL_LOCKS=0`. Selected fingerprints and both independent snapshots are included in the public evidence summary.

Only `docs/CODEX_HANDOFF.md` changed. Its SHA-256 changed, both the host and independent validator exited `0`, and the document retained two history entries (`2/5`). The future `subtract(a, b)` task stayed unimplemented. The fixture thread was archived again after the checks, and the user configuration hash remained unchanged.

## Boundaries of this acceptance

- The run used real manual compactions. Automatic compaction under context pressure was not forced.
- The observed UI-facing evidence is the App Server warning entry, not a GUI or TUI capture.
- Marketplace installation, installed-package trust interaction, Windows, and native same-thread UI clearing were not exercised here.
- Clean-session opening and task-title propagation were outside the `handoff only` scope.
- Repository unit tests, package validation, archive installation checks, and CI are separate release gates; their results should be cited separately from this host record.
