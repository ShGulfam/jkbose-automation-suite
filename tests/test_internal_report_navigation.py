import unittest,threading
from unittest.mock import Mock,patch
from selenium.common.exceptions import TimeoutException
from jkbose_tool.features import internal_assessment_students_report as reports
from jkbose_tool.features import internal_assessment_saved_report as saved
from jkbose_tool.features import internal_assessment_browser as browser

DASHBOARD='https://jkbose.jk.gov.in/utilities/auth_pages/subadminpanelforclerk.aspx'
class ReportNavigationTests(unittest.TestCase):
    def fixture(self,visible=True):
        driver=Mock(current_url=DASHBOARD);driver.execute_script.return_value='complete'
        link=Mock();link.get_attribute.return_value='PracticalMarksReportBySchool.aspx';link.is_displayed.return_value=visible;link.is_enabled.return_value=True
        toggle=Mock();toggle.is_displayed.return_value=True;toggle.is_enabled.return_value=True
        driver.find_elements.side_effect=lambda by,selector:[toggle] if selector=='a.sidebar-toggle' else [link]
        def click(d,el):
            if el is toggle:link.is_displayed.return_value=True
            else:driver.current_url=saved.URL
        return driver,link,toggle,click
    def test_dashboard_uses_exact_authenticated_sidebar_link_without_direct_get(self):
        driver,link,toggle,click=self.fixture()
        with patch.object(reports,'safe_click',side_effect=click) as clicked:reports.open_report_from_sidebar(driver,saved.URL,'Saved report')
        clicked.assert_called_once_with(driver,link);driver.get.assert_not_called()
        self.assertFalse(any(c.args[1]=='a.sidebar-toggle' for c in driver.find_elements.call_args_list))
    def test_hidden_link_expands_sidebar_once_then_navigates_once(self):
        driver,link,toggle,click=self.fixture(False)
        with patch.object(reports,'safe_click',side_effect=click) as clicked:reports.open_report_from_sidebar(driver,saved.URL,'Saved report')
        self.assertEqual([c.args[1] for c in clicked.call_args_list],[toggle,link]);driver.get.assert_not_called()
    def test_already_loaded_report_avoids_clicks_or_reload(self):
        driver=Mock(current_url=saved.URL+'?source=sidebar#report')
        with patch.object(reports,'safe_click') as clicked:reports.open_report_from_sidebar(driver,saved.URL,'Saved report')
        clicked.assert_not_called();driver.get.assert_not_called();driver.find_elements.assert_not_called()
    def test_missing_ambiguous_and_external_links_cannot_fall_back_to_get(self):
        for mode in ('missing','duplicate','outside'):
            driver,link,toggle,click=self.fixture()
            if mode=='missing':driver.find_elements.side_effect=None;driver.find_elements.return_value=[]
            if mode=='duplicate':driver.find_elements.side_effect=None;driver.find_elements.return_value=[link,link]
            if mode=='outside':link.get_attribute.return_value='https://example.invalid/PracticalMarksReportBySchool.aspx'
            with self.subTest(mode=mode),patch.object(reports,'safe_click') as clicked,self.assertRaisesRegex(ValueError,'unambiguously'):
                reports.open_report_from_sidebar(driver,saved.URL,'Saved report')
            clicked.assert_not_called();driver.get.assert_not_called()
    def test_real_login_redirect_rejected_after_one_navigation(self):
        driver,link,toggle,click=self.fixture()
        def expired(d,el):driver.current_url='https://jkbose.jk.gov.in/utilities/auth_pages/login.aspx'
        with patch.object(reports,'safe_click',side_effect=expired) as clicked,self.assertRaisesRegex(ValueError,'redirected to /utilities/auth_pages/login.aspx'):
            reports.open_report_from_sidebar(driver,saved.URL,'Saved report')
        clicked.assert_called_once();driver.get.assert_not_called()
    def test_bytes_current_url_navigates_successfully(self):
        driver,link,toggle,click=self.fixture()
        driver.current_url=b'https://jkbose.jk.gov.in/utilities/auth_pages/subadminpanelforclerk.aspx'
        def click_bytes(d,el):driver.current_url=saved.URL.encode('utf-8')
        with patch.object(reports,'safe_click',side_effect=click_bytes) as clicked:
            reports.open_report_from_sidebar(driver,saved.URL,'Saved report')
        clicked.assert_called_once_with(driver,link);driver.get.assert_not_called()
    def test_bytes_login_redirect_rejected_cleanly_without_type_error(self):
        driver,link,toggle,click=self.fixture()
        driver.current_url=b'https://jkbose.jk.gov.in/utilities/auth_pages/subadminpanelforclerk.aspx'
        def expired_bytes(d,el):driver.current_url=b'https://jkbose.jk.gov.in/utilities/auth_pages/login.aspx'
        with patch.object(reports,'safe_click',side_effect=expired_bytes) as clicked,self.assertRaisesRegex(ValueError,'redirected to /utilities/auth_pages/login.aspx'):
            reports.open_report_from_sidebar(driver,saved.URL,'Saved report')
        clicked.assert_called_once();driver.get.assert_not_called()
    def test_unchanged_dashboard_cannot_count_as_navigation_success(self):
        driver,link,toggle,click=self.fixture()
        with patch.object(reports,'safe_click') as clicked,patch.object(reports,'WebDriverWait') as waited:
            waited.return_value.until.side_effect=TimeoutException()
            with self.assertRaisesRegex(ValueError,'did not finish'):reports.open_report_from_sidebar(driver,saved.URL,'Saved report')
        clicked.assert_called_once();driver.get.assert_not_called()
    def test_stop_and_unsupported_destination_prevent_all_actions(self):
        driver,link,toggle,click=self.fixture();stop=threading.Event();stop.set()
        with self.assertRaises(browser.AssessmentStopped):reports.open_report_from_sidebar(driver,saved.URL,'Saved report',stop)
        with self.assertRaises(ValueError):reports.open_report_from_sidebar(driver,'https://example.invalid/report','Saved report')
        driver.find_elements.assert_not_called();driver.get.assert_not_called()
    def test_saved_report_reader_navigates_via_shared_helper_before_reading_filters(self):
        import test_internal_saved_report as fixtures
        reader=fixtures.SavedReportTests();driver,link,toggle,click=self.fixture()
        driver.find_element.return_value.get_attribute.return_value='2026-2027'
        driver.execute_script.side_effect=lambda script:reader.page() if script==saved.SNAPSHOT else 'complete'
        with patch.object(reports,'safe_click',side_effect=click),patch.object(saved,'Select'),patch.object(saved,'begin_read'),patch.object(saved,'wait_read'):
            result=saved._read_saved_report_status(driver,'11','school-test','2025-26')
        self.assertEqual(result['total'],1);driver.get.assert_not_called()
    def test_browser_url_accepts_bytes_without_error(self):
        driver=Mock(current_url=b'https://jkbose.jk.gov.in/utilities/auth_pages/practicalmarks.aspx')
        browser._url(driver)
    def test_browser_url_rejects_redirect_bytes_cleanly(self):
        driver=Mock(current_url=b'https://jkbose.jk.gov.in/utilities/auth_pages/login.aspx')
        with self.assertRaisesRegex(ValueError,'Internal Assessment did not open'):
            browser._url(driver)
