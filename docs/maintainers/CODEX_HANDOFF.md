# Maintainer handoff (0.7.0)

Short orientation for the next maintainer or coding agent. Read `README.md`, `docs/ARCHITECTURE.md`, `SECURITY.md` and `AGENTS.md` first.

## What exists

- Stdlib-only Python CLI `agentorg` (`src/agentorg`): `init`, `profile add|list|remove|detect`, `role add|remove|set|list`, `doctor`, `team plan|up|status|reconcile|send|down|smoke`, `install`.
- Four skills in `src/agentorg/data/skills` (manager, engineering, bootstrap, recovery), shipped as package data and as a plugin for Claude Code, Codex and Antigravity (manifests in `src/agentorg/data/`, marketplaces at `.claude-plugin/` and `.agents/plugins/`).
- `agent-org-bootstrap` is a one-question flow: detect accounts, propose a team with real job titles (mode is only the level), one "yes", then configure, commit `.ai/` and `team up --apply`.
- File protocol in `src/agentorg/data/PROTOCOL.md` (task states, escalation codes, inbox); local-only profiles; worktree per software worker; panes in the PM's Herdr App tab.
- `profile detect` uses existence checks only. Default `~/.claude` and `~/.codex` are stored with `config_dir: null` so the CLI default state is used.

## How to test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v   # on Windows PowerShell: $env:PYTHONPATH="src"
python -m pip wheel . --no-deps -w <tmpdir>              # check skills and plugin files are inside
```

Use `PYTHONPATH=src` (or an editable install of this checkout) so tests import this tree and not another installed copy. `tests/test_plugins.py` fails when manifests, skill pins and `__version__` drift. The unit tests are mocks; `agentorg team smoke` is the live check against a running Herdr core with fake agents. In reviews, say which results are mock-only and which were verified with a live Herdr process.

## What is verified

- Mock-tested: everything, including `profile detect` (temp HOME), role commands and the skill text.
- Live-verified earlier: `team smoke` against Herdr core. Not yet live-tested: the one-question bootstrap flow in a real PM session, `profile detect` against real home directories, plugin install in each harness.

## Open priorities

1. Live testing across Windows, Linux and Herdr versions, including the bootstrap flow with each provider.
2. Event-driven watcher with a persistent checkpoint (today the PM wakes on reviewer escalations and `hc` notes).
3. Enforce `max_parallel_workers` (currently PM policy, not a process cap).
4. CI/PR adapters and mature research/content templates.
5. Publishing to PyPI (see `PUBLISHING.md`).

## Rules that must not regress

No launch without `team up --apply`; no implicit account or provider fallback; no credentials in the repo; no merge, release, deploy or paid service without the owner's own message; subprocess argv lists only; Windows and Linux support. Do not interpret this file as permission to publish or change production systems.
