"""Selenium adapter. Reads/preview are default; each saved batch needs confirmation."""
import hashlib
import json
import time
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse, urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import NoAlertPresentException
from ..browser import page_change_token, wait_for_postback, safe_click
from .internal_assessment_postback import ReadPostback, begin_read as _begin_read, wait_read
from .internal_assessment import Audit, RunLock, match_batch, number, verify_transition, class_key, subject_name, live_maximum, rejected_correction

URL = 'https://jkbose.jk.gov.in/utilities/auth_pages/practicalMarks.aspx'

# Excludes auth fields, cookies, storage, ViewState and full HTML. Only the
# dedicated assessment maximum is read from a hidden field.
SNAPSHOT = r"""
const body = document.body.innerText;
const headers = [...document.querySelectorAll('span,div,p,strong,h1,h2,h3,h4')]
  .map(x => x.innerText.trim()).filter(x => x.length < 500);
const header = document.getElementById('bodypH_lblInfo')?.innerText.trim()
  || headers.find(x => /Class:\s*(10|11|12)\s*\|\s*Subject:/i.test(x)) || '';
const total = /Total Records:\s*(\d+)/i.exec(header);
const cls = /Class:\s*(10|11|12)/i.exec(header);
const subject = /Subject:\s*([^|]+)/i.exec(header);
const page = /Page\s+(\d+)\s+of\s+(\d+)/i.exec(header);
const maximum = /Max Marks:\s*(\d+(?:\.\d+)?)/i.exec(header);
const grid = document.getElementById('bodypH_gridStudents');
const gridHeaders = [...(grid?.querySelectorAll(':scope > tbody > tr > th, :scope > thead > tr > th') || [])].map(x => x.innerText.trim());
const rows = [...document.querySelectorAll('input[id*="gridStudents_txtMarks"]')].map(input => {
  const tr = input.closest('tr'), cells = [...tr.cells];
  const checked = tr.querySelector('.att-rbl input:checked');
  return {regno: cells[2]?.innerText.trim() || '', name: cells[3]?.innerText.trim() || '',
    exam_roll: cells[1]?.innerText.trim() || '', subject: cells[4]?.innerText.trim() || '',
    input_id: input.id, value: input.value, max: input.max, min: input.min, step: input.step,
    disabled: input.disabled, readonly: input.readOnly, attendance: checked?.value || '',
    attendance_count: tr.querySelectorAll('.att-rbl input:checked').length,
    absent_input_id: tr.querySelector('.att-rbl input[value="A"]')?.id || '',
    absent_enabled: !!tr.querySelector('.att-rbl input[value="A"]:not(:disabled)'),
    present_input_id: tr.querySelector('.att-rbl input[value="P"]')?.id || '',
    present_enabled: !!tr.querySelector('.att-rbl input[value="P"]:not(:disabled)')};
});
const account = /Hello\s+([a-z0-9_-]+)/i.exec(body);
const save = document.getElementById('bodypH_btnSaveMarks');
return {header, total: total ? Number(total[1]) : null,
  class: cls?.[1] || '', subject: subject?.[1].trim() || '',
  page: page ? Number(page[1]) : null, pages: page ? Number(page[2]) : null,
  account: account?.[1] || '', rows, save_enabled: !!save && !save.disabled && ['Submit & Next','Submit'].includes(save.value),
  layout_valid: JSON.stringify(gridHeaders) === JSON.stringify(['Sr.', 'Roll No.', 'Registration No.', 'Name', 'Subject', 'Marks', 'Present / Absent']),
  selected_class: document.getElementById('bodypH_ddlClass')?.value || '',
  selected_subject: document.getElementById('bodypH_ddlSubject')?.value || '',
  available_subjects: [...(document.getElementById('bodypH_ddlSubject')?.options || [])].map(o=>({value:o.value,label:o.text.trim()})).filter(o=>o.value && !/^select/i.test(o.label)),
  maximum: maximum?.[1] || '', hidden_maximum: document.getElementById('bodypH_hfMaxMarks')?.value || ''};
"""

class AssessmentStopped(RuntimeError): pass
class UncertainSubmissionError(ValueError): pass
class ChangedSavedAwardError(ValueError): pass

def _stop(stop_event):
    if stop_event is not None and stop_event.is_set(): raise AssessmentStopped('Stopped; no further awards will be entered or submitted.')

def _clean_url(u):
    if isinstance(u, bytes):
        return u.decode('utf-8', errors='replace')
    return str(u or '')

def _url(driver):
    curr = _clean_url(driver.current_url)
    parsed = urlparse(curr)
    scheme = _clean_url(parsed.scheme).lower()
    hostname = _clean_url(parsed.hostname).lower()
    path = _clean_url(parsed.path).lower()
    if scheme != 'https' or hostname != 'jkbose.jk.gov.in' or path != '/utilities/auth_pages/practicalmarks.aspx':
        raise ValueError(f'Internal Assessment did not open (current path: {path}). Use the signed-in Internal Assessment sidebar link; check login/access. No awards were submitted.')

def snapshot(driver, plan, school_account, require_first=True):
    _url(driver)
    state = driver.execute_script(SNAPSHOT)
    if not school_account or state['account'].lower() != school_account.lower():
        raise ValueError('The signed-in JKBOSE school account differs from the approved account.')
    if state['total'] is None or state['class'] != plan.student_class or subject_name(state['subject']) != plan.subject:
        raise ValueError('Cannot verify the displayed class, subject and pending count.')
    if state['total'] < len(state['rows']) or len(state['rows']) > 100:
        raise ValueError('Unexpected pending count or grid size; stop for inspection.')
    if state['total'] > 0 and not state['rows']: raise ValueError('Pending students exist but the grid is not readable.')
    if require_first and state['total'] > 0 and state.get('page') != 1:
        raise ValueError('JKBOSE did not return the first pending page. Stop rather than skip students.')
    if state['rows'] and not state['save_enabled']: raise ValueError('Marks submission is disabled.')
    if state['rows'] and not state.get('layout_valid', True): raise ValueError('JKBOSE student-grid columns changed; inspect before proceeding.')
    if 'selected_class' in state and (state['selected_class'] != plan.student_class or subject_name(state['selected_subject']) != plan.subject):
        raise ValueError('Selected class/subject do not match the approved preview.')
    if state['rows']: live_maximum(state)
    return state

def _wait_page(driver, before, stop_event):
    # This helper waits only; it never retries a click, especially a Save.
    if isinstance(before, ReadPostback):
        return wait_read(driver, before, lambda: _stop(stop_event))
    if not wait_for_postback(driver, before, timeout=30):
        raise ValueError('No confirmed postback. Stop rather than acting on a stale page.')
    _stop(stop_event)
    WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete')

def open_subject(driver, plan, stop_event):
    _stop(stop_event)
    # Use the authenticated sidebar navigation (including ASP.NET session context).
    # Never accept a dashboard/login redirect as a successful marks-page load.
    curr_url = _clean_url(driver.current_url)
    links = []
    for link in driver.find_elements(By.CSS_SELECTOR, 'a[href]'):
        raw_href = _clean_url(link.get_attribute('href') or '')
        destination = urlparse(urljoin(curr_url, raw_href))
        dest_scheme = _clean_url(destination.scheme).lower()
        dest_host = _clean_url(destination.hostname).lower()
        dest_path = _clean_url(destination.path).lower()
        if (dest_scheme == 'https' and dest_host == 'jkbose.jk.gov.in'
                and dest_path == '/utilities/auth_pages/practicalmarks.aspx'
                and link.is_displayed() and link.is_enabled()):
            links.append(link)
    if len(links) > 1: raise ValueError('Multiple Internal Assessment navigation links; inspect the site before proceeding.')
    if _clean_url(urlparse(curr_url).path).lower() == '/utilities/auth_pages/practicalmarks.aspx': pass
    elif links: safe_click(driver, links[0])  # Read-only navigation; handles a collapsed/off-screen sidebar.
    else: driver.get(URL)
    WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete')
    _url(driver)
    dropdown = WebDriverWait(driver, 20).until(lambda d: d.find_element(By.ID, 'bodypH_ddlClass'))
    if Select(dropdown).first_selected_option.get_attribute('value') != plan.student_class:
        before = _begin_read(driver, 'bodypH_ddlClass', 'Internal Assessment class selection')
        Select(dropdown).select_by_value(plan.student_class); _wait_page(driver, before, stop_event)
    dropdown = WebDriverWait(driver, 20).until(lambda d: d.find_element(By.ID, 'bodypH_ddlSubject'))
    options = [option.get_attribute('value') for option in Select(dropdown).options
               if subject_name(option.get_attribute('value')) == plan.subject]
    if len(options) != 1: raise ValueError('The selected subject is missing or ambiguous on JKBOSE for this class.')
    if Select(dropdown).first_selected_option.get_attribute('value') != options[0]:
        before = _begin_read(driver, 'bodypH_ddlSubject', 'Internal Assessment subject selection')
        Select(dropdown).select_by_value(options[0])
        _wait_page(driver, before, stop_event)
    show_students(driver, stop_event)

def show_students(driver, stop_event):
    _stop(stop_event); _url(driver)
    before = _begin_read(driver, 'bodypH_btnShow', 'Show Students')
    driver.find_element(By.ID, 'bodypH_btnShow').click()
    _wait_page(driver, before, stop_event)

def _evidence(driver, audit, label, state):
    name = f'{time.time_ns()}-{label}'
    (audit.folder / f'{name}.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    try:
        if not driver.save_screenshot(str(audit.folder / f'{name}.png')): raise ValueError('Screenshot capture failed.')
    except Exception:
        # Structured row evidence remains mandatory even if Chrome cannot capture a screenshot.
        audit.append('screenshot_unavailable', evidence=name)
    return name

def _receipt_history(root, plan, school_account=None):
    """Scope/hash-check every journal and order receipts across changed sources."""
    from datetime import datetime
    from .internal_assessment import saved_outcomes
    from .internal_assessment_history import manifest_paths
    ordered=[];folders={}
    for manifest_path in manifest_paths(root):
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if any(manifest.get(k)!=plan.manifest().get(k) for k in ['student_class','session','subject']):continue
        event_file=manifest_path.parent/'events.jsonl'
        if not event_file.exists():continue
        previous='0'*64;events=[]
        for line in event_file.read_text(encoding='utf-8').splitlines():
            event=json.loads(line);signature=event.pop('hash')
            if event.get('previous')!=previous or Audit._hash(event)!=signature:raise ValueError('Related audit history is incomplete or changed. Reconcile manually.')
            event['hash']=signature;previous=signature;events.append(event)
        accounts={e['school_account'].lower() for e in events if e['kind']=='run_started' and e.get('school_account')}
        if school_account and accounts and school_account.lower() not in accounts:
            foreign=saved_outcomes(events)
            if any(reg in {a.regno for a in plan.awards} and e['kind']!='portal_award_rejected' for reg,e in foreign.items()):raise ValueError('Saved history belongs to another school account; reconcile before resuming.')
            continue
        meaningful=any(e['kind'] in {'verified_saved','portal_award_rejected','manual_reconciliation','official_recorded_award'} for e in events)
        if meaningful and school_account and accounts!={school_account.lower()}:raise ValueError('Saved history has no unambiguous school account. Reconcile before resuming.')
        attempts={e['batch_id'] for e in events if e['kind']=='submit_attempt'}
        settled={e['batch_id'] for e in events if e['kind'] in {'verified_saved','manual_reconciliation'}}
        if attempts-settled:raise UncertainSubmissionError(f'An uncertain submission exists in {manifest_path.parent}. Official saved-report verification or manual reconciliation is required before any further submission.')
        for index,e in enumerate(events):
            if e['kind'] not in {'verified_saved','portal_award_rejected','manual_reconciliation','official_recorded_award'}:continue
            timestamp=datetime.fromisoformat(e['time'].replace('Z','+00:00'))
            if timestamp.tzinfo is None:raise ValueError('Receipt timestamp has no timezone; reconcile history.')
            ordered.append((timestamp.timestamp(),str(manifest_path.parent),index,e));folders[e['hash']]=manifest_path.parent
    ordered.sort(key=lambda item:item[:3])
    outcomes=saved_outcomes([item[3] for item in ordered])
    return {reg:(folders[e['hash']],e) for reg,e in outcomes.items()}


def _pending_history(root, plan, school_account=None):
    return {reg for reg,(_,event) in _receipt_history(root,plan,school_account).items() if event['kind']!='portal_award_rejected'}


def _fill(driver, plan, before, awards, school_account, stop_event):
    # Validate the full page before touching any input.
    _,problems=match_batch(plan,before,allow_absent=True)
    if problems: raise ValueError('Registration/exam-roll pair or award validation failed before filling.')
    mapping = {(award.regno,award.exam_roll): award for award in awards}
    for row in before['rows']:
        _stop(stop_event)
        element = driver.find_element(By.ID, row['input_id'])
        award=mapping[(row['regno'],row['exam_roll'])]
        if award.attendance == 'A':
            if row.get('value') not in ('',None,'0','0.0') and rejected_correction(plan,award,row):element.clear()
            if row['attendance'] != 'A':
                radio=driver.find_element(By.ID,row['absent_input_id'])
                if not radio.is_enabled() or radio.get_attribute('value')!='A': raise ValueError('Absent control is unavailable; no save.')
                radio.click()
            continue
        if row['attendance']!='P':
            if not rejected_correction(plan,award,row):raise ValueError('Present attendance correction lacks an exact rejected receipt.')
            radio=driver.find_element(By.ID,row['present_input_id'])
            if not radio.is_enabled() or radio.get_attribute('value')!='P':raise ValueError('Present control is unavailable; no save.')
            radio.click();element=driver.find_element(By.ID,row['input_id'])
        if element.get_attribute('value') != award.marks:
            element.clear(); element.send_keys(award.marks)
    after = snapshot(driver, plan, school_account)
    if after['total'] != before['total'] or [r['regno'] for r in after['rows']] != [r['regno'] for r in before['rows']]:
        raise ValueError('Student grid changed while filling; nothing will be submitted.')
    _, problems = match_batch(plan, after,allow_absent=True)
    if problems: raise ValueError('Read-back validation failed; batch was not submitted.')
    for row in after['rows']:
        award=mapping[(row['regno'],row['exam_roll'])]
        if row['attendance'] != award.attendance or (row.get('value') not in ('',None,'0','0.0') if award.attendance=='A' else number(row['value']) != Decimal(award.marks)):
            raise ValueError('Filled marks/attendance do not exactly match the approved preview.')
    return after

def _record_resume(audit, prior):
    audit.append('history_resume',verified_registrations=sorted(prior['verified']),
                 manual_registrations=sorted(prior['manual']),proofs=prior['proofs'])


def skip_verified_subject(plan, history_root, school_account, prior):
    audit=Audit(history_root,plan)
    _record_resume(audit,prior)
    audit.append('subject_skipped_verified_history',school_account=school_account,
                 registrations=sorted(prior['verified']|prior['manual']),
                 meaning='Unchanged awards already have intact saved receipts; no navigation, filling or saving.')
    audit.report(plan)
    print(f'[SKIPPED] {plan.subject}: {len(plan.awards)} awards already verified in history.')
    return {'subject':plan.subject,'status':'skipped_verified_history','new_verified_count':0,
            'known_saved_count':len(prior['verified']|prior['manual']),'history':str(audit.folder)}


def run(driver, plan, history_root, school_account, confirm_callback, stop_event=None,
        submit=False, confirm_session=False, lock_held=False, absence_callback=None, interface_only=False, receipt_callback=None,
        automatic_submit=False,match_evidence=''):
    if not confirm_session: raise ValueError('Confirm the active JKBOSE examination session before opening this workflow.')
    if automatic_submit and not match_evidence:raise ValueError('Automatic submission requires complete report preflight evidence.')
    if not re_account(school_account): raise ValueError('Enter the exact JKBOSE school account shown after Hello.')
    if hashlib.sha256(Path(plan.source).read_bytes()).hexdigest() != plan.source_sha256:
        raise ValueError('Workbook changed after preview; reopen the preview.')
    with (nullcontext() if lock_held else RunLock(history_root)):
        from .internal_assessment_policy import source_absences,apply_holds,CohortAbsencePolicy
        raw_holds=source_absences(plan.source,plan.sheet)
        if not lock_held:
            local_policy=CohortAbsencePolicy(history_root,school_account,plan.student_class,plan.session)
            local_policy.add(raw_holds,origin='consolidated_source',evidence=plan.source_sha256)
            local_policy.reconcile_source(plan.source,plan.sheet,current_holds=raw_holds)
            previous_callback=absence_callback
            def direct_absence_callback(hold,evidence):
                local_policy.add([hold],origin='live_jkbose_read_only',evidence=evidence)
                if previous_callback: previous_callback(hold,evidence)
            absence_callback=direct_absence_callback
            apply_holds(plan,local_policy.holds)
        else: apply_holds(plan,raw_holds)
        from .internal_assessment_batch import verified_history
        prior = verified_history(history_root,plan,school_account)
        previously_saved = prior['verified']|prior['manual']
        audit = Audit(history_root, plan)
        if any(event['kind'] == 'run_started' and event.get('school_account') != school_account for event in audit.events):
            raise ValueError('This history belongs to another school account. Never reuse it across schools.')
        if audit.unresolved(): raise ValueError('An earlier submit attempt is uncertain; reconcile manually before resuming.')
        if submit and all(award.regno in previously_saved for award in plan.awards):
            return skip_verified_subject(plan,history_root,school_account,prior)
        _record_resume(audit,prior)
        initial_verified=audit.verified()
        result={'subject':plan.subject,'status':'running','new_verified_count':0,
                'known_saved_count':len(previously_saved),'history':str(audit.folder)}
        audit.append('run_started', mode='submit' if submit else 'read_only', school_account=school_account,
                     session_confirmation=True, source=plan.manifest(), source_preview=plan.rows())
        try:
            open_subject(driver, plan, stop_event)
            if not submit:
                from .internal_assessment_matching import scan_subject
                return scan_subject(driver,plan,audit,school_account,prior,stop_event,absence_callback,interface_only=interface_only)
            while True:
                _stop(stop_event)
                before = snapshot(driver, plan, school_account)
                evidence = _evidence(driver, audit, 'pending', before)
                # A newly exposed batch can contain an absence not visible during
                # the read-only preflight. Persist it before any fill/save and
                # retain the hold for every later subject/run.
                for row in before['rows']:
                    if row.get('attendance') == 'A' and not rejected_correction(plan,next((a for a in plan.awards if a.regno==row['regno']),None),row):
                        hold={'registration':row['regno'],'exam_roll':row.get('exam_roll',''),
                              'subject':plan.subject,'reason':'Marked absent on the live JKBOSE pending page'}
                        if absence_callback: absence_callback(hold,evidence)
                        apply_holds(plan,[hold])
                if before['total'] == 0:
                    result.update(status='pending_empty',pending_count=0)
                    audit.append('pending_queue_empty', verified_saved_count=len(audit.verified()),
                                 meaning='No pending rows; awards absent from the queue are not independently certified by this tool.')
                    print('[INFO] JKBOSE pending queue is empty. See the private report for source records not verified by this tool.')
                    break
                awards, problems = match_batch(plan, before, previously_saved | audit.verified() | audit.manual_saved(),allow_absent=True)
                official = live_maximum(before)
                audit.append('official_maximum_checked', maximum=str(official), pass_marks=str(official * Decimal('0.4')),
                             excel_maximum=plan.maximum, mismatch=official != Decimal(plan.maximum), evidence=evidence)
                audit.append('batch_preview', pending_count=before['total'], evidence=evidence,
                             registrations=[row['regno'] for row in before['rows']], awards=[vars(award) for award in awards], issues=problems)
                if problems:
                    eligible=[];blocked=[]
                    reg_counts={row['regno']:sum(other['regno']==row['regno'] for other in before['rows']) for row in before['rows']}
                    exam_counts={row.get('exam_roll',''):sum(other.get('exam_roll','')==row.get('exam_roll','') for other in before['rows']) for row in before['rows']}
                    for row in before['rows']:
                        _,row_issues=match_batch(plan,{**before,'rows':[row]},previously_saved|audit.verified()|audit.manual_saved(),allow_absent=True)
                        (blocked if row_issues or reg_counts[row['regno']]!=1 or exam_counts[row.get('exam_roll','')]!=1 else eligible).append(row['regno'])
                    result.update(status='manual_required',pending_count=before['total'],reason='; '.join(problems))
                    result.update(eligible_in_blocked_batch=len(eligible),blocked_in_batch=len(blocked))
                    audit.append('batch_blocked', reasons=problems, registrations=[row['regno'] for row in before['rows']],eligible_registrations=eligible,blocked_registrations=blocked,
                                 portal_constraint='JKBOSE validates every displayed Present row; no partial-save or independent next-page control is exposed.')
                    print(f'[BLOCKED] {len(eligible)} otherwise eligible and {len(blocked)} manual awards in this displayed batch. JKBOSE requires the whole displayed batch; it cannot skip the blocked row. No marks entered. Other selected subjects will continue.')
                    break
                if not submit:
                    result.update(status='checked_read_only',pending_count=before['total'])
                    audit.append('read_only_complete', scope='Currently displayed pending batch only; later pages were not scanned.')
                    print('[INFO] First pending batch checked. Read-only mode entered and submitted no marks.')
                    break
                preview = '\n'.join(f'Reg {award.regno} | Exam roll {award.exam_roll} | {award.name} | {award.marks or 'AB'}/{official} | {award.attendance}' for award in awards)
                prompt = (f'CONFIRM SAVE — school {school_account}\nClass {plan.student_class}, session {plan.session}, {plan.subject}\n'
                          f'Official JKBOSE pass threshold: {official * Decimal("0.4")}/{official} (40%)\nPending: {before["total"]}\n\n{preview}\n\n'
                          'Save exactly this displayed batch? Explicit absences will be submitted as Absent and excluded from automatic Principal approval. Below-pass Present awards remain manual.')
                if not automatic_submit and not confirm_callback(prompt):
                    result.update(status='cancelled',pending_count=before['total'])
                    audit.append('confirmation_declined'); print('[STOPPED] Batch confirmation declined.'); break
                _stop(stop_event)
                audit.append('batch_authorised_by_preflight' if automatic_submit else 'batch_confirmed', registrations=[award.regno for award in awards], school_account=school_account,validation_evidence=match_evidence)
                current = snapshot(driver, plan, school_account)
                if current != before: raise ValueError('Page changed after preview; reopen and review the batch.')
                filled = _fill(driver, plan, before, awards, school_account, stop_event)
                _stop(stop_event)
                if hashlib.sha256(Path(plan.source).read_bytes()).hexdigest() != plan.source_sha256:
                    raise ValueError('Workbook changed; no save was clicked.')
                evidence = _evidence(driver, audit, 'filled-readback', filled)
                batch_id = hashlib.sha256(json.dumps({'state': filled, 'journal': audit.previous}, sort_keys=True).encode()).hexdigest()[:24]
                response = _begin_read(driver,'bodypH_btnSaveMarks','Marks save response') if receipt_callback else None
                # Persist intent BEFORE the only Save click. No retry on timeout/exception.
                audit.append('submit_attempt', batch_id=batch_id, registrations=[a.regno for a in awards], evidence=evidence,absent_awards=[dict(regno=a.regno,exam_roll=a.exam_roll,name=a.name,subject=plan.subject,attendance='A') for a in awards if a.attendance=='A'])
                try:
                    driver.find_element(By.ID, 'bodypH_btnSaveMarks').click()
                    if response is not None: _wait_page(driver,response,stop_event)
                    if receipt_callback and before['total']==len(before['rows']):
                        proof=receipt_callback(plan,awards,batch_id)
                        audit.append('verified_saved',batch_id=batch_id,registrations=[a.regno for a in awards],
                                     before_count=before['total'],after_count=0,origin='official_saved_report',
                                     verification='Validated source marks/attendance were read back before the single Save. Exact paired identities and names now have saved report status; receipt_detail states whether the report exposes numeric values.',**proof)
                        audit.report(plan)
                        result.update(status='saved_subject_verified',pending_count=0)
                        print(f'[VERIFIED] Final batch of {len(awards)} recorded on the official saved report. Continuing to the next selected subject.')
                        break
                    deadline = time.monotonic() + 40
                    after = None
                    while time.monotonic() < deadline:
                        _stop(stop_event)
                        try:
                            driver.switch_to.alert
                            raise ValueError('Unexpected JKBOSE alert. Submission status is uncertain; no automatic acceptance or retry.')
                        except NoAlertPresentException: pass
                        state = snapshot(driver, plan, school_account, require_first=False)
                        if verify_transition(before, state): after = state; break
                        time.sleep(0.3)
                    if after is None: raise ValueError('Pending rows/count did not prove the expected save. Do not retry automatically.')
                    # Reload the remaining queue through a read action, not the Save button.
                    show_students(driver, stop_event)
                    after = snapshot(driver, plan, school_account)
                    if not verify_transition(before, after): raise ValueError('Reloaded pending queue did not confirm the expected removal.')
                    evidence = _evidence(driver, audit, 'save-verified', after)
                    audit.append('verified_saved', batch_id=batch_id, registrations=[a.regno for a in awards],
                                 before_count=before['total'], after_count=after['total'], evidence=evidence,
                                 verification='Exact pending-count decrease and submitted registrations absent after Show Students reload; no independent saved-mark receipt was exposed.')
                    audit.report(plan)
                    print(f'[VERIFIED] Saved batch of {len(awards)}; {after["total"]} pending. No page-number increment is used.')
                except Exception:
                    audit.append('uncertain_submission', batch_id=batch_id, action='Stop. Admin must reconcile with JKBOSE; never blindly retry.')
                    raise
        except AssessmentStopped:
            audit.append('run_stopped'); print('[STOPPED] Private history preserved.'); raise
        except Exception as error:
            audit.append('run_failed', error_type=type(error).__name__, message=str(error)[:1000]); raise
        finally:
            audit.report(plan)
            print(f'[HISTORY] {audit.folder}')
        result['new_verified_count']=len(audit.verified()-initial_verified)
        return result

def re_account(value):
    import re
    return bool(re.fullmatch(r'[A-Za-z0-9_-]{3,80}', value or ''))
