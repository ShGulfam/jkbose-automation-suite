"""Real completion evidence and fail-closed regression tests (no live writes)."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from selenium.common.exceptions import StaleElementReferenceException,TimeoutException,WebDriverException
from jkbose_tool.features import internal_assessment_postback as postback

URL='https://jkbose.jk.gov.in/utilities/auth_pages/student_report.aspx'
class ImmediateWait:
    def __init__(self,*a,**k): pass
    def until(self,check):
        for _ in range(3):
            value=check(self.driver)
            if value:return value
        raise TimeoutException()

class PostbackTests(unittest.TestCase):
    def driver(self,state,replaced=False):
        driver=Mock(current_url=URL)
        driver.execute_script.return_value=state
        root=Mock()
        if replaced:root.is_enabled.side_effect=StaleElementReferenceException()
        return driver,postback.ReadPostback(root,'ticket','/utilities/auth_pages/student_report.aspx','Students report Search')
    def wait(self,driver,before,stop=None):
        with patch.object(postback,'WebDriverWait',side_effect=lambda d,*a,**k:self.make_wait(d)):
            return postback.wait_read(driver,before,stop or Mock())
    def make_wait(self,driver):
        wait=ImmediateWait();wait.driver=driver;return wait
    def state(self,**kwargs):
        return dict(ready=True,busy=False,present=True,started=0,completed=0,failed=False,active=False,**kwargs)
    def test_replaced_document_accepts_even_with_unchanged_framework_fingerprint(self):
        driver,before=self.driver(self.state(),replaced=True)
        self.wait(driver,before)
    def test_same_document_requires_completed_matching_async_response(self):
        state=self.state();state.update(started=1,completed=1)
        driver,before=self.driver(state);self.wait(driver,before)
    def test_chrome_detached_inspector_node_requires_new_document_monitor(self):
        state=self.state();state['present']=False
        driver,before=self.driver(state)
        before.root.is_enabled.side_effect=WebDriverException('unknown error: Node with given id does not belong to the document')
        self.wait(driver,before)
    def test_chrome_detached_error_with_old_monitor_does_not_prove_completion(self):
        driver,before=self.driver(self.state())
        before.root.is_enabled.side_effect=WebDriverException('Node with given id does not belong to the document')
        with self.assertRaisesRegex(ValueError,'no completed full/partial postback'):self.wait(driver,before)
    def test_unrelated_webdriver_error_is_not_treated_as_replaced_document(self):
        driver,before=self.driver(self.state())
        before.root.is_enabled.side_effect=WebDriverException('disconnected: not connected to DevTools')
        with self.assertRaisesRegex(WebDriverException,'disconnected'):self.wait(driver,before)
    def test_unchanged_old_grid_and_dropdown_alone_never_count_as_success(self):
        driver,before=self.driver(self.state())
        with self.assertRaisesRegex(ValueError,'no completed full/partial postback'):self.wait(driver,before)
    def test_loading_busy_failed_or_inflight_response_never_passes(self):
        for change in ({'ready':False},{'busy':True},{'active':True},{'completed':0},{'failed':True}):
            state=self.state();state.update(started=1,completed=1);state.update(change)
            driver,before=self.driver(state)
            with self.subTest(change=change),self.assertRaises(ValueError):self.wait(driver,before)
    def test_login_or_wrong_destination_stops_without_accepting_old_roster(self):
        driver,before=self.driver(self.state(),replaced=True)
        for url in ('https://jkbose.jk.gov.in/utilities/auth_pages/login.aspx','https://example.invalid/student_report.aspx'):
            driver.current_url=url
            with self.assertRaisesRegex(ValueError,'redirected or login expired'):self.wait(driver,before)
    def test_server_error_is_identified_separately_from_login_expiry(self):
        driver,before=self.driver(self.state(),replaced=True)
        driver.current_url='https://jkbose.jk.gov.in/utilities/auth_pages/ErrorPage.html'
        with self.assertRaisesRegex(ValueError,'JKBOSE returned its server error page') as caught:self.wait(driver,before)
        self.assertIn('/utilities/auth_pages/errorpage.html',str(caught.exception))
        self.assertNotIn('navigation redirected or login expired',str(caught.exception))
    def test_redirect_diagnostic_omits_queries_and_untrusted_origin(self):
        driver,before=self.driver(self.state(),replaced=True)
        for value,expected in [('https://jkbose.jk.gov.in/utilities/auth_pages/login.aspx?private=never-print','/utilities/auth_pages/login.aspx'),('https://untrusted.invalid/private?private=never-print','[unexpected origin]')]:
            driver.current_url=value
            with self.assertRaises(ValueError) as caught:self.wait(driver,before)
            self.assertIn(expected,str(caught.exception));self.assertNotIn('never-print',str(caught.exception));self.assertNotIn('untrusted.invalid',str(caught.exception))
    def test_empty_navigation_state_does_not_accept_stale_report(self):
        driver,before=self.driver(self.state(),replaced=True);driver.current_url=''
        with self.assertRaisesRegex(ValueError,'no completed full/partial postback'):self.wait(driver,before)
    def test_stop_interrupts_wait_and_monitor_is_cleaned(self):
        driver,before=self.driver(self.state())
        stop=Mock(side_effect=RuntimeError('Stopped'))
        with self.assertRaisesRegex(RuntimeError,'Stopped'):self.wait(driver,before,stop)
        self.assertEqual(driver.execute_script.call_args.args,(postback.CLEAN,'ticket'))
    def test_busy_page_cannot_be_armed(self):
        driver=Mock(current_url=URL);driver.execute_script.return_value={'armed':False}
        with self.assertRaisesRegex(ValueError,'still loading or busy'):postback.begin_read(driver)
    def test_actual_snapshot_accepts_final_submit_and_rejects_disabled_or_unknown_button(self):
        from jkbose_tool.features.internal_assessment_browser import SNAPSHOT
        js=r"""
const code=JSON.parse(process.argv[1]);const assert=require('assert');
let save={value:'Submit & Next',disabled:false};
const document={body:{innerText:'Hello school-test'},querySelectorAll:()=>[],getElementById:id=>({
 bodypH_lblInfo:{innerText:'Class: 12 | Subject: Mathematics | Total Records: 5 | Page 1 of 1 (Showing 1-5) | Max Marks: 20'},
 bodypH_btnSaveMarks:save,bodypH_ddlClass:{value:'12'},bodypH_ddlSubject:{value:'Mathematics',options:[]}
})[id]};
function read(){return Function('document',code)(document);}
assert.equal(read().save_enabled,true);
save.value='Submit';assert.equal(read().save_enabled,true);
save.disabled=true;assert.equal(read().save_enabled,false);
save.disabled=false;save.value='Reset';assert.equal(read().save_enabled,false);
save=null;assert.equal(read().save_enabled,false);
console.log('Final Submit and intermediate Submit & Next verified');
"""
        result=subprocess.run(['node','-e',js,json.dumps(SNAPSHOT)],capture_output=True,text=True,check=True)
        self.assertIn('verified',result.stdout)

    def test_monitor_javascript_handles_actual_begin_end_events_without_capturing_fields(self):
        # Execute the shipped JS, not a Python imitation of its counters.
        js=r"""
const {ARM,STATE,CLEAN}=JSON.parse(process.argv[1]);
let begin,end,removed=0,busy=false;
const prm={get_isInAsyncPostBack:()=>busy,add_beginRequest:f=>begin=f,add_endRequest:f=>end=f,remove_beginRequest:f=>removed++,remove_endRequest:f=>removed++};
const document={readyState:'complete'};const window={Sys:{WebForms:{PageRequestManager:{getInstance:()=>prm}}}};
function exec(code,...args){return Function('window','document','args','return (function(){'+code+'}).apply(null,args)')(window,document,args);}
const assert=require('assert');
assert.equal(exec(ARM,'ticket','search').armed,true);
begin(null,{get_postBackElement:()=>({id:'unrelated'})});end(null,{get_error:()=>null});
assert.equal(exec(STATE,'ticket').completed,0);
begin(null,{get_postBackElement:()=>({id:'search'})});busy=true;
assert.equal(exec(STATE,'ticket').active,true);
busy=false;end(null,{get_error:()=>null});
assert.equal(exec(STATE,'ticket').completed,1);
assert.equal(exec(STATE,'ticket').failed,false);
exec(CLEAN,'ticket');assert.equal(removed,2);assert.equal(window.ticket,undefined);
console.log('ASP.NET begin/end monitoring verified');
"""
        result=subprocess.run(['node','-e',js,json.dumps(dict(ARM=postback.ARM,STATE=postback.STATE,CLEAN=postback.CLEAN))],capture_output=True,text=True,check=True)
        self.assertIn('verified',result.stdout)

if __name__=='__main__':unittest.main()
