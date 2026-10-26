"""Interrupted approval verification and read-only download overlay regression tests."""
from pathlib import Path
from copy import deepcopy
from html import escape
import json,hashlib,unittest
from unittest.mock import Mock,patch
import test_internal_approval as fixtures
from selenium.common.exceptions import ElementClickInterceptedException
from jkbose_tool.features import internal_assessment_approval as approval

class ApprovalResumeTests(unittest.TestCase):
    setUp=fixtures.PrincipalTests.setUp;write_book=fixtures.PrincipalTests.write_book;jobs=fixtures.PrincipalTests.jobs;rows=fixtures.PrincipalTests.rows;roster=fixtures.PrincipalTests.roster;run_approval=fixtures.PrincipalTests.run_approval;journal=fixtures.PrincipalTests.journal
    def export(self,journal,label,rows):
        path=journal.folder/'Runs'/'synthetic-recovery'/label;path.parent.mkdir(parents=True,exist_ok=True)
        if not rows and path.suffix=='.json':
            data=dict(account='prin000001',**{'class':'11'},headers=['There are no pending requests to display.'],rows=[],total='0',empty_text='There are no pending requests to display.',page=[],pager=[]);path.write_text(json.dumps(data))
        else:
            raw=['<table><tr>'+''.join('<th>'+h+'</th>'for h in approval.EXPORT_HEADERS)+'</tr>']
            for r in rows:raw.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>'for v in [r['id'],r['class_name'],r['exam_roll'],r['regno'],r['name'],r['subject'],r['attendance'],r['marks'],r['maximum'],r['requested_on']])+'</tr>')
            path.write_text(''.join(raw)+'</table>',encoding='utf-8')
        return dict(file=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),total=len(rows))
    def interrupted(self,submitted=True):
        rows=self.rows();journal=self.journal();proof=self.export(journal,'before.xls',rows);journal.append('approval_open_attempt',request=rows[0],evidence=proof,source_sha256='synthetic')
        if submitted:journal.append('approval_submit_attempt',request_id=rows[0]['id'],request=rows[0])
        return journal,rows
    def test_exact_single_removal_recovers_receipt_without_repeating_decision(self):
        journal,rows=self.interrupted();after=rows[1:];proof=self.export(journal,'after.xls',after)
        self.assertEqual(approval.reconcile_interrupted_approvals(journal,after,proof),['1']);self.assertEqual(journal.unresolved(),{});self.assertEqual(journal.approved(),{'1'})
        self.assertEqual(approval.reconcile_interrupted_approvals(journal,after,proof),[])
    def test_current_pending_or_extra_change_never_claims_approval(self):
        for mutate in ['still_pending','other_changed','all_removed']:
            with self.subTest(mutate=mutate):
                journal,rows=self.interrupted();after=deepcopy(rows)if mutate=='still_pending'else deepcopy(rows[1:])if mutate=='other_changed'else[]
                if mutate=='other_changed':after[0]['marks']='9'
                proof=self.export(journal,'no-proof.xls',after);self.assertEqual(approval.reconcile_interrupted_approvals(journal,after,proof),[]);self.assertIn('1',journal.unresolved())
    def test_tampered_export_never_recovers(self):
        journal,rows=self.interrupted();proof=self.export(journal,'after.xls',rows[1:]);proof['sha256']='wrong'
        self.assertEqual(approval.reconcile_interrupted_approvals(journal,rows[1:],proof),[])
    def test_opening_popup_without_submit_never_recovers(self):
        journal,rows=self.interrupted(False);proof=self.export(journal,'after.xls',rows[1:])
        self.assertEqual(approval.reconcile_interrupted_approvals(journal,rows[1:],proof),[])
    def test_final_single_request_recovers_from_valid_empty_grid_evidence(self):
        journal=self.journal();row=self.rows()[0];proof=self.export(journal,'one.xls',[row]);journal.append('approval_open_attempt',request=row,evidence=proof);journal.append('approval_submit_attempt',request_id=row['id'],request=row)
        after=self.export(journal,'empty.json',[]);self.assertEqual(approval.reconcile_interrupted_approvals(journal,[],after),['1'])
    def test_intercepted_read_only_download_is_retried_until_toast_clears(self):
        driver=Mock();button=driver.find_element.return_value;button.click.side_effect=[ElementClickInterceptedException('toast'),None];portal=approval.PrincipalPortal(driver,self.root/'downloads','11','prin000001');data=dict(total='7',approve_visible=False,reject_visible=False);portal.snapshot=Mock(return_value=data)
        portal.click_download(data);self.assertEqual(button.click.call_count,2);self.assertTrue(all(c.args[1]=='bodypH_btnDownloadExcel'for c in driver.find_element.call_args_list))
    def test_changed_queue_stops_before_read_only_click(self):
        driver=Mock();portal=approval.PrincipalPortal(driver,self.root/'downloads','11','prin000001');portal.snapshot=Mock(return_value=dict(total='6',approve_visible=False,reject_visible=False))
        with self.assertRaisesRegex(ValueError,'queue/popup changed'):portal.click_download(dict(total='7'))
        driver.find_element.assert_not_called()
    def test_failed_gui_run_keeps_browser_for_inspection(self):
        portal=fixtures.FakePortal(self.rows());portal.fail_after_save=True;driver=Mock()
        with self.assertRaisesRegex(RuntimeError,'Disconnected'):self.run_approval(portal,True,on_driver_ready=Mock(),driver_factory=Mock(return_value=driver))
        driver.quit.assert_not_called();self.assertIs(driver._jkbose_keep_open,True);self.assertEqual(portal.confirms,['1'])
    def test_gui_retains_only_a_browser_explicitly_kept_for_inspection(self):
        import gui_main
        app=gui_main.App.__new__(gui_main.App);driver=Mock();app.current_driver=driver
        app._release_driver_reference();self.assertIsNone(app.current_driver)
        driver._jkbose_keep_open=True;app.current_driver=driver;app._release_driver_reference();self.assertIs(app.current_driver,driver)

    def test_force_close_releases_retained_browser_for_a_new_run(self):
        import gui_main
        app=gui_main.App.__new__(gui_main.App);driver=Mock();driver._jkbose_keep_open=True;app.current_driver=driver;app.stop_event=Mock()
        with patch.object(gui_main.messagebox,'askyesno',return_value=True):app.force_close_browser()
        driver.quit.assert_called_once();app.stop_event.set.assert_called_once();self.assertIsNone(app.current_driver)

class FastPortal(fixtures.FakePortal):
    verify_transition=approval.PrincipalPortal.verify_transition
    def __init__(self,rows,folder):super().__init__(rows);self.folder=folder;folder.mkdir(exist_ok=True)
    def snapshot(self):
        return dict(total=str(len(self.rows)),page=['1']if self.rows else [],approve_visible=False,reject_visible=False,rows=[dict(cells=[r['class_name'],r['exam_roll'],r['regno'],r['name'],r['subject'],r['marks'],r['maximum'],r['requested_on']])for r in self.rows[:10]])
    def open_approval(self,r):self.opens.append(r['id']);self.approval_context=dict(request=dict(r),before=self.snapshot(),confirmed=False)
    def confirm(self,r):super().confirm(r);self.approval_context['confirmed']=True

class FastProgressTests(unittest.TestCase):
    setUp=fixtures.PrincipalTests.setUp;write_book=fixtures.PrincipalTests.write_book;jobs=fixtures.PrincipalTests.jobs;rows=fixtures.PrincipalTests.rows;roster=fixtures.PrincipalTests.roster;run_approval=fixtures.PrincipalTests.run_approval;journal=fixtures.PrincipalTests.journal
    def test_class_mode_has_no_per_award_excel_download_and_reports_progress(self):
        base_rows=self.rows();roster=self.roster();base=roster['rows'][0];roster['rows']=[];rows=[]
        for i in range(6):
            reg='REG'+str(i+1);exam=str(301000001+i);name='Synthetic '+str(i+1);student=deepcopy(base);student.update(regno=reg,exam_roll=exam,name=name,sequence=str(i+1));roster['rows'].append(student)
            for r in base_rows:rows.append(dict(r,id=str(len(rows)+1),regno=reg,exam_roll=exam,name=name))
        portal=FastPortal(rows,self.root/'fast-proofs');updates=[]
        result,_,_=self.run_approval(portal,True,approval_mode='class_all',student_class='11',session='2025-26',report_reader=Mock(return_value=roster),on_progress=updates.append)
        self.assertEqual(len(portal.confirms),12);self.assertEqual(portal.reads,3);self.assertEqual(result['status'],'finished')
        self.assertEqual(updates[0]['students_total'],6);self.assertEqual(updates[-1]['verified'],12);self.assertEqual(updates[-1]['remaining'],0);self.assertEqual(updates[-1]['students_remaining'],0)
        self.assertEqual([e['remaining']for e in updates[1:-1]],list(range(11,-1,-1)))
    def test_transition_requires_bound_completed_response(self):
        rows=self.rows();portal=FastPortal(rows,self.root/'fast-proofs');portal.open_approval(rows[0])
        with self.assertRaisesRegex(ValueError,'completed response'):portal.verify_transition(rows,rows[0])
    def test_unchanged_or_multiple_removed_records_are_not_accepted(self):
        for remaining in [self.rows(),[]]:
            portal=FastPortal(self.rows(),self.root/'fast-proofs');before=deepcopy(portal.rows);portal.open_approval(before[0]);portal.approval_context['confirmed']=True;portal.rows=remaining
            with self.assertRaisesRegex(ValueError,'exactly one'):portal.verify_transition(before,before[0])
    def test_changed_other_visible_marks_are_not_accepted(self):
        rows=self.rows();portal=FastPortal(rows,self.root/'fast-proofs');portal.open_approval(rows[0]);portal.confirm(rows[0]);portal.rows[0]['marks']='9'
        with self.assertRaisesRegex(ValueError,'differ'):portal.verify_transition(rows,rows[0])
    def test_ui_progress_is_determinate_and_separates_students_from_awards(self):
        import gui_main
        app=gui_main.App.__new__(gui_main.App);app.approval_progress_frame=Mock();app.approval_progress_bar=Mock();app.approval_progress_var=Mock()
        data=dict(student_class='11',verified=875,total_records=882,remaining=7,students_remaining=2,students_total=196,held=0)
        app._show_approval_progress(data);app.approval_progress_bar.configure.assert_called_once_with(maximum=882,value=875)
        label=app.approval_progress_var.set.call_args.args[0];self.assertIn('7 awards remaining',label);self.assertIn('2/196 students pending',label)

if __name__=='__main__':unittest.main()
