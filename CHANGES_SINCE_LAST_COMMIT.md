# Changes since the previous commit - 26 October 2026

Exact local commit message: `feat(internal-assessment): add three principal approval modes`

## Exact files

Modified:
- `main.py`
- `jkbose_tool/features/internal_assessment_approval.py`
- `jkbose_tool/internal_assessment_approval_gui.py`
- `README.md`
- `CHANGES_SINCE_LAST_COMMIT.md`

Added:
- `tests/test_internal_approval_modes.py`

No removed files. No institutional data, journals, browser profiles or credentials are staged.

## Behavior

Added entire-class approval without a workbook, entire-class approval with exact paired student exclusions, and preserved strict consolidated-Excel matching. Class modes use the complete Principal export and Students report and process in portal order. Exclusions can be typed or selected from scoped fetched requests/Excel files; malformed, conflicting or partial identities cannot silently approve an intended exclusion. Exact identifiers, enrolment, name consistency, official maximum, pass marks, known class-wide absence/identity holds and uncertain-action protections remain active. Empty queues finish without reading a workbook or fetching a redundant Students report.

The complete selection is previewed once. The final warning names class/session and eligible/held counts and explicitly says approval cannot be undone by this software; GUI defaults to No and CLI requires APPROVE. No per-award operator confirmation is needed afterward. Each action still binds the exact request ID, verifies completed response and exact queue removal, and records durable history. Rejection functionality is unchanged. No live approval or rejection was performed.

## Validation

Full Python 3.12 synthetic suite: 284 tests passed. Coverage includes more than two pages, no-workbook class mode, exact exclusions across subjects, absence/identity holds, below-pass and malformed requests, empty queues, scoped file picker, read-only/cancellation behavior, confirmation text, portal order, strict Excel safeguards, uncertain receipts and GUI start without a workbook. Website production build was also checked per the shared workspace workflow. Backups are local under `_code_backups/approval_modes_20261026`.

## Review / manual Git

Inspect `git show HEAD` or `git show --stat HEAD`. To amend/recreate: `git reset --soft HEAD~1`, review staged files, then `git commit -m "feat(internal-assessment): add three principal approval modes"`.

Changes have been built, staged, and committed locally. Please run `git push origin main` manually whenever you are ready. No assistant push was performed; the user's explicit no-push policy takes precedence over the repository's generic synchronization instructions.
