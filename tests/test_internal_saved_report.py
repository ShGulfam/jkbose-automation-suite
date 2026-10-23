import copy,hashlib,json,unittest
from unittest.mock import Mock,patch
import test_internal_batch as fixtures
from jkbose_tool.features import internal_assessment_saved_report as saved
from jkbose_tool.features import internal_assessment_browser as browser
from jkbose_tool.features import internal_assessment_batch as batch
from jkbose_tool.features.internal_assessment import Audit,prepare_history_root

class SavedReportTests(unittest.TestCase):
    setUp=fixtures.ClassRunTests.setUp
    write_book=fixtures.ClassRunTests.write_book
    plan=fixtures.ClassRunTests.plan
    jobs=fixtures.ClassRunTests.jobs
    state=fixtures.ClassRunTests.state
    def sign(self,data):
        data.pop('sha256',None)
        data['sha256']=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest();return data
    def report(self,plan=None):
        plan=plan or self.plan('Mathematics')
        return self.sign(dict(account='school-test',student_class='11',workbook_session='2025-26',report_session='2026-2027',url=saved.URL,coverage_complete=True,total=len(plan.awards),pages=1,
            records=[dict(regno=a.regno,exam_roll=a.exam_roll,name=a.name,subject=plan.subject,marks=a.marks,maximum=plan.maximum,attendance='P',status='Requested',rejection_reason='') for a in plan.awards]))
    def recognise(self,report=None):
        plan=self.plan('Mathematics');root=prepare_history_root(self.history)
        data=report or self.report(plan);evidence=self.root/'official.json';evidence.write_text(json.dumps(data))
        result=saved.recognise_saved_awards(root,[plan],'school-test',data,evidence)
        return result,batch.verified_history(root,plan,'school-test')
    def uncertain(self):
        plan=self.plan('Mathematics');root=prepare_history_root(self.history);audit=Audit(root,plan)
        audit.append('run_started',school_account='school-test',source=plan.manifest(),source_preview=plan.rows())
        audit.append('submit_attempt',batch_id='synthetic-attempt',registrations=[a.regno for a in plan.awards])
        return audit
    def test_exact_requested_record_recognised_without_board_approval_or_save_click(self):
        result,prior=self.recognise()
        self.assertEqual(result['Mathematics'],1);self.assertEqual(prior['verified'],{'REG1'});self.assertEqual(prior['manual'],set())
        repeated,_=self.recognise();self.assertEqual(repeated['Mathematics'],0)
    def test_complete_exact_receipts_resolve_uncertain_batch_automatically(self):
        audit=self.uncertain();before=audit.path.read_bytes()
        _,prior=self.recognise()
        current,_=Audit.existing(audit.folder)
        self.assertFalse(current.unresolved());self.assertEqual(prior['verified'],{'REG1'})
        self.assertTrue(current.path.read_bytes().startswith(before))
        self.assertEqual(current.events[-1]['origin'],'official_saved_report')
    def test_missing_receipt_never_settles_an_attempt(self):
        audit=self.uncertain();report=self.report();report.update(records=[],total=0);self.sign(report)
        with self.assertRaises(browser.UncertainSubmissionError):self.recognise(report)
        self.assertTrue(Audit.existing(audit.folder)[0].unresolved())
    def test_partial_batch_receipts_never_settle_entire_attempt(self):
        self.write_book(second=True);audit=self.uncertain();report=self.report();report['records']=report['records'][:1];report['total']=1;self.sign(report)
        with self.assertRaises(browser.UncertainSubmissionError):self.recognise(report)
        self.assertTrue(Audit.existing(audit.folder)[0].unresolved())
    def test_conflicting_marks_maximum_identity_attendance_and_status_block(self):
        for field,value in [('exam_roll','301000009'),('regno','REG9'),('name','Different student'),('status','Cancelled'),('rejection_reason','Rejected by board')]:
            report=self.report();report['records'][0][field]=value;self.sign(report)
            with self.subTest(field=field),self.assertRaises(ValueError):self.recognise(report)
    def test_rejected_award_on_portal_does_not_block_and_allows_resubmission(self):
        plan=self.plan('Mathematics');root=prepare_history_root(self.history)
        report=self.report(plan)
        report['records'][0]['status']='Rejected'
        report['records'][0]['rejection_reason']='test entry'
        self.sign(report)
        evidence=self.root/'official.json';evidence.write_text(json.dumps(report))
        result=saved.recognise_saved_awards(root,[plan],'school-test',report,evidence)
        self.assertEqual(result['Mathematics'],0) # not counted as saved, remaining pending for submission
    def test_wrong_scope_incomplete_or_tampered_report_rejected(self):
        for field,value in [('account','other-school'),('student_class','12'),('workbook_session','2026-27'),('coverage_complete',False),('url','https://example.invalid/report')]:
            report=self.report();report[field]=value;self.sign(report)
            with self.subTest(field=field),self.assertRaises(ValueError):self.recognise(report)
        report=self.report();report['records'][0]['marks']='20'
        with self.assertRaises(ValueError):self.recognise(report)
    def test_duplicate_receipts_rejected(self):
        report=self.report();report['records']*=2;report['total']=2;self.sign(report)
        with self.assertRaises(ValueError):self.recognise(report)
    def test_known_absence_issue_cannot_be_overridden_by_a_receipt(self):
        self.write_book(maths='AB');report=self.report();report['records'][0]['marks']='12';self.sign(report)
        result,prior=self.recognise(report)
        self.assertEqual(result['Mathematics'],0);self.assertEqual(prior['verified'],{'REG1'})
    def page(self,page=1,pages=1,total=1,rows=None):
        return dict(account='school-test',**{'class':'11'},status='',session='2026-2027',page_label=f'Page {page} of {pages} ({total} records)',headers=saved.HEADERS,
                    next_disabled=page==pages,rows=rows if rows is not None else [['1','11','REG1','301000001','Synthetic One','Mathematics','12','20','P','Requested','']])
    def test_reader_fetches_all_readonly_pages_with_exact_session_and_sequence(self):
        driver=Mock(current_url=saved.URL);driver.find_element.return_value.get_attribute.return_value='2026-2027'
        p1=self.page(1,2,2);p2=self.page(2,2,2);p2['rows'][0][0]='2';p2['rows'][0][2]='REG2';p2['rows'][0][3]='301000002'
        pages=iter([p1,p2])
        driver.execute_script.side_effect=lambda script:next(pages) if script==saved.SNAPSHOT else 'complete'
        with patch.object(saved,'Select'),patch.object(saved,'begin_read'),patch.object(saved,'wait_read') as wait:
            report=saved._read_saved_report_status(driver,'11','school-test','2025-26')
        self.assertEqual(report['total'],2);self.assertEqual(report['pages'],2);self.assertEqual(wait.call_count,2)
        clicked=[call.args[1] for call in driver.find_element.call_args_list if call.args[1] in {'bodypH_btnSearch','bodypH_btnNext'}]
        self.assertEqual(clicked,['bodypH_btnSearch','bodypH_btnNext'])
    def test_changed_filters_headers_count_or_paging_rejected(self):
        for field,value in [('class','12'),('status','Approved'),('session','2025-2026'),('headers',[]),('next_disabled',False),('page_label','Page 2 of 2 (1 records)')]:
            data=self.page();data[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):saved.validate_page(data,'11','school-test','2026-2027',1)
    def test_batch_discovers_external_saved_awards_and_skips_without_marks_actions(self):
        jobs=self.jobs(subjects=['MA']);driver=Mock();reader=Mock(return_value=self.report())
        with patch.object(browser,'run') as runner:
            result=batch.run_jobs(jobs,self.file,self.history,'school-test',student_class='11',session='2025-26',execute=True,confirm_session=True,driver_factory=Mock(return_value=driver),login_callback=Mock(),report_session='Auto',verify_saved=True,saved_report_reader=reader)
        reader.assert_called_once();runner.assert_not_called();driver.find_element.assert_not_called()
        self.assertEqual(result['subjects'][0]['status'],'skipped_verified_history')
        self.assertEqual(result['new_verified_saved_count'],0)
    def test_batch_recovers_uncertain_attempt_from_official_report_before_history_gate(self):
        audit=self.uncertain();jobs=self.jobs(subjects=['MA']);driver=Mock()
        with patch.object(browser,'run') as runner:
            result=batch.run_jobs(jobs,self.file,self.history,'school-test',student_class='11',session='2025-26',execute=True,confirm_session=True,driver_factory=Mock(return_value=driver),login_callback=Mock(),report_session='Auto',verify_saved=True,saved_report_reader=Mock(return_value=self.report()))
        runner.assert_not_called();driver.find_element.assert_not_called()
        self.assertEqual(result['subjects'][0]['status'],'skipped_verified_history')
        self.assertFalse(Audit.existing(audit.folder)[0].unresolved())
    def test_saved_report_failure_stops_before_any_submission(self):
        with patch.object(browser,'run') as runner:
            with self.assertRaisesRegex(ValueError,'Report unavailable'):
                batch.run_jobs(self.jobs(subjects=['MA']),self.file,self.history,'school-test',student_class='11',session='2025-26',execute=True,confirm_session=True,driver_factory=Mock(return_value=Mock()),login_callback=Mock(),report_session='Auto',verify_saved=True,saved_report_reader=Mock(side_effect=ValueError('Report unavailable')))
        runner.assert_not_called()
    def test_readonly_receipt_check_skips_completed_subject_missing_from_pending_dropdown(self):
        with patch.object(browser,'run') as runner:
            result=batch.run_jobs(self.jobs(subjects=['MA']),self.file,self.history,'school-test',student_class='11',session='2025-26',execute=False,confirm_session=True,driver_factory=Mock(return_value=Mock()),login_callback=Mock(),verify_saved=True,saved_report_reader=Mock(return_value=self.report()))
        runner.assert_not_called()
        self.assertEqual(result['subjects'][0]['status'],'skipped_verified_history')
    def test_actual_saved_report_javascript_extracts_the_verified_columns(self):
        import subprocess
        script=r"""
const code=JSON.parse(process.argv[1]);const assert=require('assert');
const headers=['Sr.','Class','Registration No.','Roll No.','Name','Subject','Marks','Out Of Marks','Present/Absent','Status','Rejection Reason'];
const row=['1','11','REG1','301000001','Synthetic One','Mathematics','12','20','P','Requested',''];
const tr={querySelector:()=>true,cells:row.map(innerText=>({innerText}))};
const grid={querySelectorAll:s=>s==='th'?headers.map(innerText=>({innerText})):[tr]};
const document={body:{innerText:'Hello school-test'},getElementById:id=>({bodypH_gvMarks:grid,bodypH_ddlClass:{value:'11'},bodypH_ddlStatus:{value:''},bodypH_txtSession:{value:'2026-2027'},bodypH_lblPage:{innerText:'Page 1 of 1 (1 records)'},bodypH_btnNext:{disabled:true}})[id]};
const result=Function('document',code)(document);
assert.deepEqual(result.headers,headers);assert.deepEqual(result.rows,[row]);assert.equal(result.class,'11');assert.equal(result.session,'2026-2027');assert.equal(result.account,'school-test');assert.equal(result.next_disabled,true);console.log('verified');
"""
        result=subprocess.run(['node','-e',script,json.dumps(saved.SNAPSHOT)],capture_output=True,text=True,check=True)
        self.assertIn('verified',result.stdout)
    def test_final_receipts_allow_next_subject_after_completed_dropdown_disappears(self):
        jobs=self.jobs(subjects=['PH','MA']);driver=Mock();active={};completed=set();clicks=[]
        def open_subject(d,plan,stop):active['subject']=plan.subject
        def snapshot(d,plan,account,**kwargs):
            if plan.subject in completed:raise ValueError('Completed subject disappeared from entry dropdown')
            return self.state(plan)
        def click():clicks.append(active['subject']);completed.add(active['subject'])
        driver.find_element.return_value.click.side_effect=click
        def official(*args):
            data=self.report();data['records']=[]
            for job in jobs:
                if job['subject'] in completed:data['records'].extend(self.report(job['plan'])['records'])
            data['total']=len(data['records']);return self.sign(data)
        with patch.object(browser,'open_subject',side_effect=open_subject),patch.object(browser,'snapshot',side_effect=snapshot),patch.object(browser,'_evidence',return_value='synthetic'),patch.object(browser,'_fill',side_effect=lambda d,p,b,*args:b),patch.object(browser,'_begin_read'),patch.object(browser,'_wait_page'):
            result=batch.run_jobs(jobs,self.file,self.history,'school-test',student_class='11',session='2025-26',execute=True,confirm_session=True,confirm_callback=Mock(return_value=True),driver_factory=Mock(return_value=driver),login_callback=Mock(),verify_saved=True,saved_report_reader=official)
        self.assertEqual(clicks,['Physics','Mathematics']);self.assertEqual(result['new_verified_saved_count'],2)
        self.assertTrue(all(r['status']=='saved_subject_verified' for r in result['subjects']))
