---
name: agent-org-bootstrap
description: Set up an AI team for an existing project with one question: detect accounts, propose a team with real job titles, then configure and launch it after a single yes (requires the agentorg CLI and Herdr `hc`). Use when a user says "set up a team for this project", wants to start a new AI team, or runs `agentorg init`.
---

# Agent Organization — Bootstrap

## Running the CLI

Every `agentorg ...` command in this skill means the CLI resolved as follows. Resolve once per session: use `agentorg` only if `agentorg --version` prints exactly `0.7.0`, the version of this skill; for any other version or if the command is missing, run `uvx --from git+https://github.com/WeightForge/herdr-agent-org@v0.7.0 agentorg` in its place (no install step; needs `uv`). Pass the same arguments either way. If neither works, ask the user to install `uv` or `pip install herdr-agent-org==0.7.0`. This keeps the CLI on the same version as this skill, so an older installed `agentorg` is never used.
<!-- Release note: once herdr-agent-org is on PyPI the fallback may become `uvx herdr-agent-org==0.7.0`. tests/test_plugins.py checks the pin against __version__. -->

## One-question flow

Goal: the owner asks once, answers exactly one question, and the team is running. Roles have a real job title and focus fitted to the project (for example "Senior AI Scientist", "Senior Fullstack Developer", "Senior UX Designer"). `mode` (`reviewer` or `worker`) is only the agent's level; never use "reviewer" or "worker" as the title. The template roles are a starting point, not the answer.

### 1. Prepare silently (no questions, no launches)

- Read the repo: README, docs, manifests, code layout, tests, existing `.ai/`. Do not invent product specifics or overwrite existing docs.
- Resolve the CLI (above). Run `agentorg init --template engineering|research|content --path <project>` if `.ai/TEAM.json` is missing (it creates only missing files).
- Run `agentorg profile detect`. It checks which Claude/Codex config directories and Antigravity exist and never reads their contents. Also run `agentorg profile list` and `agentorg doctor`.
- Stop and ask only if something truly blocks: not a Git repository, no `hc`, no usable provider CLI.

### 2. Design the team from project evidence

- Give every role a domain-specific `title` and `focus` taken from what the project is. Pair each worker with a reviewer (`--reviewer-role`).
- Default size is small: one reviewer and one worker. Add a second pair only when the project clearly needs it. Maximum two pairs on first setup.
- Assign accounts from the detected profiles. Prefer accounts other than the PM's when possible, and put workers on the account with the most headroom if the owner said which. Do not invent model names: leave model and effort unset (CLI default) unless the owner specified them.
- Choose the role ids (lowercase, `-`), for example `ai-scientist`, `ai-engineer`.

### 3. Send ONE message

Contents, in this order:

1. Detected accounts (alias, provider, whether the command was found).
2. The proposed team as a table: `Title | Level | Account | Focus`.
3. Two or three lines on what `.ai/PROJECT.md` and `.ai/ROADMAP.md` will say.
4. The single question: **Start this team, or tell me what to change?**

Ask nothing else, and never ask for tokens, emails or passwords. If the owner asks for changes, update the proposal and ask the same single question again.

### 4. After "yes"

The owner's "yes" is the launch approval for this setup only. It is not permission to merge, release, deploy or spend.

1. `agentorg profile detect --add` registers the detected accounts that are not registered yet (it skips an alias already used by a different profile; report that).
2. Shape the team: for each proposed role `agentorg role add <id> --mode reviewer|worker --title "..." --focus "..." --profile <alias> [--reviewer-role <id>] [--model ...] [--effort ...]`. Remove template roles that are not part of the team with `agentorg role remove <id>` (remove the worker before its reviewer), or adapt one with `agentorg role set <id> --title ... --focus ... --profile ...`. Titles and focus must not contain `" % & | < > ^`.
3. Write `.ai/PROJECT.md` and `.ai/ROADMAP.md` from project evidence; template placeholders are not requirements.
4. `agentorg doctor`, then `agentorg team plan`. Fix any reported issue before continuing.
5. Commit only `.ai/TEAM.json`, `.ai/PROTOCOL.md`, `.ai/PROJECT.md`, `.ai/ROADMAP.md`, `.ai/STATE.md`, `.ai/DECISIONS.md`, `.ai/.gitignore` and `QUESTION.md` (worktrees branch from `HEAD`).
6. `agentorg team up --apply`.
7. Report the panes and terminals that started and hand over to `agent-org-manager`. On PM restart use `agent-org-recovery` rather than rebuilding from scratch.

## Unattended operation

Agents message each other with `hc`, and every provider asks the human before running a command it has not been allowed to run. Pre-allow only the `hc` commands agents use, in each provider's own settings; do not use dangerous skip-permission flags. Claude Code example (`settings.json`), exact targets where the version supports mid-pattern wildcards (terminal names are `ao-<project>-<role>-<hash>`): `"permissions": {"allow": ["Bash(hc send ao-myproj-*)", "Bash(hc read:*)", "Bash(hc get:*)", "Bash(hc ls:*)"]}`. A prefix rule (`:*`) matches any trailing arguments, so it may also allow flags such as `--force`; where a provider cannot express the restriction, keep interactive approval for that command. Folder trust stays a per-worktree human decision (for example Antigravity for `.agentorg-worktrees`). Never allow `hc keys`; agents must not answer each other's prompts.

Task files: `agentorg init` does not create `.ai/tasks/`; the PM creates `.ai/tasks/<id>/` per task. It is versioned project state: do not add it to `.gitignore` (only `RUNTIME.json` and `inbox/` are ignored).

## Universal separation

Global Skill = HOW to work; TEAM.json = WHO/role mapping; PROJECT.md = WHAT/constraints; STATE.md + verified Herdr/Git = CURRENT state. Software requires engineering-specific gates, research requires reproducibility/method review, content requires evidence/editorial review and publication approval. The CLI supports an initial software, research and content team template; adding new domains requires a domain workflow rather than pretending PR checks apply everywhere.
