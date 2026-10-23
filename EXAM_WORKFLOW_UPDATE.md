# Exam forms update — 22 October 2026

Check Students accepts the school's reviewed Class 11/12 automation XLSX
(Sheet2) or an existing text registration list. Submit Forms reads Sheet2.
The website's Analytics & JKBOSE Reports workspace provides **Exam Excel**:
review students dropped from the exam, save a reason, then download. Only
current Admissions with assigned Class Roll Nos. are eligible. Board roll,
form number and Approved status text do not substitute for the class roll.

Class 11: choose the folder containing RegNo.jpg and RegNo_signature.jpg or
fill PhotoPath/SignaturePath. Complete any fields flagged by Preview before
running. Exact registrations must be Excel Text. Class 12 renewal preserves
the already-loaded board fields. Both classes verify the returned identity
before treating a lookup as ready. Captcha and the final Submit remain manual.

Dropped applications are excluded, including after a manual resume boundary.
The tool stops for expired sessions, closed pages, wrong classes, mismatched
identities, missing fields and unconfirmed postbacks. Navigation or a cleared
form never counts as successful submission. Existing verified workbook statuses
are skipped on resume. A newly downloaded workbook has no prior progress;
the live explicit already-submitted response must verify any earlier submission.

History is local under history/exam_forms: Latest_Check.xlsx,
Latest_Submit.xlsx and Latest_Inspect.xlsx are the entry points. Original input
backups, their SHA256, event logs and dated reports remain in References.
Keep these private. Close a latest report before starting another run. Marks
and forms have not been submitted during verification of this update.

Inspect reads the current DOM by default and redacts input values and ASP.NET
tokens. Dropdown cycling is only enabled by --inspect-streams. The current
exam Check/Submit portals are closed: this update passed offline tests, but
their selectors and success messages must be rechecked read-only once reopened.
Do not interpret this release as a guarantee against future JKBOSE page changes.

Internal Assessment retains its separate paired registration/exam-roll checks,
official maximum-mark validation, manual handling of fail/absent/out-of-range
awards and whole-student holds when any subject is absent.
