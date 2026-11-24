## 0.6.0 - plugins
- Installable as a plugin for Claude Code, Codex and Antigravity: manifests live in `src/agentorg/data/` (the plugin root, next to the single canonical `skills/` copy); marketplaces at `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`.
- Skills resolve the CLI once: `agentorg` if on `PATH`, else `uvx --from git+https://github.com/WeightForge/herdr-agent-org@v0.6.0 agentorg`.
- Skills use a PATH `agentorg` only if it reports exactly the skill's version; otherwise the tag-pinned uvx fallback runs, so an older pip install is never mixed with newer skills.
- `release.yml` now runs on a published GitHub Release (or manually), not on tag push: tagging makes the uvx pin resolvable, publishing to PyPI is a separate decision.
- `tests/test_plugins.py` fails if manifest versions, the uvx pin and `__version__` drift.
- `team up --apply` run from a Herdr App terminal shows the team as panes in the PM's tab (PM left, one row per reviewer with its workers to the right); best effort, idempotent, opt out with `--no-panes`; the JSON output gains `panes`.
- Verified: `team smoke` passes when run through `uvx --from <repo>`.

## Documentation and packaging (0.5.x)
- README rewritten (new structure, worked example, command reference, Mermaid diagram); Thai README removed (the repository is English-only).
- `CODEX_HANDOFF.md` and `PUBLISHING.md` moved to `docs/maintainers/`.
- Added pull request template and feature request template; CONTRIBUTING gains a dev setup and the no-AI-trailer commit rule.
- PyPI metadata (classifiers, project URLs) and a tag-triggered `release.yml` using Trusted Publishing; setup documented in `docs/maintainers/PUBLISHING.md`.
- No runtime changes.

## 0.5.0 - protocol and status
- `data/PROTOCOL.md` (Protocol version 1) is the single source of the file layout, escalation codes, task lifecycle and safety rules; `init` / `team up --apply` copy it to `.ai/PROTOCOL.md` (non-destructive). Launch prompts and skills point to it instead of repeating it.
- Task lifecycle with one writer per state: dispatched, acknowledged, started (worker `ACK` recorded by the reviewer), in_review, done, blocked, cancelled, reassigned. Recovery re-sends to the worker when acknowledged without a worker ack.
- `team status` adds `tasks` (state, next actor, `unknown_delivery`) and `owner_decisions`, derived from files.
- Research and content templates are marked `experimental`; supported team is PM + worker + reviewer for software.
- `docs/UPGRADING.md`; README quickstart uses packet + path dispatch.

## 0.4.0 — robust handoffs
- Codex roles launch with `--no-daemon` (hc containment) and get label `nodaemon=1`; older live Codex terminals are refused for reuse until stopped deliberately.
- `team status` reports `blocked: [{role, terminal, kind}]` without prompt text.
- Task files `.ai/tasks/<id>/{packet.md,progress.md}` (single writer each), `blocked_by` dependencies, file-first worker handoff `.ai/handoff/<task>.md`, inbox ids with a 4-hex suffix and a "Handled escalations" list in `STATE.md`.
- `team down` reports `disabled` roles (and still stops a live, label-matching disabled terminal).
- `team smoke` checks a codex-provider fake receives `--no-daemon` and `status.blocked == []`.
- Docs: exact-target permission rules for unattended operation; four new skill evals.

## 0.3.0 — smoke, down, inbox, evals
- `team smoke [--keep]`: live end-to-end check with fake agents (no model tokens); cleans up after itself.
- `team down [--apply] [--remove-worktrees]`: label-checked stop (workers first), worktrees removed without `--force`.
- PM inbox: reviewers write escalations to `.ai/inbox/`; only the PM edits `STATE.md`; `team status` reports `inbox_pending`.
- Provider `antigravity` (`agy ... -i <prompt>`); doctor checks `agy`.
- Policy: agents never answer or press keys on another agent's permission prompt; unattended-operation guidance.
- Fixes: `role set` validates before writing and `load_project` only checks enabled workers' reviewer routes; JSON files accept a UTF-8 BOM.
- `evals/`: deterministic skill evals (regex grading, no LLM judge).

## 0.2.2 — audit fixes
- Launcher resolves provider executables with `which()` (fixes npm `codex.cmd` on Windows).
- `title`/`focus` in TEAM.json reject shell metacharacters and control characters (cmd.exe shim injection).
- `team status`/`reconcile` report per-role errors instead of aborting; `reconcile` keeps existing `.ai/RUNTIME.json` fields.
- `existing_terminal` recognizes `hc` JSON `error.kind == "not_found"`.
- Single `ESCALATION_CODES` vocabulary shared by runtime prompts and skills; RCA threshold read from `policies.review_rounds_before_rca`.
- Removed unused `default_mode`, `pm_mode`, `reporting` policies; research/content workers now have `reviewer_role`.
- Removed duplicate root `skills/` and `templates/` (single source: `src/agentorg/data/`).
- Skills: sharper trigger descriptions, fill-in templates, research/content loops, project-specific text removed.
- CI builds and installs the wheel and checks `agentorg install`; Windows test fixes.

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
