# Codex Handoff

[![CI](https://github.com/HaoPan036/codex-handoff/actions/workflows/ci.yml/badge.svg)](https://github.com/HaoPan036/codex-handoff/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Platform: macOS | Linux](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-555.svg)](#compatibility-and-limitations)

**Recover a clear, verifiable project state after repeated context compaction.**

Long Codex tasks can span many conversations and context compactions—condensing earlier context so work can continue. Details may no longer be fully available: an earlier constraint, the reason a solution was rejected, or which tests ran against which revision. The practical risks are repeated work, missed requirements, and stale assumptions. Compaction count alone does not prove quality loss; there is no universal count at which a model stops being reliable.

Codex Handoff helps you check and carry forward what matters. It reminds you at 5, 10, 15… completed compactions without interrupting work. When you explicitly invoke `$codex-handoff`, the Skill checks Git, relevant files, project rules, and verification evidence, then creates `docs/CODEX_HANDOFF.md` with the current state, unresolved questions, and one concrete next task. A fresh session can inspect those sources again while your existing changes stay intact.

The core does not hard-code a model name or context-window size. The [model-update strategy](#adapting-to-model-updates) keeps compatibility checks tied to the Codex host, and the [memory design](#working-alongside-memory) separates a current project handoff from longer-lived recall. Five compactions is a configurable reminder interval.

[中文说明](README.zh-CN.md)

![Codex Handoff v0.2.0 workflow: reminders at 5, 10 and 15 compactions; explicit invocation; repository evidence; validated handoff](docs/assets/codex-handoff-flow.svg)

<p align="center"><sub>Workflow illustration, not a screen recording. <a href="docs/demo.md">Walkthrough</a> · <a href="docs/smoke-test-2026-09-08.md">September 8 acceptance evidence</a></sub></p>

| Safe timing | Verified state | Clean continuation |
| --- | --- | --- |
| Non-blocking reminders; handoff only on explicit invocation. | Reconstructs state from Git, repository files, tests, artifacts, and `AGENTS.md`. | Creates a structured, validated `docs/CODEX_HANDOFF.md` for the next session. |

## Quick start

The profile installer installs the explicit-only Skill and reminder hook. Check that `python3 --version` is 3.11 or newer before installing.

```bash
git clone --branch v0.2.0 https://github.com/HaoPan036/codex-handoff.git
cd codex-handoff
bash install.sh 5
```

If macOS resolves `python3` to an older system Python, use your installed 3.11+ interpreter directly: `python3.11 scripts/install_profile.py --threshold 5`.

Restart Codex, review and trust the installed hooks, then work normally. The final argument is the number of completed compactions between reminders.

You can request a handoff at any milestone without waiting for the threshold:

```text
$codex-handoff
```

The result is written to `docs/CODEX_HANDOFF.md`. Use `$codex-handoff handoff only` to create and validate the document without opening a new session.

## Why Codex Handoff

Compaction count alone does not establish quality loss. At a milestone or when project state becomes unclear, a handoff helps verify:

- What is already complete?
- Which files are staged, unstaged, or untracked?
- Which decisions and project rules still apply?
- Which tests actually ran and passed?
- What is the one next task?

Codex Handoff creates a durable repository artifact from evidence that a fresh session can inspect again. When evidence cannot establish an important fact, the handoff marks it `UNKNOWN`. It cannot recover conversation-only details that are no longer available, or guarantee model accuracy. The benefit is an explicit opportunity to verify project state and prepare a reviewable continuation.

## Adapting to model updates

As OpenAI updates the models available in ChatGPT and Codex, this project's integration remains with the **Codex host**. The current hook counts completed lifecycle events; it does not estimate model quality, inspect token capacity, or replace the host's compaction algorithm. The handoff is ordinary Markdown, and the reminder interval is configurable for your workflow.

The maintenance strategy is to check the official host contracts after relevant updates, rerun reminder/resume/manual-handoff acceptance, and record the tested host and model. Changes to host events or task APIs may require code updates; a new model still needs workflow validation. Automatic adaptation to every future model is not an implemented feature. Current evidence is in the [acceptance record](docs/smoke-test-2026-09-08.md).

## Working alongside memory

Memory can carry useful context across chats. OpenAI distinguishes ChatGPT's web memory from Codex's local memories, and recommends keeping required project guidance in `AGENTS.md` or checked-in documents. See the official [memory documentation](https://learn.chatgpt.com/docs/customization/memories).

The intended division of responsibility is:

| Context | Role |
| --- | --- |
| Memory | Recall durable preferences, background, and reusable lessons. |
| `AGENTS.md` and project documentation | State the project's applicable rules and maintained decisions. |
| `docs/CODEX_HANDOFF.md` | Capture verified state for this repository and task at the handoff point, including evidence, unknowns, and the next action. |

**Current boundary:** the plugin has no dedicated memory reader, writer, or synchronization adapter. During handoff preparation, its Skill is instructed to write only `docs/CODEX_HANDOFF.md`; the hook manages its own counters and audit data. The host may still supply memory as context under its own settings. A handoff remains a snapshot that needs rechecking when the repository changes.

**Future integration principles:** keep task snapshots separate from durable memory; retain source, revision, and freshness information when transferring facts; recheck recalled project state against current files and test results; and surface unresolved conflicts without silently overwriting memory or promoting stale task details into lasting facts. Any memory integration should respect host controls and have explicit compatibility tests. These are design requirements for future work, not a claim that memory synchronization or automatic conflict resolution already exists.

## How it works

`PostCompact` deduplicates completed compactions and shows a `systemMessage` reminder at N, 2N, 3N (default N=5). `Stop` always returns `continue: true`, without dispatching work. `SessionStart(source=compact)` separates genuine compactions within one turn; resume/startup of the same session preserves the count. Clear or a new session starts a new cadence. Inactive records expire after 30 days.

```text
unique PostCompact -> count -> milestone? -> non-blocking reminder
user invokes $codex-handoff -> verify evidence -> save handoff -> clean continuation
```

Ignoring a reminder does nothing until the next milestone. It never writes a handoff, opens a session, or supplies continuation instructions to the model. See [docs/design.md](docs/design.md) for migration and state details.

## Manual handoff

Invoke the Skill at any milestone:

```text
$codex-handoff
```

To create and validate the document without opening a new session:

```text
$codex-handoff handoff only
```

Only explicit manual invocation starts the handoff workflow; reminders are not authorization.

The default command creates a titled clean task when native task controls are available; otherwise it prepares a composer and requires **Send**. `handoff only` stops after generation and validation.

## What `CODEX_HANDOFF.md` contains

The handoff uses a stable 11-section contract:

1. Objective and scope
2. Verified current state
3. Architecture and data flow
4. Decisions, constraints, and rejected approaches
5. Relevant files and symbols
6. Verification commands and results
7. Working tree state
8. Known issues, risks, and unknowns
9. One next concrete task
10. New-session startup checklist
11. Five-entry bounded history

Sections 1 through 10 are rewritten from current evidence. Section 11 retains only the five most recent handoffs. The validator rejects missing sections, unresolved placeholders, vague next tasks, oversized documents, and longer histories.

See [examples/CODEX_HANDOFF.example.md](examples/CODEX_HANDOFF.example.md) for a complete example.

## Safety model

During handoff preparation, the Skill is instructed to:

- update only `docs/CODEX_HANDOFF.md`
- preserve staged, unstaged, and untracked work
- avoid commit, push, reset, clean, discard, stash, archive, and delete actions unless explicitly requested
- mark unverified material claims as `UNKNOWN`
- exclude credentials, secrets, complete large logs, and full diffs

The hook does not read repository files or transcripts. It receives lifecycle event metadata, updates a local counter and bounded audit log, and shows a non-blocking reminder at the configured milestone. It makes no network calls and performs no repository mutation. Codex Handoff has no telemetry.

See [SECURITY.md](SECURITY.md) for the security boundary and reporting process.

## Installation details

### Profile installer

The profile installer requires Python 3.11 or newer and installs the Skill and hooks directly into your user profile:

```bash
git clone --branch v0.2.0 https://github.com/HaoPan036/codex-handoff.git
cd codex-handoff
bash install.sh 5
```

It:

- installs the Skill at `~/.agents/skills/codex-handoff/`
- installs the hook at `~/.codex/hooks/codex_handoff_hook.py`
- backs up and updates `~/.codex/config.toml`
- removes hook blocks from earlier `codex-handoff-session` packages
- preserves legacy lifetime totals for diagnostics while quarantining unverifiable active counters and pending flags
- retains the installed Skill path in profile commands for compatibility; the reminder hook does not load or invoke that file
- warns when an enabled Plugin would run alongside the profile Hook

Run the read-only installation diagnostic at any time:

```bash
python3 scripts/doctor.py
```

Restart Codex and review the exact hook definition after installation.

### Codex Plugin Marketplace

The repository includes a Plugin package and marketplace metadata. See the [current acceptance record](docs/smoke-test-2026-09-08.md) for the exact installation mode and host coverage of v0.2.0. The [August installation and automatic-handoff tests](docs/smoke-test-2026-08-11.md) remain historical evidence only.

```bash
codex plugin marketplace add HaoPan036/codex-handoff
```

If you are migrating from the profile-installed `codex-handoff-session` v4, do not leave both Hook sets enabled. From the current checkout, run `bash uninstall.sh` to remove the old profile Skill and hooks while retaining their local state, then install and trust the Plugin hooks.

Then open `/plugins` in Codex CLI or the Plugins Directory in the ChatGPT desktop app, install `Codex Handoff`, start a new session, and review the bundled hooks through `/hooks` before trusting them. The repository marketplace is at `.agents/plugins/marketplace.json`; the package is at `plugins/codex-handoff/`.

When upgrading, refresh the marketplace and confirm the installed version is **0.2.0**. Restart the session and review the updated hooks. The profile installer and marketplace are alternative installation methods; keep only one active. Existing verified counts can seed the new cadence, but old pending handoffs never dispatch automatically.

The command shape and trust flow follow the official OpenAI documentation for [packaging Codex plugins](https://developers.openai.com/plugins/build/plugins) and [Codex hooks](https://developers.openai.com/codex/hooks).

### Uninstall

Remove a profile installation while retaining local counters and logs:

```bash
bash uninstall.sh
```

Remove its local state too:

```bash
bash uninstall.sh --purge-state
```

For a Plugin installation, disable or remove the Plugin through `/plugins` or the Plugins Directory.

## Configuration

### Profile installation

Run the installer again with a new threshold:

```bash
bash install.sh 5
```

### Plugin installation

Create `~/.codex/codex-handoff.json`:

```json
{
  "compact_threshold": 5
}
```

`CODEX_HANDOFF_COMPACT_THRESHOLD` takes priority when set. Plugin mode stores state under the host-provided `PLUGIN_DATA` directory.

Profile mode stores state at:

```text
~/.codex/codex-handoff/state.json
~/.codex/codex-handoff/events.jsonl
```

The audit log rotates after approximately 1 MB. Session records older than 30 days are removed when the hook runs.

## Compatibility and limitations

- Current version: [`v0.2.0`](https://github.com/HaoPan036/codex-handoff/releases/tag/v0.2.0).
- Automated tests run on macOS and Linux with Python 3.11, 3.12, and 3.13 in the repository CI workflow.
- Python 3.11 or newer is required by the profile installer. Runtime helpers use only the Python standard library.
- Packaged hook commands currently target macOS and Linux shells.
- Codex Plugins are available in Codex CLI and the ChatGPT desktop app, but not in the IDE extension. The profile installer remains the compatibility path for the IDE extension.
- Current reminder and manual-handoff coverage is documented in the [September 8 acceptance record](docs/smoke-test-2026-09-08.md). It distinguishes real host events, UI evidence, isolated tests, and continuation behavior. See [the walkthrough](docs/demo.md) and [release checklist](docs/release-checklist.md).
- The [`codex://new` continuation opener](https://developers.openai.com/codex/app/commands/#deeplinks) is best effort. A successful OS dispatch requests a new composer with the prompt prefilled; it does not verify thread creation and never submits the prompt automatically. Press **Send**. If dispatch fails, the helper prints the complete startup prompt for manual use.
- The desktop path uses native task listing and titled task creation, so the numbered title is applied at creation. The portable path may use stable App Server `thread/read`, but a restricted nested Host sandbox can prevent that lookup; it then falls back to the workspace name. Requested and verified title fields remain separate.
- A validated handoff remains useful when automatic session opening is unavailable.

## Development

Run the full local validation suite:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_package.py
```

The tests cover 5/10/15 reminders, silent intermediate/repeated events, resume/clear behavior, old-state migration, source-independent reminders, valid non-dispatching Stop output, identity helpers, doctor diagnostics, snapshot collection, handoff validation, deep-link semantics, installers, and package metadata. Use a Python 3.11+ interpreter for both commands.

To build a release archive from a committed revision, run `python3 scripts/create_release.py --ref v0.2.0`. The archive reads committed Git content and file modes, excluding local edits and untracked files; it writes `dist/codex-handoff-v0.2.0.zip` and `dist/SHA256SUMS.txt`.

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/design.md](docs/design.md) before changing the lifecycle contract. See [docs/troubleshooting.md](docs/troubleshooting.md) for common installation and runtime problems.

## Project layout

```text
.agents/plugins/marketplace.json
.github/workflows/ci.yml
plugins/codex-handoff/
  .codex-plugin/plugin.json
  hooks/
    hooks.json
    codex_handoff_hook.py
  skills/codex-handoff/
    SKILL.md
    agents/openai.yaml
    assets/CODEX_HANDOFF.template.md
    scripts/
      verify_identity.py
docs/
  assets/
    codex-handoff-flow.svg
  demo.md
  smoke-test-2026-09-08.md
scripts/
  install_profile.py
  uninstall_profile.py
  validate_package.py
tests/
```

## Roadmap

- Revalidate relevant model and Codex host updates, recording actual compatibility results.
- Evaluate memory interoperability with provenance, freshness checks, and explicit conflict handling before adding a synchronization adapter.
- Publish a community announcement and collect installation feedback.
- Add Windows hook command packaging.
- Collect external usage feedback before expanding the handoff schema.

## License

MIT. See [LICENSE](LICENSE).
