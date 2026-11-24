# Publishing to a new public GitHub repository

No repository has been created/published by this artifact. The owner should decide the GitHub account or organization and the repository name.

## Pre-publish checklist

- Review `LICENSE`, `README.md`, `SECURITY.md`, the commands in `src/agentorg/`, and `.github/workflows/`.
- Run tests and verify no user/company data, secrets, private repo URLs, email accounts, or credentials have been copied into source.
- Replace sample model names and paths as needed; these are **illustrative**, not entitlements guaranteed by our code.
- Test in a disposable repo before giving `--apply` to real Herdr environments.

## GitHub CLI (from the unzipped repo root)

```bash
git init -b main
git add .
git commit -m "Initial open-source v2 preview"
# Replace OWNER with your chosen GitHub user or organization, and sign into gh first.
gh repo create OWNER/herdr-agent-org --public --source . --remote origin --push
```

Do **not** run the publish command automatically. Creating a public repository exposes its entire pushed Git history and files. Never push your local `profiles.json` or `.ai/RUNTIME.json`.

To let Codex continue development after publishing, either open an issue from `docs/maintainers/CODEX_HANDOFF.md` or launch Codex in the cloned repo with the handoff prompt found there. Do not assume Codex has received work until it confirms it.

## Releasing to PyPI (Trusted Publishing)

`.github/workflows/release.yml` builds an sdist and wheel and publishes them when a GitHub Release is published (or when run manually via `workflow_dispatch`). It never runs on a tag push, a branch push or a pull request. No API token is stored anywhere.

One-time setup (owner):

1. On pypi.org, go to Your projects > Publishing (or, before the first upload, Account settings > Publishing > "Add a pending publisher").
2. Add a GitHub publisher: project `herdr-agent-org`, owner `WeightForge`, repository `herdr-agent-org`, workflow `release.yml`, environment `pypi`.
3. In the GitHub repo, create an environment named `pypi` (Settings > Environments). Optionally add required reviewers so a human approves every publish.

Per release: bump `version` in `pyproject.toml` and `src/agentorg/__init__.py`, update `CHANGELOG.md`, merge, then `git tag vX.Y.Z && git push origin vX.Y.Z` (this alone only makes the uvx pin resolvable) and, when you want PyPI, publish a GitHub Release for that tag. PyPI versions cannot be re-uploaded, so check the build first (`python -m pip wheel . --no-deps -w dist`).

README links are absolute GitHub URLs (on `main`) so they work on the PyPI page; the Mermaid diagram does not render on PyPI, only on GitHub.

## Plugin release (tag-pinned uvx)

The plugin skills run the CLI with `uvx --from git+https://github.com/WeightForge/herdr-agent-org@vX.Y.Z agentorg`, so pushing tag `vX.Y.Z` is what makes the pin resolvable; a PyPI release is optional. Pushing the tag does not trigger `release.yml`; publishing to PyPI is a separate, deliberate GitHub Release.

Per release, bump the version in `pyproject.toml`, `src/agentorg/__init__.py`, the three `plugin.json` files under `src/agentorg/data/`, `.claude-plugin/marketplace.json`, and the `@vX.Y.Z` pin in each `src/agentorg/data/skills/*/SKILL.md`. `tests/test_plugins.py` checks that they agree. The skills use the PATH `agentorg` only when it reports exactly this version. Once the package is on PyPI the pin may become `uvx herdr-agent-org==X.Y.Z`; update the test with it.
