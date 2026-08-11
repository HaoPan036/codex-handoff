# Design

## Problem definition

Codex can compact a long conversation so work continues within a bounded context. A clean continuation still needs a durable answer to four questions:

1. What is true in the repository now?
2. What work is unfinished or uncommitted?
3. Which decisions and constraints remain active?
4. What is the next bounded task?

Chat history alone cannot provide a stable source of truth because it may be compacted, incomplete, or inconsistent with the working tree. Codex Handoff creates a repository artifact that a fresh session must verify.

## Lifecycle choice

The automatic flow uses two events with separate responsibilities.

### PostCompact

A completed `PostCompact` increments a per-session counter. Reaching the threshold sets `pending_handoff=true`. This event never emits a continuation or blocking decision, because compaction may complete while the active turn still has edits, tools, tests, or subagents to run.

### Stop

At a later `Stop`, the hook checks the pending flag. When a handoff is pending and `stop_hook_active` is false, it returns `decision: block` with a continuation prompt that explicitly invokes `$codex-handoff`.

Every other successful `Stop` path returns valid JSON with `continue: true`. This includes normal stops, repeated stops, missing session identifiers, and continuation stops.

## State machine

```text
IDLE
  PostCompact -> COUNTING

COUNTING
  count < threshold -> COUNTING
  count >= threshold -> PENDING

PENDING
  PostCompact -> PENDING with a higher count
  Stop and stop_hook_active=false -> HANDOFF_REQUESTED
  Stop and stop_hook_active=true -> PENDING

HANDOFF_REQUESTED
  reset count to 0 -> IDLE
```

`total_compactions` remains monotonic for local audit. `compact_count_since_handoff` resets after a handoff request so the threshold can recur.

## Data model

State is keyed by Codex `session_id`:

```json
{
  "session-id": {
    "compact_count_since_handoff": 0,
    "total_compactions": 3,
    "pending_handoff": false,
    "handoff_requests": 1,
    "cwd": "/workspace",
    "updated_at": 1786434000.0,
    "last_handoff_requested_at": "2026-08-11T13:00:00+0800"
  }
}
```

State writes use a lock and atomic replacement. Records older than 30 days are pruned when the hook runs.

## Trust boundary

The hook receives lifecycle metadata through standard input. It does not read the transcript path, inspect the repository, or call external services. Its output can only record a completed compact or request a continuation at `Stop`.

The Skill has broader read access because it must inspect repository evidence. Its write boundary is restricted to `docs/CODEX_HANDOFF.md` during preparation.

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

The helper constructs a startup prompt and makes a best-effort attempt to pass a `codex://new` URL to the operating system. This step is deliberately non-critical. Failure returns the full startup prompt for manual use, while the verified handoff remains complete.
