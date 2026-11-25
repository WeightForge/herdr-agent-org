---
name: agent-org-bootstrap
description: Set up an AI team for an existing project with one question: detect accounts, propose a team with real job titles, then configure and launch it after a single yes (requires the agentorg CLI and Herdr `hc`). Use when a user says "set up a team for this project", wants to start a new AI team, or runs `agentorg init`.
---

# Agent Organization — Bootstrap

## Running the CLI

Every `agentorg ...` command in this skill means the CLI resolved as follows. Resolve once per session: use `agentorg` only if `agentorg --version` prints exactly `0.9.0`, the version of this skill; for any other version or if the command is missing, run `uvx --from git+https://github.com/WeightForge/herdr-agent-org@v0.9.0 agentorg` in its place (no install step; needs `uv`). Pass the same arguments either way. If neither works, ask the user to install `uv` or `pip install herdr-agent-org==0.9.0`. This keeps the CLI on the same version as this skill, so an older installed `agentorg` is never used.
<!-- Release note: once herdr-agent-org is on PyPI the fallback may become `uvx herdr-agent-org==0.9.0`. tests/test_plugins.py checks the pin against __version__. -->

## One-question flow

Goal: the owner asks once, answers exactly one question, and the team is running. Roles have a real job title and focus fitted to the project (for example "Senior AI Scientist", "Senior Fullstack Developer", "Senior UX Designer"). `mode` (`reviewer` or `worker`) is only the agent's level; never use "reviewer" or "worker" as the title. The template roles are a starting point, not the answer.

### 1. Prepare silently (no questions, no launches)

- Read the repo: README, docs, manifests, code layout, tests, existing `.ai/`. Do not invent product specifics or overwrite existing docs.
- Resolve the CLI (above). Run `agentorg init --template engineering|research|content --path <project>` if `.ai/TEAM.json` is missing (it creates only missing files).
- Run `agentorg profile detect`. It checks which Claude/Codex config directories and Antigravity exist and never reads their contents. Also run `agentorg profile list` and `agentorg doctor`.
- Stop and ask only if something truly blocks: not a Git repository, no `hc`, no usable provider CLI.

### 2. Design the team from project evidence

- Give every role a domain-specific `title` and `focus` taken from what the project is. Pair each worker with a reviewer (`--reviewer-role`).
- Team size is the owner's decision. If the owner named a size or roles, propose exactly that, however large. There is no limit on reviewers or workers.
- If the owner did not say, size the team from the project: a small or single-area project starts with one reviewer and one worker; a project with clearly separate areas (for example ML, frontend, infrastructure) gets one reviewer per area. One reviewer may lead several workers when the work is one area that splits into parallel tasks. Every extra agent costs quota and a first-launch trust prompt, so do not add roles the evidence does not support.
- Assign accounts from the detected profiles. Your own (PM) account is the directory in `CLAUDE_CONFIG_DIR` (Claude Code) or `CODEX_HOME` (Codex), or the default `~/.claude` / `~/.codex` when unset. Prefer accounts other than the PM's when possible, and put workers on the account with the most headroom if the owner said which. Pick a model and effort per role from what that account's provider offers: read `agentorg profile list` and the provider CLI's help (`claude --help`, `codex --help`, `agy --help`) for the available models and effort levels, and never invent a model id. Give reviewers and hard research roles a stronger model with higher effort, and routine workers a cheaper, faster model with lower effort. If you cannot verify a model id, leave it unset (CLI default). Respect any model or effort the owner named.
- Choose the role ids (lowercase, `-`), for example `ai-scientist`, `ai-engineer`.

### 3. Send ONE message

Contents, in this order:

1. Detected accounts (alias, provider, whether the command was found).
2. The proposed team as a table: `Title | Level | Account | Model | Effort | Focus`.
3. Two or three lines on what `.ai/PROJECT.md` and `.ai/ROADMAP.md` will say.
4. Settings the owner can change in the same reply: autonomy (default `full`: agents run without permission prompts and park owner decisions in `QUESTION.md`; or `supervised`) and the approval flags for merge, release and deploy (default: the owner approves each, as in `human_approval`).
5. The single question: **Start this team, or tell me what to change?**

Ask nothing else, and never ask for tokens, emails or passwords. If the owner asks for changes, update the proposal and ask the same single question again.

### 4. After "yes"

The owner's "yes" is the launch approval for this setup only. It is not permission to merge, release, deploy or spend.

1. `agentorg profile detect --add` registers the detected accounts that are not registered yet (it skips an alias already used by a different profile; report that).
2. Shape the team: for each proposed role `agentorg role add <id> --mode reviewer|worker --title "..." --focus "..." --profile <alias> [--reviewer-role <id>] [--model <id>] [--effort <level>]` using the table's model and effort. Then set `autonomy` and any changed `human_approval` flags in `.ai/TEAM.json` to the owner's choice (edit the file by hand; keep valid JSON). Add the new roles first, then remove template roles that are not part of the team with `agentorg role remove <id>` (a team always keeps at least one role; remove the worker before its reviewer), or adapt one with `agentorg role set <id> --title ... --focus ... --profile ...`. Titles and focus must not contain `" % & | < > ^`.
3. Write `.ai/PROJECT.md` and `.ai/ROADMAP.md` from project evidence; template placeholders are not requirements.
4. `agentorg doctor`, then `agentorg team plan`. Fix any reported issue before continuing.
5. Commit only `.ai/TEAM.json`, `.ai/PROTOCOL.md`, `.ai/PROJECT.md`, `.ai/ROADMAP.md`, `.ai/STATE.md`, `.ai/DECISIONS.md`, `.ai/.gitignore` and `QUESTION.md` (worktrees branch from `HEAD`).
6. `agentorg team up --apply`, then `agentorg pm register` (records your own provider session, so `agentorg resume` can reopen you after a restart).
7. Report the panes and terminals that started and hand over to `agent-org-manager`. On PM restart use `agent-org-recovery` rather than rebuilding from scratch.

## Unattended operation

With `autonomy: full` (the default for new projects), agentorg launches Claude and Antigravity with `--dangerously-skip-permissions` and Codex with `--dangerously-bypass-approvals-and-sandbox`, so agents do not stop for permission prompts. This is not a sandbox: say so in the proposal, and tell the owner the hard lines (protocol, Autonomy) that agents never cross and park in `QUESTION.md`. With `autonomy: supervised`, no such flag is added and the human approves prompts; pre-allow only the `hc` commands agents use in each provider's own settings, for example Claude Code `"permissions": {"allow": ["Bash(hc send ao-myproj-*)", "Bash(hc read:*)", "Bash(hc get:*)", "Bash(hc ls:*)"]}`; a `:*` prefix rule also matches flags such as `--force`, so where a provider cannot restrict it keep interactive approval. Folder trust for a worktree can still show a first-run prompt: in `full` the PM or a reviewer answers it with `hc keys`; in `supervised` the human does. After the launch the PM starts `agentorg team watch --loop` (see `agent-org-manager`).

Task files: `agentorg init` does not create `.ai/tasks/`; the PM creates `.ai/tasks/<id>/` per task. It is versioned project state: do not add it to `.gitignore` (only `RUNTIME.json` and `inbox/` are ignored).

## Universal separation

Global Skill = HOW to work; TEAM.json = WHO/role mapping; PROJECT.md = WHAT/constraints; STATE.md + verified Herdr/Git = CURRENT state. Software requires engineering-specific gates, research requires reproducibility/method review, content requires evidence/editorial review and publication approval. The CLI supports an initial software, research and content team template; adding new domains requires a domain workflow rather than pretending PR checks apply everywhere.
