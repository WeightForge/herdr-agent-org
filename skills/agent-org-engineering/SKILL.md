---
name: agent-org-engineering
description: Reviewer-led multi-agent software engineering loop using Herdr and Git worktrees. Workers implement and test, reviewers coordinate feedback and independent verification, and a lightweight PM receives only milestone-ready results or escalations.
---

# Engineering loop — Worker heavy, Reviewer next, PM light

Use existing repository build/test/security/contribution instructions as source of truth. A good engineering loop minimizes PM calls, noisy PRs, duplicated agents and branch conflicts.

## Task packet (from PM to Worker, copied to Reviewer)

Task ID; objective; scope and owned worktree/branch; target acceptance criteria; dependent contracts; expected tests; reviewer role and terminal target; exit conditions; permission gates. One write owner per worktree. Workers may run tasks in parallel only if interfaces and files do not conflict.

## Worker-owned implementation loop

1. Inspect repository and task packet; implement scoped work; own implementation, regression tests, docs changes and evidence.
2. Self-test against acceptance criteria (`test`, `lint`, `typecheck`, build and domain-specific evaluation when relevant); record commands/results honestly.
3. Open a PR only when a coherent meaningful slice is ready. Present PR, worktree/branch, commits, results and risks **directly to the assigned reviewer** via `hc send`; no routine intermediary PM message.
4. Apply reviewer feedback, retest and send change/evidence to reviewer, up to the agreed RCA threshold.
5. Do not label work done solely because tests were invoked; reviewer must verify. Do not merge/deploy/publish without human approval.

## Reviewer-owned feedback and QA loop

1. Independently review the actual diff, tests, security, regressions, specifications and user experience; use relevant specialized skill when available. Validate reported tests/CI instead of trusting claims.
2. Send actionable findings **directly to Worker** with severity, location, expected correction and reproduction. Own the feedback/retest workflow rather than asking PM to relay comments.
3. At 3 unproductive review/fix rounds, stop patch churn; require root-cause analysis, minimal reproduction and regression test. Reviewer may take over implementation only exceptionally, after recording ownership change and arranging a second independent verifier.
4. Once validation passes and required gates are satisfied, send PM **one concise milestone-ready report** including task ID, PR, acceptance evidence, unresolved limitations, decisions required, and recommended next task. A review-ready PR is not permission to merge.
5. Escalate to PM immediately only for an unresolvable blocker, conflicting scope/contract, security or cost risk, change of ownership, or decision requiring the human.

## Engineering quality gate

Measurable acceptance criteria, real test evidence (including honest failures), CI and review, backward compatibility where applicable, no outstanding high severity issue, documentation matching code, independent final verification where reviewer also edited code. For model-weight manipulation also check reproducibility, operator coverage, shape safety, provenance, controlled side effects, reversibility and benchmarks.

## Event-driven and state safety

- Do **not** wake PM for every tool call, turn, PR comment or test iteration. Use reviewer as local coordination owner until ready to escalate.
- Route replies through Herdr according to `hc --skill`; if agent-to-agent messaging is unavailable, persist a handoff report in the repo/PR, not a claim that a message was delivered.
- `hc` does not create a durable task scheduler; do not imply endless autonomous progress without a running PM or watcher. Respect idle, crash, context/usage limits and human gates.
- PM decides milestones and dependencies; Reviewer decides whether the reviewed slice meets the quality gate; Worker does the implementation.
