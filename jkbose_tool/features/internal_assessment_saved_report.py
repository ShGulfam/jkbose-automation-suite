"""Read-only official saved-award receipts and exact source/history recovery."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select,WebDriverWait
from selenium.common.exceptions import TimeoutException
from .internal_assessment import Audit,class_key,session_key,subject_name,norm,number
from .internal_assessment_history import manifest_paths
from .internal_assessment_students_report import resolve_report_session,open_report_from_sidebar,is_report_page,_clean_url
from .internal_assessment_postback import begin_read,wait_read

URL='https://jkbose.jk.gov.in/utilities/auth_pages/PracticalMarksReportBySchool.aspx'
GROUPED_HEADERS=['Sr.','Class','Registration No.','Roll No.','Name','Subject-wise Marks / Status']
HEADERS=['Sr.','Class','Registration No.','Roll No.','Name','Subject','Marks','Out Of Marks','Present/Absent','Status','Rejection Reason']
SNAPSHOT=r"""
const table=document.getElementById('bodypH_gvMarks');
return {account:/Hello\s+([a-z0-9_-]+)/i.exec(document.body.innerText)?.[1]||'',
class:document.getElementById('bodypH_ddlClass')?.value,
status:document.getElementById('bodypH_ddlStatus')?.value,
session:document.getElementById('bodypH_txtSession')?.value,
page_label:document.getElementById('bodypH_lblPage')?.innerText.trim()||'',
headers:[...(table?.querySelectorAll('th')||[])].map(e=>e.innerText.trim()),
rows:[...(table?.querySelectorAll('tr')||[])].filter(tr=>tr.querySelector('td')).map(tr=>[...tr.cells].map(c=>c.innerText.trim())),
next_disabled:document.getElementById('bodypH_btnNext')?.disabled===true};
"""

def validate_page(data,cls,account,report_session,page,total=None,expected_status=''):
    if data.get('account','').lower()!=account.lower() or data.get('class')!=cls or data.get('status')!=expected_status or data.get('session')!=report_session:
        raise ValueError('Saved report school/class/session/status filters do not match.')
    match=re.fullmatch(r'Page (\d+) of (\d+) \((\d+) records\)',data.get('page_label',''))
    if not match:raise ValueError('Saved report page/record count is unreadable.')
    current,pages,count=map(int,match.groups())
    if current!=page or pages<1 or current>pages or count>20000 or (total is not None and count!=total):
        raise ValueError('Saved report changed or skipped a page.')
    if count and data.get('next_disabled')!=(page==pages):raise ValueError('Saved report pagination controls disagree with its page count.')
    rows=data.get('rows',[])
    if count==0:
        if pages!=1 or page!=1 or rows not in ([],[['No records found.']]):raise ValueError('Saved report empty state is inconsistent.')
        return pages,count,[]
    grouped=data.get('headers')==GROUPED_HEADERS
    if (data.get('headers') not in (HEADERS,GROUPED_HEADERS) or not rows or any(len(row)!=(6 if grouped else 11) for row in rows)):
        raise ValueError('Saved report columns or rows are incomplete.')
    return pages,count,rows

def _read_saved_report_status(driver,student_class,school_account,workbook_session,requested_session='Auto',stop_event=None,status=''):
    from . import internal_assessment_browser as browser
    stop=lambda:browser._stop(stop_event)
    stop();open_report_from_sidebar(driver,URL,'Official saved assessment report',stop_event)
    WebDriverWait(driver,30).until(lambda d:d.execute_script('return document.readyState')=='complete')
    curr_url=_clean_url(driver.current_url)
    if not is_report_page(curr_url,URL):
        raise ValueError(f'Official saved report redirected to {curr_url} (login expired or unexpected page). No submission is allowed without verified receipt checks.')
    cls=class_key(student_class)
    actual=driver.find_element(By.ID,'bodypH_txtSession').get_attribute('value')
    report_session=resolve_report_session(workbook_session,[actual],requested_session)
    Select(driver.find_element(By.ID,'bodypH_ddlClass')).select_by_value(cls)
    Select(driver.find_element(By.ID,'bodypH_ddlStatus')).select_by_value(status)
    before=begin_read(driver,'bodypH_btnSearch','Saved assessment report Search')
    driver.find_element(By.ID,'bodypH_btnSearch').click();wait_read(driver,before,stop)
    rows=[];page=1;total=None;layout=None
    while True:
        stop()
        curr_url=_clean_url(driver.current_url)
        if not is_report_page(curr_url,URL):
            if curr_url.lower().split('?')[0].endswith(('/login.aspx','/utilities/index.html')):
                raise ValueError('Saved report lost the authenticated session ('+curr_url+'). Sign in again; no receipt check or new save was accepted.')
            def settled(d):
                stop()
                return is_report_page(_clean_url(d.current_url),URL) and d.execute_script('return document.readyState')=='complete'
            try:
                WebDriverWait(driver,5,poll_frequency=0.2).until(
                    settled
                )
            except TimeoutException:
                curr=_clean_url(driver.current_url)
                if 'login.aspx' in curr.lower():
                    raise ValueError(f'Official saved report redirected to login ({curr}): session expired. Please log in again to resume.')
                raise ValueError(f'Saved report redirected to {curr} while reading receipts.')
        data=driver.execute_script(SNAPSHOT)
        pages,total,chunk=validate_page(data,cls,school_account,report_session,page,total,expected_status=status)
        current_layout='grouped' if data.get('headers')==GROUPED_HEADERS else 'detailed'
        if total and layout and current_layout!=layout:raise ValueError('Saved report layout changed while reading pages.')
        if total:layout=current_layout
        if status and current_layout=='detailed' and any(row[9]!=status for row in chunk):raise ValueError('Saved report returned another status; complete coverage cannot be verified.')
        rows.extend(chunk)
        if len(rows)>total:raise ValueError('Saved report rows exceed its declared total.')
        if page==pages:break
        before=begin_read(driver,'bodypH_btnNext','Saved assessment report next page')
        driver.find_element(By.ID,'bodypH_btnNext').click();wait_read(driver,before,stop);time.sleep(0.15);page+=1
    if len(rows)!=total or any(row[0]!=str(i) for i,row in enumerate(rows,1)):
        raise ValueError('Complete consecutive saved-report rows were not read.')
    records=[]
    for row in rows:
        if row[1]!=cls or not re.fullmatch(r'[A-Za-z0-9-]+',row[2]) or not re.fullmatch(r'\d{9}',row[3]):
            raise ValueError('Saved report contains an invalid class or paired identifier.')
        if layout=='grouped':
            entries=row[5].split(',');seen_subjects=set();found_filter=False
            for entry in entries:
                match=re.fullmatch(r'\s*([^:,]+):\s*(Requested|Approved|Rejected)\s*',entry)
                if not match:raise ValueError('Unrecognised grouped subject/status; receipt coverage cannot be established.')
                subject=subject_name(match[1].strip());state=match[2]
                if not subject or subject in seen_subjects:raise ValueError('Duplicate/empty grouped subject status.')
                seen_subjects.add(subject);found_filter=found_filter or state==status
                records.append(dict(regno=row[2],exam_roll=row[3],name=row[4],subject=subject,marks=None,maximum=None,attendance=None,status=state,rejection_reason='',detail='status_only'))
            if status and not found_filter:raise ValueError('Grouped student does not contain the requested status.')
        else:
            records.append(dict(regno=row[2],exam_roll=row[3],name=row[4],subject=subject_name(row[5]),marks=row[6],maximum=row[7],attendance=row[8],status=row[9],rejection_reason=row[10]))
    keys=[(row['regno'],row['exam_roll'],row['subject']) for row in records]
    if (len(set(keys))!=len(keys) or len({(r['regno'],r['subject']) for r in records})!=len(records)
            or len({(r['exam_roll'],r['subject']) for r in records})!=len(records)):
        raise ValueError('Duplicate/conflicting official saved-award identities require review.')
    result=dict(account=school_account,student_class=cls,workbook_session=session_key(workbook_session),report_session=report_session,
                url=URL,coverage_complete=True,pages=page,total=len(records),student_rows=total,receipt_detail='status_only_grouped' if layout=='grouped' else 'detailed',records=records)
    result['sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result


def read_saved_report(driver,student_class,school_account,workbook_session,requested_session='Auto',stop_event=None):
    """Read all explicit statuses; JKBOSE's blank All filter can error on Search."""
    statuses=('Requested','Approved','Rejected');parts=[]
    for status in statuses:
        parts.append(_read_saved_report_status(driver,student_class,school_account,workbook_session,requested_session,stop_event,status=status))
    first=parts[0]
    for status,part in zip(statuses,parts):
        _report_index(part,school_account)
        if part.get('receipt_detail')!='status_only_grouped' and any(row.get('status')!=status for row in part['records']):raise ValueError('Saved status report includes another status; complete receipt coverage is not proven.')
        if any(part.get(k)!=first.get(k) for k in ('account','student_class','workbook_session','report_session','url')):raise ValueError('Saved status reports changed account/class/session; no complete receipt check.')
    result={k:v for k,v in first.items() if k not in {'sha256','records','total','pages'}}
    records={}
    for part in parts:
        for row in part['records']:
            key=(row['regno'],row['exam_roll'],row['subject'])
            if key in records:
                if part.get('receipt_detail')!='status_only_grouped' or records[key]!=row:raise ValueError('Duplicate/conflicting awards across status reports; rerun receipt check.')
            records[key]=row
    result.update(records=list(records.values()),total=len(records),pages=sum(p['pages'] for p in parts),student_rows=sum(p.get('student_rows',p['total']) for p in parts),status_filters=list(statuses))
    result['receipt_detail']='status_only_grouped' if any(row.get('detail')=='status_only' for row in result['records']) else 'detailed'
    result['sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    _report_index(result,school_account)
    return result


def _report_index(report,school_account):
    """Validate once and share indexed receipt matching across all subjects."""
    unsigned={key:value for key,value in report.items() if key!='sha256'}
    if (not report.get('coverage_complete') or report.get('account','').lower()!=school_account.lower()
            or report.get('url')!=URL or hashlib.sha256(json.dumps(unsigned,sort_keys=True).encode()).hexdigest()!=report.get('sha256')):
        raise ValueError('A complete account-scoped saved report is required.')
    rows=report['records'];counts=Counter((r['regno'],r['exam_roll'],r['subject']) for r in rows)
    if report.get('total')!=len(rows):raise ValueError('Official saved-report coverage is incomplete.')
    if any(n!=1 for n in counts.values()):raise ValueError('Duplicate saved-report awards require review.')
    by_key={(r['regno'],r['exam_roll'],r['subject']):r for r in rows}
    if (len({(r['regno'],r['subject']) for r in rows})!=len(rows)
            or len({(r['exam_roll'],r['subject']) for r in rows})!=len(rows)):
        raise ValueError('Conflicting saved-report registration/exam pairs require review.')
    return by_key,{(r['regno'],r['subject']) for r in rows},{(r['exam_roll'],r['subject']) for r in rows}


def _status_receipt_matches(plan,award,row):
    return bool(row and row.get('detail')=='status_only' and row.get('regno')==award.regno and row.get('exam_roll')==award.exam_roll and row.get('subject')==plan.subject and norm(row.get('name'))==norm(award.name) and row.get('status') in {'Requested','Approved'} and not row.get('rejection_reason'))

def _award_matches(plan,award,row):
    from .internal_assessment import submission_issues
    if row is None:return False
    try:
        return (not submission_issues(award) and norm(row['name'])==norm(award.name) and row['attendance']==award.attendance
                and row['status'] in {'Requested','Approved'} and not row['rejection_reason']
                and (str(row['marks']).strip().upper() in {'','AB','A','ABS','ABSENT','0','0.0'} if award.attendance=='A' else number(row['marks'])==number(award.marks)) and number(row['maximum'])==number(plan.maximum))
    except ValueError:return False


def annotate_rejected_corrections(plan,report,school_account):
    indexed,_,_=_report_index(report,school_account)
    if report['student_class']!=plan.student_class or report['workbook_session']!=plan.session:raise ValueError('Rejected receipt class/session differs from source.')
    plan.rejected_receipts={}
    for award in plan.awards:
        row=indexed.get((award.regno,award.exam_roll,plan.subject))
        if row and row.get('status')=='Rejected' and norm(row['name'])==norm(award.name):
            plan.rejected_receipts[(award.regno,award.exam_roll)]={**row,'source_sha256':plan.source_sha256,'official_report_sha256':report['sha256']}


def recognise_saved_awards(root,plans,school_account,report,evidence):
    """Append official receipt evidence; never infer a save from a missing pending row."""
    by_key,registrations,exam_rolls=_report_index(report,school_account)
    def matches(plan,award):
        return _award_matches(plan,award,by_key.get((award.regno,award.exam_roll,plan.subject)))
    def receipt(audit,receipt_plan,batch,regs):
        awards={a.regno:a for a in receipt_plan.awards}
        audit.append('verified_saved',batch_id=batch,registrations=sorted(regs),evidence=str(evidence),
                     official_report_sha256=report['sha256'],origin='official_saved_report',
                     receipt_detail=report.get('receipt_detail','detailed'),verification='Exact paired identity/name and Requested/Approved status; grouped report does not expose saved marks/attendance.' if report.get('receipt_detail')=='status_only_grouped' else 'Exact registration/exam roll, class/session/subject, name, marks, maximum and exact source attendance in the complete official report. Requested means recorded awaiting board approval; it is not approval.',
                     official_statuses={reg:by_key[(reg,awards[reg].exam_roll,receipt_plan.subject)]['status'] for reg in regs})
    recognised={};recovered={};plan_by_subject={p.subject:p for p in plans};rejections=[];recorded_differences=[]
    for plan in plans:
        if report['student_class']!=plan.student_class or report['workbook_session']!=plan.session:
            raise ValueError('Saved report class/session differs from the source plan.')
        for award in plan.awards:
            related=(award.regno,plan.subject) in registrations or (award.exam_roll,plan.subject) in exam_rolls
            if related and (award.regno,award.exam_roll,plan.subject) not in by_key:
                raise ValueError('Official saved report registration/exam pair conflicts with the source for '+plan.subject+'.')
            saved_row = by_key.get((award.regno,award.exam_roll,plan.subject))
            if saved_row:
                if saved_row.get('status') == 'Rejected':
                    if norm(saved_row['name'])!=norm(award.name):raise ValueError('Rejected receipt student name differs from the source; review identity.')
                    rejections.append((plan,award.regno,saved_row))
                    continue
                if not matches(plan,award) and saved_row.get('status') in {'Requested','Approved'} and not saved_row.get('rejection_reason') and norm(saved_row['name'])==norm(award.name):
                    recorded_differences.append((plan,award.regno,saved_row));continue
                if not matches(plan,award):
                    raise ValueError('Official saved award conflicts with the source, attendance or status for '+plan.subject+'. Review the saved-report evidence before continuing.')
    for plan in plans:annotate_rejected_corrections(plan,report,school_account)
    # Record official rejection as a local outcome, not as a portal decision.
    # It supersedes earlier receipts but never settles an uncertain save attempt.
    for plan in plans:
        rows=[(reg,row) for p,reg,row in rejections if p is plan]
        if not rows:continue
        audit=Audit(root,plan)
        accounts={e['school_account'].lower() for e in audit.events if e['kind']=='run_started' and e.get('school_account')}
        if accounts and accounts!={school_account.lower()}:raise ValueError('Rejection history school account is ambiguous.')
        from .internal_assessment import saved_outcomes
        latest=saved_outcomes(audit.events)
        pending=[reg for reg,row in rows if reg not in latest or latest[reg]['kind']!='portal_award_rejected' or latest[reg].get('official_report_sha256')!=report['sha256']]
        if pending:
            if not accounts:audit.append('run_started',mode='official_saved_receipt_check',school_account=school_account,source=plan.manifest(),source_preview=plan.rows())
            audit.append('portal_award_rejected',registrations=pending,evidence=str(evidence),official_report_sha256=report['sha256'],origin='official_saved_report',
                         rejected_records=[row for reg,row in rows if reg in pending],disposition='returned_to_pending',
                         verification='Complete official report shows Rejected for exact school/class/session, paired identifiers and name. Fresh pending-row checks are still mandatory before resubmission.')
    # Recover an attempted batch only when every original award has an exact receipt.
    for path in manifest_paths(root):
        manifest=json.loads(path.read_text(encoding='utf-8'))
        plan=plan_by_subject.get(manifest.get('subject'))
        if plan is None or manifest.get('student_class')!=plan.student_class or manifest.get('session')!=plan.session:continue
        audit,old_plan=Audit.existing(path.parent)
        accounts={e['school_account'].lower() for e in audit.events if e['kind']=='run_started' and e.get('school_account')}
        if accounts!={school_account.lower()}:continue
        old={a.regno:a for a in old_plan.awards}
        for batch in sorted(audit.unresolved()):
            attempt=next(e for e in audit.events if e['kind']=='submit_attempt' and e['batch_id']==batch)
            regs=attempt['registrations']
            if regs and all(reg in old and (matches(old_plan,old[reg]) or _status_receipt_matches(old_plan,old[reg],by_key.get((reg,old[reg].exam_roll,old_plan.subject)))) for reg in regs):
                receipt(audit,old_plan,batch,regs)
                recovered.setdefault(plan.subject,set()).update(regs)
    # Accepted awards are not editable through the clerk pending queue. A new
    # export may change them; preserve actual saved values and skip only the ID.
    for plan,reg,row in recorded_differences:
        audit=Audit(root,plan)
        accounts={e['school_account'].lower() for e in audit.events if e['kind']=='run_started' and e.get('school_account')}
        if accounts and accounts!={school_account.lower()}:raise ValueError('Recorded-award history account is ambiguous.')
        if not accounts:audit.append('run_started',mode='official_saved_receipt_check',school_account=school_account,source=plan.manifest(),source_preview=plan.rows())
        from .internal_assessment import saved_outcomes
        latest=saved_outcomes(audit.events).get(reg)
        if not latest or latest['kind']!='official_recorded_award' or latest.get('official_report_sha256')!=report['sha256']:
            audit.append('official_recorded_award',registrations=[reg],saved_records={reg:row},official_report_sha256=report['sha256'],evidence=str(evidence),
                         verification='Exact paired identity and name are Requested/Approved. Existing award is skipped. A grouped status-only report does not expose saved marks or attendance; values remain unverified.' if row.get('detail')=='status_only' else 'Exact paired identity and name are Requested/Approved in the complete official report. Current source differs; record discrepancy only and never retry these awards.')
        audit.report(plan)
    for plan in plans:
        from .internal_assessment_batch import verified_history
        prior=verified_history(root,plan,school_account) # unresolved/conflicting history still blocks
        found={a.regno for a in plan.awards if matches(plan,a)}-prior['verified']-prior['manual']
        if found:
            audit=Audit(root,plan)
            audit.append('run_started',mode='official_saved_receipt_check',school_account=school_account,source=plan.manifest(),source_preview=plan.rows())
            receipt(audit,plan,'official-'+report['sha256'][:24],found);audit.report(plan)
        recognised[plan.subject]=len((found|recovered.get(plan.subject,set()))&{a.regno for a in plan.awards})
    return recognised


def verify_saved_batch(plan,awards,school_account,report):
    """Verify a just-saved final batch independently of a disappearing dropdown."""
    mapping,_,_=_report_index(report,school_account)
    if report.get('student_class')!=plan.student_class or report.get('workbook_session')!=plan.session:
        raise ValueError('The final batch saved report is incomplete or has a different account/class/session.')
    statuses={}
    for award in awards:
        row=mapping.get((award.regno,award.exam_roll,plan.subject))
        status_only=bool(row and row.get('detail')=='status_only' and report.get('receipt_detail')=='status_only_grouped' and norm(row.get('name'))==norm(award.name) and row.get('status') in {'Requested','Approved'})
        if not status_only and not _award_matches(plan,award,row):
            raise ValueError('The final batch lacks an exact official saved receipt. Stop without retrying.')
        statuses[award.regno]=row['status']
    return statuses
