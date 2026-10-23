# Automated Git & Sensitive Data Policy

- **Sensitive Data Isolation**: Never stage, commit, or push files containing student PII, exam rolls, marks, photos, signatures, Chrome session profiles, audit journals, or private workbooks.
- **Pre-commit Build & Test**: Always run `python -m unittest discover tests` before committing. Commits are blocked if tests fail.
- **Automated Git Sync**: Use `python -m jkbose_tool.git_sync "<message>"` or the standard 5-step build, leak check, stage, commit, and push protocol described in `AGENTS.md`.
