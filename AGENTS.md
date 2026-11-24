# Contributing agent instructions

This repository is a public starter kit for running **reusable AI organizations** using Herdr App and herdr-core (`hc`). Do not confuse it with the unrelated legacy `herdr` TUI.

Read `README.md`, `docs/ARCHITECTURE.md`, `SECURITY.md`, `docs/maintainers/CODEX_HANDOFF.md` before changing runtime logic.

- Preserve safe defaults: no role launches without `team up --apply`, no implicit account/provider fallback, no merge/release/deploy/paid services without user approval.
- Never place credentials, personal identities or vendor API keys in source, tests, logs, PR comments, or project `.ai/TEAM.json`.
- Keep Python standard-library-only runtime, support Windows and Linux, and use subprocess argv lists (not shell interpolation) for command execution.
- `agentorg profile add` stores only local config paths and public model/effort choices; do not build an auth manager.
- Any Herdr command compatibility change must be validated against the installed `hc --skill` / `hc <cmd> --help` and mocked in unit tests before relying on it.
- Preserve worktree isolation, idempotent terminal reconciliation, human approval gates and non-destructive init behavior.
- Run `python -m unittest discover -s tests -v` and test wheel packaging before proposing completion.
- In a code review, distinguish what passed in a mock test from what was verified with a live Herdr process.

For next engineering priorities, see `docs/maintainers/CODEX_HANDOFF.md`.
