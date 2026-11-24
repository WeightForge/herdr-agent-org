# Herdr Agent Organization (v0.2 preview)

**Build a reusable AI team from any project—without rewriting a giant PM prompt.**

`agentorg` is an open-source-ready **agent organization starter kit** for Herdr App + herdr-core (`hc`), Claude Code and Codex CLI. It ships installable skills, reusable team templates, a local-only provider profile registry, an explicit dry-run/start workflow, Git worktree separation for software workers, and conservative recovery checks.

> Status: **v0.2 preview / local prototype.** Source and unit tests are included. We have **not** verified live spawning with Herdr or authenticated provider sessions on your machine. The CLI does not run itself 24/7: your PM/Herdr runtime must remain active. No GitHub repository has been published by this package.

The main difference from a single orchestration prompt: the **policy** (skills), **team configuration** (project manifest), **authentication selection** (local profile aliases) and **runtime state** (Herdr + Git) are separate.

## Quick start (Windows PowerShell)

Requires Python 3.10+, Herdr App + `hc`, the desired Claude/Codex CLIs and Git for software worktrees. `hc --skill` describes the installed Herdr version. Python scripts require no extra runtime libraries.

```powershell
# From this cloned/unzipped repository
py -m pip install -e .
agentorg install --target both       # skills for Claude Code and Codex

# In your existing project repository
cd C:\Code\my-project
agentorg init --template engineering --name my-project

# Profiles are LOCAL ONLY. No email or API key is written to the repo.
agentorg profile add reviewer --provider claude --config-dir "$HOME\.claude-work" --model opus --effort medium
agentorg profile add implementer --provider claude --config-dir "$HOME\.claude-personal" --model sonnet --effort high
agentorg profile add designer --provider claude --config-dir "$HOME\.claude-work" --model opus --effort medium
agentorg profile add frontend --provider codex --model gpt-6.2-sol --effort medium

# Bind team roles to aliases; use a different combination in each project
agentorg role set technical-reviewer --profile reviewer
agentorg role set backend-worker --profile implementer
agentorg role set design-reviewer --profile designer
agentorg role set frontend-worker --profile frontend

agentorg doctor
agentorg team plan                 # safe preview; no agents/worktrees started

# Review/edit .ai/PROJECT.md, .ai/ROADMAP.md and .ai/TEAM.json.
# Software worker worktrees require .ai/TEAM.json in a Git commit.
git add .ai QUESTION.md
git commit -m "Configure agent organization"

agentorg team up --apply          # explicit action: creates worktrees and Herdr agents
agentorg team status
# Dispatch is packet + path only (see .ai/PROTOCOL.md): the PM writes .ai/tasks/T-1/packet.md, then sends the
# worker AND its reviewer just that absolute path. Do not paste task text into `team send`.
agentorg team send backend-worker "/abs/path/to/project/.ai/tasks/T-1/packet.md"
agentorg team send technical-reviewer "/abs/path/to/project/.ai/tasks/T-1/packet.md"
agentorg team status              # per-task state, next actor, unknown delivery, pending owner decisions
```

**Important:** The sample `~/.claude-work` and `~/.claude-personal` directories must already exist and be authenticated; adjust them to your local paths. Model names/effort are user-configurable and must be supported by the installed CLI and account. `agentorg doctor` checks executables and directories, **not** an API's actual model entitlements. If you use only one personal Claude config, omit `--config-dir` for that profile. Environment-based API secrets are intentionally not managed by this project.

For macOS/Linux replace `py` with `python3` and use shell paths. For a Codex account/profile isolated from the default Codex login, provide `--config-dir /path/to/codex-home` (sets `CODEX_HOME`), or Codex's native `--native-profile <name>` if configured. Claude Code uses `CLAUDE_CONFIG_DIR`—there is no universal Claude `--profile` flag.

## What gets installed

```text
src/agentorg/data/skills/
  agent-org-manager/SKILL.md        # project management + team policy
  agent-org-engineering/SKILL.md    # software-specific SDLC/PR/review gates
  agent-org-bootstrap/SKILL.md      # first setup, profiles, manifests
  agent-org-recovery/SKILL.md       # checkpoint + crash/limit recovery
src/agentorg/data/*.json           # engineering, research, content templates
src/agentorg/                      # dependency-free Python CLI
examples/layerdelta/               # an illustrative, nonsecret team manifest
```

After `agentorg install --target both` the skills are copied to `~/.claude/skills/` and `~/.agents/skills/`. Existing skill directories are skipped unless `--force`. To load manager in Claude Code: `/agent-org-manager`. In Codex, ask it to use the `agent-org-manager` skill. Never run a downloaded skill without inspecting the source first.

## A PM's first message

> Use the `agent-org-manager` and `agent-org-engineering` skills. Read `.ai/PROJECT.md`, `.ai/TEAM.json`, `.ai/ROADMAP.md`, `.ai/STATE.md` and `QUESTION.md`; run `hc --skill`, `agentorg doctor` and `agentorg team plan`. Reconcile Herdr, Git and PR state. After I approve the execution plan, use `agentorg team up --apply`. Work within the documented scope and approval gates; do not merge, publish or deploy automatically.

For research or content, use only `agent-org-manager` plus relevant domain criteria; the starter templates intentionally omit software-specific PR rules. **Supported team: PM + worker + reviewer for software. The research and content templates are experimental** (`"experimental": true`, shown by `team plan`).

## Commands

| Command | Effect |
|---|---|
| `agentorg init --template engineering` | Create missing `.ai` project manifests; no overwrite |
| `agentorg profile add NAME --provider claude|codex|antigravity ...` | Save profile alias in user config only (`antigravity` runs `agy`; no `--config-dir`/`--native-profile`) |
| `agentorg profile list` | Inspect aliases; no tokens |
| `agentorg role list / role set ROLE --profile NAME` | Update team manifest |
| `agentorg doctor` | Availability preflight (not live authentication) |
| `agentorg team plan` | Preview exact role launch arguments and worktree paths |
| `agentorg team up --apply` | Start/reuse terminals and create worker worktrees |
| `agentorg team status` | Query recognized live terminals; reports `inbox_pending` (unhandled `.ai/inbox/*.md` escalations) and `blocked` (`{role, terminal, kind}` per blocked terminal; never prompt text, read-only, sends no input) |
| `agentorg team down [--apply] [--remove-worktrees]` | Dry-run by default; `--apply` kills then removes only terminals whose labels match this project (workers first). `--remove-worktrees` runs `git worktree remove` without `--force` (dirty worktrees are kept; branches never deleted). Disabled roles report `disabled`; a disabled role's terminal is still stopped if it is live and its labels match |
| `agentorg team smoke [--keep]` | Live end-to-end check against the running Herdr core using fake agents (zero model tokens; includes a codex-provider fake that must receive `--no-daemon`, and asserts `status.blocked == []`); run it from an installed `agentorg`; exit code 1 on any failed check; always cleans up unless `--keep` |
| `agentorg team reconcile` | Refresh untracked local runtime manifest from Herdr |
| `agentorg team send ROLE "TASK"` | Send a scoped message to a role via `hc send` |
| `agentorg install --target both` | Copy skills into local agent directories |
| `python evals/run.py --agent-cmd "agy --model M --mode plan -p"` | Skill evals: deterministic regex grading of an agent's planned replies (see `evals/`) |

## Safety & limitations

- **Explicit execution:** the default is dry-run. `--apply` starts external processes and may create Git branches/worktrees. Nothing merges, publishes, deploys or tags without separate human approval.
- **Local-only profiles:** `AGENTORG_HOME/profiles.json` or OS-specific user config. Never commit it. `TEAM.json` stores aliases, not credentials. Profiles with explicit config directories clear conflicting inherited API authentication variables before launch. On Windows normal account-file permissions apply; validate machine security controls.
- **No duplicate work:** deterministic Herdr terminal names are probed before launch. If the runtime fails to report accurate state, do not blindly retry. Parent PM can stop without terminating child processes started with `--outlive-parent`, subject to Herdr/core and machine availability.
- **Git worktrees:** each enabled software *worker* gets its own worktree/branch. Reviewer roles normally read the project checkout. When docs are not committed to HEAD, startup is blocked rather than launching an uninformed agent.
- **Real lifecycle:** Herdr is the source for whether a terminal exists, Git/CI/PR are sources for whether a task is done. The local `.ai/RUNTIME.json` is ignored by Git and never the sole source of truth.
- **Concurrency:** `max_parallel_workers` is a policy for the PM, not enforced as a live process cap in v0.2. Monitor actual active tasks before sending new work.
- **No automatic watcher daemon yet:** `hc wait --children any` / `hc events` can support event-driven PM operation, but v0.2 does not install a background supervisor. A stopped PM will not independently restart itself.
- **Provider/account constraints:** corporate policies and quota limits still apply. We intentionally do not implement account fallback or auto-switch accounts.
- **Compatibility:** targets current **Herdr App + herdr-core (`hc`)**, not the unrelated Herdr TUI's `herdr` CLI. Check `hc --skill` for your installed version.

## Development and publishing

```bash
python -m unittest discover -s tests -v
python -m build       # optional packaging dependency
```

See [Thai guide](README_TH.md), [architecture](docs/ARCHITECTURE.md), [security](SECURITY.md), [Codex handoff](CODEX_HANDOFF.md), and [contributing](CONTRIBUTING.md).

License: Apache-2.0. Not affiliated with the Herdr, Anthropic or OpenAI teams.

## v2.1 — Coordinator-first PM (Worker > Reviewer > PM)

The PM only plans milestones, assigns task owners/reviewers, resolves blockers/decisions and receives **reviewer-verified milestone reports**. Workers implement/test and notify their paired reviewer directly; reviewers own feedback, QA and correction cycles. PM must not poll frequently or relay ordinary review comments. Runtime topology: `team up --apply` launches reviewers first as children of the PM, and each paired worker with `--parent <its reviewer terminal>`, so worker notes from Herdr reach the reviewer and only reviewer escalations reach the PM (PM -> reviewers -> workers). The launching terminal's `HC_TERMINAL_ID` is passed to reviewers as the PM address. Beyond that this is a **skill policy and initial agent prompt**, not a background watcher or guaranteed always-on scheduler.

The engineering template includes `reviewer_role` on worker roles, e.g. `backend-worker → technical-reviewer`. On new work, explicitly pair the worker with the reviewer. Users may override or remove the optional routing field, but a configured reviewer must exist and be enabled.

### Install skill for a PM host

```powershell
agentorg install --target claude       # ~/.claude/skills (or CLAUDE_CONFIG_DIR)
agentorg install --target codex        # ~/.agents/skills
agentorg install --target antigravity  # ~/.gemini/config/skills
agentorg install --target all          # all three
```

`both` remains the backwards-compatible Claude + Codex alias. When updating an older install, use `--force` **after checking for local custom edits**. Codex can invoke `$agent-org-manager`; Antigravity App/IDE supports `/agent-org-manager`. Skill discovery does not confer access to Herdr: the agent must have shell/tool permission to call `hc` in an environment connected to the running Herdr Core.

Antigravity can serve as an interactive PM through its skill and `hc` shell calls, and (v0.3) as a launched role: `agentorg profile add NAME --provider antigravity [--model M] [--effort low|medium|high|xhigh|max]` starts `agy [--model M] [--effort E] -i <prompt>`. A PM outside a Herdr terminal may not receive `hc send` push messages: reviewers write each escalation to `.ai/inbox/` and the PM reads that folder whenever it wakes.

### PM inbox

Reviewers write escalations as new files `.ai/inbox/<UTC YYYYmmddTHHMMSSZ>-<task>-<code>-<4 hex>.md` (the 4 hex chars are generated once and reused on retry) in the project root checkout and, if they know the PM address, `hc send` a one-line pointer. Only the PM edits `.ai/STATE.md`; on every wake it reads `.ai/inbox/*.md`, skips ids already in the "Handled escalations" list of `.ai/STATE.md`, handles each other file, records its id there BEFORE moving the file to `.ai/inbox/done/`, and reconciles against evidence before replaying an id whose action may have happened unrecorded. `agentorg init` ignores `inbox/` in `.ai/.gitignore` (existing `.gitignore` files are not rewritten; add `inbox/` yourself).

### Task files and file-first handoff

Software tasks live in the root checkout under `.ai/tasks/<id>/` (versioned project state: do not gitignore it; `agentorg init` does not create it). Every file has one writer:

- `packet.md`: written once by the PM before dispatch (immutable). The PM sends the worker and the paired reviewer only its absolute path. Optional `blocked_by: <task id>`; the dependent task's reviewer records the accepted prerequisite commit in `progress.md` before releasing the dependent worker.
- `progress.md`: created and solely owned by the reviewer on receipt (the acknowledgement): state, consecutive UNPRODUCTIVE rounds (RCA counter), accepted dependency commits, evidence refs as `<branch>@<commit>:<path>`. Receivers dedupe by task id.
- Recovery: packet without `progress.md` = unacknowledged, resend the same path (safe, deduped); packet with `progress.md` = in flight, never re-dispatch.
- The worker commits its report to its branch at `.ai/handoff/<task>.md` BEFORE `hc send`, then sends `<branch>@<commit>:.ai/handoff/<task>.md`; the reviewer reads it with `git show <commit>:<path>`. If the send blocks, the evidence already exists.

Codex roles are launched with `--no-daemon` (required by `hc --skill`, otherwise Codex commands run outside hc) and carry an extra label `nodaemon=1`. A Codex terminal started by an older agentorg lacks that label, so `team up` refuses to reuse it ("label differs"): stop it deliberately (`team down --apply`) and start it again.

### Unattended operation

Agents run `hc send/read/get/ls`, and each provider prompts the human for commands it has not been allowed to run. Pre-allow just those commands in each provider's own settings and do not use dangerous skip-permission flags. Prefer exact targets: terminal names are `ao-<project>-<role>-<hash>`, so Claude Code (`settings.json`) can use `"permissions": {"allow": ["Bash(hc send ao-myproj-*)", "Bash(hc read:*)", "Bash(hc get:*)", "Bash(hc ls:*)"]}` where your version supports mid-pattern wildcards. A prefix rule (`Bash(hc send:*)`) matches any trailing arguments and may also allow flags such as `--force`, so where a provider cannot express the restriction keep interactive approval. For Codex and Antigravity configure their equivalent allowlist or approval mode. Folder trust remains a per-worktree human decision (for example Antigravity for `.agentorg-worktrees`). `team status` lists blocked terminals (`blocked`: role, terminal, kind) so the PM can tell the human which terminal needs action. Agents must never answer each other's permission prompts (`hc keys` to a blocked agent is forbidden); a blocked worker is escalated as `blocked` to the human.

For existing teams, configure reviewer pairing with `agentorg role set backend-worker --reviewer-role technical-reviewer`. Existing agent processes are not re-prompted or restarted by installing updated skills; communicate the new handoff policy explicitly to running agents, and do not relaunch an active terminal blindly.
