#!/usr/bin/env python3
"""
JKBOSE automation tool -- single entry point for all site automations.

Run with no arguments for an interactive dashboard/menu:
    python main.py

Or run a specific command directly:
    python main.py browse                         just log in and browse the live site
    python main.py inspect --output fields.csv    dump field ids/names/labels on a page
    python main.py screenshot --rr-file "..." --class 12    look up RR numbers, save screenshots
    python main.py submit --excel-file "..." --photos-dir "..." --class 12   fill exam forms

There's also a desktop GUI: `python gui_main.py`.

Every command opens one Chrome window and waits for you to log in manually
(the site's captcha needs a human). Login persists across runs via a
dedicated Chrome profile (see jkbose_tool/config.py: CHROME_PROFILE_DIR).

To add a new feature later (e.g. extracting admit-card PDFs):
  1. Write jkbose_tool/features/your_feature.py with a run(driver, ...) function
     (see features/screenshots.py or features/submit_form.py as a template).
  2. Add a subparser for it below (and a menu option in interactive_menu()).
"""
import argparse
import sys
from pathlib import Path

from jkbose_tool import config
from jkbose_tool.browser import get_driver, login_and_enter_exam_section, login_only
from jkbose_tool.features import screenshots, submit_form, inspect, photo_copy
from jkbose_tool.features.exam_input import load_check_inputs, read_exam_dataframe, excluded_reason
from jkbose_tool.features.exam_history import ExamRunHistory
from jkbose_tool.utils import parse_stream_map_string


# ---------------------------------------------------------------------
# Command implementations -- each manages its own browser lifecycle, so
# the CLI, the interactive menu, and gui_main.py can all call these the
# same way.
# ---------------------------------------------------------------------

def cmd_browse(url=None, pause_callback=input, on_driver_ready=None):
    """
    pause_callback  : called with a prompt string when the tool needs you
                      to acknowledge before continuing (default: console
                      input()). A GUI passes a callback that shows a
                      "Continue" dialog instead.
    on_driver_ready : optional callback invoked with the live driver as
                      soon as it's created, so a caller (e.g. the GUI) can
                      keep a reference for a forced close.
    """
    driver = get_driver()
    if on_driver_ready:
        on_driver_ready(driver)
    try:
        login_only(driver)
        if url:
            driver.get(url)
        print(f"[INFO] Browser is open at: {driver.current_url}")
        print("[INFO] Browse the site freely -- nothing here will click or fill anything.")
        pause_callback("Press ENTER when you're done, to close the browser...")
    finally:
        try:
            driver.quit()
            print("[INFO] Browser closed.")
        except Exception:
            # If Chrome crashed/disconnected, quit() itself may raise
            # InvalidSessionIdException. The useful error was already reported.
            print("[INFO] Browser session was already closed/disconnected.")


def cmd_inspect(url=None, output="fields.csv", pause_callback=input, on_driver_ready=None, inspect_streams=False):
    history = ExamRunHistory('Inspect')
    if output == 'fields.csv':
        output = str(history.reference / 'fields.csv')
    driver = get_driver()
    if on_driver_ready:
        on_driver_ready(driver)
    try:
        login_only(driver)
        history.bind_account(driver)
        if not url:
            pause_callback("Navigate to the page you want to inspect in the browser, "
                            "then press ENTER here...")
        inspect.run(driver, url=url, output_csv=output, inspect_streams=inspect_streams)
        history.record('inspection_saved', file=str(output))
        history.finish('Inspection complete')
    except Exception as error:
        history.finish('Stopped - review required', str(error)[:1000])
        raise
    finally:
        try: driver.quit()
        except Exception: print('[INFO] Browser session already closed.')
        print("[INFO] Browser closed.")


def cmd_screenshot(rr_file, output_dir=None, fmt=None, jpeg_quality=None, student_class=None,
                    stream_map=None, output_mode="screenshot", capture_mode="top_and_subjects",
                    on_driver_ready=None, stop_event=None):
    """
    student_class : "11" or "12" -- set on the site's Class dropdown before
                    every RR lookup (the site requires that order).
    stream_map    : optional {serial_number: stream_value} dict (serial
                    number = 1-indexed line number in rr_file). Selects
                    Stream before the subjects screenshot, per-student.
                    Build with jkbose_tool.utils.parse_stream_map_string()
                    or build_stream_map().
    output_mode   : "screenshot" (default, compressed image) or
                    "pdf" (whole page via Chrome's Page.printToPDF).
    capture_mode  : (screenshot mode only) "top_and_subjects" (default,
                    slower, includes Subjects) or "top" (faster, top of
                    page only). See features/screenshots.py for details.
    stop_event    : optional threading.Event. Checked between RR numbers so
                    a caller (e.g. the GUI's Stop button) can end the batch
                    early.
    """
    inputs = load_check_inputs(rr_file, student_class)
    if not any(row['RegNo'] and not row.get('_skip_reason') for row in inputs):
        print('[SKIP] No eligible students. Browser was not opened.')
        return
    history = ExamRunHistory('Check', rr_file)
    driver = get_driver()
    if on_driver_ready:
        on_driver_ready(driver)
    try:
        login_and_enter_exam_section(driver)
        history.bind_account(driver)
        screenshots.run(
            driver,
            rr_file=rr_file,
            output_dir=output_dir,
            screenshot_format=fmt,
            jpeg_quality=jpeg_quality,
            student_class=student_class,
            stream_map=stream_map,
            output_mode=output_mode,
            capture_mode=capture_mode,
            stop_event=stop_event,
            history=history,
        )
        history.finish('Stopped by operator' if stop_event and stop_event.is_set() else 'Run ended; review student results')
    except Exception as error:
        history.finish('Stopped - review required', str(error)[:1000])
        raise
    finally:
        try: driver.quit()
        except Exception: print('[INFO] Browser session already closed.')
        print("[INFO] Browser closed.")


def cmd_submit(excel_file, sheet="Sheet2", photos_dir=None, student_class=None,
               subject_input_mode='names', auto_skip_submitted=True, last_submitted_regno=None,
               pause_callback=input, on_driver_ready=None, stop_event=None):
    """
    student_class : "11" or "12" -- used for every row, overriding each
                    row's own 'Class' column if present. If omitted, each
                    row's own 'Class' column is used.
    """
    frame = read_exam_dataframe(excel_file, sheet, student_class)
    candidates = frame[frame.apply(lambda row: not excluded_reason(row) and not submit_form._status_is_completed(row.get('Status', '')), axis=1)]
    if last_submitted_regno:
        boundary = submit_form._find_resume_after_index(frame, last_submitted_regno)
        indexes = list(frame.index)
        below = frame.loc[indexes[indexes.index(boundary) + 1:]]
        candidates = below[below.apply(lambda row: not excluded_reason(row), axis=1)] if not below.empty else below
    if candidates.empty:
        print('[SKIP] No pending eligible students. Browser was not opened.')
        return
    preview = submit_form.build_preflight(excel_file, sheet, photos_dir or '', student_class, subject_input_mode)
    active_registrations = set(candidates['RegNo'])
    blocking = [row for row in preview if row['regno'] in active_registrations and row['issues'] and any(not issue.startswith('Check optional subject on live page:') for issue in row['issues'].split('; '))]
    if blocking:
        raise ValueError('Offline preflight blocked the run. Review rows: ' + ', '.join(str(row['row']) + ': ' + row['issues'] for row in blocking[:10]))
    history = ExamRunHistory('Submit', excel_file, frame.to_dict('index'))
    driver = get_driver()
    if on_driver_ready:
        on_driver_ready(driver)
    try:
        login_and_enter_exam_section(driver)
        history.bind_account(driver)
        submit_form.run(
            driver,
            excel_file=excel_file,
            sheet_name=sheet,
            photos_dir=photos_dir,
            class_override=student_class,
            subject_input_mode=subject_input_mode,
            auto_skip_submitted=auto_skip_submitted,
            last_submitted_regno=last_submitted_regno,
            pause_callback=pause_callback,
            stop_event=stop_event,
            history=history,
        )
        history.finish('Stopped by operator' if stop_event and stop_event.is_set() else 'Run ended; review student results')
    except Exception as error:
        history.finish('Stopped - review required', str(error)[:1000])
        raise
    finally:
        try:
            driver.quit()
            print("[INFO] Browser closed.")
        except Exception:
            print("[INFO] Browser session was already closed/disconnected.")


def cmd_photos(reg_file, source_dir, destination_dir, rename_map_file=None,
               recursive=True, overwrite=False, stop_event=None):
    """Extract/copy photos locally by registration number; no browser needed."""
    return photo_copy.run(
        reg_file=reg_file, source_dir=source_dir, destination_dir=destination_dir,
        rename_map_file=rename_map_file, recursive=recursive, overwrite=overwrite,
        stop_event=stop_event,
    )


def cmd_internal(excel_file, sheet="Auto", student_class="11", session="", subject="Biology",
                 maximum="Auto", biology_component_max=None, school_account="", history_dir=None,
                 execute=False, confirm_session=False, confirm_callback=None, on_driver_ready=None,
                 stop_event=None, preview_only=False, plan=None, combine_biology=True,
                 subjects=None, all_subjects=False, jobs=None, report_session='Auto',automatic_submit=False):
    from jkbose_tool.features.internal_assessment import submission_issues
    from jkbose_tool.features.internal_assessment_batch import load_jobs, run_jobs
    if plan is not None:
        student_class,session=plan.student_class,plan.session
    jobs = jobs or ([{'subject':plan.subject,'plan':plan,'error':''}] if plan is not None else
                   load_jobs(excel_file,sheet,student_class,session,subjects or [subject],all_subjects,
                             maximum,biology_component_max,combine_biology))
    for job in jobs:
        selected=job['plan']
        if selected:
            print(f'[PREVIEW] Class {selected.student_class}, {selected.session}, {selected.subject}: '
                  f'{len(selected.awards)} awards; {sum(bool(submission_issues(a)) for a in selected.awards)} require manual handling.')
        else: print(f'[SOURCE BLOCKED] {job["subject"]}: {job["error"]}')
    if confirm_callback is None:
        confirm_callback = lambda prompt: input(prompt + "\nType SAVE to confirm: ").strip() == 'SAVE'
    return run_jobs(jobs,excel_file,history_dir,school_account,student_class=student_class,session=session,
                    execute=execute,preview_only=preview_only,confirm_session=confirm_session,
                    confirm_callback=confirm_callback,on_driver_ready=on_driver_ready,stop_event=stop_event,
                    driver_factory=get_driver,login_callback=login_only,report_session=report_session,verify_saved=True,automatic_submit=automatic_submit)


# ---------------------------------------------------------------------
# CLI (for direct / scripted use)
# ---------------------------------------------------------------------

def cmd_internal_approve(excel_file=None,sheet='Auto',student_class='11',session='',subjects=None,all_subjects=False,
                         school_account='',principal_account='',history_dir=None,execute=False,confirm_session=False,
                         report_session='Auto',jobs=None,confirm_callback=None,on_driver_ready=None,stop_event=None,approval_mode='excel',exclusions=None,on_progress=None):
    from jkbose_tool.features.internal_assessment_batch import load_jobs
    from jkbose_tool.features.internal_assessment_approval import run_approval,approval_confirmation_text
    if approval_mode=='excel':
        if not excel_file:raise ValueError('Choose the consolidated awards workbook for Excel approval mode.')
        jobs=jobs or load_jobs(excel_file,sheet,student_class,session,subjects,all_subjects or not subjects)
    else:jobs=[]
    if confirm_callback is None:
        def confirm_callback(data):
            for row in data['rows']:
                r=row['request'];print(r['subject'],r['regno'],r['exam_roll'],r['name'],r['marks']+'/'+r['maximum'],'READY' if row['eligible'] else '; '.join(row['reasons']))
            print(approval_confirmation_text(data))
            return input('Type APPROVE to confirm the irreversible software action: ').strip()=='APPROVE'
    return run_approval(jobs,excel_file,history_dir,school_account,principal_account,execute=execute,confirm_session=confirm_session,
                        report_session=report_session,confirm_callback=confirm_callback,on_driver_ready=on_driver_ready,stop_event=stop_event,
                        approval_mode=approval_mode,exclusions=exclusions,student_class=student_class,session=session,on_progress=on_progress)

def build_parser():
    parser = argparse.ArgumentParser(
        description="Automate tasks on jkbose.jk.gov.in"
    )
    sub = parser.add_subparsers(dest="command", required=False)

    p_shot = sub.add_parser(
        "screenshot",
        help="Look up each RR number and save a compressed screenshot of the result."
    )
    p_shot.add_argument("--rr-file", required=True, help="Text file, one RR number per line.")
    p_shot.add_argument("--output-dir", default=None, help="Defaults to the RR file's folder.")
    p_shot.add_argument("--format", choices=["png", "jpeg"], default=None,
                         help="Compression format (default: png, palette-quantized).")
    p_shot.add_argument("--jpeg-quality", type=int, default=None,
                         help="Only used with --format jpeg (default: 80).")
    p_shot.add_argument("--class", dest="student_class", choices=["11", "12"], default=None,
                         help="Class to select before each lookup (required by the site's "
                              "Class dropdown before entering the registration number).")
    p_shot.add_argument("--stream-map", default=None,
                         help="Which serial numbers (RR file line numbers) get which Stream, "
                              "before the subjects screenshot. Format: "
                              "'Science:1-40,45;Commerce:41-90;Humanities:91-120' "
                              "(semicolon-separated groups, each 'StreamValue:serial-spec').")
    p_shot.add_argument("--output-mode", choices=["screenshot", "pdf"], default="screenshot",
                         help="'screenshot' (default): image capture, per --capture-mode below. "
                              "'pdf': whole page in one shot via Chrome's Page.printToPDF -- "
                              "no scroll/stitch/compression needed, smaller files, vector text. "
                              "--format/--jpeg-quality/--capture-mode are ignored in pdf mode.")
    p_shot.add_argument("--capture-mode", choices=["top", "top_and_subjects"],
                         default="top_and_subjects",
                         help="Only used when --output-mode is 'screenshot'. "
                              "'top_and_subjects' (default): top of the page + a shot scrolled "
                              "to the SUBJECT DETAILS heading, stacked into one image -- slower "
                              "(one extra screenshot per student) but includes Subjects. "
                              "'top': just the top-of-page shot -- faster, skips Subjects.")

    p_submit = sub.add_parser(
        "submit",
        help="Fill exam forms row-by-row from an Excel sheet; you solve captcha + submit."
    )
    p_submit.add_argument("--excel-file", required=True, help="Path to the .xlsx workbook.")
    p_submit.add_argument("--sheet", default="Sheet2", help="Sheet name (default: Sheet2).")
    p_submit.add_argument("--photos-dir", default="",
                           help="Folder containing photo/signature files. Optional for Class 12 renewal.")
    p_submit.add_argument("--class", dest="student_class", choices=["11", "12"], default=None,
                           help="Class to use for every row, overriding each row's own "
                                "'Class' column if present.")
    p_submit.add_argument("--subject-input-mode", choices=["names", "codes"], default="names",
                           help="How Class 11 subjects are supplied: 'names' (default; sub1/sub2/...) "
                                "or 'codes' (legacy Group*_choice/SubjectCode* + VocationalCode).")
    p_submit.add_argument("--no-auto-skip-submitted", action="store_true",
                           help="Disable automatic skipping when JKBOSE explicitly says a record is already submitted/renewed.")
    p_submit.add_argument("--last-submitted-regno", default="",
                           help="Manual resume point: skip this exact RegNo and every row above it, then process every row below it.")

    p_inspect = sub.add_parser(
        "inspect",
        help="Log in, then dump every field's id/name/label on a page to a CSV "
             "(use this to find current field IDs after a site change)."
    )
    p_inspect.add_argument("--url", default=None,
                            help="Page to inspect. If omitted, click there yourself "
                                 "in the browser after logging in, then press ENTER.")
    p_inspect.add_argument("--output", default="fields.csv", help="CSV output path.")
    p_inspect.add_argument('--inspect-streams', action='store_true', help='Explicitly allow Stream dropdown postbacks while inspecting. Default inspection leaves controls unchanged.')

    p_browse = sub.add_parser(
        "browse",
        help="Log in and leave the browser open so you can browse the live JKBOSE "
             "site manually -- no automation runs."
    )
    p_browse.add_argument("--url", default=None,
                           help="Optional page to jump straight to after login.")

    p_photos = sub.add_parser(
        "photos", help="Copy photos whose filenames contain registration numbers; optionally rename by class roll."
    )
    p_photos.add_argument("--reg-file", required=True, help="Text file containing registration numbers, one per line.")
    p_photos.add_argument("--source-dir", required=True, help="Folder containing the large collection of student photos.")
    p_photos.add_argument("--destination-dir", required=True, help="Existing folder to copy selected photos into.")
    p_photos.add_argument("--rename-map-file", default=None, help="Optional text/CSV file with registration_no,class_roll pairs.")
    p_photos.add_argument("--no-recursive", action="store_true", help="Do not search subfolders inside the source folder.")
    p_photos.add_argument("--overwrite", action="store_true", help="Overwrite same-named files in destination (default adds _2, _3, ...).")

    p_internal = sub.add_parser("internal", help="Preview/check Internal Assessment awards; saving requires --execute and confirmation per batch.")
    p_internal.add_argument('--excel-file', required=True)
    p_internal.add_argument('--sheet', default='Auto')
    p_internal.add_argument('--class', dest='student_class', choices=['10', '11', '12'], required=True)
    p_internal.add_argument('--session', required=True)
    p_internal.add_argument('--report-session',default='Auto',help='Students report dropdown label. Auto uses the confirmed 2025-26 -> 2026-2027 mapping; never shifts other school years.')
    selection=p_internal.add_mutually_exclusive_group(required=True)
    selection.add_argument('--subject', help='One subject (legacy option).')
    selection.add_argument('--subjects', nargs='+', help='One or more quoted subject names/codes.')
    selection.add_argument('--all-subjects', action='store_true', help='All subjects present in this class/session workbook.')
    p_internal.add_argument('--maximum', default='Auto', help='Auto reads Excel maxima; numeric values support verified legacy workbooks.')
    p_internal.add_argument('--biology-component-max', default=None)
    p_internal.add_argument('--no-combine-biology', dest='combine_biology', action='store_false', help='Import a completed Biology total, or Botany/Zoology separately if offered by JKBOSE.')
    p_internal.add_argument('--school-account', default='')
    p_internal.add_argument('--history-dir', default=None)
    p_internal.add_argument('--confirm-session', action='store_true')
    p_internal.add_argument('--automatic-submit','--automatic-after-match',dest='automatic_submit', action='store_true', help='With --execute and --confirm-session, run complete preflight and submit eligible batches without repeated prompts. A separate Match is optional.')
    modes = p_internal.add_mutually_exclusive_group()
    modes.add_argument('--preview-only', action='store_true', help='Offline Excel validation and private report; no Chrome.')
    modes.add_argument('--execute', action='store_true', help='Allow Save only after complete batch validation and explicit confirmation.')

    p_approve=sub.add_parser('internal-approve',help='Principal approval: read-only by default; exact preview and --execute required for decisions.')
    p_approve.add_argument('--excel-file');p_approve.add_argument('--sheet',default='Auto')
    p_approve.add_argument('--class',dest='student_class',choices=['10','11','12'],required=True);p_approve.add_argument('--session',required=True)
    choose=p_approve.add_mutually_exclusive_group()
    choose.add_argument('--subjects',nargs='+');choose.add_argument('--all-subjects',action='store_true')
    p_approve.add_argument('--school-account',required=True);p_approve.add_argument('--principal-account',required=True)
    p_approve.add_argument('--history-dir',default=None);p_approve.add_argument('--report-session',default='Auto')
    p_approve.add_argument('--confirm-session',action='store_true');p_approve.add_argument('--execute',action='store_true')
    p_approve.add_argument('--approval-mode',choices=['excel','class_all','class_except'],default='excel')
    p_approve.add_argument('--exclude',action='append',default=[],help='Registration,exam-roll pair; repeat for multiple students in class_except mode.')
    return parser


# ---------------------------------------------------------------------
# Interactive dashboard -- shown when you run `python main.py` with no
# arguments. This is a menu for *this tool*, not a JKBOSE site page.
# ---------------------------------------------------------------------

def _prompt(label, default=None, required=False):
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"{label}{suffix}: ").strip().strip('"')
        if not val and default is not None:
            return default
        if not val and required:
            print("  This is required.")
            continue
        return val


def _session_status_line():
    profile_dir = Path(config.CHROME_PROFILE_DIR) if config.CHROME_PROFILE_DIR else None
    if profile_dir and profile_dir.exists():
        return "Saved login session: found (you likely won't need to log in again)"
    return "Saved login session: none yet (you'll need to log in on first use)"


def interactive_menu():
    while True:
        print()
        print("=" * 56)
        print(" JKBOSE Automation Tool -- Dashboard")
        print("=" * 56)
        print(f" Site:   {config.LOGIN_URL}")
        print(f" {_session_status_line()}")
        print(" Tip: 'python gui_main.py' opens a desktop GUI instead.")
        print("-" * 56)
        print(" 1) Check students / save screenshots")
        print(" 2) Submit exam forms (from Excel)")
        print(" 3) Inspect a page (find current field IDs)")
        print(" 4) Browse the live site manually")
        print(" 5) Extract / rename student photos")
        print(" 6) Help / where to look if something breaks")
        print(" 7) Internal Assessment awards (preview/check/save)")
        print(" 0) Exit")
        print("-" * 56)
        choice = input("Select an option: ").strip()

        if choice == "1":
            rr_file = _prompt("Path to RR numbers text file", required=True)
            student_class = _prompt("Class: 11 or 12", default="12")
            stream_spec = _prompt(
                "Stream map (blank = don't touch Stream). Format: "
                "Science:1-40,45;Commerce:41-90", default=""
            )
            stream_map = parse_stream_map_string(stream_spec) if stream_spec else None
            output_mode = _prompt("Output: screenshot or pdf", default="screenshot").lower()
            output_dir = _prompt("Output folder (blank = same folder as RR file)", default="") or None
            fmt = None
            jpeg_quality = None
            capture_mode = "top_and_subjects"
            if output_mode != "pdf":
                capture_mode = _prompt(
                    "Capture: 'top' (faster) or 'top_and_subjects' (includes Subjects)",
                    default="top_and_subjects"
                ).lower()
                fmt = _prompt("Format: png or jpeg", default="png").lower()
                if fmt == "jpeg":
                    jq = _prompt("JPEG quality (1-100)", default="80")
                    jpeg_quality = int(jq) if jq.isdigit() else None
            cmd_screenshot(rr_file, output_dir=output_dir, fmt=fmt, jpeg_quality=jpeg_quality,
                            student_class=student_class, stream_map=stream_map,
                            output_mode=output_mode, capture_mode=capture_mode)

        elif choice == "2":
            excel_file = _prompt("Path to the Excel (.xlsx) file", required=True)
            sheet = _prompt("Sheet name", default="Sheet2")
            photos_dir = _prompt("Folder with photos/signatures", required=True)
            student_class = _prompt(
                "Class: 11 or 12 (blank = use each row's own 'Class' column)", default=""
            ) or None
            subject_input_mode = _prompt(
                "Class 11 subject input: names or codes", default="names"
            ).lower()
            if subject_input_mode not in {"names", "codes"}:
                subject_input_mode = "names"
            cmd_submit(excel_file, sheet=sheet, photos_dir=photos_dir, student_class=student_class,
                       subject_input_mode=subject_input_mode)

        elif choice == "3":
            output = _prompt("Output CSV path", default="fields.csv")
            url = _prompt("URL to inspect (blank = navigate manually)", default="") or None
            cmd_inspect(url=url, output=output)

        elif choice == "4":
            url = _prompt("URL to open (blank = default landing page)", default="") or None
            cmd_browse(url=url)

        elif choice == "5":
            reg_file = _prompt("Registration numbers text file", required=True)
            source_dir = _prompt("Source folder containing all student photos", required=True)
            destination_dir = _prompt("Existing destination folder", required=True)
            rename_map_file = _prompt("Rename map file regno,class-roll (blank = keep names)", default="") or None
            recursive = _prompt("Search source subfolders? yes/no", default="yes").lower() not in {"n", "no", "0", "false"}
            overwrite = _prompt("Overwrite same-named destination files? yes/no", default="no").lower() in {"y", "yes", "1", "true"}
            cmd_photos(reg_file, source_dir, destination_dir, rename_map_file, recursive, overwrite)

        elif choice == "6":
            print()
            print("If screenshot/submit start failing with 'element not found' errors,")
            print("or a form's fields visibly changed on screen, the site's field IDs")
            print("probably changed. Steps:")
            print("  1. Run option 3 (Inspect) on the affected page -> get a fresh CSV.")
            print("  2. Compare it to an older CSV dump to see what changed.")
            print("  3. Update the IDs in jkbose_tool/config.py (FIELD_MAP etc).")
            print("  Full details are in README.md, section")
            print("  'If the site's fields change in the future'.")
            print()
            print("If things feel slow: fields not present on the current page are now")
            print("skipped quickly (config.QUICK_WAIT) instead of waiting the full")
            print("config.ELEMENT_WAIT (25s) each -- if it's still slow, check your")
            print("network/Chrome startup time, not the field-fill logic.")

        elif choice == "7":
            cmd_internal(
                _prompt('Awards Excel path', required=True),
                sheet=_prompt('Worksheet', default='Auto'),
                student_class=_prompt('Class: 10, 11 or 12', required=True),
                session=_prompt('Session YYYY-YY', required=True),
                subject=_prompt('JKBOSE subject', required=True),
                maximum=_prompt('Subject maximum (Auto reads Excel)', default='Auto'),
                biology_component_max=_prompt('Each Botany/Zoology maximum (blank for other subjects)', default='') or None,
                preview_only=True)
            print('Offline preview complete. Use the GUI Internal Assessment section for the read-only site check and confirmed saving.')

        elif choice == "0":
            print("Goodbye.")
            break

        else:
            print("Not a valid option, try again.")


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    args = build_parser().parse_args()

    if args.command is None:
        interactive_menu()
        return
    elif args.command == "inspect":
        cmd_inspect(url=args.url, output=args.output, inspect_streams=args.inspect_streams)
    elif args.command == "browse":
        cmd_browse(url=args.url)
    elif args.command == "screenshot":
        stream_map = parse_stream_map_string(args.stream_map) if args.stream_map else None
        cmd_screenshot(args.rr_file, output_dir=args.output_dir,
                        fmt=args.format, jpeg_quality=args.jpeg_quality,
                        student_class=args.student_class, stream_map=stream_map,
                        output_mode=args.output_mode, capture_mode=args.capture_mode)
    elif args.command == "submit":
        cmd_submit(args.excel_file, sheet=args.sheet, photos_dir=args.photos_dir,
                   student_class=args.student_class, subject_input_mode=args.subject_input_mode,
                   auto_skip_submitted=not args.no_auto_skip_submitted,
                   last_submitted_regno=args.last_submitted_regno or None)
    elif args.command == "internal":
        cmd_internal(args.excel_file, args.sheet, args.student_class, args.session, args.subject,
                     args.maximum, args.biology_component_max, args.school_account, args.history_dir,
                     execute=args.execute, confirm_session=args.confirm_session, preview_only=args.preview_only,
                     combine_biology=args.combine_biology,subjects=args.subjects,all_subjects=args.all_subjects,report_session=args.report_session,
                     automatic_submit=args.automatic_submit)
    elif args.command == 'internal-approve':
        cmd_internal_approve(args.excel_file,sheet=args.sheet,student_class=args.student_class,session=args.session,subjects=args.subjects,
                             all_subjects=args.all_subjects,school_account=args.school_account,principal_account=args.principal_account,
                             history_dir=args.history_dir,execute=args.execute,confirm_session=args.confirm_session,report_session=args.report_session,
                             approval_mode=args.approval_mode,exclusions=args.exclude)
    elif args.command == "photos":
        cmd_photos(args.reg_file, args.source_dir, args.destination_dir,
                   rename_map_file=args.rename_map_file, recursive=not args.no_recursive,
                   overwrite=args.overwrite)


if __name__ == "__main__":
    sys.exit(main())
