# Design

## Problem definition

Codex can compact a long conversation so work continues within a bounded context. A clean continuation still needs a durable answer to four questions:

1. What is true in the repository now?
2. What work is unfinished or uncommitted?
3. Which decisions and constraints remain active?
4. What is the next bounded task?

Chat history alone cannot provide a stable source of truth because it may be compacted, incomplete, or inconsistent with the working tree. Codex Handoff creates a repository artifact that a fresh session must verify.

## Reminder-only lifecycle (2026-09-08)

The hook and Skill have separate triggers. Only an explicit user invocation starts the Skill; a hook message never authorizes handoff.

- SessionStart startup/resume: retain this session's count, receipts and last reminder; reactivate after SessionEnd. A new session ID starts at zero.
- SessionStart clear: reset the cadence and receipt generation. Lifetime audit totals remain diagnostic.
- SessionStart compact: advance the receipt boundary, so multiple genuine compactions in one turn count separately.
- PostCompact: ignore duplicate delivery before that boundary and events for ended sessions. Increment compact_count on each unique completed event. At N, 2N, 3N (default N=5), emit only continue=true and systemMessage, and record last_reminded_count.
- Stop: always return continue=true. Never resolve a Skill, block a turn, reset the cadence, or request continuation.
- SessionEnd: mark inactive, retaining state for later resume. State older than 30 days expires.

The last-reminded milestone prevents repeated Stop calls or ignored reminders from spamming the user. A manually invoked handoff does not reset the old session's count: the new session has its own state.

## State and migration

Schema 3 uses compact_count, last_reminded_count, reminder_count, bounded compact_receipts and the existing generation/sequence identifiers. Counts can exceed the receipt retention window. Locking, atomic replacement, and bounded metadata-only audit logging remain.

Schema-2 generation-bound receipts may seed the new cadence, but old pending_handoff/continuation flags are discarded and old milestones are not replayed on upgrade. Legacy unverified counters are diagnostic only. Corrupt state restarts counting rather than inventing history; no transcript reconstruction is performed.

The hook makes no network call, does not inspect projects or transcripts, and never opens sessions. The manual Skill retains its own identity verifier and evidence/write boundaries.

## Evidence hierarchy

The Skill resolves conflicts in this order:

1. Current repository files and applicable `AGENTS.md`
2. Git branch, HEAD, status, and history
3. Commands and test results observed in the current workspace
4. Generated artifacts with traceable provenance
5. Existing handoff document
6. Conversation context and compaction summaries

A material statement that cannot be verified is labeled `UNKNOWN`.

## Handoff schema

Sections 1 through 10 are replaced with the current verified state. Section 11 preserves a maximum of five concise historical entries. This gives a new session enough recent orientation while preventing the file from growing without bound.

## Clean-session opening

The workflow constructs a startup prompt and separates native task creation, OS dispatch, prompt prefill, prompt submission, turn start, and thread naming. In the Codex desktop app, it uses native task listing plus titled task creation: the current explicit title is treated as untrusted data, its trailing sequence is incremented, and the title is applied as the clean task is created. The desktop path is:

```text
verified handoff
  -> resolve exact source task title
  -> increment familiar sequence
  -> create local clean task with title and startup prompt
```

When native controls cannot match the exact current workspace (including a worktree), the helper uses the documented [App Server protocol](https://learn.chatgpt.com/docs/app-server):

```text
verified handoff
  -> thread/start with exact cwd
  -> verify cwd, set numbered title, read title back
  -> turn/start with startup prompt once
  -> report task and turn IDs
  -> detached worker keeps server alive until turn/completed
```

The worker owns a private stdio server, inherits normal Codex configuration, and makes no model or permission override. It saves no transcript or new diagnostic files. Closing the launching session does not close the worker. Interactive approval/input requests interrupt the initial turn for continuation in the task UI.

A partial failure can leave a created task or submitted turn. Receipts retain the known IDs and stage; the launcher never retries creation or silently opens a composer. Inspect the existing task before recovery. The bundled desktop CLI is preferred when available, with an explicit executable override for other environments.

`--manual` is an explicit opt-in to the official deep-link composer contract and requires Send. `--print-only` constructs a prompt without opening or sending. Source-name lookup uses `thread/read`; unavailable titles fall back transparently to the workspace name. Compaction reminders still never invoke this workflow.

## Duplicate installation diagnostics

Official Codex behavior merges matching hooks from all active sources. `scripts/doctor.py` therefore reports Plugin, profile, project, and legacy sources without modifying them. The profile installer emits a strong warning when the Plugin is already enabled; it does not silently disable that Plugin.
