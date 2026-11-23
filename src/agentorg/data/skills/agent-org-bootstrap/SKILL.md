---
name: agent-org-bootstrap
description: Initialize an AI organization for any existing software, research or content project, select team roles and configure local provider profiles via agentorg CLI and Herdr. Use when a user says start a new AI team, initialize a PM, or make a repository autonomous.
---

# Agent Organization — Bootstrap

1. Inspect README, docs, current repo, legal/privacy needs and user request. Do not invent product specifics or overwrite existing docs.
2. Ensure CLI is installed (`agentorg --version`). For the selected domain, run `agentorg init --template engineering|research|content --path <project>`; this creates only missing files.
3. Populate `.ai/PROJECT.md` and `.ai/ROADMAP.md` based on project evidence and owner constraints; template placeholders are **not** validated product requirements.
4. Team config lives in `.ai/TEAM.json`; profile aliases live **outside Git** in the local user profile store. Check `agentorg profile list` then guide the user through `agentorg profile add <alias> --provider claude|codex ...`. For CLI-authenticated accounts `--config-dir` selects `CLAUDE_CONFIG_DIR` or `CODEX_HOME`; do not ask for tokens/emails.
5. Use `agentorg role set <role> --profile <alias> [--model ...] [--effort ...]` to assign exact providers. Run `agentorg doctor` and `agentorg team plan`; verify actual local model availability and corporate policy.
6. For software worktrees commit the generated `.ai/TEAM.json` and project docs before `agentorg team up --apply` so new worktrees contain the shared instructions. Explicit permission to launch the team is required. Preview is safe and side-effect-free with respect to Herdr and worktrees.
7. Load `agent-org-manager` and add domain loop. On PM restart use `agent-org-recovery` rather than rebuilding from scratch.

## Universal separation

Global Skill = HOW to work; TEAM.json = WHO/role mapping; PROJECT.md = WHAT/constraints; STATE.md + verified Herdr/Git = CURRENT state. Software requires engineering-specific gates, research requires reproducibility/method review, content requires evidence/editorial review and publication approval. The CLI supports an initial software, research and content team template; adding new domains requires a domain workflow rather than pretending PR checks apply everywhere.
