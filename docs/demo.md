# Demo and recording guide

## Current demo status

The repository contains a passing isolated Codex CLI installation test, a passing two-cycle model-backed host test, and a reviewed 18-second terminal demo from a separate host-driven run. The exact environment, observed state, fallback behavior, clean-session verification, and publication evidence are recorded in [smoke-test-2026-08-11.md](smoke-test-2026-08-11.md).

The visual at the top of both READMEs is a frame-edited recording of actual Codex terminal output. It shows repository verification, three host-emitted `PostCompact` events, the next task finishing normally, a safe `Stop` continuation whose prompt names `$codex-handoff`, successful handoff validation, and the clean-session fallback prompt. The 2026-08-11 recording did not capture the exact loaded Skill identity; that evidence is documented separately in `smoke-test-2026-08-12.md`. Frames were cropped for privacy and pacing; execution output was not recreated or simulated.

The published GIF is 18 seconds, 980×602 pixels, and 477,503 bytes. Its four unique frames were reviewed for usernames, absolute personal paths, credentials, private repository names, and unrelated notification content. The only visible workspace path is the neutral `/private/tmp/codex-handoff-demo` fixture.

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
8. Confirm the continuation is bound to the exact `codex-handoff` Skill path and that its identity verifier succeeds.
9. Confirm `docs/CODEX_HANDOFF.md` is created and passes the bundled validator.
10. Confirm a clean session opens, or that the helper returns the complete manual startup prompt.
11. Repeat the threshold cycle and confirm a second handoff can be requested without a continuation loop.

Record the Codex version, operating system, installation mode, threshold, and exact result in the release notes or a dedicated smoke-test record.

## Recording the verified flow

Keep the final terminal demo between 15 and 25 seconds. Show only these moments:

1. The threshold becomes pending while the active task continues.
2. The Turn reaches a normal `Stop`.
3. The exact `codex-handoff` Skill path and identity receipt are visible.
4. `docs/CODEX_HANDOFF.md` is created and validated.
5. A clean-session prompt is ready.

Crop unrelated logs. Replace the disposable workspace path with a neutral path such as `~/demo/codex-handoff-example`. Check every frame for usernames, absolute private paths, tokens, API keys, private repository names, and notification content.

Save the reviewed recording as `docs/assets/codex-handoff-demo.gif`, then replace the conceptual visual in both READMEs and update their status text together.

The v0.1.0 recording followed this procedure on 2026-08-11. Because macOS displays a privacy shield during automated desktop control, the final GIF uses four original VS Code terminal captures from the same uninterrupted Codex run rather than a continuous screen capture. The frames are held for readability and cropped to the relevant terminal region; the sequence and output remain the observed host execution.
