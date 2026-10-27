## Explicit absence submission and class registers

Preview & Submit submits explicitly absent source awards as **Absent**, without assigning a numeric mark. It checks paired registration/exam roll, name, subject, maximum, attendance control and read-back before saving the complete displayed batch. Missing marks, unknown/conflicting attendance, below-pass Present awards and identity conflicts remain manual exceptions. An absence in one subject does not turn valid Present awards in other subjects into absences.

A student absent in any source/history/live subject is excluded from **automatic Principal approval in every subject**. Approval must be handled manually. Submission and approval are separate actions.

Match/Submit refreshes `Class_11_Internal_Assessment_Absence_Register_YYYY_YY.xlsx` or the corresponding Class 12 file beside the original consolidated workbook. One row per absent subject award includes paired identifiers, name, source attendance, submitted/uncertain state, evidence and manual-approval requirement. Source absence alone is never labelled submitted. Append-only history remains authoritative; uncertain saves are never retried automatically. The selected original workbook remains unchanged.

`JKBOSE_Identity_Confirmations.json` beside the original workbook can record an administrator-confirmed correction for the exact class/session/name/paired identifiers and the specific stale roster warning. It never changes identifiers or dismisses other warnings. Normal live Students report and pending-row identity checks remain required. Tracking copies clear only that confirmed warning and retain a verification note.

# jkbose_tool

## Principal approval in Internal Assessment

Select the original consolidated workbook, class, school session and subjects in Internal Assessment, then choose **Principal approval…**. The normal account remains the school/clerk account. The Principal window derives a separate expected `prinNNNNNN` account for the same `schNNNNNN` school.

- **Check requests (read only)** logs in with the Principal browser profile and exports/matches all pending requests for the selected class. It never clicks either decision button.
- **Preview & Approve** performs its own preflight; an earlier check is optional. Confirm the session/exclusive-operation checkbox, log in manually including captcha, then inspect the exact request preview and choose **Approve matched awards** once. Subjects run in the selected source order. Held or mismatched individual requests remain untouched. No rejection action is implemented.
- The browser profile `.chrome_profile_principal` is separate from the clerk profile. Credentials are entered manually and are not stored by the Python program. Download evidence goes into each private approval run.
- Session and enrolment checks use the complete Students Report, since the Principal queue has no session selector. Check requested registration/exam roll, name, subject, marks, maximum, Present attendance, source issues and class-wide absence holds. Reuse the existing match validators. Only queued selected subjects need roster reconciliation.
- Match each grid row to the full-class Excel export. The export is an HTML table with `.xls` extension and supplies a stable request ID and attendance. Never use a row index as a durable identity. Verify the popup hidden request ID before the one Approved confirmation.
- Journal intent before opening the decision control, then intent before confirmation. After a completed response, obtain a fresh full-class export and require removal of only that request ID with every other request unchanged. This is action/queue evidence, not an independently read separate Approved-status report. A failure or interruption leaves an uncertain action and never repeats a decision automatically.
- **Reconcile uncertain approval…** records an administrator's specific official finding, with account/class/session context, actor and note. It does not change JKBOSE. Run a fresh preview after reconciliation.
- **Open Principal history** shows readable per-class/session histories under `history/internal_assessment/References/Principal_Approvals/`. Keep journals and export receipts. The separate source tracking copy projects verified approvals and distinguishes tool confirmation from manual administrator verification. Newer official saved-report status takes precedence over older local approval evidence.

CLI: `python main.py internal-approve --excel-file awards.xlsx --class 11 --session 2025-26 --subjects Mathematics Economics --school-account sch000001 --principal-account prin000001 --confirm-session` is read-only. Add `--execute` to request approval mode, which still requires one exact preview confirmation. Replace the synthetic account examples with the actual school accounts.

## Compact desktop workspace

Restart `python gui_main.py` after installing this update. **Workspace** holds the task forms; **Activity Log** is a separate full-height tab with an unread indicator, Save log and Clear view. Status, Stop, Force Close Browser and View log remain available below both tabs. The sidebar is narrower and controls use compact spacing.

Internal Assessment places the workbook and class/session/account on the first rows. Single-subject and selected-subject controls appear only for the chosen mode. Advanced settings holds worksheet/report-session/maximum/history overrides and uncertain-batch reconciliation. Preview & Submit shows one confirmation and performs all required checks itself. Match read only is optional. Run locks, manual-only exceptions and class-wide absence checks remain active. Reconciliation and task actions are disabled during a running operation. Opening settings or switching tabs never starts a task or enables saving.

## Internal Assessment: independent Preview and Submit

Choose the original consolidated export, class, session, school account and subjects. Click **Preview & Submit**, inspect the student/subject awards and confirm the preview once. The tool reads complete official saved and Students reports, validates identity/subject enrolment and assessment interface/count, then processes valid batches and selected subjects in order without per-batch dialogs. **Match read only is optional**, not a prerequisite. A valid unchanged Match snapshot can be reused for 24 hours; otherwise Submit performs fresh preflight. CLI opt-in: `--execute --confirm-session --automatic-submit` (old `--automatic-after-match` remains an alias).

Every selected workbook is reloaded and fingerprinted. A newly downloaded explicit portal handoff can correct an older source-only absence: every award for that student must be explicitly Present and valid, and the registration/exam-roll pair must be unchanged. Append a correction to the existing hash-chained journal; never delete earlier hold evidence. Actual current absences retain student-wide automatic-approval holds. Live JKBOSE absence holds, identity conflicts, missing students, changed pairs, invalid awards and uncertain saves are never cleared by a new workbook alone.

Every batch still requires exact paired identity, source marks, attendance, official maximum and saved-history checks before a single journalled Save. No automatic Save retry. Completed subjects are skipped only with exact evidence. JKBOSE requires all displayed rows and exposes no independent Next/skip control, so a mixed batch containing a held student stops and other selected subjects can continue.

Online Match/Submit refreshes `<original name>_Submission_Tracking.xlsx` beside the original. It retains original sheets, adds student/subject status flags and a summary, and never rewrites the source. Requested means submitted awaiting separate Principal approval. Rejected has its own status/count and preserves the official rejection reason; Uncertain is reserved for unresolved saves or conflicting receipts. A tracking-copy export failure preserves original data/history and appears in the log. Close the copy in Excel before refreshing.

## Internal Assessment history: latest reports first

Open `history/internal_assessment/OPEN HISTORY.html`, or choose **Open History — latest reports** in the GUI. The history root shows only the latest Students matching Excel/PDF pair per class and school account, named `Class 11 - sch010061 - 2025-26 - Student Matching.xlsx` (and `.pdf`). The page lists each report's run, school/report session, latest run outcome and links to pending-awards checks. An earlier report is explicitly labelled when the newest run did not produce an export.

All original journals, saved receipts, uncertainty records, class-wide absence holds, screenshots, detailed JSON/CSV files, older runs and pending-page reports live under the single `References/` folder. The tool automatically migrates the previous flat technical folders without rewriting their contents and continues to recognize saved/uncertain history. It refuses locked or colliding migrations. Previously recorded absolute evidence paths are resolved to their new location when read; signed audit events are not edited. Do not delete `References` to reset submission state.

Future class runs refresh the landing page and fingerprint-verified report copies. A failed export is recorded in the original run evidence and console; readable report copies never act as saved receipts or enable submission. Enrolment matching and practical pending/attendance coverage remain separate checks.

One tool for automating tasks on `jkbose.jk.gov.in`. Run it with no
arguments for an interactive menu, or use direct commands for scripting.
Either way, everything shares the same login/browser handling, so you
generally only log in once (the browser reuses a persistent profile
across runs — see below).

```
python main.py
```

```
============================================================
 JKBOSE Automation Tool -- Dashboard
============================================================
 Site:   https://jkbose.jk.gov.in/utilities/auth_pages/login.aspx
 Saved login session: found (you likely won't need to log in again)
------------------------------------------------------------
 1) Check students / save screenshots
 2) Submit exam forms (from Excel)
 3) Inspect a page (find current field IDs)
 4) Browse the live site manually
 5) Help / where to look if something breaks
 0) Exit
------------------------------------------------------------
Select an option:
```

Pick a number, answer the prompts (file paths, sheet name, etc.), and it
runs the same code as the direct commands below.

## Direct commands (for scripting)

| Command      | What it does |
|--------------|--------------|
| `browse`     | Log in and leave the browser open so you can look around the live site. No automation. |
| `inspect`    | Log in, dump every field's `id`/`name`/label on a page to a CSV. Use this whenever the site changes and field IDs need re-mapping. |
| `screenshot` | Look up each RR number from a text file, save a compressed screenshot of the result. |
| `submit`     | Fill exam forms row-by-row from an Excel sheet, then pause for you to solve the captcha and click Submit. |

A fifth feature — extracting PDFs/CSVs (admit cards, submitted forms,
results) — is stubbed out in `jkbose_tool/features/extract.py`, ready to
build out later.

## Setup

```
pip install -r requirements.txt
```

Needs Google Chrome installed. `webdriver-manager` downloads the matching
chromedriver automatically on first run.

## Login & persistent session

Every command opens its own Chrome window (separate from your regular
browser — being logged into your normal Chrome doesn't carry over). The
first time you run any command, log in inside that window as usual.

The tool uses a dedicated, persistent profile folder
(`~/.jkbose_tool_chrome_profile` by default — see `CHROME_PROFILE_DIR` in
`jkbose_tool/config.py`), so that session is reused on later runs; you
won't need to log in every single time, until the site session expires.
To force a clean, logged-out run, delete that folder (or set
`CHROME_PROFILE_DIR = None` in config).

## Desktop GUI (alternative to the terminal)

If you'd rather use buttons and file-picker dialogs than typing commands:

```
python gui_main.py
```

Same four things as the terminal dashboard — Screenshots, Submit Forms,
Inspect, Browse — each as its own tab, with a live log panel at the
bottom. Long-running steps (like the manual captcha/submit pause) show as
a popup with an OK button instead of a terminal prompt. Only one job runs
at a time; the buttons grey out while something's running.

## Usage (terminal)

All of these are what the interactive menu (`python main.py` with no
arguments) calls under the hood — use them directly if you want to
script or automate a batch run instead of clicking through the menu.

### Just look around (browse)

```
python main.py browse
```

Logs in, opens on the site's landing page, and waits — browse freely,
nothing gets clicked or filled automatically. Press ENTER in the
terminal when you're done to close the browser. Add `--url "https://..."`
to jump straight to a specific page after login.

### Inspect a page (find real field IDs)

```
python main.py inspect --output fields.csv
```

Logs you in, then waits for you to click over to whatever page you want
mapped — press ENTER in the terminal once you're there. Writes a CSV with
every visible field's `id`, `name`, `type`, and a best-effort guess at its
label, **in page order**, plus any links (`<a>` tags, including ASP.NET
LinkButtons like a "Get Details" trigger — for those rows, `placeholder`
holds the `href` and `nearby_label_guess` holds the `onclick`).

Skip the manual click-over by passing the page directly:

```
python main.py inspect --url "https://jkbose.jk.gov.in/utilities/auth_pages/renewalformxixii.aspx" --output fields.csv
```

### Check student / save screenshots

```
python main.py screenshot --rr-file "C:\path\to\_11rr_nos.txt" --class 12
```

`--class` (11 or 12) is set on the site's Class dropdown **before** each
registration-number lookup — the site requires that order, otherwise the
lookup can target the wrong class. If omitted, the Class dropdown is left
as-is (only safe if you've already set it manually via `browse`).

Screenshots save next to the RR file by default (`--output-dir` to
change), named `1_<rr>.png`, `2_<rr>.png`, etc.

Compression: PNG (palette-quantized, default) keeps text crisp and cuts
file size a lot versus a raw screenshot. For even smaller files:

```
python main.py screenshot --rr-file "..." --class 12 --format jpeg --jpeg-quality 80
```

### Submit forms

```
python main.py submit --excel-file "C:\path\to\forms.xlsx" --sheet Sheet2 --photos-dir "C:\path\to\photos"
```

Same Class rule applies here: it's set **before** the registration number
on every row. By default each row uses its own `Class` column; pass
`--class 12` to force every row to that class instead (overriding the
column, if present).

Expects columns matching the current live form's fields (see
`jkbose_tool/config.py` and `features/submit_form.py` for the current
mapping). Adds/updates `Status` and `Notes` columns as it goes, and skips
rows already marked `Filled...` if you re-run it.

Excel columns it reads (from `config.FIELD_MAP`, confirmed against a live
`inspect` dump of the RR renewal form on 2026-08-15 — leave any column
blank/omitted to skip that field):

```
RegNo, Class, LastClassAttended, Stream,
FirstName, MiddleName, LastName, FatherName, MotherName, DOB,
Gender, Religion, Category, Landline, Email, Mobile,
CurrAddress1, CurrAddress2, CurrVillage, CurrArea, CurrPincode, CurrDistrict,
PermanentSameCurrent, PermAddress1, PermAddress2, PermVillage, PermArea,
PermPincode, PermDistrict,
Disability, DisabilityPercent, VocationalCode, AdditionalSubject,
PhotoPath / pho, SignaturePath / sig
```

`PermanentSameCurrent` should be `Yes`/`No` (checks the "same as current
address" box). `PhotoPath`/`SignaturePath` are full file paths; `pho`/`sig`
are just filenames looked up inside `--photos-dir`.

Note: the "Additional Subjects" dropdown replaced the old radio-button
subject groups (Group2–8) entirely on the live form, so this only sets
one value per student for that dropdown — if the real form allows
picking several additional subjects some other way, re-run `inspect` on
that part of the page and this'll need another small update.

## If the site's fields change in the future

The JKBOSE portal has changed field IDs and even form layouts before
(e.g. the domain move to `jkbose.jk.gov.in`, and the RR Renewal form
currently showing "Closed" with a different subject-selection UI than the
old radio-button groups). When `submit`/`screenshot` starts failing with
"element not found" errors, or a form's fields visibly change on screen,
do this:

1. **Re-inspect the page.**
   ```
   python main.py inspect --output fields_new.csv
   ```
   Log in, navigate to the affected page/form manually, press ENTER.

2. **Compare against the last known-good dump.** Keep your CSVs around
   with dated names (`fields_2026-08-15.csv`, `fields_new.csv`, ...) so
   you can diff them — open both in Excel or run:
   ```
   python -c "import csv,sys; a=set(map(tuple,csv.reader(open('fields_2026-08-15.csv')))); b=set(map(tuple,csv.reader(open('fields_new.csv')))); print('NEW/CHANGED:'); [print(r) for r in b-a]"
   ```
   This prints rows that are new or different in the latest dump.

3. **Update the mapping.** Field IDs used by the automation live in one
   place for the submit form:
   - `jkbose_tool/config.py` — edit `FIELD_MAP` (excel column, element id,
     kind) to match the new `fields_new.csv` values, plus `EXAM_RR_LINK_ID`,
     `GET_DETAILS_BTN_ID`, etc. if those changed too.
   - `jkbose_tool/features/screenshots.py` — separately uses
     `bodypH_txt_rege` / `bodypH_btnregdetails` directly; update there if
     the lookup field itself changes.
   `submit_form.py` shouldn't need editing for ordinary field changes —
   it just loops over `FIELD_MAP`.

4. **Re-test on one row/RR number** before running a full batch, to catch
   anything the CSV dump missed (e.g. a field that only appears after a
   dropdown selection triggers a postback).

If you're not comfortable editing the Python yourself at that point, the
fastest path is: run `inspect`, share the resulting CSV (and a
screenshot of the live form) back with whoever maintains this tool, and
they can update the field mapping from that.

## Project layout

```
main.py                        CLI entry point + interactive terminal dashboard
gui.py                          Tkinter desktop GUI (same features, buttons/tabs)
jkbose_tool/
  config.py                    URLs, timeouts, compression settings, Chrome profile, FIELD_MAP
  browser.py                   shared: launch Chrome, manual login, postback waits
  utils.py                     shared: filename sanitizing, screenshot compression
  features/
    screenshots.py             "screenshot" command
    submit_form.py             "submit" command (generic, driven by config.FIELD_MAP)
    inspect.py                 "inspect" command
    extract.py                 stub for future PDF/CSV extraction
```

## Adding a new feature

1. Create `jkbose_tool/features/your_feature.py` with a
   `run(driver, **kwargs)` function, following `screenshots.py` or
   `submit_form.py` as a template — the driver you get is already logged
   in (and, for `screenshot`/`submit`, already inside the Exam/RR
   section).
2. Add a subparser for it in `main.py` (copy the `screenshot`/`submit`
   block) and call `your_feature.run(...)` in `main()`.

## Extract / rename student photos (local utility)

The desktop GUI now has a **Photo Extract / Rename** section. This feature does
not use the JKBOSE website and does not open Chrome.

Use it when you have:

1. A large folder containing many student photos, where each required photo's
   filename contains the student's registration number somewhere in the name.
2. A text file containing the registration numbers you want to extract, one per
   line.
3. An existing destination folder (you can create/name this manually anywhere,
   including beside your source/input files).
4. Optionally, another text/CSV file containing `registration_no,class_roll`
   pairs if you want the copied photos renamed by class roll.

Example registration-number file (`required_regs.txt`):

```text
301002068
301002069
301002070
```

Example rename mapping (`photo_names.txt`):

```text
301002068,1
301002069,2
301002070,3
```

If the source folder contains files such as:

```text
DShk_GulfamProjectscontextoptimized_photos_301002068.jpeg
student_301002069_photo.jpg
IMG_301002070_2026.jpg
```

then, with the rename mapping above, they are copied into the chosen destination
folder as:

```text
1.jpg
2.jpg
3.jpg
```

JPEG/JPEG files are normalized to the `.jpg` filename extension. Non-JPEG
images keep their actual extension so the tool never simply labels a PNG as a
JPG without converting it.

By default the source folder is searched recursively, including its subfolders.
The source images are only **copied**; they are never moved or deleted. If a
same-named file already exists in the destination, the default behaviour is to
create `_2`, `_3`, etc. You can enable overwrite from the GUI or CLI.

If more than one photo filename contains the same registration number, the tool
logs a warning and deterministically chooses the shortest/best filename match.
If a registration number is absent from the optional rename file, its matching
photo is still copied with the original filename.

CLI equivalent:

```bash
python main.py photos \
  --reg-file "C:\\path\\required_regs.txt" \
  --source-dir "D:\\AllStudentPhotos" \
  --destination-dir "D:\\contextoptimized_photos (8 aug 2026)" \
  --rename-map-file "C:\\path\\photo_names.txt"
```

Useful optional flags:

```text
--no-recursive   search only the selected source folder, not subfolders
--overwrite      overwrite a same-named file already in the destination
```

## Performance safeguards (fetch / submit)

The current build avoids several expensive operations in the high-volume pipelines:

- ASP.NET postbacks are detected with a lightweight page token instead of repeatedly transferring/comparing the complete HTML source.
- The delayed Subjects-grid stability check runs only when the selected output actually needs Subjects/PDF content; **top-only** capture skips it.
- Registration input lookup no longer performs a duplicate Selenium element search after an explicit wait.
- Submit does **not** refresh + sleep before every student. It reuses the current form and refreshes only if the core registration field is actually absent.
- Text/select fields already holding the requested value are left unchanged. This is especially important for postback dropdowns, because re-selecting an unchanged value can otherwise cause a full postback-timeout wait.
- File uploads are verified immediately after Selenium `send_keys`; the old unconditional upload delay is removed.
- Optional-field fallback wait is intentionally short (`QUICK_WAIT = 1`) after the relevant postback has already completed.
- Excel progress is written only to the `Status` / `Notes` cells of the existing workbook and saved in batches (`PROGRESS_SAVE_EVERY = 5`) instead of rebuilding the entire workbook after each student.

These changes remove client-side redundancy only; network/server response time, genuine JKBOSE postbacks, captcha entry, and manual submission time remain outside the program's control.


### Photo extraction run report
Each Photo Extract / Rename run automatically writes `photo_copy_report_YYYYMMDD_HHMMSS.txt` into the selected destination folder. The report contains the run summary plus detailed registration numbers for missing photos, all candidate paths for multiple filename matches (with the selected file marked), and registrations missing from the rename mapping.

## Submit Excel structure (updated)

The submitter accepts **subject names**, so you do not need to know JKBOSE numeric subject codes. After the Stream is selected, the tool reads the live optional-subject radio labels and clicks the matching subject by visible name. The local subject-code catalog is used only for preflight validation/fallback; the live page remains authoritative.

### Class 11 (full registration / fill)

Minimum recommended columns:

| Column | Purpose |
|---|---|
| `RegNo` | Registration number (required) |
| `Class` | `11` (can instead be fixed in the GUI) |
| `Stream` | `Science`, `Commerce`, `Humanities`, or `Home Science` (site codes `S/C/H/HS` also accepted) |
| `Subject1`, `Subject2`, ... | One subject name per column. Any number of `SubjectN` columns is supported. |
| `VocationalSubject` | Optional friendly vocational name, e.g. `IT And ITES`; `VocationalCode` is still supported. |
| `AdditionalSubject` | Optional additional-subject visible text/value |
| `PhotoPath` / `SignaturePath` | Full image paths, OR use `pho` / `sig` filenames with the selected Photos folder |

All personal/address columns in `jkbose_tool.config.FIELD_MAP` remain optional and are filled only when a nonblank value is supplied: `LastClassAttended`, `FirstName`, `MiddleName`, `LastName`, `FatherName`, `MotherName`, `DOB`, `Gender`, `Religion`, `Category`, `Landline`, `Email`, `Mobile`, `CurrAddress1`, `CurrAddress2`, `CurrVillage`, `CurrArea`, `CurrPincode`, `CurrDistrict`, `PermanentSameCurrent`, `PermAddress1`, `PermAddress2`, `PermVillage`, `PermArea`, `PermPincode`, `PermDistrict`, `Disability`, `DisabilityPercent`.

Instead of separate `Subject1`, `Subject2`, etc., a single `Subjects` column may contain multiple names separated by commas, semicolons, `|`, or line breaks. `OptionalSubject1`, `OptionalSubject2`, etc. and `Sub1`, `Sub2`, etc. are also accepted.

### Class 12 (renewal)

For the current renewal workflow the tool intentionally treats Stream, subjects, personal fields, photo, and signature as **read-only / already carried from Class 11**. It performs only Class -> RegNo -> Get Details, then waits for manual captcha/Submit.

Recommended Class 12 input therefore needs only:

| Column | Purpose |
|---|---|
| `RegNo` | Registration number (required) |
| `Class` | `12` (or choose Class 12 once in the GUI) |
| `Status` | Optional; generated/updated by tool |
| `Notes` | Optional; generated/updated by tool |

Extra Stream/Subject/photo/personal columns can exist in the workbook; the submitter ignores them for Class 12.

### Preview & Validate before Submit

The GUI now has **Preview & Validate**. Running Submit also opens this preview first. It shows every student in a table with Registration No, Class, Stream, resolved subject names, photo status, signature status, and warnings. Selecting a row shows the actual photo/signature thumbnails when readable. The user must choose **Proceed to Submit** before the browser automation starts.

## Deep Inspect Page

`Inspect Page` now produces three CSV files from the live form:

* `fields.csv` - all form/link elements, including hidden/disabled state, id/name/value/events and nearby label.
* `fields_options.csv` - every dropdown option plus every radio/checkbox label and numeric value.
* `fields_stream_subjects.csv` - if the Stream dropdown is present, the inspector cycles Science/Commerce/Humanities/Home Science, waits for each ASP.NET postback, and records Group No, visible subject name, numeric subject code, radio id and radio name.

This makes it possible to refresh the software's local catalog from the live page instead of manually opening DevTools for every stream.

## Submit templates
The Submit Exam Forms screen includes **Download Class 11 Template** and **Download Class 12 Template** buttons. Class 11 supports friendly headings such as `AddressLine1`, `Village/Town`, `Pincode`, `District`, `Area`, plus subject names in `sub1`, `sub2`, etc. Compulsory, optional-radio, and vocational subjects are routed automatically. See `SUBMIT_COLUMNS.md`.


## Class 11 subject input: names or codes
The Submit screen now has a **Subject Input Mode** selector. It defaults to **Subject Names (recommended)**, using `sub1`, `sub2`, ... and matching against the live JKBOSE labels after the Stream postback. Select **Subject Codes (legacy)** to keep older workbooks that use `Group2_choice` ... `Group8_choice` (or `SubjectCode1`, etc.) plus `VocationalCode`. The Class 11 template download automatically follows the selected mode; Class 12 uses its minimal renewal template.

## Browser / JKBOSE connection interruptions

The submit batch distinguishes ordinary row problems from fatal browser/session loss.
If Chrome is closed, crashes, or disconnects from ChromeDriver (`invalid session id`,
`not connected to DevTools`, `no such window`), the batch stops immediately instead
of repeating the same error for every remaining student. Progress already written to
`Status` / `Notes` is saved. Start **Submit Exam Forms** again when the browser/site is
available; rows whose Status begins with `Filled` are skipped, so unfinished/error rows
are retried automatically.

The login page also retries transient JKBOSE/network errors such as
`ERR_CONNECTION_TIMED_OUT` a few times. If the portal still cannot be reached, the GUI
shows a short connection message rather than filling the status area with a Selenium
stack trace.

### Auto-skip already submitted / renewed records

The Submit screen now enables **Auto-skip records JKBOSE reports as already submitted / renewed** by default. After each **Get Details** lookup, the tool checks only for strong explicit JKBOSE completion wording (including JavaScript alerts and visible page messages). When found, it writes `Already Submitted` to the row's Status, stores the site message in Notes, and advances immediately without showing the manual Continue dialog. Rows previously marked `Already Submitted` are also skipped automatically on later runs. Disable the checkbox if JKBOSE changes its message wording and you want every record to pause manually.

### Auto-skip completed / already-submitted records

The Submit screen option is enabled by default for both Class 11 and Class 12.
Rows already carrying a completed Excel status such as `Filled...`, `Already Submitted`,
or `Submitted - verified` are skipped before browser lookup. For unfinished rows, after
`Get Details` the live JKBOSE page/alert is checked for an explicit already-submitted or
already-renewed message; if found the row is marked `Already Submitted` and the batch
continues automatically without the manual Continue dialog.

## Bulk auto-skip completed rows (2026-09-01)
- The submit pipeline pre-scans the selected Excel sheet before Selenium row processing.
- Rows with explicit completed statuses such as `Submitted - verified`, `Already Submitted`, `Submitted successfully`, etc. are removed from the work queue and never trigger Get Details or the Continue dialog.
- Unicode dash/spacing variations in Excel status text are normalized.
- Live JKBOSE completion wording is detected more flexibly for both Class 11 and Class 12.
- A generic `Filled` status is no longer treated as proof of successful submission. After manual Continue, the tool attempts to verify a success/completion message; unverifiable rows remain retryable.

### 2026-09-01: Silent verified-row skip + no Submit modal

- `Submitted - verified` is treated as a hard completed status before Selenium processes a row. Extra spaces, NBSPs, Unicode dashes, and common punctuation variants are normalized, so `Submitted -   verified`, `Submitted – verified`, etc. are also skipped.
- The Submit Forms GUI no longer shows the modal **Action needed / Continue** window. For a pending row, fill completes and the tool quietly waits while the user solves the captcha and clicks JKBOSE **Submit** in Chrome.
- The tool advances automatically when JKBOSE reports success/completion or the successful ASP.NET submission resets/navigates away from the student form. Wrong-captcha postbacks keep the row active.
- Browse Site / Inspect Page retain their explicit Continue dialog where a manual navigation checkpoint is still useful.


## Manual resume point (Last submitted RegNo)

Submit Forms now includes a **Last submitted RegNo** field. If you know the last student actually submitted in the Excel order, enter that exact registration number before running. The tool skips that row and every row above it, and processes **every row below it regardless of stale Status values**. This is intentionally stronger than the normal Status-based resume logic and is useful after an interrupted or previously buggy run. The RegNo must occur exactly once in the selected sheet; otherwise the run stops before touching any student.

After **Get Details**, the browser automatically scrolls to the captcha/Submit area. For Class 11 it scrolls there again after field/subject/photo filling, so later postbacks cannot leave the captcha off-screen.


## Internal Assessment awards

Open `python gui_main.py` and choose **Internal Assessment**. This feature is separate from Exam Form submission; it never changes exam-form behaviour.

1. Export completed **Internal Assessment** awards from the school portal. Choose **Export Consolidated Excel / JKBOSE** and leave the automation worksheet set to **Auto**. It prefers the `JKBOSE_Internal_Assessment` values sheet and falls back to `Awards_Matrix`. New matrices contain an aligned **Maximum Marks** row. Do not use the blank `Student_Roster` template.
2. Choose the workbook, sheet, class and session. Use **Single subject**, check several subjects in **Selected subjects**, or choose **All workbook subjects**. The workbook subject loader selects actual exported subjects and combines Botany/Zoology once when enabled. One class/session runs with one login and one exclusive history lock. Leave **Excel maximum** on **Auto**; multiple subjects require Auto because maxima can differ. During the live check, the official JKBOSE maximum is authoritative: the header, its validation maximum and every marks input must agree. The minimum is **40% of that official maximum**. An Excel/official disagreement blocks automation for manual review. Marks are never scaled, rounded, clamped or increased. Numeric maximum/component CLI options remain only as explicit fallbacks for verified legacy single-subject sources without metadata.
3. Check **Combine Botany and Zoology and submit as Biology** to add both marks and their Excel maxima. Equal component maxima are not required, and no each-part entry is needed. Select Biology when combining. Uncheck to import a completed Biology total or a separate Botany/Zoology award, but only if JKBOSE actually offers that subject for the selected class. Missing/invalid parts are never replaced with zero.
4. Preview Excel. Explicit absences submit as Absent without numeric marks. Missing, below-pass Present, over-maximum and conflicting records remain manual exceptions. Absence in any source/history subject excludes that student from automatic Principal approval across all subjects. Other valid Present awards retain Present attendance.
5. Confirm the exact school account displayed after `Hello`, the active JKBOSE examination session, and that no other operator is working on this subject. The visible page does not expose a reliable session field: session confirmation is a required human check, and workbook session/class are validated independently.
6. **Match JKBOSE (read only; Excel + PDF history)** opens the dedicated browser, waits for manual login and checks every selected subject. It compares Excel-to-JKBOSE and JKBOSE-to-Excel using the mandatory **registration number AND nine-digit exam roll as the same pair**, with names as an additional check. It neither fills marks nor clicks Save. Only a real independent grid paging link may navigate further. On the current live site there is none: fetched HTML contains ten displayed students, no additional roster in hidden state, and only **Submit & Next**, which writes awards. Reports prominently label later pages **INCOMPLETE**, never treating unseen students as missing or submitted.
7. **Preview & Submit** is independent of Match read only. It shows one source preview, performs saved-report and complete Students report preflight, validates each displayed batch and processes selected subjects sequentially. Source/history/live absence checks remain active for Principal approval. Unmatched or otherwise unsafe rows still block the complete displayed JKBOSE batch; explicit validated absence does not.
8. `Submit & Next` is clicked once. Verification requires the exact pending-count decrease and removal of that batch's registration numbers, confirmed after a fresh **Show Students** read. The tool then processes the new first pending batch; it never increments pagination and never uses Save to browse. This verification relies on the portal's observed pending-removal behaviour; it is not an independently downloaded saved-marks receipt.
9. Stop is checked before filling, before Save and while waiting. Any timeout, changed identity, expired login, unexpected alert or uncertain save stops the run. An attempted save without verified removal is never retried automatically, including after changing the workbook.

## Full-roster matching and private audit history

### Full Students report matching (2026-10-21)

The live read-only check now also opens **Reports > Students** (`student_report.aspx`), loads the complete class report once, and compares the registration **and** nine-digit exam roll for every selected subject in both directions. Subject enrolment comes from the report's compulsory, elective, additional, vocational and optional columns, never from a broad Science-stream assumption. Biology enrolment can supply Botany/Zoology matching when using separate parts. Names remain an additional check.

**Board report session is a separate setting.** For the owner's confirmed current cycle, workbook **2025-26** maps to the report's latest label **2026-2027**. Leave **Board report session = Auto** to use that exact mapping; it stops if the expected dropdown label disappears or a newer report year appears. Other workbook years need an explicitly verified `--report-session YYYY-YYYY`; they are never automatically shifted. The workbook, submission session and absence/saved-history scopes keep their original school session. The selected report year is recorded separately in history and exports.

Changing the report class can trigger a postback while a previous result remains visible. The reader waits for dropdown postbacks, reacquires replaced controls, always clicks **Search**, and validates the returned student class, school account, exact columns, row sequence and absence of uninspected pagination before claiming complete report coverage. Navigation or login errors stop the run. Only Search and read-only navigation are used; no printing or marks-save controls are clicked.

**Skip JKBOSE applications with no assigned exam roll.** Blank/unassigned exam-roll applications are excluded before subject matching and duplicate checks, and recorded in **Skipped Applications** in the report Excel/PDF. A valid second application is matched normally using both identifiers. The tool never deduplicates by student name. Malformed non-empty exam rolls, two conflicting assigned rolls, and missing exam rolls in the source Excel remain manual identity exceptions.

Each live class run now stores an additional private **students_report/** folder with minimal `roster.json`, per-subject comparisons, **matching.xlsx** and **matching.pdf**. Both session labels, full report coverage, paired identifiers, subject mismatches, name differences, skipped applications, source/official maxima and observed pending-page status are included. Snapshot/report SHA-256 hashes and paths are journalled in the class history. Photos, dates of birth, parentage, demographic details and authentication/ViewState values are not copied into the report snapshot. Actual Practical-page matching evidence remains in the existing files outside that subfolder.

**Full enrolment matching is not a practical-attendance or saved-award check.** The Students report contains neither practical marks nor attendance nor submission receipts. An enrolled student may already have disappeared from the pending award queue after saving. The existing absent/fail/over-maximum protections, class-wide absence holds, exact live-batch validation and unread-pending-page submission block all remain in force. Enrolment discrepancies block automatic entry before filling; a complete enrolment match never relaxes those other checks. Fully verified completed submission jobs still skip without opening a browser.

Example read-only check (no `--execute`):

```powershell
python main.py internal --excel-file "C:\path\awards.xlsx" --class 11 --session 2025-26 --all-subjects --report-session Auto --school-account sch010061 --confirm-session
```

### Existing private audit history and resume

The original Excel is never saved or overwritten. History defaults to `history/internal_assessment` inside this automation folder and the entire `history/` tree is excluded from Git. On first use, the previous `~/.jkbose_tool_private/internal_assessment` evidence is copied intact; originals remain in place. Conflicting files or a legacy run lock stop migration without overwriting evidence. Each exact source/configuration has a private folder containing:

- `manifest.json`: source SHA-256 fingerprint and approved class/session/subject/maxima/pass threshold.
- `events.jsonl`: append-only, hash-chained, flushed-to-disk journal of previews, confirmations, attempts, verified saves, failures and stop events.
- `report.json` and `report.csv`: source records, actual status, Excel maximum, official maximum, official 40% pass mark, exceptions and blocked-batch reasons. Absent, failed and over-maximum records are manual-only. A safe record in an unsafe displayed batch is separately marked `batch_blocked`. Open the CSV in Excel for manual work.
- Timestamped row snapshots and screenshots before/after attempted saves, where Chrome can capture them.

Reuse the same history folder on subsequent runs. Source records absent from JKBOSE are **not** automatically labelled submitted: only a verified batch saved by this tool receives that status. Previously verified students reappearing in the pending grid block the batch. A crash leaves an exclusive lock; reconcile it and any uncertain submission against JKBOSE before manually clearing the lock. Use **Reconcile an uncertain batch** only after checking the entire batch on JKBOSE. Record whether it was saved or not saved, the administrator name and a specific verification note. This adds a permanent human-attestation event; it never rewrites history or claims automated verification. A verified-not-saved finding permits a fresh validated retry; a verified-saved finding prevents repetition. Do not delete/rename history to bypass an unresolved attempt. Keep history, source workbooks and browser profiles private and out of Git/shared folders.

A hash chain detects accidental changes or incomplete journals; it is not a signed, tamper-proof institutional archive. Back up the private history folder through the school's authorized private backup process.

### Command line

Each class invocation has `_class_runs/<timestamp-id>/manifest.json`, hash-chained `events.jsonl`, `report.json`/`report.csv`, and (for live checks) **matching.xlsx** plus **matching.pdf**. These include subject totals, paired student identities, official/Excel maxima, name/identity mismatches, JKBOSE-only rows, unverified Excel rows, incomplete coverage and class-wide manual holds. Export hashes and failures are recorded; a failed export never reports success. Details link to per-subject `matching.json` and private page evidence. `_cohort_holds/` preserves known absences and identity conflicts for later selections.

During submission, unchanged awards with intact account/class/session/subject-scoped saved evidence are skipped automatically, including byte-different re-exports of identical interpreted awards. Changed previously saved marks/identifiers or unresolved attempts stop the run. A read-only or empty pending list is never saved proof. Administrator-attested saved outcomes remain distinguished from automated verification. Read-only matching still visits previously saved subjects.

At the owner's request, obsolete preview-only history was removed on 21 Oct 2026 after checking all journals for attempts, saves and reconciliation evidence. A minimal cleanup record remains in `_maintenance/`; no submission evidence was removed. Newly generated matching reports are retained. Do not delete actual saved/uncertain histories to force a retry.

Offline preview (no Chrome):

```powershell
python main.py internal --excel-file "C:\path\awards.xlsx" --sheet Auto --class 11 --session 2025-26 --subject Biology --preview-only
python main.py internal --excel-file "C:\path\awards.xlsx" --sheet Auto --class 11 --session 2025-26 --subjects Physics Mathematics --preview-only
python main.py internal --excel-file "C:\path\awards.xlsx" --sheet Auto --class 12 --session 2025-26 --all-subjects --school-account sch010061 --confirm-session
```

A live **read-only** check adds `--school-account sch010061 --confirm-session` and removes `--preview-only`. Saving additionally requires `--execute`; each batch still requires typing `SAVE`. The GUI provides the same workflow with confirmation dialogs. There is no unattended/assume-yes option.

Use `--no-combine-biology` for an already-completed Biology total or a separate component. Both Classes 11 and 12 were checked against the live site without entering or submitting marks. Their maxima are class-specific (for example, Physical Education differs). The site exposes no reliable academic-session selector; the operator must verify the actual examination cycle before a real save. Read-only checks inspect the first pending batch of each subject, not all later pages.

### Local validation

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py gui_main.py jkbose_tool
python main.py internal --help
```

Tests use synthetic workbooks and simulated browser states. No automated live award was submitted during development. Check your actual export with Offline Preview and the live page with Read-only Check before the first real batch.

The updated website must be released before downloads include the dedicated handoff sheet. Review flags retain missing/unapproved awards, identity conflicts, invalid maxima and attendance issues as manual exceptions. Auto-selection never submits marks by itself.

### Report matching and displayed batches (23 October 2026)

- Confirm completion of full document and ASP.NET partial postbacks for Students Search, class/subject filters and Show Students. Reject stale grids, login redirects, busy pages and unconfirmed responses; do not retry saves.
- Use the complete Students Report for paired registration/exam-roll and subject matching. Save the report snapshot, reconciliation Excel/PDF and journal before any submission. Keep report and workbook session mapping explicit.
- With a report available, check Internal Assessment interface, available subjects, maximum and pending count without browsing later pending pages. Do not claim full pending coverage.
- Owner-approved workflow validates and confirms each displayed batch. Persist newly observed absences before filling and apply all known source/history/live holds to later subjects. Keep exact paired identities, marks bounds, source fingerprints and single-save verification.
- Persist intent before each single save; verify pending count reduction and removal after read-only reload. Skip only unchanged awards with intact scoped saved evidence. Uncertain submissions require reconciliation.
- Regression verification: 128 synthetic tests, including Mathematics 10+5, resume skip, declined confirmation, later-page absence, partial/full postback and read-only report scope. Live Class 12 Mathematics: 15 pending, first 10 blank, maximum 20; no live marks entered or saved.
- This companion application is not a Git repository. Preserve private history and source workbooks. Installation backups and fingerprints are under _code_backups/ia_postback_batch_<timestamp>/.


### Source preview serial numbers

The source preview shows general S.No., Class/Subject S.No., and Class. Group numbering restarts for each class and subject pair; searches retain original source numbers.

### Final pending batch button

The verified marks button may read Submit & Next for intermediate batches and Submit for the final batch. Both enabled labels are supported. A previous run stopped after a save may have an uncertain journal entry: check the official saved awards and use Advanced → Reconcile an uncertain batch before retrying. Never delete history to bypass it.

### Finding reconciliation records

Use Advanced → Reconcile an uncertain batch. The picker opens Reconciliation with readable Class - Subject - Session - Needs review references. Reviewed references move to Completed on refresh. Original manifests and journals remain in References; a class-run summary manifest cannot be used for batch reconciliation.

### Selected-subject preflight

After complete Students Report matching, assessment preflight checks only selected unfinished subjects. All-source absence and persistent history holds remain mandatory. Completed or unselected subjects disappearing from the pending dropdown do not block other selections. Saved awards require intact saved evidence; absence from the pending dropdown is not a saved-mark receipt.

### Automatic saved-award recognition

Match read only and Submit first check the complete official saved-assessment report. One indexed receipt matcher is shared across subjects and final-batch verification; initial saved and Students reports are fetched once per class run. Exact receipts are stored privately and skipped automatically; fully proven uncertain batches are recovered by appending official evidence. Requested means recorded, not Principal-approved. A final save is checked through this report before advancing to the next subject. Missing or conflicting receipts stop safely without a repeated save. Approval through a separate Principal login will be implemented later.

### Authenticated report navigation

Saved-assessment and Students reports share one authenticated sidebar navigator. It expands a collapsed sidebar only when needed, follows the exact verified report link, and waits for the actual destination to finish loading. No direct GET fallback is used. A genuine login redirect stops before entering marks.

## Chrome detached-document response fix

Handle Chrome's exact "Node with given id does not belong to the document" error during old-document checks. Accept it as a replaced page only when the old document's monitor is also absent and the new same-URL document is ready and idle. Preserve matching ASP.NET completion checks, cancellation and errors for unrelated driver failures. Never repeat a report Next click or Save click. Restart the tool after this update, then rerun Match read only. A tracking copy generated during a failed check is not proof of matching or submission.

Validation: 173 synthetic tests, including the exact inspector error, retained-monitor rejection and unrelated DevTools failure.


## New website exports and returned awards (23 October 2026)

Choose the newest original consolidated export from hssshangus.in. Preview and Submit refresh its Submission Tracking copy; Match read only is optional. Source_Changes compares award fields with the previous selected export across renamed downloads, preserves a private immutable version history, and distinguishes current pending values from already recorded JKBOSE values. The original export is never rewritten. Changes are detected when the file is selected and previewed/run, not by a background watcher.

Exact Requested/Approved receipts suppress repeat entry even when the new export differs: report the discrepancy for review, do not retry. Missing pending rows alone never prove submission. Official Rejected receipts revoke older saved outcomes and permit fresh paired-ID validation of the returned row using current export values, including Absent to Present. No automatic Principal rejection or approval is performed by this reconciliation. Unknown identities, unexpected prefilled values and uncertain save attempts still require evidence; no save is repeated blindly.

Verification: 256 synthetic tests; isolated replay of real history against a complete 435-record saved report. Clerk report navigation read live across 44 pages without Save/Approve/Reject clicks. Live automatic submission was not executed during this review. Restart the automation tool to load the changes.


## Clerk submission with the grouped status report - 23 October 2026

JKBOSE currently errors when searching the blank All status and returns a grouped student/subject-status table for explicit status filters. Read Requested, Approved and Rejected separately, validate every page and filter/account/class/session, expand subjects and combine exact duplicate status entries. Reject changed/conflicting identities or statuses and incomplete coverage. No downloads are used.

Skip existing Requested/Approved paired identities without retrying or claiming their saved marks are visible. Exact Rejected status returns the student/subject to current-source and live pending-row validation, including deliberate changes to rejected attendance/marks. Keep fresh maximum/pass/source/identity controls, input read-back and single Save checks. Final saved status confirms registration/exam/name/subject after the validated Save, while numeric saved-report verification remains explicitly unavailable. Preserve independent Principal approval and absence exclusions.

Distinguish JKBOSE ErrorPage.html from login expiry and include only the destination path in diagnostics. Preserve bounded read completion and never retry Save automatically.

Verification: 271 synthetic tests; live read-only report read 435 awards (424 Requested, 0 Approved, 11 Rejected) across 23 pages. No live mark save, approval/rejection or download was executed. Restart the tool after installation.

## Principal approval modes

Open Internal Assessment, select class and academic session, then choose **Principal approval**.

- **Approve entire class**: no workbook or student list required. Reads the complete Principal queue and Students report, previews eligible and held awards, then processes eligible requests one by one through all pages.
- **Approve class except selected students**: the same class-wide workflow with exact registration-number/exam-roll exclusions across every subject. Enter one `registration, exam-roll` pair per line, or select students from a fetched approval report JSON or Excel awards/requests file. Conflicting pairs stop before any decision.
- **Approve strictly from consolidated Excel**: uses the selected original consolidated workbook and subjects. Both identifiers, subject, marks, attendance and official maximum must match the source.

Complete the separate Principal login and captcha yourself. One preview lists the complete selection and hold reasons. The final warning states the class, session, eligible count and held count, and requires explicit confirmation that approval cannot be undone by this software. Cancelling does not approve anything. After confirmation, no per-student prompt is required.

Absent students and existing class-wide holds remain excluded from automatic approval in every subject. Below-pass, invalid, unsupported-subject or conflicting-identity requests stay untouched. Previously approved requests are absent from the pending queue; uncertain prior actions are never retried blindly. Every verified action retains a durable Principal receipt. A workbook is refreshed only in Excel mode; class-wide mode keeps its receipts in Principal history for later tracking refresh.

CLI defaults remain read-only. Class-wide example (no Excel required):

```powershell
python main.py internal-approve --approval-mode class_all --class 11 --session 2025-26 --school-account schNNNNNN --principal-account prinNNNNNN --confirm-session
```

Use `--approval-mode class_except --exclude "REGISTRATION,EXAMROLL"` for exclusions; repeat `--exclude` for more students. Strict mode uses `--approval-mode excel --excel-file "awards.xlsx" --all-subjects` or `--subjects` with the desired subjects. Only add `--execute` when an approval run is intended. The final explicit approval confirmation still applies.

Restart the software after installing this update. No live Principal approval or rejection was performed during development.

## Approval progress and safe interrupted-run recovery

Class-wide approval modes no longer download Excel after each award. Initial checks establish exact request identities and attendance. Each approval is bound to the selected class and exact popup request ID, requires a completed server response, an exact one-record decrease in the live class total, disappearance of the targeted student/subject, and validation of the complete displayed page. A final full-queue audit checks the remaining list. These live-page proofs are explicitly recorded separately from full exported queue proofs. Strict Excel mode retains full exported verification per award.

The UI shows a determinate progress bar and separate counts for tracked award records, verified approvals, pending awards, pending students, and excluded/held awards. Previously verified receipts are included in tracked totals; approvals performed outside the local history are not invented. One student is complete only when none of that student's pending subject awards remain. Known absence, exclusion and identity holds are still respected.

The read-only Download Excel control now waits for an overlapping success toast to clear; approval/rejection clicks are never automatically retried. An interrupted receipt can be recovered only from a recorded exact submit attempt and intact, complete hashed before/after exports showing that only that request was removed, with every other request unchanged. Mere absence from a queue is insufficient. Unrecoverable uncertainty holds its affected request instead of blocking unrelated eligible awards. Failed GUI runs retain the browser for inspection; use Force Close Browser before starting a new task.

Restart the application to load the update. No live approval or rejection was performed during development or history repair.


## Offline award verification

Restart the application, then open **Internal Assessment > Verify files / verification history**. Verification never opens a browser or changes marks, approvals, original PDFs or original workbooks.

Choose class and school academic session. Class is editable (1–12). Existing Class 11/12 Internal Assessment maxima are built in; other classes require explicit subject maxima, such as `English=20; Science=10; Computing=25`. Known subject codes or the exact printed subject name may be used. Pass is 40%. Unsupported subjects and layouts produce a visible issue rather than a passing result. The existing board admit-card and award layouts are supported; choosing another class does not imply arbitrary school document layouts or scanned images can be parsed.

Choose any supported evidence combination:
- One or more admit-card PDFs with school consolidated awards only.
- Admit cards with JKBOSE awards only.
- Admit cards with both sources.
- School awards versus JKBOSE awards without admit cards.
- A single award source for internal consistency, identity, maximum and pass checks.

School PDF matrices and XLSX exports are supported, including the automation handoff and Awards_Matrix consistency check. JKBOSE individual request rows and grouped student/subject marks are supported in PDF, XLSX and HTML-style XLS exports. Original binary XLS is not supported. PDFs need searchable text; image-only scans are flagged and no OCR is attempted. Admit-card parts are combined. Each award file is independently checked as a complete snapshot: records from different exports are never silently combined, counted twice or used to fill each other's omissions.

Analysis uses exact registration + exam-roll + subject, with names as a secondary warning. It reports duplicate/conflicting identities, missing or extra student subjects, attendance, wrong maxima, below-pass/over-maximum marks, changed values between sources, and inconsistent workbook views. Botany/Zoology are combined once with valid component limits; Healthcare and IT/ITES are excluded from the required Internal Assessment list. The known school 2025-26 / board report 2026-2027 mapping remains explicit. Without readable admit cards, enrollment completeness is clearly unverified; offline files never prove current portal submission or approval status.

The Analysis tab displays overall counts, per-source and per-subject counts and detailed exceptions. Every completed run retains a PDF, full analysis and checksummed manifest beneath the configured private history's `References/Verification/Class <class> - <session>/<timestamp>-<id>/` (or `Verification/` when no References migration exists). `LATEST.json` points to the latest run. Open older results in the Verification history tab without rerunning sources. **Save PDF as…** copies the saved report to any selected location while preventing overwrite of input evidence or immutable history.

No live award submission, Principal approval/rejection or production portal changes are performed by this feature.
