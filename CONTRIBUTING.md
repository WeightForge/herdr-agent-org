# Contributing

Thanks for helping make multi-agent engineering repeatable and safe.

- Keep skills provider-neutral; avoid hard-coding personal email accounts, model availability, tokens or project-specific business logic.
- Use current **Herdr App + herdr-core** (`hc`) command semantics. The older `herdr` TUI uses a different protocol.
- Any operation that creates processes, branches, external changes, spending or publishing must require a clear explicit action/approval.
- Maintain Windows and Linux compatibility; use Python stdlib where possible.
- Include unit tests and documented behavior changes. Run `python -m unittest discover -s tests -v`.
- Prefer stable, narrow APIs over custom auth managers, polling loops and magic automation.
- For substantial changes, document an upgrade path and include security considerations.

Open an issue describing the use case and relevant `hc --version`/`hc --skill` before creating a broad refactor. No account credentials should appear in test fixtures or bug reports.
