# Real-host lifecycle and continuation smoke test — 2026-08-14

## Scope

This record covers the unreleased lifecycle-isolation and clean-continuation corrections prepared on top of public `v0.1.1`. All model turns and file writes used `/private/tmp/codex-handoff-appserver.mIHh8Y`; no private repository or credential was supplied. The installed Plugin cache was refreshed from the local source checkout before testing.

## Environment

| Item | Observed value |
| --- | --- |
| Source HEAD before the patch | `57864a62be41` |
| Codex CLI | `0.147.0-alpha.6.5` |
| Codex Desktop host | `26.803.61601` |
| Operating system | macOS `26.5.1` (`25F80`) |
| Installation mode | Plugin, four trusted lifecycle Hooks |
| Active Codex Handoff sources | `plugin` only |
| Duplicate execution risk | `false` |
| Configured compact threshold | `3` |

`scripts/doctor.py --json` found no active profile or project Hook. Two old files remained as inactive evidence: `~/.codex/hooks/compact_handoff.py` and `~/.codex/compact_handoff_state.json`. They were not deleted.

## Pre-fix runtime evidence

**VERIFIED:** audit records for session `019ff9b8-94a4-7de1-8db3-00e54f7135dd` contain two `PostCompact(trigger=auto)` events on 2026-08-13 and a third on 2026-08-14 before `handoff_requested_at_safe_stop`. The pre-fix Hook had no `SessionStart` handler, so it accumulated those events under the reused `session_id` across the later resume.

**INFERENCE:** this cross-resume accumulation explains the reported short-session handoff. The audit proves the Host sent the third automatic compact; it does not prove what compaction indicator the user interface displayed.

No active Plugin + profile duplicate was present during evidence capture. Historical audit entries with repeated `session_id`, `turn_id`, and trigger were insufficient to prove duplicate delivery because multiple genuine automatic compactions can occur in one long turn. The official Hook payload does not expose a stable event UUID, so the new implementation combines generation, compact boundary, turn, and trigger and records its decision.

## Scenario 1 — fresh short session

App Server created thread `019ffe2f-eb9e-7202-a206-775d6c765886` and completed ten small normal turns.

Observed audit:

```text
SessionStart(source=startup)       1
PostCompact                        0
Stop(action=normal_stop)          10
handoff_requested_at_safe_stop     0
SessionEnd                         1
```

Result: **PASS**. The generation stayed at zero receipts and produced no false handoff.

## Scenario 2 — genuine threshold

App Server created thread `019ffe35-6839-7b70-be9c-0e5235ae5831`. Three official `thread/compact/start` requests completed as three Host compaction turns. Each was followed by the documented `SessionStart(source=compact)` boundary and a short normal turn.

Observed receipts:

```text
de70f559d29679cdc982c459
2c4643b0bae1ae45a537694c
adc2aef0e96210afbe9f7bb1
```

The first two Stops continued normally. The third Stop recorded exactly one `handoff_requested_at_safe_stop`, reset active receipts, and bound the workflow to:

```text
name: codex-handoff
resolver: plugin_root
skill: /Users/SIPSS0586/.codex/plugins/cache/codex-handoff/codex-handoff/0.1.1/skills/codex-handoff/SKILL.md
sha256: 88e0f7ad84bbeebacac0c68ef55f889c4d43ef446f59748f89122071fd40f696
```

The automatic continuation reported a successful identity receipt, wrote only `docs/CODEX_HANDOFF.md` in the disposable workspace, and the bundled validator passed with one retained history entry. Result: **PASS**.

When the continuation invoked the deep-link helper, the old App Server turn became `interrupted` rather than emitting its usual `turn/completed` notification. The handoff artifact and identity validation had already completed. This is additional evidence for keeping best-effort composer opening separate from core handoff correctness.

## Scenario 3 — stale pending resume

Thread `019ffe38-5614-7132-a7a9-2504cebb247c` was seeded through the real Hook contract with three receipts in generation `5521aab73446fc4ebd726ed7` and `pending_handoff=true`. A real App Server `thread/resume` then caused:

```text
SessionStart(source=resume)
previous_compact_count=3
previous_pending_handoff=true
new generation=26ecbd3339c3bddfad7b08d9
compact_count_since_handoff=0
pending_handoff=false
```

The resumed turn completed with `Stop(action=normal_stop)`, zero active receipts, and zero handoff requests. Result: **PASS**.

## Clean-session deep link

The installed helper returned:

```json
{
  "deep_link_dispatched": true,
  "thread_creation_verified": false,
  "prompt_prefill_requested": true,
  "prompt_prefilled": null,
  "prompt_submission_verified": false,
  "turn_started_verified": false,
  "thread_name_verified": false,
  "user_action_required": "Press Send in the new Codex composer."
}
```

The official [Codex deep-link reference](https://developers.openai.com/codex/app/commands/#deeplinks) says `prompt` sets the initial composer text and is not sent automatically. OS dispatch therefore does not prove thread creation, prompt submission, turn start, or naming. The helper does not set a title; the cause of the reported old-looking title remains **UNKNOWN**.

## App Server capability test

The official [Codex App Server](https://developers.openai.com/codex/app-server/) test used `thread/start`, `turn/start`, and `thread/name/set` in the same disposable workspace. It received thread ID `019ffe20-710c-7343-aeab-a1db73ad97f7`, turn ID `019ffe20-71c4-7b53-8b60-7e6da1bc396a`, a completed turn, and a successful name-set acknowledgement. Desktop history then showed that exact thread, workspace, and title `Codex Handoff App Server Smoke`.

Result: these capabilities are **VERIFIED ON THIS HOST**. Stable cross-version Desktop visibility is **UNSPECIFIED BY OFFICIAL DOCS**, so App Server is not the default continuation path.

## Automated validation

Before the final documentation update:

```text
python3 -m unittest discover -s tests -v  PASS (37 tests)
python3 scripts/validate_package.py       PASS
git diff --check                         PASS
```

The complete release-gate commands are rerun after all source and documentation edits; their final result belongs in the release review that references this record.
