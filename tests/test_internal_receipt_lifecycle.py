import copy,unittest,threading
from unittest.mock import Mock,patch
import test_internal_saved_report as fixtures
from jkbose_tool.features import internal_assessment_saved_report as saved
from jkbose_tool.features import internal_assessment_browser as browser
from jkbose_tool.features import internal_assessment_batch as batch
from jkbose_tool.features import internal_assessment_students_report as navigation
from jkbose_tool.features.internal_assessment import Audit,prepare_history_root

class ReceiptLifecycleTests(unittest.TestCase):
    setUp=fixtures.SavedReportTests.setUp
    write_book=fixtures.SavedReportTests.write_book
    plan=fixtures.SavedReportTests.plan
    sign=fixtures.SavedReportTests.sign
    report=fixtures.SavedReportTests.report
    def started(self,plan=None,account='school-test'):
        plan=plan or self.plan('Mathematics');audit=Audit(self.history,plan)
        audit.append('run_started',school_account=account,source=plan.manifest(),source_preview=plan.rows());return audit
    def receipt(self,audit,batch_id='first'):
        audit.append('submit_attempt',batch_id=batch_id,registrations=['REG1']);audit.append('verified_saved',batch_id=batch_id,registrations=['REG1'])
    def recognise(self,plan,report):
        return saved.recognise_saved_awards(self.history,[plan],'school-test',report,self.root/'official.json')
    def test_saved_rejected_then_saved_same_source_counts_latest_receipt(self):
        a=self.started();self.receipt(a);a.record_portal_rejection('REG1');self.assertEqual(a.verified(),set());self.receipt(a,'second')
        self.assertEqual(a.rejected(),set());self.assertEqual(a.verified(),{'REG1'});self.assertEqual(batch.verified_history(self.history,self.plan('Mathematics'),'school-test')['verified'],{'REG1'})
    def test_later_verified_source_supersedes_rejected_previous_source(self):
        a=self.started();self.receipt(a);a.record_portal_rejection('REG1');self.write_book(maths=19);p=self.plan('Mathematics');b=self.started(p);self.receipt(b)
        self.assertEqual(batch.verified_history(self.history,p,'school-test')['verified'],{'REG1'})
    def test_newer_rejection_in_different_source_revokes_old_receipt(self):
        a=self.started();self.receipt(a);self.write_book(maths=19);p=self.plan('Mathematics');b=self.started(p);b.record_portal_rejection('REG1')
        self.assertEqual(batch.verified_history(self.history,p,'school-test')['verified'],set())
    def test_source_change_without_official_rejection_never_authorises_retry(self):
        a=self.started();self.receipt(a);self.write_book(maths=19)
        with self.assertRaisesRegex(ValueError,'previously saved award changed'):batch.verified_history(self.history,self.plan('Mathematics'),'school-test')
    def test_official_rejection_auto_records_then_later_receipt_reenables_skip(self):
        old=self.plan('Mathematics');a=self.started(old);self.receipt(a);self.write_book(maths=19);p=self.plan('Mathematics');r=self.report(old);r['records'][0].update(status='Rejected',rejection_reason='review');self.sign(r)
        self.assertEqual(self.recognise(p,r)['Mathematics'],0);self.assertEqual(batch.verified_history(self.history,p,'school-test')['verified'],set())
        newer=self.report(p);self.assertEqual(self.recognise(p,newer)['Mathematics'],1);self.assertEqual(batch.verified_history(self.history,p,'school-test')['verified'],{'REG1'})
        self.assertEqual(self.recognise(p,newer)['Mathematics'],0)
    def test_rejected_wrong_name_still_blocks_and_cannot_revoke_saved_receipt(self):
        a=self.started();self.receipt(a);r=self.report();r['records'][0].update(status='Rejected',name='Different Student');self.sign(r)
        with self.assertRaisesRegex(ValueError,'student name differs'):self.recognise(self.plan('Mathematics'),r)
        self.assertEqual(batch.verified_history(self.history,self.plan('Mathematics'),'school-test')['verified'],{'REG1'})
    def test_rejection_never_settles_an_uncertain_save(self):
        p=self.plan('Mathematics');a=self.started(p);a.append('submit_attempt',batch_id='uncertain',registrations=['REG1']);r=self.report(p);r['records'][0].update(status='Rejected',rejection_reason='review');self.sign(r)
        with self.assertRaises(browser.UncertainSubmissionError):self.recognise(p,r)
        self.assertEqual(Audit.existing(a.folder)[0].unresolved(),{'uncertain'})
    def test_foreign_account_rejection_cannot_revoke_own_receipt(self):
        a=self.started();self.receipt(a);self.write_book(maths=19);p=self.plan('Mathematics');b=self.started(p,account='another-school');b.record_portal_rejection('REG1')
        with self.assertRaisesRegex(ValueError,'previously saved award changed'):batch.verified_history(self.history,p,'school-test')
    def test_manual_verified_receipt_after_rejection_is_retained(self):
        a=self.started();self.receipt(a);a.record_portal_rejection('REG1');a.append('submit_attempt',batch_id='manual',registrations=['REG1']);a.reconcile('manual','saved_manually_verified','Synthetic Admin','Checked the complete synthetic saved report.')
        self.assertEqual(a.verified(),set());self.assertEqual(a.manual_saved(),{'REG1'});self.assertEqual(batch.verified_history(self.history,self.plan('Mathematics'),'school-test')['manual'],{'REG1'})

class RedirectWaitTests(unittest.TestCase):
    def test_empty_and_about_blank_during_navigation_wait_for_real_report(self):
        import test_internal_report_navigation as f
        driver,link,toggle,click=f.ReportNavigationTests().fixture()
        class Wait:
            def __init__(self,*a,**k):pass
            def until(self,check):
                for value in [None,'about:blank',saved.URL]:
                    driver.current_url=value
                    if check(driver):return True
                raise AssertionError('Report never accepted')
        with patch.object(navigation,'safe_click') as clicked,patch.object(navigation,'WebDriverWait',Wait):navigation.open_report_from_sidebar(driver,saved.URL,'Saved report')
        clicked.assert_called_once();driver.get.assert_not_called()
    def test_public_index_redirect_is_never_accepted_or_retried(self):
        driver=Mock(current_url=saved.URL);driver.execute_script.return_value='complete';driver.find_element.return_value.get_attribute.return_value='2026-2027'
        def redirect(*a):driver.current_url='https://jkbose.jk.gov.in/utilities/index.html'
        with patch.object(saved,'Select'),patch.object(saved,'begin_read'),patch.object(saved,'wait_read',side_effect=redirect),self.assertRaisesRegex(ValueError,'lost the authenticated session'):
            saved.read_saved_report(driver,'11','school-test','2025-26')
        driver.find_element.return_value.click.assert_called_once();driver.get.assert_not_called()
    def test_stop_during_transient_report_wait_is_not_swallowed(self):
        driver=Mock(current_url=saved.URL);driver.execute_script.return_value='complete';driver.find_element.return_value.get_attribute.return_value='2026-2027';stop=threading.Event()
        class Wait:
            def __init__(self,*a,**k):self.short=k.get('poll_frequency')==0.2
            def until(self,check):
                if self.short:stop.set()
                return check(driver)
        def redirect(*a):driver.current_url='https://jkbose.jk.gov.in/utilities/auth_pages/temporary.aspx'
        with patch.object(saved,'Select'),patch.object(saved,'begin_read'),patch.object(saved,'wait_read',side_effect=redirect),patch.object(saved,'WebDriverWait',Wait),self.assertRaises(browser.AssessmentStopped):
            saved.read_saved_report(driver,'11','school-test','2025-26',stop_event=stop)

if __name__=='__main__':unittest.main()
