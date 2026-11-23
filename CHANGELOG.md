## 0.2.1 — 2026-11-23
- Coordinator-first PM: Worker → Reviewer → PM handoff policy with fewer manager interventions.
- Optional validated `reviewer_role` pairs and direct Herdr reviewer terminal targets in launch prompts.
- New `agentorg install --target antigravity|all` global skill installer targets.
- Explicit caution: Antigravity skill access is not the same as being a Herdr child session; no watcher yet.

# Changelog

## 0.2.0 — Open-source-ready preview (2026-11-23)

- Split global PM/engineering/bootstrap/recovery skills from project-specific manifests.
- Added dependency-free `agentorg` CLI and three domain team templates.
- Added machine-local Claude/Codex profile aliases and environment-aware launcher.
- Added explicit dry-run / --apply orchestration and Herdr terminal reconciliation.
- Added Git worktree isolation for software workers; preserved no-overwrite project init.
- Added English/Thai docs, security guidance, publishing instructions and Codex handoff.
- Added automated unit tests and Windows/Linux CI matrix.

Known preview limitations: live Herdr/agent auth behavior not tested in this sandbox; no background watcher daemon or automatic PR/CI adapter; max parallel workers is PM policy, not an enforced process cap.
