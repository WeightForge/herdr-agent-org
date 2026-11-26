## 1.1.0 - per-role skill sets chosen by the PM
- Fix (found live with a 10-pane team in Herdr App): with full autonomy, `team up --apply` now answers each new Claude Code, Codex and Antigravity folder-trust prompt itself and waits until every agent shows its ready prompt, then hands over. Before, the PM answered those prompts while already dispatching: a task path typed into Codex's trust prompt was read as menu keys, opened its Agent Command Center and forked an unrelated old session. Agents still not ready after 60 s are named in a warning. Each prompt is answered once: the screen can still show the prompt for a moment, and a second Enter on Codex's next screen opened another thread (seen live).
- Fix (found live): `team up --apply` no longer stops the whole team when a running worker has switched branches in its own worktree; only a worker that needs a new launch has its worktree checked.
- New `agentorg profile skills [NAME...] [--json]`: skills installed for each profile (name, one-line description, source). Layouts per provider are in docs/ARCHITECTURE.md. Only skill folder names and SKILL.md `name`/`description` are read, plus plugin names and versions from Claude's `installed_plugins.json`; no credential or settings file is opened.
- New optional role field `skills` (max 8 names, `plugin:skill` allowed) and `agentorg role set ROLE --skills a,b` (empty value clears). Old TEAM.json files stay valid.
- `team plan` / `team up` warn, never fail, when a role skill is not installed for the role's profile (also in the report's `warnings` list).
- A role's launch prompt gains one sentence naming its skills; nothing is added when it has none.
- Bootstrap skill: the PM runs `profile skills` for the proposal's profiles, proposes 2-4 skills per role from that list in a new `Skills` column, and applies them with `role set --skills` after the owner's yes. The manager skill may propose skill changes at the post-milestone reassessment. Nothing is ever installed.
- Panes are named `<Title> \· <provider>` with `herdr-app do pane.rename` after placement (best effort, a failure only warns). Equal row heights are still not handled (existing shortcut).
- Plugin skill folders follow the plugin manifest's `skills` path (for example `.claude/skills`), else `<plugin>/skills/*`, plus a root SKILL.md.
- Known limits: Codex and Antigravity plugin skills are listed by bare name; with no `installed_plugins.json` (Codex) the newest plugin version dir is used.
- Mock-tested only (`tests/test_v11.py`): discovery over fake folder trees (the layouts were also read, names only, on one Windows machine with Claude Code, Codex and Antigravity installed), skills validation, the prompt sentence, the plan warning, and the `pane.rename` call. Not verified live: that `pane.rename` takes effect in a running Herdr App, that Codex and Antigravity honor the skill names in the prompt, and the bootstrap/manager skill wording with a real PM.

## 1.0.1 - Codex workers pick up their tasks
- Fix (found live in Herdr App): Codex roles start with `-c disable_paste_burst=true`. `hc send` types fast, so Codex treated a dispatch as a paste and kept the Enter as a newline. The message sat unsent in the composer and the worker never started (seen twice as `unknown_delivery`). Verified live: without the flag the same message stayed in the composer, and with it Codex started work at once.
- Fix (found live in Herdr App): `team watch --loop` crashed on Windows decoding `hc` output as cp1252. All subprocess output is now read as UTF-8 (`errors="replace"`).
- Fix (found live): `agentorg resume --apply` typed in the PM's own pane now resumes the PM. Before, that pane's foreground was `agentorg` itself, so the PM looked busy and got the wake text typed into a bare shell instead; a wake is now only typed into a terminal where an agent is idle or done.
- Fix (found live): pane arrangement retries `terminal.keep` while herdr-app still reports a just-created terminal as not running; before, the resumed worker stayed hidden.
- README demo is now a Herdr App screen recording (Claude Code PM on Haiku 5.5, Antigravity reviewer on Gemini 4 Hydrogen, Codex worker on GPT-6-Luna), sped up with captions; local paths are blurred.
- Verified live in Herdr App after the fixes: resume from the PM pane brought back the Claude PM in its conversation and all three panes; the Codex worker picked up its packet without help.

## 1.0.0 - concurrency warnings, event wakes, cleanup, adaptive bootstrap
All items are unit-tested with mocked `hc` and git state (`tests/test_v10.py`). The last two bullets list what was verified live and what was not.
- Packet fields: optional `Worker: <role id>`, `Paths: <comma-separated paths or globs>` and `Test command: <exact command>` (PROTOCOL.md, manager and engineering skills). Old packets still parse; Protocol version stays 2. Reviewers start from the worker's commit diff and test evidence, then widen.
- Warnings, never blocks: `team status` flags `worker_busy` and `overlap:<id>` on active tasks and has a top-level `warnings` list (including "active tasks N exceed policies.max_parallel_workers M"). `team send` prints a stderr warning when the worker already has an active task. The watcher appends the warnings to wake messages.
- Watcher wake events: a new `.ai/inbox/*.md` not under "Handled escalations", and a new owner answer in `QUESTION.md` (a line `Answer: ...` under a question; the PM writes the empty `Answer:` line and changes handled ones to `Answered:`). Each event wakes once: announced inbox ids and answers (keyed by question heading and answer text, so the PM editing the file does not re-wake it) persist in `RUNTIME.json`, so a restart does not repeat them. Event wakes skip the stale-minutes throttle and the busy-PM rule is unchanged. `team status` shows `watcher_last_wake`.
- `agentorg team cleanup [--apply]` (dry run by default): per finished task, the worker worktree, branch, merged state and uncommitted changes. `--apply` runs `git worktree remove` (no `--force`) only for clean worktrees with a merged branch and `git branch -d` for merged branches; a worktree an active task still uses, an unmerged branch or a dirty worktree is reported and kept.
- Bootstrap proposal table gets a `Why` column and states which tasks can run in parallel; the manager skill reassesses team size after each milestone and proposes role changes to the owner.
- Fix: `resume --all` printed `projects: []` for teams created before 0.9.0. `resume`, `team status` and `team watch` now register the project too, and `resume --all` with nothing registered hints on stderr to run `agentorg resume` in each project folder.
- `agentorg team cleanup` keeps a worktree whose worker terminal is still live (`run team down first`), and the PM writes an empty `Answer:` line under each `QUESTION.md` question so the owner's answer is detectable.
- Fix (found live): a resumed PM in a `full` autonomy team now gets the skip-permissions flag; before, it came back in plain permission mode. Codex roles start with `-c check_for_update_on_startup=false`, because on resume Codex showed an update menu that stalled the agent.
- Verified live on Windows with three harnesses on small models (Claude Haiku 5.5 PM, Antigravity Gemini 4 Hydrogen low reviewer, Codex GPT-6-Luna low worker) on a sample repo: bootstrap launched the mixed team; the watcher woke the PM when the Codex worker never picked up its packet (`unknown_delivery`) and the PM re-sent it; the reviewer verified the work and escalated `milestone_ready`; the PM parked the merge in `QUESTION.md`; writing `Answer: merge` woke the PM through the watcher and it merged. Then every team terminal, the PM and the watcher were killed and removed: `agentorg resume --apply` recreated the reviewer and the worker in their original Antigravity and Codex conversations (session ids discovered from disk), and resumed the Claude PM with `--resume <id>` in a fresh shell standing in for the restored PM pane; the PM ran recovery, re-registered and restarted the watcher. The first live run showed the PM editing `QUESTION.md` re-woke it (mtime-based), which led to answer-keyed dedupe.
- Fix (found live): packets written without a `Worker:` line (any PM on 0.9 skills) map to the one worker role named in the packet, else the one worker paired with its `Reviewer`, so warnings and cleanup still work.
- Also verified live after the fixes: the resumed Claude PM came back with bypass permissions and Codex resumed without the update menu; `team cleanup` kept the worktree while the worker terminal was live, then after `team down --apply` kept it for untracked `__pycache__` files, and once those were gone `--apply` removed the merged worktree and `git branch -d` deleted its branch.
- Not live-verified: concurrency warnings on a real multi-worker team, and a real Windows reboot (terminals were removed by hand instead).
- Windows note: `uv tool install --force` of a new version fails while a team launched from the uv-installed CLI is running (its Python is in use); stop the team first.

## 0.9.0 - resume after a restart
- `agentorg resume [--path P] [--all] [--apply]` (dry run by default): after a shutdown, each role and the PM comes back in its original Herdr pane with its original provider conversation. A role whose terminal now holds a shell gets the provider resume command typed in through a small `agentorg _launch --resume` entry point (so quoting and account env are handled in Python); a terminal that no longer exists is recreated like `team up` would, then paned. Autonomy flags, model and effort are the same as at launch.
- Team terminals start with `hc run --keep`: herdr-core replaces a lost program (host shutdown, signal) with a shell in the same terminal. Resume treats a terminal as lost only when its own program (`hc get --json` `argv[0]`) is a shell, hc reports no agent status, and only a shell is in the foreground. The foreground alone is not used: it shows a shell while a running agent executes a tool.
- Sessions in `.ai/RUNTIME.json` `terminals.<role>`: `provider`, `profile`, `cwd`, `session_id`. Claude roles get `--session-id <uuid>` from agentorg. Codex and Antigravity ids are discovered best-effort by `team reconcile` and `resume` (Codex: newest unclaimed rollout whose cwd matches; Antigravity: earliest unclaimed conversation created since launch, since it stores no cwd). Without an id a worker in its own worktree falls back to the provider's "most recent" (`--continue`, `codex resume --last`); a project-root role is reported `no_session`.
- `agentorg pm register [--model M] [--effort E]` (run by the PM; the bootstrap and manager skills say when) records the PM's provider, session id, terminal, and the model and effort to resume it on (without them it comes back on the provider default). Claude and Codex PMs use the session id from the environment, else the newest transcript for the project.
- `team up --apply` records the project in `projects.json` under the agentorg home; `resume --all` walks it and skips missing paths. The recovery skill documents the PM side.
- Verified live on Linux (hc 0.1.22, Antigravity with Gemini 4 Hydrogen): an agentorg-launched reviewer's process group was killed with SIGKILL; hc put `/bin/bash` in its place, `resume --apply` typed the launch line into that pane, and the agent reopened its own conversation (it recalled a codeword given before the kill) with the same model, effort and skip-permission flags. A second `resume` left the resumed agent alone; a removed terminal was recreated with `--keep` and the same conversation. A PM pane (shell running agy) registered with `pm register --provider antigravity`, killed with the reviewer, came back in its pane with the restart message and ran recovery and the watcher by itself. Three bugs found this way are fixed (foreground-based detection, a second resume typing into a running agent, a named PM pane refused). Not verified: a real reboot (on Windows `taskkill` counts as an exit, so hc does not replace the program; the Windows path rests on hc's documented shutdown recovery), Claude and Codex resume, and Codex session discovery.

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
