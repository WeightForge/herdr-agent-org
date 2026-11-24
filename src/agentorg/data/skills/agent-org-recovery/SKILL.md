---
name: agent-org-recovery
description: Recover a PM/team after Claude/Codex context loss, app restart, machine reconnect, rate limit or crash by reconciling Herdr terminals with Git/PR state and durable checkpoints (requires the agentorg CLI and Herdr `hc`). Use when a PM session restarts or `.ai/STATE.md` may be stale.
---

# Agent Organization — Recovery

**Never treat a stale checkpoint as proof of active agents or finished tasks.** Read `.ai/STATE.md` / `.ai/RUNTIME.json` then use `agentorg team reconcile`, `hc ls`, `hc get`, and current Git worktrees/branches/PR/CI to determine truth.

1. Identify working directory, project ID, environment and accounts. Validate company/personal data routing.
2. Read `.ai/PROTOCOL.md`, then `.ai/inbox/*.md` (reviewer escalations written while you were away): skip ids already under "Handled escalations" in `.ai/STATE.md`, handle the rest, record the id there BEFORE moving the file to `.ai/inbox/done/`; for an id whose action may have happened unrecorded, reconcile against evidence first. `agentorg team status` reports `inbox_pending`, `owner_decisions`, `blocked` (role, terminal, kind only; never copy prompt text) and `tasks`. Then determine live terminals, current agent status and parent/child lifetime. A hidden pane is not a dead process; a terminated process is not recovered by reopening a pane.
3. Task recovery: use the `tasks` list of `agentorg team status` (state derived from `.ai/tasks/<id>/`). Never mint a new task id; receivers dedupe by id, so re-sending a path is safe.
   - `dispatched` (packet, no `progress.md`): resend the packet path to worker and reviewer.
   - `acknowledged` with flag `unknown_delivery` (reviewer acked, no worker `ACK`): resend the packet path to the **worker only**, then end your turn. With flag `waiting_on_dependency`: do nothing, the reviewer releases it.
   - `started`, `in_review`, `blocked`: in flight, never re-dispatch; inspect worktree/PR and ask the reviewer if the status is unknown.
   - `cancelled`: do not dispatch. `reassigned`: resend the packet and `reassign.md` paths to the new owners.
   - Never spawn a duplicate writer on the same worktree.
4. Compare `.ai/STATE.md`, `.ai/DECISIONS.md`, project task system with live evidence; update checkpoint with discrepancies and next actions, but do not forge timestamps or successes.
5. Reconnect/restore only missing roles with explicit operator authorization via `agentorg team up --apply`. The CLI reuses recognized live role terminals by deterministic name; if a mismatched terminal occupies that name, fail and escalate.
6. After a PM restart the PM terminal id changes: send each live reviewer the new address once (`agentorg team send <reviewer> "PM address is now <id>"`) instead of relaunching anything.
7. For rate limits, pause affected work and do independent authorized tasks. Never bypass subscription limits or send business data to a different account as a workaround.
8. For broken provider contexts, produce concise handoff summary and start a new provider session if authorized. Preserve repo/worktree/PR as source of truth; do not rely on provider native transcript presence.
9. Keep merge, release, deploy, publication, destructive operations and account policy changes behind owner approval.

Checkpoint format for `.ai/STATE.md`:

```text
# Project checkpoint (verified <date>)
Milestone: <id/name>
Active tasks: <task -> role, branch/PR, status>
Live terminals: <role -> name, live|missing> (from team reconcile)
Blockers / discrepancies: <...>
Next action: <...>
```

Report to human: recovered/active/blocked agents, unresolved state mismatches, actual test/PR evidence, and questions requiring human choice.
