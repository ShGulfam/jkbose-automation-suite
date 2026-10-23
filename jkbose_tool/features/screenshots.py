"""
Feature: "check student" -- for each RR number in a text file, enter it on
the registration-details page, click 'Get Details', then capture either
just the top of the fetched details, or the top PLUS a shot scrolled to
the Subjects section (stacked into one image), depending on capture_mode.

Was: rr_screenshots.py
"""
from pathlib import Path
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from .. import config
from .exam_input import load_check_inputs
from .exam_guard import require_exam_form, require_lookup_details, ExamPortalUnavailable
from ..browser import page_change_token, wait_for_postback, wait_until_page_stable, scroll_to_text
from ..utils import (sanitize_filename, read_lines, compress_screenshot,
                      stack_images_vertically, save_page_as_pdf)


def _ensure_class_selected(driver, wait, desired_class):
    """
    Sets the Class dropdown to desired_class ONLY if it isn't already set
    that way. This matters a lot in practice: selecting an option that's
    already selected fires no browser 'change' event, so a naive
    select-then-wait_for_postback ends up blocking for the full
    PAGE_CHANGE_TIMEOUT (20s) doing nothing -- once per RR number, since
    the dropdown's value typically survives the 'Get Details' postback.
    Checking first turns that into a near-instant no-op on every repeat
    lookup within the same class.
    """
    sel_elem = wait.until(EC.presence_of_element_located((By.ID, config.CLASS_SELECT_ID)))
    sel_class = Select(sel_elem)
    try:
        current = sel_class.first_selected_option.get_attribute("value")
    except Exception:
        current = None
    if current == str(desired_class):
        return  # already correct -- nothing to click, nothing to wait for

    before = page_change_token(driver)
    try:
        sel_class.select_by_value(str(desired_class))
    except Exception:
        sel_class.select_by_visible_text(str(desired_class))
    wait_for_postback(driver, before)
    print(f"[INFO] Class set to {desired_class}")


def _ensure_stream_selected(driver, wait, desired_stream):
    """
    Sets the Stream dropdown to desired_stream, unless it's already set
    that way. Unlike Class, changing Stream is expected to genuinely
    change the page (different subjects), so this always waits for the
    postback when a change actually happens -- the "skip if already
    correct" check just avoids that wait on consecutive RR numbers that
    share the same stream (common when using serial-number ranges).

    Returns True if a change was actually made (caller should then also
    wait_until_page_stable() for the subjects grid to catch up), False if
    it was already correct (nothing to settle).
    """
    sel_elem = wait.until(EC.presence_of_element_located((By.ID, config.STREAM_SELECT_ID)))
    sel_stream = Select(sel_elem)
    try:
        current = sel_stream.first_selected_option.get_attribute("value")
    except Exception:
        current = None
    if current == str(desired_stream):
        return False

    before = page_change_token(driver)
    try:
        sel_stream.select_by_value(str(desired_stream))
    except Exception:
        sel_stream.select_by_visible_text(str(desired_stream))
    wait_for_postback(driver, before)
    print(f"[INFO] Stream set to {desired_stream}")
    return True


def run(driver, rr_file: str, output_dir: str = None,
        screenshot_format: str = None, jpeg_quality: int = None,
        student_class: str = None, stream_map: dict = None, stop_event=None,
        output_mode: str = "screenshot", capture_mode: str = "top_and_subjects", history=None):
    """
    driver         : an already-logged-in Selenium driver, already inside the
                     Exam/RR section (see browser.login_and_enter_exam_section).
    rr_file        : path to a text file with one RR number per line.
    output_dir     : where files are saved. Defaults to rr_file's folder.
    student_class  : "11" or "12" (or whatever the site's Class dropdown
                     expects). If given, the Class dropdown is checked/set
                     before every lookup (cheaply -- see _ensure_class_selected),
                     since the site requires it be selected before entering
                     the registration number.
    stream_map     : optional {serial_number: stream_value} dict, where
                     serial_number is the RR file's 1-indexed line number
                     (matches the output filename's leading number). Build
                     one with jkbose_tool.utils.build_stream_map() or
                     parse_stream_map_string(). If a serial number isn't
                     in the map, its Stream is left as whatever's already
                     selected on the page (a warning is logged).
    stop_event     : optional threading.Event, checked between RR numbers so
                     a caller (e.g. a GUI Stop button) can end the batch
                     early without killing the process.
    output_mode    : "screenshot" (default) or "pdf" (whole page via
                     Chrome's Page.printToPDF -- capture_mode is ignored
                     in this mode, since printToPDF already gets everything).
    capture_mode   : (screenshot mode only)
                     "top_and_subjects" (default) -- two shots, the top of
                     the details plus a shot scrolled to the "SUBJECT
                     DETAILS" heading, stacked into one image. Slower (one
                     extra screenshot + scroll per student) but includes
                     Subjects.
                     "top" -- just the top-of-page shot. Faster (skips the
                     scroll, second screenshot, and stacking entirely) --
                     use this if you don't need Subjects in the image, or
                     are capturing it a different way (e.g. PDF mode).
    """
    rr_file = Path(rr_file)
    output_dir = Path(output_dir) if output_dir else rr_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_mode = (output_mode or "screenshot").lower()
    capture_mode = (capture_mode or "top_and_subjects").lower()

    wait = WebDriverWait(driver, config.ELEMENT_WAIT)
    # keep_blanks=True: a blank line still consumes a serial number, so
    # line-number-based stream_map entries and output filenames stay
    # aligned with the file's real line numbers even if it has gaps.
    input_rows = load_check_inputs(rr_file, student_class)
    rrs = [row['RegNo'] for row in input_rows]
    non_blank = sum(1 for r in rrs if r)
    print(f"[INFO] {len(rrs)} lines loaded from {rr_file} ({non_blank} RR numbers, "
          f"{len(rrs) - non_blank} blank lines skipped but still counted)")
    print(f"[INFO] Output mode: {output_mode}"
          + (f", capture mode: {capture_mode}" if output_mode == "screenshot" else ""))
    if student_class:
        print(f"[INFO] Class will be kept set to '{student_class}' (only re-selected if it changes)")
    if stream_map:
        print(f"[INFO] Stream map covers {len(stream_map)} of {len(rrs)} serial numbers")

    results = []
    for idx, rr in enumerate(rrs, start=1):
        if stop_event is not None and stop_event.is_set():
            print("[INFO] Stop requested -- ending batch before the next RR number.")
            break

        if not rr:
            print(f"[{idx}/{len(rrs)}] Skipping blank line (serial #{idx} still counted)")
            results.append(("", "", "blank line"))
            continue

        source_row = input_rows[idx - 1]
        if source_row.get('_skip_reason'):
            results.append((rr, '', source_row['_skip_reason']))
            if history: history.record('check_result', registration=rr, status=source_row['_skip_reason'])
            print(f"[SKIP] {rr}: {source_row['_skip_reason']}")
            continue

        clean_name = sanitize_filename(rr)
        raw_path = output_dir / f"{idx}_{clean_name}_raw.png"
        try:
            print(f"[{idx}/{len(rrs)}] Processing RR: {rr}")
            if history: history.bind_account(driver)
            require_exam_form(driver)
            _ensure_class_selected(driver, wait, source_row['Class'])
            require_exam_form(driver, source_row['Class'])

            reg_input = wait.until(EC.presence_of_element_located((By.ID, "bodypH_txt_rege")))
            reg_input.clear()
            reg_input.send_keys(rr)

            before = page_change_token(driver)
            get_btn = driver.find_element(By.ID, config.GET_DETAILS_BTN_ID)
            get_btn.click()
            if not wait_for_postback(driver, before):
                raise ExamPortalUnavailable('Get Details response was not confirmed; no screenshot was accepted.')
            require_lookup_details(driver, rr, source_row)
            # Only wait for delayed/secondary content when the requested
            # output actually needs it. Top-only capture does not depend on
            # the Subjects grid, so paying this stability wait per student is
            # unnecessary.
            needs_subjects_settle = (output_mode == "pdf" or
                                     capture_mode == "top_and_subjects" or
                                     stream_map is not None)
            if needs_subjects_settle:
                wait_until_page_stable(driver)

            # ---------- Stream must be set BEFORE the subjects show up ----------
            if stream_map is not None:
                desired_stream = stream_map.get(idx)
                if desired_stream:
                    try:
                        changed = _ensure_stream_selected(driver, wait, desired_stream)
                        if changed:
                            wait_until_page_stable(driver)  # let subjects catch up to the new Stream
                    except Exception as e:
                        raise ExamPortalUnavailable(f'Stream selection failed: {e}') from e
                else:
                    print(f"[WARN] Serial #{idx} not covered by the stream map -- "
                          f"leaving Stream as-is.")

            if output_mode == "pdf":
                # ---------- One shot: whole page, native PDF ----------
                pdf_path = output_dir / f"{idx}_{clean_name}.pdf"
                save_page_as_pdf(driver, pdf_path)
                print(f"[OK] Saved: {pdf_path} ({pdf_path.stat().st_size / 1024:.1f} KB)")
                results.append((rr, str(pdf_path), "ok"))

            elif capture_mode == "top":
                # ---------- One shot: top of the fetched details only ----------
                driver.save_screenshot(str(raw_path))
                final_path = compress_screenshot(
                    raw_path, fmt=screenshot_format, jpeg_quality=jpeg_quality
                )
                print(f"[OK] Saved: {final_path} "
                      f"({final_path.stat().st_size / 1024:.1f} KB)")
                results.append((rr, str(final_path), "ok"))

            else:
                # ---------- Two shots, combined into one image ----------
                # Shot 1: top of the fetched details, as-loaded.
                # Shot 2: scrolled to the "SUBJECT DETAILS" heading -- NOT
                # the document's bottom, since how much content sits below
                # Subjects (photo/signature/captcha, extra stream-specific
                # fields) varies per student; scrolling to the literal
                # bottom would scroll PAST Subjects for exactly the
                # students with more content below it, leaving it out of
                # the shot. Falls back to document-bottom only if the
                # heading text can't be found at all.
                top_path = output_dir / f"{idx}_{clean_name}_top.png"
                bottom_path = output_dir / f"{idx}_{clean_name}_bottom.png"

                driver.save_screenshot(str(top_path))

                found = scroll_to_text(driver, "SUBJECT DETAILS", block="start")
                if not found:
                    print("[WARN] 'SUBJECT DETAILS' heading not found -- "
                          "falling back to scrolling to the page bottom.")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.3)  # let the scroll/repaint settle before capturing
                driver.save_screenshot(str(bottom_path))
                driver.execute_script("window.scrollTo(0, 0);")  # reset for the next RR number

                stack_images_vertically([top_path, bottom_path], raw_path)
                for p in (top_path, bottom_path):
                    try:
                        p.unlink()
                    except Exception:
                        pass

                final_path = compress_screenshot(
                    raw_path, fmt=screenshot_format, jpeg_quality=jpeg_quality
                )
                print(f"[OK] Saved: {final_path} "
                      f"({final_path.stat().st_size / 1024:.1f} KB)")
                results.append((rr, str(final_path), "ok"))

            try:
                driver.find_element(By.ID, "bodypH_txt_rege").clear()
            except Exception:
                pass

        except ExamPortalUnavailable as e:
            results.append((rr, '', f'blocked: {e}'))
            print(f'[STOP] {e}')
            break
        except Exception as e:
            print(f"[ERROR] Failed processing RR {rr}: {e}")
            results.append((rr, "", f"error: {e}"))
            continue
        finally:
            if history and results and results[-1][0] == rr:
                history.record('check_result', registration=rr, file=results[-1][1], status=results[-1][2])
                history.report()

    print("[DONE] All RR numbers processed.")
    return results
