import copy
import hashlib
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jkbose_tool.features.internal_assessment import load_plan, match_batch, verify_transition, Audit, RunLock
from jkbose_tool.features import internal_assessment_browser as browser

class InternalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root / 'synthetic.xlsx'
        self.history = self.root / 'history'

    def matrix(self, rows=None, headers=None, title='INTERNAL ASSESSMENT — Class 11th', session='2025-26'):
        book = Workbook(); ws = book.active; ws.title = 'Awards_Matrix'
        ws.append(['Synthetic School']); ws.append([title]); ws.append([f'Session & Year: {session}']); ws.append([])
        ws.append(headers or ['S.No.', 'Class Roll No.', 'Exam Roll No.', 'Board Reg. No.', 'Student Name', 'Botany (BO)', 'Zoology (ZO)', 'Physics (PH)'])
        for index,row in enumerate(rows or [[1, '1', '201000001', '00000000000000001', 'Synthetic One', 2, 2, 4],
                            [2, '2', '201000002', '00000000000000002', 'Synthetic Two', 2.5, 2.5, 8]]):
            row=list(row)
            if row[2] in ('',None): row[2]=str(201000001+index)
            ws.append(row)
        book.save(self.path); book.close()

    def plan(self, **kwargs):
        kwargs.setdefault('maximum', '10')  # Explicit fallback for old matrices without metadata.
        return load_plan(self.path, session='2025-26', biology_component_max='5', **kwargs)

    def live(self, plan, count=None):
        return {'total': len(plan.awards) if count is None else count, 'class': '11', 'subject': plan.subject,
                'account': 'school-test', 'rows': [
            {'regno': award.regno, 'name': award.name, 'exam_roll': award.exam_roll, 'subject': plan.subject,
             'value': '', 'max': plan.maximum, 'min': '0', 'step': 'any', 'attendance': 'P', 'input_id': f'marks_{index}', 'disabled': False, 'readonly': False}
            for index, award in enumerate(plan.awards)]}

    def test_split_biology_combined_without_rounding_and_original_unchanged(self):
        self.matrix(); before = self.path.read_bytes(); plan = self.plan()
        self.assertEqual([a.marks for a in plan.awards], ['4', '5.0'])
        self.assertTrue(all(not a.issues for a in plan.awards)); self.assertEqual(plan.pass_marks, '4')
        self.assertEqual(plan.awards[0].regno, '00000000000000001')
        self.assertEqual(self.path.read_bytes(), before)

    def test_below_pass_absent_missing_and_zero_never_become_eligible(self):
        for raw in ['AB', '', None, 0, 1.9]:
            with self.subTest(raw=raw):
                self.matrix(rows=[[1, 1, '201000001', 'REG1', 'Synthetic One', raw, 1, 0]])
                plan = self.plan(); self.assertTrue(plan.awards[0].issues)
                _, problems = match_batch(plan, self.live(plan)); self.assertTrue(problems)

    def test_other_subjects_use_40_percent_of_their_maximum(self):
        self.matrix(rows=[[1, 1, '', 'REG1', 'Synthetic One', 2, 2, 9.99]])
        plan = self.plan(subject='Physics', maximum='25'); self.assertEqual(plan.pass_marks, '10')
        self.assertTrue(plan.awards[0].issues)
        self.matrix(rows=[[1, 1, '', 'REG1', 'Synthetic One', 2, 2, 10]])
        self.assertFalse(self.plan(subject='Physics', maximum='25').awards[0].issues)
        with self.assertRaises(ValueError): load_plan(self.path, session='2025-26', subject='Physics', pass_percent='33')

    def test_biology_requires_explicit_component_max_and_both_columns(self):
        self.matrix()
        with self.assertRaises(ValueError): load_plan(self.path, session='2025-26')
        self.matrix(headers=['S.No.', 'Class Roll No.', 'Exam Roll No.', 'Board Reg. No.', 'Student Name', 'Biology (BI)'],
                    rows=[[1, 1, '', 'REG1', 'Synthetic One', 10]])
        with self.assertRaises(ValueError): self.plan()

    def test_over_max_components_block_instead_of_clamping(self):
        self.matrix(rows=[[1, 1, '', 'REG1', 'Synthetic One', 6, 2, 5]])
        self.assertTrue(self.plan().awards[0].issues)

    def test_wrong_class_session_and_external_matrix_are_rejected(self):
        for title, session in [('EXTERNAL PRACTICAL — Class 11th', '2025-26'),
                               ('INTERNAL ASSESSMENT — Class 12th', '2025-26'),
                               ('INTERNAL ASSESSMENT — Class 11th', '2024-25')]:
            self.matrix(title=title, session=session)
            with self.assertRaises(ValueError): self.plan()

    def test_duplicate_awards_formula_and_rounded_registration_are_rejected(self):
        for rows in [
            [[1, 1, '', 'REG1', 'Synthetic One', 2, 2, 4], [2, 1, '', 'REG1', 'Synthetic One', 2, 2, 4]],
            [[1, 1, '', 'REG1', 'Synthetic One', '=2+2', 2, 4]],
            [[1, 1, '', 24010000000000001, 'Synthetic One', 2, 2, 4]]
        ]:
            self.matrix(rows=rows)
            with self.assertRaises(ValueError): self.plan()

    def test_row_based_portal_headers_code_name_and_component_maximum(self):
        book = Workbook(); ws = book.active; ws.title = 'Awards_Matrix'
        ws.append(['Class', 'Session', 'Evaluation Type', 'Subject Code', 'Subject Name', 'Board Registration Number', 'Exam Roll No', 'Class Roll No', 'Student Name', 'Practical Marks', 'Max Marks'])
        ws.append(['11th', '2025-26', 'internal', 'BO', 'Botany', 'REG1', '201000001', '1', 'Synthetic One', 2, 5])
        ws.append(['11th', '2025-26', 'internal', 'ZO', 'Zoology', 'REG1', '201000001', '1', 'Synthetic One', 3, 5])
        book.save(self.path); book.close()
        plan = self.plan(); self.assertEqual(plan.awards[0].marks, '5'); self.assertFalse(plan.awards[0].issues)

    def test_identity_attendance_maximum_existing_marks_and_reappearing_awards_block_whole_batch(self):
        self.matrix(); plan = self.plan()
        for field, value in [('regno', 'UNKNOWN'), ('name', 'Different Name'), ('exam_roll', '9'),
                             ('attendance', 'A'), ('max', '5'), ('value', '9'), ('disabled', True)]:
            live = self.live(plan); live['rows'][1][field] = value
            awards, problems = match_batch(plan, live)
            self.assertTrue(problems)
        live = self.live(plan)
        _, problems = match_batch(plan, live, [plan.awards[0].regno]); self.assertTrue(problems)

    def test_transition_requires_exact_count_and_disappearance(self):
        self.matrix(); before = self.live(self.plan(), 3)
        after = copy.deepcopy(before); after['total'] = 1; after['rows'] = [{'regno': 'REG3'}]
        self.assertTrue(verify_transition(before, after))
        for total, rows in [(2, [{'regno': 'REG3'}]), (1, before['rows'][:1]), (0, []), (1, [])]:
            self.assertFalse(verify_transition(before, {'total': total, 'rows': rows}))

    def test_durable_audit_report_integrity_and_uncertain_resume(self):
        self.matrix(); plan = self.plan(); audit = Audit(self.history, plan)
        audit.append('submit_attempt', batch_id='batch1', registrations=['REG1'])
        self.assertEqual(Audit(self.history, plan).unresolved(), {'batch1'})
        audit.report(plan); self.assertTrue((audit.folder/'report.json').exists())
        with self.assertRaises(ValueError): browser._pending_history(self.history, plan)
        audit.append('verified_saved', batch_id='batch1', registrations=['REG1'])
        self.assertFalse(Audit(self.history, plan).unresolved())
        content = audit.path.read_text(); audit.path.write_text(content.replace('REG1', 'REG2'))
        with self.assertRaises(ValueError): Audit(self.history, plan)

    def test_history_lock_blocks_concurrent_runs(self):
        with RunLock(self.history):
            with self.assertRaises(ValueError):
                with RunLock(self.history): pass
        self.assertFalse((self.history/'internal-assessment.lock').exists())

    def test_pending_blocking_batch_never_fills_or_clicks(self):
        self.matrix(rows=[[1, 1, '', 'REG1', 'Synthetic One', 'AB', 2, 4]])
        plan = self.plan(); live = self.live(plan); driver = Mock()
        with patch.object(browser, 'open_subject'), patch.object(browser, 'snapshot', return_value=live), \
             patch.object(browser, '_evidence', return_value='synthetic-evidence'), patch.object(browser, '_fill') as fill:
            browser.run(driver, plan, self.history, 'school-test', Mock(return_value=True), submit=True, confirm_session=True)
        fill.assert_not_called(); driver.find_element.assert_not_called()

    def test_read_only_and_declined_confirmation_never_fill_or_save(self):
        self.matrix(); plan = self.plan(); driver = Mock(); live = self.live(plan)
        for submit in [False, True]:
            with patch.object(browser, 'open_subject'), patch.object(browser, 'snapshot', return_value=live), \
                 patch.object(browser, '_evidence', return_value='synthetic-evidence'), patch.object(browser, '_fill') as fill:
                browser.run(driver, plan, self.history, 'school-test', Mock(return_value=False), submit=submit, confirm_session=True)
            fill.assert_not_called(); driver.find_element.assert_not_called()

    def test_save_timeout_is_logged_before_click_and_never_retried(self):
        self.matrix(); plan = self.plan(); driver = Mock(); live = self.live(plan)
        with patch.object(browser, 'open_subject'), patch.object(browser, 'snapshot', return_value=live), \
             patch.object(browser, '_evidence', return_value='synthetic-evidence'), patch.object(browser, '_fill', return_value=live), \
             patch.object(browser.time, 'monotonic', side_effect=[0, 41]):
            with self.assertRaises(ValueError):
                browser.run(driver, plan, self.history, 'school-test', Mock(return_value=True), submit=True, confirm_session=True)
        driver.find_element.return_value.click.assert_called_once()
        self.assertTrue(Audit(self.history, plan).unresolved())
        with self.assertRaises(ValueError): browser._pending_history(self.history, plan)

    def test_verified_save_reloads_queue_and_records_only_verified_batch(self):
        self.matrix(); plan = self.plan(); driver = Mock(); before = self.live(plan)
        after = self.live(plan, 0); after['rows'] = []
        driver.switch_to = Mock()
        type(driver.switch_to).alert = property(lambda _: (_ for _ in ()).throw(browser.NoAlertPresentException()))
        with patch.object(browser, 'open_subject'), patch.object(browser, 'snapshot', side_effect=[before, before, after, after, after]), \
             patch.object(browser, '_evidence', return_value='synthetic-evidence'), patch.object(browser, '_fill', return_value=before), patch.object(browser, 'show_students') as reload:
            browser.run(driver, plan, self.history, 'school-test', Mock(return_value=True), submit=True, confirm_session=True)
        reload.assert_called_once(); driver.find_element.return_value.click.assert_called_once()
        audit = Audit(self.history, plan)
        self.assertEqual(audit.verified(), {award.regno for award in plan.awards}); self.assertFalse(audit.unresolved())

    def test_class_roll_never_used_as_registration_fallback(self):
        self.matrix(rows=[[1, 1, '201000001', None, 'Synthetic One', 2, 2, 4]])
        with self.assertRaises(ValueError): self.plan()

    def test_non_enrolled_x_is_excluded_but_live_unexpected_student_still_blocks(self):
        self.matrix(rows=[[1, 1, '', 'REG1', 'Synthetic One', 'x', 'x', 5], [2, 2, '', 'REG2', 'Synthetic Two', 2, 3, 5]])
        plan = self.plan(); self.assertEqual([a.regno for a in plan.awards], ['REG2'])
        live = self.live(plan); live['rows'][0]['regno'] = 'REG1'
        self.assertTrue(match_batch(plan, live)[1])

    def test_policy_rechecked_even_if_cached_plan_marks_are_changed(self):
        self.matrix(); plan = self.plan(); plan.awards[0].marks = '3.9'
        self.assertTrue(match_batch(plan, self.live(plan))[1])
        plan.awards[0].marks = '8'
        self.assertTrue(match_batch(plan, self.live(plan))[1])

    def test_integer_only_live_input_blocks_fractional_source(self):
        self.matrix(); plan = self.plan(); plan.awards[1].marks = '4.5'; plan.awards[1].components['Zoology'] = '2'
        live = self.live(plan); live['rows'][1]['step'] = '1'
        self.assertTrue(match_batch(plan, live)[1])

    def test_stopped_before_first_page_never_fills_or_saves(self):
        self.matrix(); plan = self.plan(); driver = Mock(); stop = threading.Event(); stop.set()
        with patch.object(browser, 'open_subject'):
            with self.assertRaises(browser.AssessmentStopped):
                browser.run(driver, plan, self.history, 'school-test', Mock(return_value=True), stop_event=stop, submit=True, confirm_session=True)
        driver.find_element.assert_not_called()

    def test_changed_source_cannot_bypass_related_uncertain_attempt(self):
        self.matrix(); plan = self.plan(); audit = Audit(self.history, plan)
        audit.append('submit_attempt', batch_id='uncertain', registrations=[plan.awards[0].regno])
        self.matrix(rows=[[1, 1, '', 'REG1', 'Synthetic One', 3, 3, 7]])
        changed = self.plan(); self.assertNotEqual(changed.digest(), plan.digest())
        with self.assertRaises(ValueError): browser._pending_history(self.history, changed)

    def test_workbook_changed_after_preview_never_opens_page(self):
        self.matrix(); plan = self.plan(); self.matrix(rows=[[1, 1, '', 'REG1', 'Synthetic One', 3, 3, 7]])
        with patch.object(browser, 'open_subject') as open_page:
            with self.assertRaises(ValueError): browser.run(Mock(), plan, self.history, 'school-test', Mock(), confirm_session=True)
        open_page.assert_not_called()

    def test_snapshot_rejects_login_redirect_wrong_school_and_nonfirst_page(self):
        self.matrix(); plan = self.plan(); driver = Mock()
        driver.current_url = 'https://jkbose.jk.gov.in/utilities/auth_pages/login.aspx'
        with self.assertRaises(ValueError): browser.snapshot(driver, plan, 'school-test')
        driver.current_url = browser.URL
        live = self.live(plan); live.update(save_enabled=True, page=2)
        driver.execute_script.return_value = live
        with self.assertRaises(ValueError): browser.snapshot(driver, plan, 'school-test')
        live['page'] = 1; live['account'] = 'wrong-school'
        with self.assertRaises(ValueError): browser.snapshot(driver, plan, 'school-test')

    def test_two_batches_are_processed_by_refreshed_pending_queue(self):
        self.matrix(); plan = self.plan(); driver = Mock(); first = self.live(plan, 2)
        first['rows'] = first['rows'][:1]
        second = self.live(plan, 1); second['rows'] = second['rows'][1:]
        empty = self.live(plan, 0); empty['rows'] = []
        driver.switch_to = Mock()
        type(driver.switch_to).alert = property(lambda _: (_ for _ in ()).throw(browser.NoAlertPresentException()))
        states = [first, first, second, second, second, second, empty, empty, empty]
        with patch.object(browser, 'open_subject'), patch.object(browser, 'snapshot', side_effect=states), \
             patch.object(browser, '_evidence', return_value='synthetic'), patch.object(browser, '_fill', side_effect=[first, second]), \
             patch.object(browser, 'show_students') as reload:
            browser.run(driver, plan, self.history, 'school-test', Mock(return_value=True), submit=True, confirm_session=True)
        self.assertEqual(reload.call_count, 2); self.assertEqual(driver.find_element.return_value.click.call_count, 2)
        self.assertEqual(len(Audit(self.history, plan).verified()), 2)

    def test_manual_reconciliation_is_distinct_audited_and_cannot_rewrite_settled_batch(self):
        self.matrix(); plan = self.plan(); audit = Audit(self.history, plan)
        audit.append('offline_preview', source=plan.manifest(), awards=plan.rows())
        audit.append('submit_attempt', batch_id='batch', registrations=[plan.awards[0].regno])
        audit, original = Audit.existing(audit.folder)
        with self.assertRaises(ValueError): audit.reconcile('batch', 'saved_manually_verified', '', 'too short')
        audit.reconcile('batch', 'saved_manually_verified', 'Synthetic Administrator', 'Checked the official JKBOSE saved award and pending list manually.')
        self.assertFalse(audit.verified()); self.assertEqual(audit.manual_saved(), {plan.awards[0].regno})
        self.assertFalse(audit.unresolved())
        audit.report(original); report = json.loads((audit.folder/'report.json').read_text())
        self.assertEqual(report['records'][0]['status'], 'saved_manually_verified')
        self.assertTrue((audit.folder/'report.csv').exists())
        with self.assertRaises(ValueError): audit.reconcile('batch', 'not_saved_manually_verified', 'Synthetic Admin', 'Attempt to alter an already settled award.')
        self.assertIn(plan.awards[0].regno, browser._pending_history(self.history, plan))

    def test_admin_verified_not_saved_allows_fresh_retry_without_claiming_saved(self):
        self.matrix(); plan = self.plan(); audit = Audit(self.history, plan)
        audit.append('submit_attempt', batch_id='batch', registrations=[plan.awards[0].regno])
        audit.reconcile('batch', 'not_saved_manually_verified', 'Synthetic Admin', 'Verified the entire batch is still pending and no award was saved.')
        self.assertFalse(audit.unresolved()); self.assertFalse(audit.manual_saved())
        self.assertFalse(browser._pending_history(self.history, plan))

    def test_cli_offline_preview_never_creates_a_browser(self):
        import main
        self.matrix(); plan = self.plan()
        with patch.object(main, 'get_driver') as get_driver:
            main.cmd_internal(plan.source, plan=plan, history_dir=str(self.history), preview_only=True)
        get_driver.assert_not_called()

    def test_unexpected_alert_never_accepted_and_marks_attempt_uncertain(self):
        self.matrix(); plan = self.plan(); driver = Mock(); live = self.live(plan)
        with patch.object(browser, 'open_subject'), patch.object(browser, 'snapshot', return_value=live), \
             patch.object(browser, '_evidence', return_value='synthetic'), patch.object(browser, '_fill', return_value=live):
            with self.assertRaises(ValueError): browser.run(driver, plan, self.history, 'school-test', Mock(return_value=True), submit=True, confirm_session=True)
        driver.switch_to.alert.accept.assert_not_called()
        self.assertTrue(Audit(self.history, plan).unresolved())

if __name__ == '__main__': unittest.main()
