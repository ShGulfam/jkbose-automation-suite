# Changes since the previous commit - 27 October 2026

Exact local commit message: `fix(internal-assessment): approve all streams and handle queue reordering`

## Exact files modified

- `jkbose_tool/features/internal_assessment_approval.py`
- `tests/test_internal_approval_modes.py`
- `tests/test_internal_approval_resume.py`
- `README.md`
- `CHANGES_SINCE_LAST_COMMIT.md`

No added or removed files. Institutional exports, students, journals, generated evidence and backups remain private and unstaged.

## Summary

- Remove the fixed subject whitelist only from Entire class and class-except-students approval. Use official enrolled subjects and displayed maxima for Commerce and all other streams. Normalize subject labels for enrollment matching; retain exact paired IDs, eligibility, attendance, absence/history/exclusion holds and the 40% pass range. Strict Excel matching is unchanged.
- When the server reorders pending page membership after approval, verify the complete queue with exact single removal rather than falsely reporting changed rows. Never retry an approval click.
- Reconstruct interrupted-action baselines from the complete hashed export and intact, journaled request-bound live transition chain. A fresh complete queue must prove exact single removal; missing, changed or unsubmitted evidence remains unresolved.
- Document restarting and resuming from the fresh pending queue without repeating confirmed decisions.

## Validation

- Full Python suite: 317 tests passed, including all-stream enrollment/maxima and safety cases, reordered-page full-queue fallback and interrupted recovery after a verified transition.
- Offline replay of the saved 1,141-request queue: 1,141 eligible, zero held; previously 154 subjects were held by the fixed-list/case restrictions.
- Required npm run build passed with Exit Code 0, including 13-page SEO checks. No portal source changes belong to this commit.
- No live Principal approval/rejection, submission or journal modification was performed during development.

## Manual review and push

Review with `git show --stat HEAD` and `git show HEAD`. To recreate the local commit if desired, run `git reset --soft HEAD~1`, then `git commit -m "fix(internal-assessment): approve all streams and handle queue reordering"`.

Changes are committed locally only. Run `git push origin main` manually whenever ready. The assistant does not push.
