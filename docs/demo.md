# v0.2.0 walkthrough

The homepage [workflow illustration](assets/codex-handoff-flow.svg) shows the current reminder-only behavior. It is a diagram, not a terminal recording. The [September 8 acceptance record](smoke-test-2026-09-08.md) identifies the host, source hashes, real events, observed results, and remaining limits.

## 1. Keep working through reminders

Install v0.2.0 using one of the README installation paths, restart Codex, and review the exact hooks before trusting them. Use a disposable repository for a demo.

At the default interval of five, completed compactions produce this cadence:

| Completed compactions | Expected behavior |
| --- | --- |
| 1–4 | Count locally; no reminder |
| 5 | One reminder; current task continues |
| 6–9 | No reminder |
| 10 | One reminder; current task continues |
| 11–14 | No reminder |
| 15 | One reminder; current task continues |

The reminder text at five is:

```text
本会话已累计压缩 5 次。需要交接时手动调用 $codex-handoff；当前任务照常继续。下次提醒：10 次。
```

This is the source-defined message, not a screenshot or a claim about every host's visual presentation. The hook uses `systemMessage`; Codex surfaces it in its UI or event stream. `Stop` returns `{"continue": true}` and schedules no work. Ignoring the reminder never writes a handoff or opens a task.

Resuming the same session keeps the count and last reminder. Clearing the conversation or starting a new session starts a new cadence. Manually requesting a handoff does not reset the reminder count.

## 2. Request the handoff yourself

When a milestone is complete, enter:

```text
$codex-handoff handoff only
```

The Skill verifies its identity, checks current Git state and relevant files, and writes `docs/CODEX_HANDOFF.md`. The document has eleven sections, one concrete next task, and at most five history entries. Staged, unstaged, and untracked work should remain intact.

Validate the result from the plugin checkout, replacing the final path with your disposable repository's document:

```bash
python3 plugins/codex-handoff/skills/codex-handoff/scripts/validate_handoff.py /path/to/demo/docs/CODEX_HANDOFF.md
```

Use Python 3.11 or newer. Document validation checks the contract and unresolved placeholders; it does not establish the semantic accuracy of every claim.

## 3. Continue when ready

For a handoff that also prepares a clean continuation, invoke `$codex-handoff` without `handoff only`.

- A host with native task controls can create a titled task.
- The portable helper requests a prefilled composer or prints the startup prompt if opening is unavailable.
- A successful URL dispatch is not proof that a task was created or started. A prefilled composer still requires **Send**.

The release acceptance record states which of these paths were actually exercised. Do not infer fresh desktop UI or native task-creation coverage from a passing hook test.

## Reproduce the host test

1. Use a disposable Git repository with a small deterministic test and representative staged, unstaged, and untracked fixture files.
2. Confirm only one Codex Handoff hook source is active. Isolate its state directory from normal use.
3. Use the real Codex host to complete fifteen compactions. In CLI, use `/compact`; in App Server, use the documented `thread/compact/start` operation.
4. After each request, wait for the host's `contextCompaction` and turn completion events, then continue with a normal short turn before requesting another compaction.
5. Check that the hook audit contains exactly three reminders, at 5/10/15; correlate them with host UI or event output. Verify no handoff document appeared and no automatic continuation started.
6. Resume the same session and check that its count persists. Start a fresh session or use clear and verify the new cadence. Record these cases separately.
7. Explicitly invoke the Skill with `handoff only`; record the identity check, document validation, and preservation of existing work.
8. Test continuation only when intended, recording composer preparation, task creation, and actual turn startup as separate outcomes.

Official contracts: [Hooks](https://learn.chatgpt.com/docs/hooks), [App Server](https://learn.chatgpt.com/docs/app-server).

## Historical recording

The [August 11 GIF](assets/codex-handoff-demo.gif) records the retired v0.1.x automatic-handoff behavior. It is retained for the [historical acceptance record](smoke-test-2026-08-11.md), and is no longer the homepage demo. [August 12 identity checks](smoke-test-2026-08-12.md) and [August 14 lifecycle checks](smoke-test-2026-08-14.md) are also historical, not v0.2.0 acceptance.
