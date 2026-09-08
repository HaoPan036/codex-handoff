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

When native task controls are unavailable, the helper uses the official [desktop deep-link contract](https://developers.openai.com/codex/app/commands/#deeplinks), which sets initial composer text but does not send it:

```text
verified handoff
  -> deep-link dispatch (best effort)
  -> prefilled composer
  -> user presses Send
```

Dispatch failure returns the full startup prompt for manual use, while the verified handoff remains complete. Outside a restricted nested Host sandbox, the portable helper can use stable App Server `thread/read` to resolve an explicit source name. If SQLite initialization is blocked by the sandbox, it reports that failure and falls back to the workspace name rather than claiming title verification.

## Duplicate installation diagnostics

Official Codex behavior merges matching hooks from all active sources. `scripts/doctor.py` therefore reports Plugin, profile, project, and legacy sources without modifying them. The profile installer emits a strong warning when the Plugin is already enabled; it does not silently disable that Plugin.
