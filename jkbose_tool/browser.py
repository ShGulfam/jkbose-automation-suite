"""
Shared Selenium/browser plumbing used by every feature: launch Chrome,
open the login page, wait for you to log in manually (incl. captcha),
then click into the "Exam / RR" section.

Every feature module (features/screenshots.py, features/submit_form.py,
future features/extract.py, ...) calls get_driver() + login() from here
instead of duplicating this setup.
"""
import time
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from . import config


def get_driver(profile_dir=None, download_dir=None):
    """
    Launch a visible (non-headless) Chrome window -- manual login/captcha
    needs it. Uses a dedicated, persistent profile folder by default
    (config.CHROME_PROFILE_DIR) so that once you log in inside this
    automated window, the session survives across runs -- no need to log
    in again every time you run the tool, until the site session expires.
    Pass profile_dir=None explicitly, or set config.CHROME_PROFILE_DIR to
    None, to always start logged-out.
    """
    profile_dir = config.CHROME_PROFILE_DIR if profile_dir is None else profile_dir
    options = Options()
    options.add_argument("--start-maximized")
    if profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")
    if download_dir:
        from pathlib import Path
        destination=Path(download_dir).resolve();destination.mkdir(parents=True,exist_ok=True)
        options.add_experimental_option('prefs',{'download.default_directory':str(destination),'download.prompt_for_download':False})
    service = ChromeService(executable_path=ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def _open_url_with_retry(driver, url, attempts=3):
    """Open a JKBOSE URL with a few short retries for transient network timeouts.

    A portal/network outage is different from a dead Selenium session. Chrome
    generally remains usable after ERR_CONNECTION_TIMED_OUT, so retrying the
    navigation is cheap and avoids failing an entire run on one transient hit.
    """
    attempts = max(1, int(attempts))
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            driver.get(url)
            return
        except WebDriverException as exc:
            last_exc = exc
            text = str(exc).lower()
            transient = any(marker in text for marker in (
                'err_connection_timed_out',
                'err_connection_reset',
                'err_network_changed',
                'err_internet_disconnected',
                'err_name_not_resolved',
            ))
            if not transient or attempt >= attempts:
                break
            delay = attempt * 2
            print(f"[WARN] JKBOSE page did not respond (attempt {attempt}/{attempts}); retrying in {delay}s...")
            time.sleep(delay)
    first = str(last_exc).splitlines()[0] if last_exc else 'connection failed'
    raise RuntimeError(
        f"JKBOSE portal could not be reached after {attempts} attempts: {first}. "
        "Check internet/site availability, then run again."
    ) from last_exc


def _clean_url(u):
    if isinstance(u, bytes):
        return u.decode('utf-8', errors='replace')
    return str(u or '')


def login_only(driver, timeout=None, role=None):
    """
    Opens the login page and waits for you to log in manually (including
    captcha). Doesn't click anything afterwards -- use this when you want
    to navigate the sidebar yourself (e.g. for `inspect`).
    """
    if role not in (None,'principal'):raise ValueError('Unsupported JKBOSE login role.')
    timeout = timeout or config.MANUAL_LOGIN_TIMEOUT
    _open_url_with_retry(driver, config.LOGIN_URL)
    print(f"[INFO] Browser opened at {config.LOGIN_URL}")
    print("[INFO] Please complete login (including captcha) manually in the browser window.")
    print("[INFO] Waiting for you to land on a logged-in page (checking for the sidebar)...")
    def signed_in(d):
        location = urlparse(_clean_url(d.current_url))
        scheme = _clean_url(location.scheme).lower()
        host = _clean_url(location.hostname).lower()
        path = _clean_url(location.path).lower()
        return (scheme == 'https' and host == 'jkbose.jk.gov.in'
                and path != '/utilities/auth_pages/login.aspx'
                and bool(d.find_elements(By.CSS_SELECTOR,
                    'a#HyperLink6[href*="generatePracticalMarks.aspx"]' if role=='principal' else
                    'a#HyperLink18, a#HyperLink11, a[href*="practicalMarks.aspx"], a[href*="renewalformxixii.aspx"]')))
    WebDriverWait(driver, timeout).until(signed_in)
    print(f"[INFO] Login detected. Now at: {_clean_url(driver.current_url)}")


def login_and_enter_exam_section(driver, link_id=None, timeout=None):
    """
    Opens the login page, waits (up to MANUAL_LOGIN_TIMEOUT) for you to log
    in and solve the captcha manually, then clicks the given sidebar link
    to land inside the Exam/RR section. Call this once per run, before
    handing the driver off to a feature module.

    If the sidebar link ID has changed (e.g. after a domain migration) and
    can't be found, falls back to login_only() and warns you -- you can
    still navigate manually, or use `python main.py inspect` to find the
    right IDs and update config.EXAM_RR_LINK_ID.
    """
    link_id = link_id or config.EXAM_RR_LINK_ID
    timeout = timeout or config.MANUAL_LOGIN_TIMEOUT

    _open_url_with_retry(driver, config.LOGIN_URL)
    print(f"[INFO] Browser opened at {config.LOGIN_URL}")
    print("[INFO] Please complete login (including captcha) manually in the browser window.")

    try:
        WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.ID, link_id)))
        print("[INFO] Login detected. Entering Exam/RR section...")
        driver.find_element(By.ID, link_id).click()
        time.sleep(config.SHORT_WAIT)
    except Exception:
        print(f"[WARN] Could not find/click sidebar link id='{link_id}' after login.")
        print("[WARN] The page markup may have changed. Navigate manually in the browser, "
              "or run 'python main.py inspect' to find the current field/link IDs.")


def safe_click(driver, el):
    """Scroll an element into view and click it, falling back to a JS click."""
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)


def scroll_to_text(driver, text, block="start"):
    """
    Scrolls the first element containing the given visible text into view.
    Returns True if found and scrolled, False otherwise.

    This is deliberately used instead of "scroll to the bottom of the
    page" for capturing the Subjects section: how much content sits below
    Subjects (photo/signature/captcha, extra fields for some streams,
    etc.) varies per student, so scrolling to the document's absolute
    bottom can land on THAT instead -- leaving Subjects scrolled past and
    missing from the screenshot for exactly the students who have more
    content below it. Scrolling to the section's own heading text is
    correct regardless of page length.
    """
    script = """
        var searchText = arguments[0];
        var alignBlock = arguments[1];
        var xpath = "//*[not(self::script) and not(self::style) and " +
                    "contains(normalize-space(text()), '" + searchText.replace("'", "\\'") + "')]";
        var result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        var el = result.singleNodeValue;
        if (el) {
            el.scrollIntoView({block: alignBlock});
            return true;
        }
        return false;
    """
    try:
        return bool(driver.execute_script(script, text, block))
    except Exception:
        return False


def page_change_token(driver):
    """
    Return a lightweight fingerprint of the current ASP.NET page.

    This is intentionally much cheaper than transferring the complete
    ``driver.page_source`` across the Selenium bridge. A full navigation gets
    a new ``performance.timeOrigin``; ASP.NET partial postbacks normally update
    ``__VIEWSTATE`` / ``__EVENTVALIDATION``. Together these are reliable enough
    for the JKBOSE form while avoiding repeated multi-hundred-KB HTML copies.
    """
    try:
        return tuple(driver.execute_script("""
            var vs = document.getElementById('__VIEWSTATE');
            var ev = document.getElementById('__EVENTVALIDATION');
            function sig(el) {
                if (!el || !el.value) return ['', 0];
                var v = el.value;
                return [v.slice(-64), v.length];
            }
            var a = sig(vs), b = sig(ev);
            return [location.href, performance.timeOrigin || 0,
                    a[0], a[1], b[0], b[1], document.readyState];
        """))
    except Exception:
        # Rare fallback during a navigation transition. Still much smaller than
        # page_source in the normal path.
        try:
            return (driver.current_url, driver.title)
        except Exception:
            return ()


def wait_for_postback(driver, before_token, timeout=None):
    """Wait for an ASP.NET full/partial postback using a lightweight token."""
    timeout = timeout or config.PAGE_CHANGE_TIMEOUT
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.2).until(
            lambda d: page_change_token(d) != before_token
        )
        # Do not add a fixed sleep here; callers that need delayed content use
        # wait_until_page_stable().
        return True
    except Exception:
        return False


def _render_state(driver):
    """Cheap DOM-size state used by wait_until_page_stable()."""
    try:
        return tuple(driver.execute_script("""
            var b = document.body;
            var vs = document.getElementById('__VIEWSTATE');
            return [document.readyState,
                    b ? b.scrollHeight : 0,
                    b ? b.innerText.length : 0,
                    b ? b.getElementsByTagName('*').length : 0,
                    vs && vs.value ? vs.value.length : 0];
        """))
    except Exception:
        return ()


def wait_until_page_stable(driver, timeout=None, poll_interval=None, stable_reads=None):
    """
    Waits until driver.page_source stops changing across several
    consecutive polls, or until timeout -- then returns.

    wait_for_postback only proves the page changed ONCE; it says nothing
    about content that finishes loading a beat later (e.g. a subjects
    grid populated by a secondary AJAX call after the main postback
    response, or a slow follow-up render). Selecting Class/Stream and
    then capturing immediately can catch that content mid-load (showing
    a stale "No Records Found" even though data is on its way) -- polling
    for stability catches that regardless of whether the underlying cause
    is a classic postback or async JS.

    Returns True if it settled before the timeout, False if it gave up
    still changing (caller can decide whether that's worth logging).
    """
    timeout = timeout if timeout is not None else config.SUBJECTS_STABLE_TIMEOUT
    poll_interval = poll_interval if poll_interval is not None else config.SUBJECTS_STABLE_POLL
    stable_reads = stable_reads if stable_reads is not None else config.SUBJECTS_STABLE_READS

    start = time.time()
    last = _render_state(driver)
    consecutive_unchanged = 0
    while time.time() - start < timeout:
        time.sleep(poll_interval)
        current = _render_state(driver)
        if current == last:
            consecutive_unchanged += 1
            if consecutive_unchanged >= stable_reads:
                return True
        else:
            consecutive_unchanged = 0
            last = current
    return False
