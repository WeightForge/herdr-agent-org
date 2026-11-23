---
name: agent-org-recovery
description: Recover a PM/team after Claude/Codex context loss, app restart, machine reconnect, rate limit or crash by reconciling Herdr terminals with Git/PR state and durable project checkpoints.
---

# Agent Organization — Recovery

**Never treat a stale checkpoint as proof of active agents or finished tasks.** Read `.ai/STATE.md` / `.ai/RUNTIME.json` then use `agentorg team reconcile`, `hc ls`, `hc get`, and current Git worktrees/branches/PR/CI to determine truth.

1. Identify working directory, project ID, environment and accounts. Validate company/personal data routing.
2. Determine live terminals, observed current agent status and parent/child lifetime. A hidden pane is not a dead process; a terminated process is not recovered by reopening a pane.
3. Inspect each assigned worktree and PR before creating new terminals. If task status unknown, read logs/terminal/CI and ask original worker; never spawn duplicate writer on the same worktree.
4. Compare `.ai/STATE.md`, `.ai/DECISIONS.md`, project task system with live evidence; update checkpoint with discrepancies and next actions, but do not forge timestamps or successes.
5. Reconnect/restore only missing roles with explicit operator authorization via `agentorg team up --apply`. The CLI reuses recognized live role terminals by deterministic name; if a mismatched terminal occupies that name, fail and escalate.
6. For rate limits, pause affected work and do independent authorized tasks. Never bypass subscription limits or send business data to a different account as a workaround.
7. For broken provider contexts, produce concise handoff summary and start a new provider session if authorized. Preserve repo/worktree/PR as source of truth; do not rely on provider native transcript presence.
8. Keep merge, release, deploy, publication, destructive operations and account policy changes behind owner approval.

Report to human: recovered/active/blocked agents, unresolved state mismatches, actual test/PR evidence, and questions requiring human choice.
