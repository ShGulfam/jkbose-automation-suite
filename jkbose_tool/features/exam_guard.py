"""Fail closed on expired sessions, closed portals and incomplete form lookups."""
import re
from urllib.parse import urlsplit
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from .. import config

class ExamPortalUnavailable(ValueError):
    pass

def _clean_url(u):
    if isinstance(u, bytes):
        return u.decode('utf-8', errors='replace')
    return str(u or '')

def official_url(url):
    parsed = urlsplit(_clean_url(url))
    scheme = _clean_url(parsed.scheme).lower()
    hostname = _clean_url(parsed.hostname).lower()
    if scheme != 'https' or hostname != 'jkbose.jk.gov.in' or parsed.port not in (None, 443):
        raise ExamPortalUnavailable('Only the official HTTPS JKBOSE website is supported.')
    return parsed

def require_exam_form(driver, expected_class=None):
    parsed = official_url(driver.current_url)
    if parsed.path.lower() != '/utilities/auth_pages/renewalformxixii.aspx':
        raise ExamPortalUnavailable('Exam/RR form is unavailable or login expired. Stop and sign in again.')
    text = driver.find_element(By.TAG_NAME, 'body').text or ''
    if re.search(r'(?:rr\s+renewal|exam(?:ination)?(?:\s+form)?|registration|submission|portal)\s+(?:is\s+)?(?:currently\s+)?closed|session\s+(?:has\s+)?expired|please\s+(?:log\s*in|sign\s*in)', text, re.I):
        raise ExamPortalUnavailable('JKBOSE reports that the portal is closed or the session expired. No student will be filled.')
    for identifier in (config.CLASS_SELECT_ID, 'bodypH_txt_rege', config.GET_DETAILS_BTN_ID):
        nodes = driver.find_elements(By.ID, identifier)
        if len(nodes) != 1 or not nodes[0].is_displayed() or not nodes[0].is_enabled():
            raise ExamPortalUnavailable('The active exam form controls are missing or disabled. Inspect the page before continuing.')
    if expected_class:
        actual = Select(driver.find_element(By.ID, config.CLASS_SELECT_ID)).first_selected_option.get_attribute('value')
        if actual != str(expected_class):
            raise ExamPortalUnavailable('The live Class selection differs from this student. Lookup stopped.')

def require_lookup_details(driver, registration, row=None):
    require_exam_form(driver, (row or {}).get('Class'))
    lookup = driver.find_element(By.ID, 'bodypH_txt_rege').get_attribute('value') or ''
    if lookup.strip() != registration:
        raise ExamPortalUnavailable('The registration lookup changed unexpectedly. Stop and review this student.')
    def value(identifier):
        found = driver.find_elements(By.ID, identifier)
        return (found[0].get_attribute('value') or '').strip() if len(found) == 1 else ''
    parts = [value(f'bodypH_txt{part}name') for part in ('first', 'middle', 'last')]
    if not parts[0]:
        raise ExamPortalUnavailable('No returned student name was loaded. Navigation and the lookup box are not proof of success.')
    row = row or {}
    normalize = lambda text: re.sub(r'[^a-z0-9]', '', str(text or '').lower())
    expected = row.get('Name') or row.get('StudentName') or ' '.join(str(row.get(k, '')).strip() for k in ('FirstName', 'MiddleName', 'LastName'))
    if expected.strip() and normalize(expected) != normalize(' '.join(parts)):
        raise ExamPortalUnavailable('Returned student name differs from the source workbook. Manual review required.')
    father = str(row.get('FatherName', '')).strip()
    if father and normalize(father) != normalize(value('bodypH_txtfathername')):
        raise ExamPortalUnavailable('Returned parentage differs from the source workbook. Manual review required.')
    return ' '.join(part for part in parts if part)
