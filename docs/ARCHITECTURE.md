# Architecture

```text
Human owner
   │
   ▼
PM (Claude Code or Codex + agent-org-manager skill)
   │
   ├── agentorg (local Python CLI; checks and explicit launch)
   │       ├── .ai/TEAM.json (project roles, policy, profile aliases; versioned)
   │       ├── user profiles.json (local machine; provider config directories)
   │       ├── Git worktrees (per software worker)
   │       └── hc run --bg --outlive-parent (persistent terminals)
   │
   ├── hc send / wait / read / get / events (message & evidence)
   │
   └── .ai/STATE.md + Git/PR/CI (checkpoint + reality)
   │
   └── Herdr agent processes (native Claude/Codex CLI)
```

## Herdr parent tree

`team up --apply` starts reviewer roles first as children of the PM terminal, then each worker with `--parent <reviewer terminal>`. Herdr types worker notes (turn ended, blocked, exited) into the reviewer, so PM -> reviewers -> workers and the PM is woken only by reviewer escalations. The PM's `HC_TERMINAL_ID` (if valid) is passed to launched roles as `--pm` and recorded as `pm_terminal` in `.ai/RUNTIME.json`; it is deliberately not part of the role label fingerprint.

## Escalation inbox

Reviewers write each escalation to `.ai/inbox/<UTC>-<task>-<code>.md` (git-ignored) and optionally `hc send` the PM a pointer. The PM reads the folder on every wake, moves handled files to `.ai/inbox/done/` and alone edits `.ai/STATE.md`.

## Boundaries

- **Config**: source-controlled `.ai/TEAM.json` stores only role IDs, profile aliases and requirements; local `AGENTORG_HOME/profiles.json` maps aliases to CLI binaries, models and config directories. No OAuth/access tokens stored by `agentorg`.
- **Runtime**: Python bootstrapper uses real `hc` commands, not direct Herdr App UI calls. It launches a small Python process under the Herdr PTY that starts the authenticated native CLI in the correct environment. No separate SDK proxy.
- **Persistence**: Herdr owns terminal/process state; Git/PR/CI owns implementation status; Markdown holds durable decisions. `.ai/RUNTIME.json` is ignored by Git and is diagnostic, not authority.
- **Authorization**: user approval required for risky external actions. Role profile and local config directory never imply authority to publish/merge/deploy.
- **Isolation**: worker worktrees prevent concurrent file overlap by default; reviewer root checkout is read-only by convention (not an OS sandbox). Processes are not sandboxed by this tool—provider permissions and machine policy still matter.

## Reconciliation and failure modes

`team up --apply` checks Herdr availability and `hc get <name>` for each deterministic terminal name. It never starts a second live terminal with the same deterministic identity. It does not infer task success from a terminal being idle. `--outlive-parent` is used to avoid killing workers whenever the PM exits, but OS/core restarts or user shutdown may terminate processes; checking Herdr is mandatory. If a launch is ambiguous, inspect `hc get`/`hc ls` before retrying.

## Roadmap beyond preview

1. Event-driven watcher with fault-safe persistent checkpoint, no busy polling and no accidental duplicates.
2. End-to-end testing on Windows, Linux and Herdr App versions, including slow agent startup and profile switching.
3. Config schema validation, onboarding TUI/GUI, migration from v1 `TEAM.yaml` and verified runtime capacities.
4. CI/PR adapter, optional task tracker adapters, rate limit/resume audit, security hardening and provider-specific capability verification.
5. Template registry with independent domain loops and artifact ownership beyond software.
