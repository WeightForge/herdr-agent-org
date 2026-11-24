---
name: agent-org-bootstrap
description: Initialize an AI organization for an existing software, research or content project: select team roles and configure local provider profiles (requires the agentorg CLI and Herdr `hc`). Use when a user says to start a new AI team, set up a PM and roles for a repository, or run `agentorg init`.
---

# Agent Organization — Bootstrap

## Running the CLI

Every `agentorg ...` command in this skill means the CLI resolved as follows. Resolve once per session: use `agentorg` only if `agentorg --version` prints exactly `0.6.0`, the version of this skill; for any other version or if the command is missing, run `uvx --from git+https://github.com/WeightForge/herdr-agent-org@v0.6.0 agentorg` in its place (no install step; needs `uv`). Pass the same arguments either way. If neither works, ask the user to install `uv` or `pip install herdr-agent-org==0.6.0`. This keeps the CLI on the same version as this skill, so an older installed `agentorg` is never used.
<!-- Release note: once herdr-agent-org is on PyPI the fallback may become `uvx herdr-agent-org==0.6.0`. tests/test_plugins.py checks the pin against __version__. -->

1. Inspect README, docs, current repo, legal/privacy needs and user request. Do not invent product specifics or overwrite existing docs.
2. Resolve the CLI as described above. For the selected domain, run `agentorg init --template engineering|research|content --path <project>`; this creates only missing files.
3. Populate `.ai/PROJECT.md` and `.ai/ROADMAP.md` based on project evidence and owner constraints; template placeholders are **not** validated product requirements.
4. Team config lives in `.ai/TEAM.json`; profile aliases live **outside Git** in the local user profile store. Check `agentorg profile list` then guide the user through `agentorg profile add <alias> --provider claude|codex|antigravity ...`. For CLI-authenticated accounts `--config-dir` selects `CLAUDE_CONFIG_DIR` or `CODEX_HOME`; do not ask for tokens/emails.
5. Use `agentorg role set <role> --profile <alias> [--model ...] [--effort ...]` to assign exact providers. Run `agentorg doctor` and `agentorg team plan`; verify actual local model availability and corporate policy.
6. For software worktrees commit the generated `.ai/TEAM.json`, `.ai/PROTOCOL.md` and project docs before `agentorg team up --apply` so new worktrees contain the shared instructions. Explicit permission to launch the team is required. Preview is safe and side-effect-free with respect to Herdr and worktrees.
7. Load `agent-org-manager` and add domain loop. On PM restart use `agent-org-recovery` rather than rebuilding from scratch.

## Unattended operation

Agents message each other with `hc`, and every provider asks the human before running a command it has not been allowed to run. Pre-allow only the `hc` commands agents use, in each provider's own settings; do not use dangerous skip-permission flags. Claude Code example (`settings.json`), exact targets where the version supports mid-pattern wildcards (terminal names are `ao-<project>-<role>-<hash>`): `"permissions": {"allow": ["Bash(hc send ao-myproj-*)", "Bash(hc read:*)", "Bash(hc get:*)", "Bash(hc ls:*)"]}`. A prefix rule (`:*`) matches any trailing arguments, so it may also allow flags such as `--force`; where a provider cannot express the restriction, keep interactive approval for that command. Folder trust stays a per-worktree human decision (for example Antigravity for `.agentorg-worktrees`). Never allow `hc keys`; agents must not answer each other's prompts.

Task files: `agentorg init` does not create `.ai/tasks/`; the PM creates `.ai/tasks/<id>/` per task. It is versioned project state: do not add it to `.gitignore` (only `RUNTIME.json` and `inbox/` are ignored).

## Universal separation

Global Skill = HOW to work; TEAM.json = WHO/role mapping; PROJECT.md = WHAT/constraints; STATE.md + verified Herdr/Git = CURRENT state. Software requires engineering-specific gates, research requires reproducibility/method review, content requires evidence/editorial review and publication approval. The CLI supports an initial software, research and content team template; adding new domains requires a domain workflow rather than pretending PR checks apply everywhere.
