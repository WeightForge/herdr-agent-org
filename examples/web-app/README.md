# Web app example

An illustrative team manifest for a small web product: two reviewers, each leading one worker. It is not a runnable repository.

To use it, copy `.ai/TEAM.json` and `.ai/PROJECT.md` into your own project, edit them to match it, and create the local profile aliases it names (`claude-main`, `codex-main`) with `agentorg profile add`. Confirm your installation supports the chosen models, efforts and permissions, then run `agentorg team plan` before `agentorg team up --apply`.
