"""Read-only full enrolment matching. This report never certifies practical attendance."""
from pathlib import Path
from urllib.parse import urlparse,urljoin
import hashlib
import json
import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select,WebDriverWait
from selenium.common.exceptions import TimeoutException
from ..browser import safe_click,page_change_token
from .internal_assessment import class_key,session_key,subject_name,number

URL='https://jkbose.jk.gov.in/utilities/auth_pages/student_report.aspx'
HEADERS=['#','Image','Roll No','Full Name','Parentage','Date of Birth','Gender','Category','Religion','Disability',
         'RR Fee','Exam Fee','Class','Approval Status','RR No','Stream Opted','Compulsory','','Additional','Vocational','Optional']
# Confirmed by the owner for this examination cycle. Never apply this offset
# to another workbook year, or silently select a different/latest report year.
CONFIRMED_REPORT_SESSIONS={'2025-26':'2026-2027'}


def has_assigned_exam_roll(row):
    # Ignore only explicit unassigned values. A malformed non-empty roll must
    # remain visible as an identity exception, never silently disappear.
    return str(row.get('exam_roll','')).strip().lower() not in {'','-','—','n/a','na','nil','none','not allotted','not assigned','pending','0'}

SNAPSHOT=r"""
const table=document.getElementById('mytable');
const bodyRows=table?[...table.rows].slice(1):[];
return {account:(/Hello\s+([a-z0-9_-]+)/i.exec(document.body.innerText)||[])[1]||'',
 selected_class:document.getElementById('bodypH_ddlclasssearch')?.value||'',
 selected_session:document.getElementById('bodypH_ddlsessionsearch')?.value||'',
 headers:table?[...table.rows[0].cells].map(c=>c.innerText.trim()):[],
 row_widths:bodyRows.map(r=>r.cells.length),
 rows:bodyRows.map(r=>{const c=[...r.cells].map(x=>x.innerText.trim());return {
 sequence:c[0],exam_roll:c[2],name:c[3],class_name:c[12],approval:c[13],regno:c[14],exam_fee:c[11],subjects:c.slice(16,21)};}),
 has_pager:[...document.querySelectorAll('a[href],input[type=submit],button')].some(e=>/^(next|previous|prev|last|first|\d+)$/i.test((e.innerText||e.value||'').trim())),
 data_table:!!window.jQuery?.fn?.dataTable};
"""


def resolve_report_session(workbook_session,options,requested='Auto'):
    school=session_key(workbook_session)
    if requested in ('Auto','',None):
        target=CONFIRMED_REPORT_SESSIONS.get(school)
        if not target: raise ValueError('No confirmed Students report session mapping for '+school+'. Choose the board report session explicitly; school sessions are not shifted automatically.')
        valid=[value for value in options if re.fullmatch(r'20\d{2}-20\d{2}',value)]
        if not valid or target!=max(valid):
            raise ValueError('The latest Students report session changed. Verify its mapping before selecting it explicitly.')
    else:
        target=str(requested).strip()
        if not re.fullmatch(r'20\d{2}-20\d{2}',target): raise ValueError('Board report session must be the exact YYYY-YYYY dropdown label.')
    if options.count(target)!=1: raise ValueError('The selected Students report session is missing or ambiguous.')
    return target


def validate_snapshot(data,student_class,school_account,report_session):
    cls=class_key(student_class)
    if data.get('account','').lower()!=school_account.lower(): raise ValueError('Students report belongs to a different school account or login expired.')
    if data.get('selected_class')!=cls or data.get('selected_session')!=report_session: raise ValueError('Students report filters changed during the read-only check.')
    if data.get('headers')!=HEADERS: raise ValueError('Students report columns changed or no report was returned. Stop for inspection.')
    rows=data.get('rows',[])
    if not rows or len(rows)>20000 or len(data.get('row_widths',[]))!=len(rows) or any(width!=21 for width in data['row_widths']):
        raise ValueError('Students report has an empty, oversized or unrecognised roster; complete coverage cannot be certified.')
    if data.get('has_pager') or data.get('data_table'): raise ValueError('Students report pagination changed; complete coverage cannot be certified.')
    if [str(row.get('sequence','')) for row in rows]!=[str(i) for i in range(1,len(rows)+1)]:
        raise ValueError('Students report row numbering is incomplete or repeated.')
    roman={'9':'IX','10':'X','11':'XI','12':'XII'}[cls]
    for row in rows:
        if row.get('class_name') not in {cls,roman}: raise ValueError('Stale Students report: returned student class differs from the requested class. Search again; never trust the dropdown alone.')
        if len(row.get('subjects',[]))!=5: raise ValueError('Student subject columns are incomplete.')
        for key in ['name','regno','exam_roll','approval','exam_fee']:
            if not isinstance(row.get(key),str) or len(row[key])>250: raise ValueError('Invalid student report field: '+key)
        if any(not isinstance(value,str) or len(value)>1500 for value in row['subjects']): raise ValueError('Invalid subject field in Students report.')
    return data


def _clean_url(u):
    if isinstance(u, bytes):
        return u.decode('utf-8', errors='replace')
    return str(u or '')


def is_report_page(current,expected):
    location,target=urlparse(_clean_url(current)),urlparse(_clean_url(expected))
    loc_scheme=_clean_url(location.scheme).lower()
    loc_host=_clean_url(location.hostname).lower()
    loc_path=_clean_url(location.path).lower()
    tgt_path=_clean_url(target.path).lower()
    return loc_scheme=='https' and loc_host=='jkbose.jk.gov.in' and loc_path==tgt_path


def open_report_from_sidebar(driver,destination,label,stop_event=None):
    """Use authenticated report links, never a fresh direct GET or a Save control."""
    from . import internal_assessment_browser as browser
    browser._stop(stop_event)
    dest_str=_clean_url(destination)
    label_str=_clean_url(label)
    target=urlparse(dest_str)
    tgt_scheme=_clean_url(target.scheme).lower()
    tgt_host=_clean_url(target.hostname).lower()
    tgt_path=_clean_url(target.path).lower()
    if (tgt_scheme!='https' or tgt_host!='jkbose.jk.gov.in'
            or tgt_path not in {'/utilities/auth_pages/student_report.aspx','/utilities/auth_pages/practicalmarksreportbyschool.aspx','/utilities/auth_pages/generatepracticalmarks.aspx'}):
        raise ValueError('Unsupported read-only report destination.')
    curr_url=_clean_url(driver.current_url)
    current=urlparse(curr_url)
    cur_scheme=_clean_url(current.scheme).lower()
    cur_host=_clean_url(current.hostname).lower()
    cur_path=_clean_url(current.path).lower()
    if cur_scheme!='https' or cur_host!='jkbose.jk.gov.in' or cur_path.endswith('/login.aspx'):
        raise ValueError(label_str+' requires the signed-in official JKBOSE site. No marks were submitted.')
    if not is_report_page(curr_url,dest_str):
        links=[]
        for link in driver.find_elements(By.CSS_SELECTOR,'a[href]'):
            href=urljoin(curr_url,_clean_url(link.get_attribute('href') or ''))
            if is_report_page(href,dest_str) and link.is_enabled():links.append(link)
        if len(links)!=1: raise ValueError('Cannot identify the authenticated '+label_str+' sidebar link unambiguously. No direct-navigation fallback was attempted.')
        if not links[0].is_displayed():
            toggles=[el for el in driver.find_elements(By.CSS_SELECTOR,'a.sidebar-toggle') if el.is_displayed() and el.is_enabled()]
            if len(toggles)!=1:raise ValueError(label_str+' link is hidden and the sidebar toggle is missing or ambiguous.')
            safe_click(driver,toggles[0])
            def visible(d):
                browser._stop(stop_event)
                return links[0].is_displayed()
            try:WebDriverWait(driver,10,poll_frequency=0.2).until(visible)
            except TimeoutException as exc:raise ValueError(label_str+' sidebar did not expand. No report navigation or save was attempted.') from exc
        safe_click(driver,links[0])
        def loaded(d):
            browser._stop(stop_event)
            d_url=_clean_url(d.current_url)
            if not d_url or d_url.lower()=='about:blank':return False
            location=urlparse(d_url)
            loc_scheme=_clean_url(location.scheme).lower()
            loc_host=_clean_url(location.hostname).lower()
            loc_path=_clean_url(location.path)
            if loc_scheme!='https' or loc_host!='jkbose.jk.gov.in' or loc_path.lower().endswith('/login.aspx'):
                raise ValueError(f"{label_str} sidebar navigation redirected to {loc_path}. Sign in again; no receipt check or save was accepted.")
            return is_report_page(d_url,dest_str) and d.execute_script('return document.readyState')=='complete'
        try:WebDriverWait(driver,30,poll_frequency=0.2).until(loaded)
        except TimeoutException as exc:
            final_path=_clean_url(urlparse(_clean_url(driver.current_url)).path)
            raise ValueError(f"{label_str} sidebar navigation did not finish (current path: {final_path}). No save was attempted.") from exc


def read_student_report(driver,student_class,school_account,workbook_session,requested_session='Auto',stop_event=None):
    from . import internal_assessment_browser as browser
    open_report_from_sidebar(driver,URL,'Students report',stop_event)
    cls=class_key(student_class)
    class_control=driver.find_element(By.ID,'bodypH_ddlclasssearch')
    classes=Select(class_control)
    if len([option for option in classes.options if option.get_attribute('value')==cls])!=1: raise ValueError('Students report class is missing or ambiguous.')
    class_changed=classes.first_selected_option.get_attribute('value')!=cls
    class_postback=bool(class_control.get_attribute('onchange'))
    before=browser._begin_read(driver,'bodypH_ddlclasssearch','Students report class selection') if class_changed and class_postback else None
    classes.select_by_value(cls)
    if class_changed and class_postback: browser._wait_page(driver,before,stop_event)
    # Changing class posts back and replaces the session element. Never reuse
    # an element captured before that navigation.
    session_control=driver.find_element(By.ID,'bodypH_ddlsessionsearch')
    sessions=Select(session_control)
    options=[option.get_attribute('value') for option in sessions.options]
    report_session=resolve_report_session(workbook_session,options,requested_session)
    session_changed=sessions.first_selected_option.get_attribute('value')!=report_session
    session_postback=bool(session_control.get_attribute('onchange'))
    before=browser._begin_read(driver,'bodypH_ddlsessionsearch','Students report session selection') if session_changed and session_postback else None
    sessions.select_by_value(report_session)
    if session_changed and session_postback: browser._wait_page(driver,before,stop_event)
    # Selecting a class alone can leave a previous class's grid visible.
    # Search is read-only; require its completed full or partial response.
    browser._stop(stop_event)
    before=browser._begin_read(driver,'bodypH_btnsearch','Students report Search')
    driver.find_element(By.ID,'bodypH_btnsearch').click(); browser._wait_page(driver,before,stop_event)
    destination=urlparse(_clean_url(driver.current_url))
    dest_scheme=_clean_url(destination.scheme).lower()
    dest_host=_clean_url(destination.hostname).lower()
    dest_path=_clean_url(destination.path).lower()
    if dest_scheme!='https' or dest_host!='jkbose.jk.gov.in' or dest_path!='/utilities/auth_pages/student_report.aspx':
        raise ValueError('Students report Search redirected or login expired. No report is accepted.')
    data=validate_snapshot(driver.execute_script(SNAPSHOT),cls,school_account,report_session)
    data.update(workbook_session=session_key(workbook_session),report_session=report_session,report_url=URL,
                session_mapping_basis='owner-confirmed mapping' if requested_session in ('Auto','',None) else 'explicit operator report session',
                coverage_complete=True,coverage_reason='Full Students report: consecutive rows, validated class/session filters and inspected non-paginated layout.',
                purpose='Enrolment and subject matching only. No practical marks, attendance or saved-award status is provided by this report.')
    data['skipped_applications']=[{**row,'skip_reason':'No assigned exam roll; excluded from matching by school instruction'} for row in data['rows'] if not has_assigned_exam_roll(row)]
    return data


def write_snapshot(folder,data):
    folder=Path(folder)/'students_report'; folder.mkdir(parents=True,exist_ok=True)
    path=folder/'roster.json'; temporary=folder/'roster.tmp'
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(data,stream,indent=2); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary,path)
    return {'snapshot':str(path),'snapshot_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'workbook_session':data['workbook_session'],'report_session':data['report_session'],
            'school_account':data['account'],'student_count':sum(has_assigned_exam_roll(row) for row in data['rows']),
            'raw_application_count':len(data['rows']),'skipped_no_exam_roll_count':sum(not has_assigned_exam_roll(row) for row in data['rows']),
            'coverage_complete':True,'report_url':URL}


def enrolled_in_subject(row,subject):
    tokens={subject_name(token.strip()) for field in row['subjects'] for token in re.split(r'[,;\n]+',field) if token.strip()}
    wanted=subject_name(subject)
    if wanted in {'Botany','Zoology'}: return wanted in tokens or 'Biology' in tokens
    if wanted=='Biology': return wanted in tokens or {'Botany','Zoology'}<=tokens
    return wanted in tokens


def match_student_report(plan,snapshot,prior,pending_result=None):
    from .internal_assessment_matching import compare_rosters
    rows=[]
    for raw in snapshot['rows']:
        if not has_assigned_exam_roll(raw): continue
        if not enrolled_in_subject(raw,plan.subject): continue
        row=dict(raw); row['report_issues']=[]
        if raw['approval'].lower()!='approved': row['report_issues'].append('Board report approval is not Approved; manual review.')
        if raw['exam_fee'].lower()!='paid': row['report_issues'].append('Board report examination fee is not Paid; manual review.')
        rows.append(row)
    pending_result=pending_result or {}; pending=pending_result.get('matching_summary',{})
    official=number(pending['official_maximum']) if pending.get('official_maximum') else None
    note=f'Full Students report subject roster: {len(rows)} students. '
    note+=f'Practicals pending rows read: {pending.get("scanned_jkbose_count",0)}/{pending.get("expected_pending_count","unknown")}; '
    note+='complete pending coverage. ' if pending.get('coverage_complete') else 'pending coverage is incomplete/unverified. '
    note+='Enrolment matching does not verify practical attendance, marks or submission.'
    data=compare_rosters(plan,rows,complete=True,official_maximum=official,prior=prior,coverage_reason=note,source_kind='students_report')
    data.update(expected_pending_count=len(rows),pages_scanned=1,source=plan.source,source_sha256=plan.source_sha256,
                class_name=plan.student_class,session=plan.session,report_session=snapshot['report_session'],
                matching_source='students_report',pending_summary=pending,report_url=URL)
    pending_pairs=set()
    if pending_result.get('matching_report'):
        pending_data=json.loads(Path(pending_result['matching_report']).read_text(encoding='utf-8'))
        pending_pairs={(row['jkbose_registration'],row['jkbose_exam_roll']) for row in pending_data['records'] if row['jkbose_registration']}
    report_pairs={(row['regno'],row['exam_roll']) for row in rows}
    unexpected=pending_pairs-report_pairs
    data['pending_pairs_not_in_report']=[{'registration':reg,'exam_roll':exam} for reg,exam in sorted(unexpected)]
    if unexpected: data['identity_roster_reconciled']=False
    by_pair={(row['regno'],row['exam_roll']):row for row in rows}
    for record in data['records']:
        pair=(record['jkbose_registration'],record['jkbose_exam_roll'])
        raw=by_pair.get(pair,{})
        record.update(report_subjects=' | '.join(raw.get('subjects',[])),report_approval=raw.get('approval',''),report_exam_fee=raw.get('exam_fee',''),
                      pending_observation='Seen on read pending pages' if pair in pending_pairs else 'Not seen on read pending pages; not proof of submission or non-enrolment')
    return data


def export_report_matching(class_audit,jobs,snapshot,prior_by_subject,pending_results,holds):
    from .internal_assessment_matching import export_matching_reports
    folder=class_audit.folder/'students_report'; folder.mkdir(exist_ok=True)
    results=[]; pending_by_subject={row['subject']:row for row in pending_results}
    for job in jobs:
        if job['plan'] is None:
            results.append({'subject':job['subject'],'status':'source_blocked','reason':job['error']}); continue
        plan=job['plan']
        data=match_student_report(plan,snapshot,prior_by_subject.get(plan.subject,{'verified':set(),'manual':set()}),pending_by_subject.get(plan.subject))
        path=folder/(re.sub(r'[^a-z0-9]+','_',plan.subject.lower()).strip('_')+'.json')
        temporary=path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as stream:
            json.dump(data,stream,indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)
        results.append({'subject':plan.subject,'status':'roster_reconciled' if data['identity_roster_reconciled'] else 'roster_review_required',
                        'matching_report':str(path),'matching_summary':{key:value for key,value in data.items() if key not in {'records','source'}}})
    skipped=[{**row,'skip_reason':'No assigned exam roll; excluded from matching by school instruction'} for row in snapshot['rows'] if not has_assigned_exam_roll(row)]
    manifest={**class_audit.manifest,'matching_source':'students_report','report_session':snapshot['report_session']}
    report={'manifest':manifest,'status':'roster_reconciled' if all(row['status']=='roster_reconciled' for row in results) else 'roster_review_required',
            'subjects':results,'skipped_applications':skipped}
    exports=export_matching_reports(folder,report,holds)
    return {'subjects':results,'status':report['status'],'exports':exports,'report_session':snapshot['report_session']}
