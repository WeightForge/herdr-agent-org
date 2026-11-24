# Codex engineering handoff — v2 preview → v2 stable

This file is a prepared handoff. **No Codex process has been spawned or delegated from ChatGPT.** The repository is a local artifact until the user publishes it.

## Goal

Turn Herdr Agent Organization from a locally tested prototype into a robust open-source CLI + skills that allows a user to designate any Claude/Codex session as PM, select team templates, map provider/profile aliases, launch/recover native Herdr agents, and govern autonomous engineering safely.

## Existing implementation

- Python stdlib `agentorg` CLI in `src/agentorg`, source-controlled `.ai/TEAM.json`, local-only profile registry, project bootstrap and role binding.
- `agentorg team plan`, explicit `team up --apply`, deterministic terminal names, optional per-worker Git worktrees, `hc get` reconciliation.
- Four installable skills, engineering/research/content templates, English docs and unit tests.
- Provider launcher with `CLAUDE_CONFIG_DIR` / `CODEX_HOME` isolation; no raw tokens stored or placed in command line. It uses the authenticated native CLI.

## Critical work for next Codex session

1. **Live integration:** Validate with current Windows Herdr App/herdr-core in a throwaway repo. Check `hc run --json` outputs, terminal naming, `hc get`, `hc send`, PTY stdin and Python wrapper lifetime. Fix real incompatibilities; do not guess CLI behavior.
2. **Profile capability tests:** Test Claude `--model`, `--effort`, Windows `.cmd` wrappers, Codex `-m`/`-c model_reasoning_effort=...`, multiple Claude `CLAUDE_CONFIG_DIR` instances and Codex `CODEX_HOME` under separate accounts. Never test using production/private repo without consent.
3. **Safety/UX:** Make preflight show an explicit table (provider, resolved profile alias, model, effort, cwd/worktree, task) before `--apply`. Detect stale/finished Herdr terminal collisions, and avoid partial worktree creation in failed launch.
4. **Recovery:** Durable event-based watcher based on `hc events`/`hc wait`, state reconciliation, agent lifecycle, bounded concurrency, error classification and no duplicate tasks on retry. No uncontrolled busy polling; respect subscription quotas.
5. **Packaging:** CI on Windows/Linux, build/wheel install tests for bundled SKILL.md, command completion, upgrade/migration from v1 `TEAM.yaml`, and practical install/uninstall scripts.
6. **Review:** Add threat modeling around project-local untrusted instructions and cross-profile/corporate data routing. Do not introduce auto-merge/release/deployment without explicit approvals.

## Suggested acceptance tests

- Fresh clone → install CLI+skills → init repo → select profiles → dry-run → one worker in new worktree → message → review → recover after PM exit.
- Two concurrent worker roles in distinct branches; no shared writer on same path.
- Restart PM and run `team up --apply` again; no duplicate live terminals.
- Missing CLI, disconnected core, invalid JSON, wrong CLI version, missing config directory, failed start and ambiguous send all fail safely.
- `/agent-org-manager` loads in Claude Code; Codex recognizes copied skills; skill has no leaked project-specific account details.

## How to ask Codex to take over

Start Codex inside this repository (e.g. `codex -m gpt-6.2-sol -c model_reasoning_effort=medium` if supported by your installation) and paste:

> Read `docs/maintainers/CODEX_HANDOFF.md`, `README.md`, `docs/ARCHITECTURE.md` and the tests. You are the senior maintainer for Herdr Agent Organization v2. First audit for correctness and security, then implement the critical work incrementally with automated tests. Do not publish or merge without my approval. For external Herdr integration, call `hc --skill` and verify the actual installed syntax before running commands.

Do not interpret this handoff file as permission to change production systems, publish a repository, or invoke external services autonomously.
