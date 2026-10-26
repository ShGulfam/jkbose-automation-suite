"""Synthetic approval-mode coverage. No live portal or decision is used."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock,patch
import json,unittest
import test_internal_approval as fixtures
FakePortal=fixtures.FakePortal
from jkbose_tool.features import internal_assessment_approval as approval

class ApprovalModesTests(unittest.TestCase):
    setUp=fixtures.PrincipalTests.setUp;write_book=fixtures.PrincipalTests.write_book;jobs=fixtures.PrincipalTests.jobs;rows=fixtures.PrincipalTests.rows;roster=fixtures.PrincipalTests.roster;run_approval=fixtures.PrincipalTests.run_approval;journal=fixtures.PrincipalTests.journal
    def test_entire_class_needs_no_workbook_and_approves_changed_portal_marks(self):
        rows=self.rows();rows[0]['marks']='10';roster=self.roster();self.file.unlink();portal=FakePortal(rows);driver=Mock()
        result=approval.run_approval([],None,self.history,'sch000001','prin000001',approval_mode='class_all',student_class='11',session='2025-26',execute=True,confirm_session=True,
            driver_factory=lambda **k:driver,login_callback=Mock(),report_reader=Mock(return_value=roster),portal_factory=lambda *a:portal,confirm_callback=Mock(return_value=True))
        self.assertEqual(result['status'],'finished');self.assertEqual(portal.confirms,['1','2']);self.assertEqual(result['source'],'')
    def test_class_modes_finish_more_than_two_pages_and_exclusions_cover_every_subject(self):
        jobs=self.jobs();base_rows=self.rows(jobs);roster=self.roster();base=roster['rows'][0];roster['rows']=[];rows=[]
        for i in range(12):
            reg='REG'+str(i+1);exam=str(301000001+i);name='Synthetic '+str(i+1);student=deepcopy(base);student.update(regno=reg,exam_roll=exam,name=name,sequence=str(i+1));roster['rows'].append(student)
            for raw in base_rows:
                r=dict(raw,id=str(len(rows)+1),regno=reg,exam_roll=exam,name=name);rows.append(r)
        rows[0].update(attendance='A',marks='AB')
        portal=FakePortal(rows);result,_,_=self.run_approval(portal,True,approval_mode='class_except',exclusions=[('REG2','301000002')],student_class='11',session='2025-26',report_reader=Mock(return_value=roster))
        self.assertEqual(len(portal.confirms),20);self.assertEqual(len(portal.rows),4);self.assertEqual({r['regno'] for r in portal.rows},{'REG1','REG2'});self.assertEqual(result['status'],'finished_with_holds')
    def test_wrong_exclusion_pair_aborts_before_any_decision(self):
        portal=FakePortal(self.rows())
        with self.assertRaisesRegex(ValueError,'exclusion conflicts'):self.run_approval(portal,True,approval_mode='class_except',exclusions=[('REG1','301000099')],student_class='11',session='2025-26')
        self.assertEqual(portal.opens,[])
    def test_durable_hold_applies_without_a_workbook(self):
        from jkbose_tool.features.internal_assessment_policy import CohortAbsencePolicy
        from jkbose_tool.features.internal_assessment import prepare_history_root
        policy=CohortAbsencePolicy(prepare_history_root(self.history),'sch000001','11','2025-26');policy.add([dict(registration='REG1',exam_roll='301000001',subject='Education',reason='Known absence')],origin='test')
        portal=FakePortal(self.rows());result,_,_=self.run_approval(portal,True,approval_mode='class_all',student_class='11',session='2025-26')
        self.assertEqual(result['status'],'nothing_eligible');self.assertEqual(portal.confirms,[])
    def test_broad_mode_rejects_bad_identity_subject_and_below_pass(self):
        for field,value in [('name','Different Person'),('marks','1'),('attendance','A'),('exam_roll','301000099'),('subject','Healthcare')]:
            with self.subTest(field=field):
                rows=self.rows(self.jobs(['MA']));rows[0][field]=value;portal=FakePortal(rows)
                result,_,_=self.run_approval(portal,True,approval_mode='class_all',student_class='11',session='2025-26')
                self.assertEqual(result['status'],'nothing_eligible');self.assertEqual(portal.opens,[])
    def test_exclusion_parser_never_accepts_partial_or_conflicting_identifiers(self):
        for raw in ['REG1','REG1,123','REG1,301000001\nREG1,301000002','REG1,301000001\nREG2,301000001']:
            with self.assertRaises(ValueError):approval.parse_exclusions(raw)
        self.assertEqual(approval.parse_exclusions('REG1,301000001\nREG1,301000001'),{('REG1','301000001')})
    def test_exclusion_picker_reads_awards_and_scoped_fetched_requests(self):
        students=approval.exclusion_students(self.file,'11','2025-26','sch000001','prin000001');self.assertEqual(len(students),1)
        p=self.root/'fetched.json';p.write_text(json.dumps(dict(scope=dict(school='sch000001',principal='prin000001',**{'class':'11'},session='2025-26'),requests=[dict(request=r)for r in self.rows()])))
        self.assertEqual(len(approval.exclusion_students(p,'11','2025-26','sch000001','prin000001')),1)
        with self.assertRaisesRegex(ValueError,'different account'):approval.exclusion_students(p,'12','2025-26','sch000001','prin000001')
    def test_cli_all_class_does_not_require_excel_or_subject_arguments(self):
        import main
        args=main.build_parser().parse_args(['internal-approve','--approval-mode','class_all','--class','11','--session','2025-26','--school-account','sch000001','--principal-account','prin000001'])
        self.assertIsNone(args.excel_file);self.assertFalse(args.execute)
        with patch('jkbose_tool.features.internal_assessment_approval.run_approval')as run:
            main.cmd_internal_approve(student_class='11',session='2025-26',school_account='sch000001',principal_account='prin000001',approval_mode='class_all')
            self.assertEqual(run.call_args.kwargs['approval_mode'],'class_all');self.assertEqual(run.call_args.args[0],[])
    def test_class_mode_readonly_and_cancellation_never_decide(self):
        for execute in [False,True]:
            portal=FakePortal(self.rows());result,_,_=self.run_approval(portal,execute,confirm=Mock(return_value=False),approval_mode='class_all',student_class='11',session='2025-26')
            self.assertEqual(portal.opens,[]);self.assertEqual(result['status'],'cancelled' if execute else 'checked_read_only')

    def test_empty_class_queue_needs_no_student_report_or_workbook(self):
        portal=FakePortal([]);reader=Mock(side_effect=AssertionError('No report required for empty queue'))
        result,_,_=self.run_approval(portal,True,approval_mode='class_all',student_class='11',session='2025-26',report_reader=reader)
        self.assertEqual(result['status'],'nothing_eligible');reader.assert_not_called();self.assertEqual(portal.opens,[])
    def test_final_warning_states_class_session_counts_and_no_undo(self):
        rows=[dict(eligible=True),dict(eligible=False)]
        warning=approval.approval_confirmation_text(dict(scope={'class':'12','session':'2025-26'},rows=rows))
        self.assertIn('all 1 eligible awards in Class 12',warning);self.assertIn('session 2025-26',warning);self.assertIn('1 excluded or held',warning);self.assertIn('cannot be undone by this software',warning)
    def test_class_mode_keeps_portal_order_for_sequential_processing(self):
        rows=list(reversed(self.rows()));portal=FakePortal(rows)
        self.run_approval(portal,True,approval_mode='class_all',student_class='11',session='2025-26')
        self.assertEqual(portal.confirms,[r['id']for r in rows])

class ApprovalModeGuiTests(unittest.TestCase):
    def test_class_mode_start_does_not_load_a_workbook(self):
        import tkinter as tk
        from tkinter import ttk
        from jkbose_tool.internal_assessment_approval_gui import PrincipalApprovalGUI
        root=tk.Tk();root.withdraw()
        try:
            app=PrincipalApprovalGUI();app.root=root;app.ia={k:tk.StringVar(value=v)for k,v in dict(account='sch000001',file='',**{'class':'11'},session='2025-26',history='synthetic-history',report_session='Auto').items()};app._internal_jobs=Mock(side_effect=AssertionError('No workbook'));app._set_driver_ready=Mock();app._start_task=Mock()
            app._open_principal_approval();top=next(w for w in root.winfo_children()if isinstance(w,tk.Toplevel))
            def descendants(w):
                return [c for child in w.winfo_children() for c in [child,*descendants(child)]]
            widgets=descendants(top);combo=next(w for w in widgets if isinstance(w,ttk.Combobox));combo.set('Approve entire class');combo.event_generate('<<ComboboxSelected>>');root.update()
            next(w for w in widgets if isinstance(w,ttk.Button)and w.cget('text')=='Check requests (read only)').invoke()
            app._internal_jobs.assert_not_called();kwargs=app._start_task.call_args.args[2];self.assertEqual(kwargs['approval_mode'],'class_all');self.assertIsNone(kwargs['excel_file'])
        finally:root.destroy()

if __name__=='__main__':unittest.main()
