# Changes since the previous commit - 27 October 2026

Exact local commit message: `fix(verification): support alphanumeric student registrations`

## Exact modified files

- `jkbose_tool/features/internal_assessment_verification.py`
- `jkbose_tool/internal_assessment_verification_gui.py`
- `tests/test_internal_verification.py`
- `README.md`
- `CHANGES_SINCE_LAST_COMMIT.md`

No added or removed files. Real student documents, private history, scratch files and generated PDFs remain excluded from Git.

## Changes

- Preserve legacy letter-prefixed registration numbers throughout admit-card, matrix, individual and grouped PDF readers instead of rejecting a whole input as unreadable.
- Exclude the matched registration from the exam-roll scan, preventing a nine-digit registration suffix being interpreted as a second exam roll. Keep exact identifiers distinct across sources.
- Add a selectable full-details area for Analysis findings so source paths and errors remain readable without horizontal scrolling.
- Retain failed historical analyses and generate a new completed history/report from the original unchanged evidence.

## Verification

- Full automation suite: 319 tests passed, including legacy registrations across four PDF layouts and identifier distinction.
- Actual Class 12 files: 203 admit-card students, 914 expected awards; school consolidated PDF and grouped JKBOSE PDF each contain all 914 awards and match without issues or warnings.
- Fresh PDF rendered and visually inspected; originals and live awards unchanged.
- Required npm run build completed with Exit Code 0 and SEO checks passed. No website source changes belong to this commit.

## Manual review, amend and push

Inspect with `git show --stat HEAD` or `git show HEAD`. To recreate the commit if desired: `git reset --soft HEAD~1`, then `git commit -m "fix(verification): support alphanumeric student registrations"`.

Changes are committed locally only. Run `git push origin main` manually whenever ready. The assistant does not push.
