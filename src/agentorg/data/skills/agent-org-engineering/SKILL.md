---
name: agent-org-engineering
description: Reviewer-led multi-agent software engineering loop using Herdr and Git worktrees (requires the agentorg CLI and Herdr `hc`). Workers implement and test, reviewers coordinate feedback and verification, and the PM receives only milestone-ready results or escalations. Use when a PM, worker or reviewer role in an agentorg software team is assigned or reviewing a task.
---

# Engineering loop — Worker heavy, Reviewer next, PM light

## Running the CLI

Every `agentorg ...` command in this skill means the CLI resolved as follows. Resolve once per session: use `agentorg` only if `agentorg --version` prints exactly `0.7.0`, the version of this skill; for any other version or if the command is missing, run `uvx --from git+https://github.com/WeightForge/herdr-agent-org@v0.7.0 agentorg` in its place (no install step; needs `uv`). Pass the same arguments either way. If neither works, ask the user to install `uv` or `pip install herdr-agent-org==0.7.0`. This keeps the CLI on the same version as this skill, so an older installed `agentorg` is never used.
<!-- Release note: once herdr-agent-org is on PyPI the fallback may become `uvx herdr-agent-org==0.7.0`. tests/test_plugins.py checks the pin against __version__. -->

Use existing repository build/test/security/contribution instructions as source of truth. A good engineering loop minimizes PM calls, noisy PRs, duplicated agents and branch conflicts.

**Read `.ai/PROTOCOL.md` (absolute path in your launch prompt) first.** It is authoritative for the file layout, task states, `ACK`, dependencies, cancellation, escalation codes and format, handoffs and the rule against answering another agent's permission prompt. This skill adds only role guidance.

## Task packet template (PM writes, immutable)

```text
TASK <id>
Protocol version: <n>
Objective: <one sentence>
Scope / worktree+branch: <owned files, branch>
Acceptance criteria: <measurable>
Expected tests: <commands>
Reviewer: <role> (terminal <name>)
blocked_by: <task id or none>
Exit conditions / permission gates: <...>
```

One write owner per worktree. Workers may run tasks in parallel only if interfaces and files do not conflict.

## Worker-owned implementation loop

1. Read the packet at its absolute path, send the reviewer `ACK <task>`, then implement the scoped work; own implementation, regression tests, docs changes and evidence. If the packet has `blocked_by`, wait for the reviewer's go-ahead.
2. Self-test against acceptance criteria (`test`, `lint`, `typecheck`, build and domain-specific evaluation when relevant); record commands/results honestly.
3. Report only a coherent slice: commit `.ai/handoff/<task>.md` first, then send the reviewer its `<branch>@<commit>:` reference (protocol). No routine PM message.
4. Apply reviewer feedback, retest and send change/evidence to the reviewer, up to the agreed RCA threshold.
5. Do not label work done solely because tests were invoked; the reviewer must verify. Do not merge/deploy/publish without human approval.
6. Stay inside your worktree and task scope; out-of-scope requests become a `scope_change` to your reviewer. Stop at once when a task is cancelled or re-assigned.
7. If you are blocked on a permission prompt, tell your reviewer the exact command you wait on; never use `hc keys`.

## Reviewer-owned feedback and QA loop

The reviewer is the Herdr parent of its paired workers, so hc notes about them (turn ended, blocked, exited) arrive at the reviewer, who handles them and escalates to the PM address in its launch prompt.

1. On a packet path: create `progress.md` with `State: acknowledged`; a repeated path for a known task id is not a new task. Move the state on as the protocol table says (`started` after the worker's `ACK`, `in_review` on a handoff reference, then `done` or `blocked`). Release dependent tasks once the prerequisite is `done`.
2. Independently review the actual diff, tests, security, regressions, specifications and user experience; validate reported tests/CI instead of trusting claims.
3. Send actionable findings **directly to the worker** with severity, location, expected correction and reproduction. Do not ask the PM to relay comments.
4. Count consecutive UNPRODUCTIVE rounds in `progress.md`. At `policies.review_rounds_before_rca` (default 3) stop patch churn; require root-cause analysis, minimal reproduction and a regression test. Reviewer may take over implementation only exceptionally, after recording ownership change and arranging a second independent verifier.
5. When validation passes and gates are met, escalate one `milestone_ready` (a review-ready PR is not permission to merge). Escalate immediately only with `blocked`, `scope_change`, `safety_or_cost_risk`, `requires_owner_decision` or `review_exhausted`. File format and delivery: protocol.
6. When a worker is blocked on a permission prompt, escalate `blocked` with the exact command it waits on; never use `hc keys`. The human approves.

## Engineering quality gate

Measurable acceptance criteria, real test evidence (including honest failures), CI and review, backward compatibility where applicable, no outstanding high severity issue, documentation matching code, independent final verification where reviewer also edited code.

## Event-driven and state safety

- Do **not** wake PM for every tool call, turn, PR comment or test iteration. Use reviewer as local coordination owner until ready to escalate.
- If agent-to-agent messaging is unavailable, persist a handoff report in the repo/PR, not a claim that a message was delivered.
- `hc` does not create a durable task scheduler; do not imply endless autonomous progress without a running PM or watcher. Respect idle, crash, context/usage limits and human gates.
- PM decides milestones and dependencies; Reviewer decides whether the reviewed slice meets the quality gate; Worker does the implementation.
