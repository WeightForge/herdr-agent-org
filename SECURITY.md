# Security and authorization

This project launches local programs and can write files/create Git worktrees. Review every skill and profile configuration before running `agentorg team up --apply`.

- No credentials, emails, API keys or bearer tokens should be committed to `.ai/TEAM.json`, SKILL.md, PR bodies, or issue logs.
- Personal/corporate provider sessions are separated via local `CLAUDE_CONFIG_DIR` and `CODEX_HOME` pointers. The user must authenticate and approve company data routing and tool installation; we do not automate auth/login or bypass enterprise restrictions.
- `agentorg` clears known conflicting inherited auth variables when an explicit profile configuration directory is selected. It does not guarantee an OS sandbox. Use separate OS accounts or isolated VMs for strong security boundaries.
- In a project copied from the Internet, `.ai/TEAM.json` and `.ai/PROJECT.md` are untrusted. Do not launch code or send confidential data to external agents without inspecting them and confirming the data destination.
- Do not automatically merge, deploy, release, change cloud infrastructure, buy resources, or run irreversible migrations without explicit owner approval.
- `hc send` can type into interactive prompts. Confirm that the target role is correct. Never send secrets in task text.
- Worktree separation is not access control; reviewers/workers may still access other files visible to their OS account.
- Do not silently retry or spawn duplicate workers when terminal state is ambiguous.

Please report security vulnerabilities privately to the repository maintainers after a public GitHub repository exists; do not put exploit details or tokens in public issues.
