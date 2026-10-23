"""Completion evidence for read-only ASP.NET actions. Never retries a save."""
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException

ARM = r"""
const key=arguments[0], target=arguments[1];
const prm=window.Sys?.WebForms?.PageRequestManager?.getInstance();
if(document.readyState!=='complete' || prm?.get_isInAsyncPostBack()) return {armed:false};
const state={started:0,completed:0,failed:false,active:false};
const begin=(sender,args)=>{
  const el=args.get_postBackElement?.();
  if(!target || el?.id===target){state.started++;state.active=true;}
};
const end=(sender,args)=>{
  if(state.active){state.failed=!!args.get_error?.();state.completed++;state.active=false;}
};
if(prm){prm.add_beginRequest(begin);prm.add_endRequest(end);}
state.dispose=()=>{if(prm){prm.remove_beginRequest(begin);prm.remove_endRequest(end);}};
window[key]=state;
return {armed:true};
"""
STATE = r"""
const state=window[arguments[0]];
const prm=window.Sys?.WebForms?.PageRequestManager?.getInstance();
return {ready:document.readyState==='complete',busy:!!prm?.get_isInAsyncPostBack(),
  present:!!state,started:state?.started||0,completed:state?.completed||0,
  failed:!!state?.failed,active:!!state?.active};
"""
CLEAN = r"""
const key=arguments[0]; if(window[key]){window[key].dispose();delete window[key];}
"""

@dataclass
class ReadPostback:
    root: object
    key: str
    path: str
    label: str


def _clean_url(u):
    if isinstance(u, bytes):
        return u.decode('utf-8', errors='replace')
    return str(u or '')


def begin_read(driver, target='', label='Read-only action'):
    location=urlparse(_clean_url(driver.current_url))
    loc_scheme=_clean_url(location.scheme).lower()
    loc_host=_clean_url(location.hostname).lower()
    loc_path=_clean_url(location.path).lower()
    if loc_scheme!='https' or loc_host!='jkbose.jk.gov.in':
        raise ValueError('Read-only assessment checks require the official signed-in JKBOSE site.')
    if loc_path not in {'/utilities/auth_pages/student_report.aspx','/utilities/auth_pages/practicalmarks.aspx','/utilities/auth_pages/practicalmarksreportbyschool.aspx','/utilities/auth_pages/generatepracticalmarks.aspx'}:
        raise ValueError('Read-only assessment action is on an unexpected page. No marks were submitted.')
    root=driver.find_element(By.TAG_NAME,'html')
    key='__jkbose_read_'+uuid4().hex
    result=driver.execute_script(ARM,key,target)
    if not isinstance(result,dict) or result.get('armed') is not True:
        raise ValueError(label+': the page is still loading or busy. Wait before starting another action.')
    return ReadPostback(root,key,loc_path,label)


def wait_read(driver,before,stop,timeout=60):
    """Require replaced document OR a matching completed UpdatePanel response.

    A changed dropdown, unchanged old table, elapsed delay or a merely changed
    readyState is never sufficient evidence. Values/hidden framework data are
    not collected. The caller still validates returned account/class/subject.
    """
    def finished(d):
        stop()
        location=urlparse(_clean_url(d.current_url))
        loc_scheme=_clean_url(location.scheme).lower()
        loc_host=_clean_url(location.hostname).lower()
        loc_path=_clean_url(location.path).lower()
        if not _clean_url(d.current_url) or _clean_url(d.current_url).lower()=='about:blank':return False
        if loc_scheme=='https' and loc_host=='jkbose.jk.gov.in' and loc_path.endswith('/errorpage.html'):
            raise ValueError(before.label+': JKBOSE returned its server error page ('+loc_path+'). This does not establish login expiry. The report was not read; no stale report or new save was accepted.')
        if loc_scheme!='https' or loc_host!='jkbose.jk.gov.in' or loc_path!=before.path:
            destination=loc_path if loc_host=='jkbose.jk.gov.in' else '[unexpected origin]'
            raise ValueError(before.label+': navigation redirected or login expired (destination: '+destination+'). No stale report is accepted.')
        replaced=False; detached_inspector_node=False
        try: before.root.is_enabled()
        except StaleElementReferenceException: replaced=True
        except WebDriverException as exc:
            # Chrome can report a detached old document through CDP instead
            # of Selenium's stale-element exception. Require disappearance
            # of our old document's monitor as additional replacement proof.
            if 'Node with given id does not belong to the document' not in str(exc): raise
            detached_inspector_node=True
        try: state=d.execute_script(STATE,before.key)
        except WebDriverException: return False
        if not isinstance(state,dict): return False
        if detached_inspector_node and state.get('present') is False: replaced=True
        if state.get('failed'): raise ValueError(before.label+': ASP.NET reported an asynchronous response error. Nothing will be submitted.')
        complete=state.get('present') and state.get('started',0)>0 and state.get('completed',0)>=state.get('started',0) and not state.get('active')
        return state.get('ready') is True and not state.get('busy') and (replaced or complete)
    try:
        WebDriverWait(driver,timeout,poll_frequency=0.2).until(finished)
    except TimeoutException as exc:
        raise ValueError(before.label+': no completed full/partial postback was confirmed. Check the portal response or validation messages; no automatic retry or marks submission.') from exc
    finally:
        try: driver.execute_script(CLEAN,before.key)
        except WebDriverException: pass
