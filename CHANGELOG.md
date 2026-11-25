## 0.9.0 - resume after a restart
- `agentorg resume [--path P] [--all] [--apply]` (dry run by default): after a shutdown, each role and the PM comes back in its original Herdr pane with its original provider conversation. A role whose terminal now holds a shell gets the provider resume command typed in through a small `agentorg _launch --resume` entry point (so quoting and account env are handled in Python); a terminal that no longer exists is recreated like `team up` would, then paned. Autonomy flags, model and effort are the same as at launch.
- Team terminals start with `hc run --keep`: herdr-core replaces a lost program (host shutdown, signal) with a shell in the same terminal. A shell in the foreground (`hc get --json` `foreground.name`) is how resume recognizes this.
- Sessions in `.ai/RUNTIME.json` `terminals.<role>`: `provider`, `profile`, `cwd`, `session_id`. Claude roles get `--session-id <uuid>` from agentorg. Codex and Antigravity ids are discovered best-effort by `team reconcile` and `resume` (Codex: newest unclaimed rollout whose cwd matches; Antigravity: earliest unclaimed conversation created since launch, since it stores no cwd). Without an id a worker in its own worktree falls back to the provider's "most recent" (`--continue`, `codex resume --last`); a project-root role is reported `no_session`.
- `agentorg pm register` (run by the PM; the bootstrap and manager skills say when) records the PM's provider, session id and terminal. Claude and Codex PMs use the session id from the environment, else the newest transcript for the project.
- `team up --apply` records the project in `projects.json` under the agentorg home; `resume --all` walks it and skips missing paths. The recovery skill documents the PM side.
- Verification: unit tests with every `hc` and provider call mocked. Not yet verified live: a real shutdown, `hc` keep replacement against agentorg-launched roles, each provider's resume with the typed command, and Codex/Antigravity session discovery.

## 0.8.0 - full autonomy
- `autonomy` in `.ai/TEAM.json`: `full` (default in the templates and the example) or `supervised`; a project without the field is `supervised`, so existing teams keep their behavior.
- With `full`, roles launch with `--dangerously-skip-permissions` (Claude, Antigravity) or `--dangerously-bypass-approvals-and-sandbox` (Codex). `supervised` adds nothing.
- Protocol version 2: agents act freely inside the project and its worktrees; the PM and reviewers may answer a teammate's prompt with `hc keys`; owner decisions are parked in `QUESTION.md` while the team continues; hard lines (outside the project, default-branch force-push, spend, secrets off the machine, merge/release/deploy per `human_approval`) always go to the owner. Launch prompts, skills and SECURITY.md follow the mode.
- `agentorg team watch [--loop --interval N --stale-minutes M]` wakes the PM with `hc send` (only when it is idle or done) when tasks are stale or no role is working; `team status` flags `stale` tasks.
- Bootstrap proposal table is `Title | Level | Account | Model | Effort | Focus`, chosen from what each provider offers, plus autonomy and approval flags in the one question.
- Verified live on Windows with an Antigravity (Gemini 4 Hydrogen) PM, reviewer and worker on a 3-item roadmap, unattended: the one-question proposal showed model and effort per role; the team answered the worker's worktree trust prompt itself, finished and reviewed two milestones with tests, pushed the team branch, and parked merge and PyPI publishing in `QUESTION.md` without stopping; after the owner answered there, the PM merged and pushed `main` and closed the task. `team watch` woke a `done` PM for a stale task and suppressed the repeat. The PM's own first-run folder trust prompt is still the owner's to answer. Claude and Codex launches in `full` mode are mock-tested only.

## 0.7.0 - one-question team setup
- `agent-org-bootstrap` is rewritten around one question: the PM reads the repo, detects accounts, and sends one proposal (accounts, team table, PROJECT/ROADMAP summary); after a single "yes" it configures, commits `.ai/` and runs `team up --apply`.
- `agentorg profile detect [--add]`: finds `~/.claude`, `~/.claude-*`, `~/.codex`, `~/.codex-*` and `agy` by existence checks only (no file is opened). The default dirs are stored as `config_dir: null`; `--add` skips an alias already used by a different profile.
- `agentorg role add` / `role remove`, and `role set --title/--focus`: every agent has a real job title and focus fitted to the project; `mode` is only its level.
- `docs/maintainers/CODEX_HANDOFF.md` rewritten as a current handoff.
- Team size is the owner's decision: the bootstrap skill proposes exactly the size or roles the owner names, with no limit; otherwise it sizes from the project (one reviewer per area, several workers per reviewer allowed).
- Verified live on Windows with an Antigravity PM (Gemini 4 Hydrogen): one proposal message, a change request answered with one revised proposal, then after "yes" profiles registered, roles with project titles, `.ai/` committed and the team launched with the worker under its reviewer. `profile detect` verified on Windows and two Linux machines. Not yet verified live: Claude Code or Codex as PM, and pane layout during bootstrap.

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
