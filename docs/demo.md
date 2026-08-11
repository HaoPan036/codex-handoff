# Demo and recording guide

## Current demo status

The repository contains a passing isolated Codex CLI installation and installed-Hook lifecycle smoke test. The exact commands, environment, observed state, and unverified boundary are recorded in [smoke-test-2026-08-11.md](smoke-test-2026-08-11.md).

The visual at the top of both READMEs remains a conceptual workflow diagram. It is not a recording of actual execution. Interactive Hook trust, host-emitted lifecycle events, Skill-authored handoff creation, and clean-session opening have not yet been recorded as one end-to-end run.

Do not publish a terminal GIF as a real demo until every relevant item in the [manual smoke-test checklist](release-checklist.md#manual-smoke-test) has been completed in a disposable repository.

## Host-driven end-to-end test

Use a disposable repository containing no credentials, private remotes, personal paths in visible prompts, or proprietary code.

1. Add the local marketplace from the Codex Handoff repository root.

   ```bash
   codex plugin marketplace add ./
   ```

2. Open `/hooks`. If an earlier profile-installed v4 Hook is active, remove it with the current checkout's `bash uninstall.sh` before enabling the Plugin Hook.
3. Install Codex Handoff through `/plugins` or the ChatGPT desktop Plugins Directory.
4. Start a new Codex session in the disposable repository.
5. Open `/hooks`, review the exact `PostCompact` and `Stop` commands, and trust them.
6. Set the threshold to a small value for the test and trigger that number of completed compactions.
7. Confirm the active task reaches a normal `Stop` before the handoff continuation starts.
8. Confirm the continuation explicitly invokes `$codex-handoff`.
9. Confirm `docs/CODEX_HANDOFF.md` is created and passes the bundled validator.
10. Confirm a clean session opens, or that the helper returns the complete manual startup prompt.
11. Repeat the threshold cycle and confirm a second handoff can be requested without a continuation loop.

Record the Codex version, operating system, installation mode, threshold, and exact result in the release notes or a dedicated smoke-test record.

## Recording plan after the smoke test passes

Keep the final terminal demo between 15 and 25 seconds. Show only these moments:

1. The threshold becomes pending while the active task continues.
2. The Turn reaches a normal `Stop`.
3. `$codex-handoff` is invoked.
4. `docs/CODEX_HANDOFF.md` is created and validated.
5. A clean-session prompt is ready.

Crop unrelated logs. Replace the disposable workspace path with a neutral path such as `~/demo/codex-handoff-example`. Check every frame for usernames, absolute private paths, tokens, API keys, private repository names, and notification content.

Save the reviewed recording as `docs/assets/codex-handoff-demo.gif`, then replace the conceptual visual in both READMEs and update their status text together.
