# Security Policy

## Supported version

Security fixes currently target the latest release on the default branch.

## Reporting a vulnerability

Use GitHub private vulnerability reporting after the public repository is enabled. Do not open a public issue containing credentials, private repository details, sensitive transcripts, or a working exploit against another user.

Include:

- affected version and installation mode
- operating system and Codex surface
- minimal reproduction steps
- observed and expected behavior
- security impact
- suggested mitigation, when known

## Security boundaries

The hook is intended to operate locally. It does not require network access, read transcript files, inspect repository contents, or execute Git mutations. The Skill may read repository evidence and update `docs/CODEX_HANDOFF.md` under the explicit workflow described in `SKILL.md`.

Users must review and trust hook definitions before enabling them.
