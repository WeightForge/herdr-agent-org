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

To let Codex continue development after publishing, either open an issue from `CODEX_HANDOFF.md` or launch Codex in the cloned repo with the handoff prompt found there. Do not assume Codex has received work until it confirms it.
