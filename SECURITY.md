# Security and authorization

This project launches local programs and can write files/create Git worktrees. Review every skill and profile configuration before running `agentorg team up --apply`.

- No credentials, emails, API keys or bearer tokens should be committed to `.ai/TEAM.json`, SKILL.md, PR bodies, or issue logs.
- Personal/corporate provider sessions are separated via local `CLAUDE_CONFIG_DIR` and `CODEX_HOME` pointers. The user must authenticate and approve company data routing and tool installation; we do not automate auth/login or bypass enterprise restrictions.
- `agentorg profile skills` (and the skill warning in `team plan`/`team up`) reads only skill folder names and the `name` and `description` lines of each `SKILL.md` frontmatter under a profile's skills and plugin folders, plus plugin names and versions from Claude's `installed_plugins.json` and the `skills` path from each plugin's `plugin.json` manifest (kept inside the plugin folder). It never opens auth, credential, settings or token files.
- `agentorg` clears known conflicting inherited auth variables when an explicit profile configuration directory is selected. It does not guarantee an OS sandbox. Use separate OS accounts or isolated VMs for strong security boundaries.
- In a project copied from the Internet, `.ai/TEAM.json` and `.ai/PROJECT.md` are untrusted. Do not launch code or send confidential data to external agents without inspecting them and confirming the data destination.
- **Autonomy.** `autonomy` in `.ai/TEAM.json` is `full` (default for new projects) or `supervised` (also what a project without the field gets). In `full`, `team up` launches Claude and Antigravity with `--dangerously-skip-permissions` and Codex with `--dangerously-bypass-approvals-and-sandbox`: agents run commands without asking and nothing sandboxes them, so use it only on a machine and OS account you accept that for, in a repository without secrets. Protocol rules still bind agents: they act freely inside the project and its worktrees, and never change anything outside them or on the system, force-push or rewrite the default branch, spend money, send secrets off the machine, or merge, release or deploy as gated by `human_approval`; these go to `QUESTION.md` while the team keeps working. In `full` the PM and reviewers may answer a teammate's permission prompt with `hc keys`; in `supervised` nobody but the human does. These are instructions to the agents, not technical enforcement.
- Do not automatically merge, deploy, release, change cloud infrastructure, buy resources, or run irreversible migrations without explicit owner approval (in `full` autonomy the request is parked in `QUESTION.md`).
- `hc send` can type into interactive prompts. Confirm that the target role is correct. Never send secrets in task text.
- Worktree separation is not access control; reviewers/workers may still access other files visible to their OS account.
- Do not silently retry or spawn duplicate workers when terminal state is ambiguous.

Please report security vulnerabilities privately to the repository maintainers after a public GitHub repository exists; do not put exploit details or tokens in public issues.
