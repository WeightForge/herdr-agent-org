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

## Panes

When the PM runs in a Herdr App terminal, `team up --apply` then gives each role a pane in the PM's tab (`herdr-app do terminal.keep`, focusing the anchor pane first): reviewers go down a column, each reviewer's workers to its right. It is best effort and idempotent: panes that exist are skipped, a pane that lands outside the PM's tab is parked and arranging stops, and failures only warn. `--no-panes` disables it.

## Escalation inbox

Reviewers write each escalation to `.ai/inbox/<UTC>-<task>-<code>-<hex4>.md` (git-ignored) and optionally `hc send` the PM a pointer. The PM reads the folder on every wake, moves handled files to `.ai/inbox/done/` and alone edits `.ai/STATE.md`.

## Protocol and task lifecycle

`src/agentorg/data/PROTOCOL.md` (versioned, `Protocol version: 2`) is the single source of the file layout, task states, escalation codes and safety rules. `agentorg init` and `team up --apply` copy it to `.ai/PROTOCOL.md` (never overwritten unless the project copy is an older protocol version; a differing copy that is not older is kept with a warning). Launch prompts give each role the absolute path and keep only a short role summary; skills add role guidance only.

Task state is derived from files, with no database: `dispatched` -> `acknowledged` (reviewer wrote `progress.md`) -> `started` (reviewer records the worker's `ACK <task>`) -> `in_review` -> `done` / `blocked`, plus `cancelled` (PM `cancel` marker) and `reassigned` (PM `reassign.md`). `team status` prints `tasks` (id, state, next actor, flags such as `unknown_delivery`) and `owner_decisions`. Workers never write into the root checkout, so the worker ack is a message that the reviewer records.

## Task files and handoffs

Per task, in the root checkout, `.ai/tasks/<id>/` (versioned): `packet.md` (PM, immutable, written before dispatch; workers and reviewers receive only its absolute path) and `progress.md` (reviewer only: state, UNPRODUCTIVE-round counter, accepted dependency commits, `<branch>@<commit>:<path>` evidence refs; it doubles as the acknowledgement). `blocked_by: <task id>` records a dependency without a commit; the dependent reviewer records the accepted prerequisite commit before releasing the worker. Recovery: packet without progress is resent to worker and reviewer; acknowledged without a worker ack (`unknown_delivery`) is resent to the worker only; later states are in flight (receivers dedupe by task id).

Workers commit their report to `.ai/handoff/<task>.md` on their branch before `hc send` and send `<branch>@<commit>:<path>`; a blocked send loses nothing.

Inbox file names carry a 4-hex suffix generated once per escalation (`<UTC>-<task>-<code>-<hex>.md`) so retries reuse the same id. The PM lists handled ids under "Handled escalations" in `.ai/STATE.md` before moving files to `inbox/done/`, skips recorded ids on wake, and reconciles against evidence for an id that may have been acted on unrecorded.

## Containment and blocked terminals

Codex is launched with `--no-daemon` (`hc --skill`: otherwise its commands execute outside hc) and labelled `nodaemon=1`; a pre-0.4 terminal without the label is refused for reuse. `team status` reports `blocked: [{role, terminal, kind}]` from hc's structured `status.kind` (or `unknown`); `status.msg` is never copied since it may hold credentials.

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
