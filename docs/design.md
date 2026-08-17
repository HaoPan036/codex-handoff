# Design

## Problem definition

Codex can compact a long conversation so work continues within a bounded context. A clean continuation still needs a durable answer to four questions:

1. What is true in the repository now?
2. What work is unfinished or uncommitted?
3. Which decisions and constraints remain active?
4. What is the next bounded task?

Chat history alone cannot provide a stable source of truth because it may be compacted, incomplete, or inconsistent with the working tree. Codex Handoff creates a repository artifact that a fresh session must verify.

## Lifecycle choice

The automatic flow uses four events with separate responsibilities.

### SessionStart

`startup`, `clear`, and `resume` each start a new lifecycle generation and discard unverified compact evidence or pending state from the previous generation. `compact` does not start a new generation. It acknowledges the preceding `PostCompact` boundary so a later compaction in the same long turn can receive a different receipt.

### PostCompact

A completed `PostCompact` creates a deterministic receipt from the session, generation, compact boundary, turn, and trigger. Redelivery of the same payload before `SessionStart(source=compact)` is audited as a duplicate and does not increment the count. Reaching the threshold sets `pending_handoff=true`. This event never emits a continuation or blocking decision, because compaction may complete while the active turn still has edits, tools, tests, or subagents to run.

### Stop

At a later `Stop`, the hook does not trust `pending_handoff` alone. It revalidates that the active generation still has at least the configured number of receipts. Stale pending state without that evidence is cleared and audited. When a handoff is valid and `stop_hook_active` is false, the Hook resolves the exact workflow file from the official `PLUGIN_ROOT` (Plugin mode) or installer-provided `CODEX_HANDOFF_SKILL_PATH` (profile mode). It verifies the frontmatter name and verifier file, hashes the Skill, and returns `decision: block` with a structured dispatch record containing the exact path and SHA-256.

The continuation must run the bundled identity verifier with that expected hash before it reads the exact Skill file. It is explicitly forbidden from using Skill discovery, filesystem search, or a similarly named fallback. A missing, unreadable, renamed, or unverifiable workflow produces `CODEX_HANDOFF_SKILL_UNAVAILABLE`; the per-handoff compact count is preserved and no handoff request is recorded.

Every other successful `Stop` path returns valid JSON with `continue: true`. This includes normal stops, repeated stops, missing session identifiers, and continuation stops.

### SessionEnd

`SessionEnd` marks the current generation inactive and clears its pending flag. A later `resume` starts another generation, so an ended lifecycle cannot authorize a future continuation.

## State machine

```text
SESSION_START(startup|clear|resume)
  -> NEW_GENERATION

NEW_GENERATION
  unique PostCompact -> COUNTING

COUNTING
  duplicate PostCompact before compact boundary -> COUNTING unchanged
  SessionStart(compact) -> advance receipt boundary
  unique receipt count < threshold -> COUNTING
  count >= threshold -> PENDING

PENDING
  Stop -> revalidate current-generation receipts
  Stop and stop_hook_active=false -> HANDOFF_REQUESTED
  Stop and stop_hook_active=true -> PENDING
  SessionStart(startup|clear|resume) -> NEW_GENERATION, stale pending discarded

HANDOFF_REQUESTED
  reset count to 0 -> IDLE

PENDING
  Stop with unavailable exact Skill -> IDENTITY_FAILURE

IDENTITY_FAILURE
  preserve count; next PostCompact -> PENDING for retry

ANY ACTIVE STATE
  SessionEnd -> INACTIVE
```

`total_compactions` remains monotonic for local audit. Active receipts and `compact_count_since_handoff` reset after a handoff request so the threshold can recur with independent evidence.

## Data model

State is keyed by Codex `session_id`:

```json
{
  "session-id": {
    "schema_version": 2,
    "generation_id": "6ac2c7...",
    "generation_index": 3,
    "generation_source": "resume",
    "generation_started_at": "2026-08-14T10:00:00+0800",
    "generation_active": true,
    "compact_sequence": 3,
    "compact_receipts": [],
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

Legacy state has no generation-bound receipts. Its lifetime total remains diagnostic history, but its old count and pending flag cannot authorize a continuation.

## Trust boundary

The hook receives lifecycle metadata through standard input. It does not read the transcript path, inspect the repository, or call external services. Its output can only record a completed compact or request a continuation at `Stop`.

The Skill has broader read access because it must inspect repository evidence. Its write boundary is restricted to `docs/CODEX_HANDOFF.md` during preparation.

## Skill identity boundary

Manual `$codex-handoff` remains an explicit Host Skill invocation and `allow_implicit_invocation` remains `false`. Automatic dispatch does not depend on implicit selection. The Hook uses only a host- or installer-provided root of trust, one fixed relative path, an exact frontmatter name, and a content hash. It never enumerates other Skill directories.

Official Codex documentation specifies that a blocking `Stop` reason becomes a continuation prompt and that Plugin hooks receive `PLUGIN_ROOT`; it does not specify a dedicated Hook-to-Skill dispatch API or guarantee that a `$name` embedded in a Hook reason follows the same structured resolver path as a composer mention. The deterministic file identity protocol therefore treats that behavior as unspecified rather than relying on it.

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
