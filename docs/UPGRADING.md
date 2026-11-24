# Upgrading

## Versioning

`agentorg` follows semver. Patch: fixes only. Minor (0.x.0): new features; may change prompts, skills and the protocol version, never silently rewrites user data. Major: breaking CLI or `.ai/TEAM.json` changes, with notes here. Before 1.0 a minor release may still change behavior; read `CHANGELOG.md`.

Two versions matter: the package version (`agentorg --version`) and the `Protocol version` in `PROTOCOL.md`. The protocol version changes only when file layout, task states or escalation rules change incompatibly.

## What an upgrade touches

- **`.ai/TEAM.json`**: never rewritten by `init` or `team up`. `schema_version: 2` is unchanged in 0.5. New optional keys (for example `experimental` in the research and content templates) are not added to existing files.
- **`.ai/PROTOCOL.md`**: `init` and `team up --apply` copy the packaged file. agentorg owns this copy: any difference at the same or an older protocol version is overwritten (wording fixes ship without a version bump, so local edits are not preserved). A copy with a newer protocol version is kept, with a warning, so an older agentorg never downgrades a project. Running agents read the file when they start; restart them to pick up changes.
- **Skills**: `agentorg install` copies skill folders to the Claude / Codex / Antigravity skill directories. An existing skill folder is skipped unless `--force`, which deletes and replaces the whole folder, so local edits to an installed skill are lost. Keep customizations elsewhere or re-apply them after `--force`. Skills carry no version number; after upgrading, run `agentorg install --force` if you have not customized them.
- **Running agents**: launch prompts are fixed at start. After an upgrade, a live role keeps its old prompt until its terminal is stopped (`team down --apply`) and started again (`team up --apply`). Role terminals are reused only when their labels match.

## In-flight tasks when the protocol version changes

A task keeps the protocol version in its `packet.md` and `progress.md`. Finish in-flight tasks under the old version before replacing `.ai/PROTOCOL.md` and restarting roles, or accept that new rules apply to old tasks (a task already `started` is not re-dispatched). Never edit a packet to change its version; a new task gets a new packet. Tasks without a `Protocol version` line predate protocol 1 and are treated as such: their `progress.md` has no `State:` line, so `team status` reports them as `unknown`.
