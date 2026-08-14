---
name: codex-handoff
description: Create or update docs/CODEX_HANDOFF.md from repository, Git, tests, and current-task evidence, validate it, and prepare a clean Codex continuation. Use after repeated context compaction, before switching sessions, at milestone boundaries, or when the user explicitly asks for a handoff or clean session.
---

# Codex handoff workflow

Move ongoing repository work into a clean Codex session using evidence that a fresh session can verify. When the compact-threshold hook invokes this skill, the current user turn has already reached a normal `Stop` boundary. Do not resume implementation in the old session.

## Default result

1. Create or update `docs/CODEX_HANDOFF.md`.
2. Verify it against current repository evidence.
3. Validate the document with the bundled validator.
4. Best-effort: open a clean Codex composer with the startup prompt prepared.
   The user must press Send to start the continuation turn.
5. End work in the old session after reporting the result.

When the user requests `handoff only`, complete steps 1 through 3 and do not open another session.

## Safety and source-of-truth rules

- Treat repository files, Git history, test results, generated artifacts, and applicable `AGENTS.md` files as authoritative.
- Treat conversation history and compaction summaries as leads that require verification.
- Mark a material claim `UNKNOWN` when available evidence cannot verify it.
- Do not commit, push, reset, clean, discard, stash, archive, delete, or rewrite user work unless the user explicitly requested that action.
- Do not modify application source files while preparing the handoff. Only update `docs/CODEX_HANDOFF.md`, apart from temporary files created outside the repository by helper scripts.
- Do not include secrets, credentials, full large logs, complete diffs, or unnecessary user data.
- Preserve staged, unstaged, and untracked work and describe it accurately.

## Workflow

### 0. Verify workflow identity

Run the identity helper located beside this `SKILL.md` before gathering repository evidence:

```bash
python3 <skill-directory>/scripts/verify_identity.py <skill-directory>/SKILL.md
```

Require a successful JSON receipt whose `name` is exactly `codex-handoff` and retain the receipt in the host trace or final report as workflow provenance. Do not add the receipt or a provenance marker to `docs/CODEX_HANDOFF.md`. If an automatic dispatch supplied an expected SHA-256, pass it with `--expect-sha256` and stop with `CODEX_HANDOFF_SKILL_IDENTITY_ERROR` if verification fails. Never substitute another handoff Skill.

### 1. Resolve the workspace

Use the current working directory. When it belongs to a Git repository, resolve the repository root:

```bash
git rev-parse --show-toplevel
```

Use `<repository-root>/docs/CODEX_HANDOFF.md`. For a non-Git workspace, use `<current-working-directory>/docs/CODEX_HANDOFF.md`.

### 2. Gather deterministic evidence

Run the snapshot helper located beside this `SKILL.md`:

```bash
python3 <skill-directory>/scripts/collect_snapshot.py <workspace-path>
```

Read its JSON output. Then inspect the evidence relevant to the current task:

- Every applicable `AGENTS.md` from the workspace root to the current working directory.
- The existing `docs/CODEX_HANDOFF.md`, when present.
- Git branch, HEAD, status, staged changes, unstaged changes, untracked files, and recent commits.
- Relevant source files, configuration, schemas, tests, documentation, and generated artifacts.
- Exact commands and results that establish the current behavior.

Do not run an expensive full test suite solely for the handoff when focused verification is sufficient. Record important checks that were not run and the reason.

### 3. Write the current state plus bounded history

Use `assets/CODEX_HANDOFF.template.md` as the structural contract.

- Rewrite sections 1 through 10 to represent the verified state now. Remove stale claims.
- Preserve valid entries in section 11, append one entry for the current handoff, and retain only the 5 most recent entries.
- When an older handoff lacks section 11, add the section and only the current entry. Do not invent earlier history.
- Keep each history entry concise. Include timestamp, reason, branch and HEAD, 1 to 4 verified changes since the previous handoff, and one next task.
- Derive progress since the previous handoff from repository, Git, and test evidence. Use `UNKNOWN` when the delta cannot be established safely.

The final document must contain:

1. Timestamp, workspace, branch, HEAD, and reason.
2. Objective, exact scope, and explicit non-goals.
3. Completed, in-progress, and remaining work.
4. Architecture, data flow, interfaces, schemas, and dependencies.
5. Decisions, reasons, invariants, constraints, and rejected approaches.
6. Relevant file and symbol references.
7. Commands run, results, and checks not run.
8. Staged, unstaged, and untracked work.
9. Failures, risks, edge cases, and `UNKNOWN` items.
10. One bounded next task and a startup checklist.
11. No more than 5 compact history entries.

Prefer file paths, symbols, commit SHAs, commands, and observable behavior over narrative history.

### 4. Validate

Run:

```bash
python3 <skill-directory>/scripts/validate_handoff.py <handoff-path>
```

Read the final file. In a Git repository, inspect:

```bash
git diff -- docs/CODEX_HANDOFF.md
git status --short -- docs/CODEX_HANDOFF.md
```

Fix missing sections, unresolved placeholders, stale claims, unsupported certainty, contradictory status, oversized history, or vague next steps.

### 5. Prepare the clean continuation

Unless the user requested `handoff only`, run:

```bash
python3 <skill-directory>/scripts/open_new_session.py <workspace-root> docs/CODEX_HANDOFF.md --json
```

The helper makes a best-effort attempt to pass a `codex://new` deep link to the local operating system. The official deep-link contract pre-fills the composer and does not submit the prompt. Treat `deep_link_dispatched` only as an operating-system dispatch receipt; it does not verify thread creation, prompt submission, turn start, or thread naming. When dispatch succeeds, tell the user to press Send. When it fails, use the returned `startup_prompt` in a new Codex composer. Either outcome leaves the verified handoff valid.

Do not use `/fork`. The goal is a clean session that verifies the handoff against the repository.

### 6. End the old session

Report only:

- Handoff path.
- Branch and HEAD used.
- Verification commands and results.
- The helper's separate dispatch and verification fields.
- `User action required: press Send` whenever a composer was prepared.

Do not continue feature implementation in the old session.
