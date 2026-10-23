import json,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock,patch
import test_internal_batch as fixtures
import test_internal_students_report as roster_fixtures
import test_internal_saved_report as saved_fixtures
from jkbose_tool.features import internal_assessment_batch as batch,internal_assessment_browser as browser
from jkbose_tool.features.internal_assessment_match_check import save_match_check,load_match_check
from jkbose_tool.features.internal_assessment import prepare_history_root

class MatchCheckTests(unittest.TestCase):
    setUp=fixtures.ClassRunTests.setUp
    write_book=fixtures.ClassRunTests.write_book
    plan=fixtures.ClassRunTests.plan
    jobs=fixtures.ClassRunTests.jobs
    state=fixtures.ClassRunTests.state
    def proof(self):
        root=prepare_history_root(self.history);folder=root/'_class_runs'/'synthetic';folder.mkdir(parents=True)
        for name in ('events.jsonl','report.json','official_saved_assessment_report.json','snapshot.json'):(folder/name).write_text('{}')
        jobs=self.jobs(subjects=['MA']);path=save_match_check(root,[jobs[0]['plan']],'school-test','Auto',folder,folder/'snapshot.json')
        return root,jobs,path,folder
    def test_matching_scope_reuses_evidence(self):
        root,jobs,path,folder=self.proof()
        self.assertEqual(load_match_check(root,[jobs[0]['plan']],'school-test','Auto')['path'],str(path))
    def test_account_selection_config_or_workbook_changes_require_matching_again(self):
        root,jobs,path,folder=self.proof()
        variants=[([jobs[0]['plan']],'different-school','Auto'),([self.plan('Physics')],'school-test','Auto'),([jobs[0]['plan']],'school-test','2026-2027')]
        for plans,account,session in variants:
            with self.assertRaisesRegex(ValueError,'Match read only again'):load_match_check(root,plans,account,session)
        self.write_book(maths=13)
        with self.assertRaises(ValueError):load_match_check(root,[jobs[0]['plan']],'school-test','Auto')
    def test_expired_or_modified_evidence_rejected(self):
        root,jobs,path,folder=self.proof();plans=[jobs[0]['plan']]
        with self.assertRaises(ValueError):load_match_check(root,plans,'school-test','Auto',now=datetime.now(timezone.utc)+timedelta(days=2))
        (folder/'snapshot.json').write_text('{"changed":true}')
        with self.assertRaises(ValueError):load_match_check(root,plans,'school-test','Auto')
    def test_path_escape_reference_rejected(self):
        root,jobs,path,folder=self.proof();data=json.loads(path.read_text());data['proofs']['../../outside']='bad';path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):load_match_check(root,[jobs[0]['plan']],'school-test','Auto')
    def test_automatic_submit_without_required_live_report_settings_stops_before_browser(self):
        factory=Mock();confirm=Mock()
        with self.assertRaisesRegex(ValueError,'complete live report preflight'):
            batch.run_jobs(self.jobs(subjects=['MA']),self.file,self.history,'school-test',student_class='11',session='2025-26',execute=True,confirm_session=True,verify_saved=False,automatic_submit=True,report_session='Auto',driver_factory=factory,confirm_callback=confirm)
        factory.assert_not_called();confirm.assert_not_called()
    def test_gui_submit_shows_one_preview_without_requiring_match(self):
        from jkbose_tool.internal_assessment_gui import InternalAssessmentGUI
        app=Mock();app.ia={key:Mock(get=Mock(return_value=value)) for key,value in
            {'file':'synthetic.xlsx','class':'11','session':'2025-26','history':'private-history','account':'school-test','report_session':'Auto'}.items()}
        app._internal_jobs.return_value=['synthetic-plan']
        app._internal_preview.return_value=['synthetic-plan']
        InternalAssessmentGUI._start_internal(app,True)
        app._internal_preview.assert_called_once_with(require_confirm=True)
        kwargs=app._start_task.call_args.args[2]
        self.assertTrue(kwargs['execute']);self.assertTrue(kwargs['automatic_submit'])
        self.assertNotIn('confirm_callback',kwargs)
    def test_cancelled_submit_preview_does_not_start_work(self):
        from jkbose_tool.internal_assessment_gui import InternalAssessmentGUI
        app=Mock();app._internal_preview.return_value=None
        InternalAssessmentGUI._start_internal(app,True)
        app._start_task.assert_not_called()
    def test_readonly_then_submit_reuses_roster_without_batch_confirmation(self):
        self.submit_workflow(True)
    def test_submit_alone_runs_full_preflight_without_batch_confirmation(self):
        self.submit_workflow(False)
    def submit_workflow(self,use_match):
        jobs=self.jobs(subjects=['MA']);driver=Mock();done=[]
        driver.find_element.return_value.click.side_effect=lambda:done.append(True)
        helper=saved_fixtures.SavedReportTests()
        def official(*args):
            data=helper.report(jobs[0]['plan'])
            if not done:data.update(records=[],total=0)
            return helper.sign(data)
        options=dict(student_class='11',session='2025-26',confirm_session=True,verify_saved=True,report_session='Auto',driver_factory=Mock(return_value=driver),login_callback=Mock(),saved_report_reader=official)
        confirm=Mock(side_effect=AssertionError('No per-batch confirmation after validated Match'))
        with patch.object(browser,'open_subject'),patch.object(browser,'snapshot',side_effect=lambda d,p,a,**k:self.state(p)),patch.object(browser,'_evidence',return_value='synthetic'),patch.object(browser,'_fill',side_effect=lambda d,p,b,*args:b),patch.object(browser,'_begin_read'),patch.object(browser,'_wait_page'):
            if use_match:batch.run_jobs(jobs,self.file,self.history,'school-test',report_reader=Mock(return_value=roster_fixtures.StudentsReportTests().snapshot()),**options)
            reader=Mock(side_effect=AssertionError('Students Report should be reused')) if use_match else Mock(return_value=roster_fixtures.StudentsReportTests().snapshot())
            result=batch.run_jobs(self.jobs(subjects=['MA']),self.file,self.history,'school-test',execute=True,automatic_submit=True,confirm_callback=confirm,report_reader=reader,**options)
        self.assertEqual(len(done),1);self.assertEqual(result['new_verified_saved_count'],1)
        confirm.assert_not_called()
        if use_match:reader.assert_not_called()
        else:reader.assert_called_once()
