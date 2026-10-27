# Changes since the previous commit - 27 October 2026

Exact local commit message: `feat(internal-assessment): add offline award verification`

## Exact files

Modified:
- `jkbose_tool/internal_assessment_gui.py`
- `requirements.txt`
- `README.md`
- `CHANGES_SINCE_LAST_COMMIT.md`

Added:
- `jkbose_tool/features/internal_assessment_verification.py`
- `jkbose_tool/internal_assessment_verification_gui.py`
- `tests/test_internal_verification.py`

No removed files. Student evidence, generated reports, immutable history, local scratch and code backups remain ignored and unstaged.

## Summary

- Add an offline verification window within Internal Assessment, independent of submission and approval. Accept any supported combination of admit-card PDFs, school PDF/XLSX awards and either JKBOSE individual or grouped PDF/XLSX/HTML-XLS award format.
- Allow classes 1–12 with configurable subject names/maxima for other classes and existing Class 11/12 defaults. Validate exact exam-roll/registration/subject pairs, secondary names, enrollment completeness, duplicates, marks/attendance/pass thresholds and source/workbook consistency. Flag unreadable evidence and unverified scope explicitly.
- Show source and subject counts and exception details, retain complete checksummed analysis/PDF history with IST display dates, and support saving a PDF copy anywhere without overwriting source evidence or immutable history.
- Add the PDF text-reading dependency to requirements and install it for the application's Python runtime. Leave existing clerk and Principal workflows unchanged.

## Verification

- Full Python automation suite: 313 tests passed, including 14 new offline parser, identity, threshold, history, class configuration and GUI layout tests.
- Actual local Class 11 sample: both admit-card PDFs contain 196 students with 882 expected awards; school PDF, individual JKBOSE PDF, grouped JKBOSE PDF and JKBOSE XLSX each contain 196 students/882 awards and agree without issues or warnings.
- Generated PDF rendered and inspected. No live approval, rejection, submission, data change or file download.
- Required portal production build: npm run build passed with Exit Code 0, including 13-page SEO checks. No website source changes are part of this software commit.

## Manual review, amend and push

Inspect locally with `git show --stat HEAD` and `git show HEAD`. To re-create/amend the commit if desired: `git reset --soft HEAD~1` then `git commit -m "feat(internal-assessment): add offline award verification"`.

Changes are committed locally only. Run `git push origin main` manually whenever ready. No push is executed by the assistant.
