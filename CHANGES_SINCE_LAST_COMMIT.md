# Clerk submission grouped-report workflow - 23 October 2026


## Clerk submission with the grouped status report - 23 October 2026

JKBOSE currently errors when searching the blank All status and returns a grouped student/subject-status table for explicit status filters. Read Requested, Approved and Rejected separately, validate every page and filter/account/class/session, expand subjects and combine exact duplicate status entries. Reject changed/conflicting identities or statuses and incomplete coverage. No downloads are used.

Skip existing Requested/Approved paired identities without retrying or claiming their saved marks are visible. Exact Rejected status returns the student/subject to current-source and live pending-row validation, including deliberate changes to rejected attendance/marks. Keep fresh maximum/pass/source/identity controls, input read-back and single Save checks. Final saved status confirms registration/exam/name/subject after the validated Save, while numeric saved-report verification remains explicitly unavailable. Preserve independent Principal approval and absence exclusions.

Distinguish JKBOSE ErrorPage.html from login expiry and include only the destination path in diagnostics. Preserve bounded read completion and never retry Save automatically.

Verification: 271 synthetic tests; live read-only report read 435 awards (424 Requested, 0 Approved, 11 Rejected) across 23 pages. No live mark save, approval/rejection or download was executed. Restart the tool after installation.

Exact modified/added code and test files:
- jkbose_tool/features/internal_assessment.py
- jkbose_tool/features/internal_assessment_batch.py
- jkbose_tool/features/internal_assessment_browser.py
- jkbose_tool/features/internal_assessment_postback.py
- jkbose_tool/features/internal_assessment_saved_report.py
- jkbose_tool/features/internal_assessment_tracking.py
- tests/test_internal_grouped_submission.py
- tests/test_internal_postback.py
- tests/test_internal_report_navigation.py
- tests/test_internal_saved_report.py
- tests/test_internal_status_partitions.py
- README.md
- CHANGES_SINCE_LAST_COMMIT.md
