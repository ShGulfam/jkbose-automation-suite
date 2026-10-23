"""Deep live-page inspector for JKBOSE forms.

Creates three companion files:
  * fields.csv              every input/select/textarea/button/link (visible or hidden)
  * fields_options.csv      every select option + radio/checkbox label/value
  * fields_stream_subjects.csv  stream-dependent optional-subject catalog, when possible

The default run reads the current DOM without changing dropdowns. The optional
--inspect-streams flag cycles academic stream choices and restores the original
selection. Input values and ASP.NET authentication tokens are redacted.
"""
import csv
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from .. import config
from ..browser import page_change_token, wait_for_postback
from .exam_guard import official_url

_TAGS = ["input", "select", "textarea", "button", "a"]

def _private(el, tag):
    kind = (el.get_attribute('type') or '').lower()
    key = ' '.join(el.get_attribute(k) or '' for k in ('id', 'name'))
    return tag == 'textarea' or (tag == 'input' and kind not in ('button', 'submit', 'reset', 'radio', 'checkbox')) or bool(re.search(r'password|captcha|token|secret|viewstate|eventvalidation|csrf|session|auth', key, re.I))

def _safe_href(value):
    parsed = urlsplit(value or '')
    if parsed.scheme.lower() == 'javascript':
        return '[javascript handler]'
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode([(key, '[redacted]') for key, _ in parse_qsl(parsed.query)]), ''))


def _nearby_label(driver, el):
    try:
        return driver.execute_script("""
            let el = arguments[0];
            if (el.id) {
              let l = document.querySelector('label[for="'+CSS.escape(el.id)+'"]');
              if (l && l.innerText.trim()) return l.innerText.trim();
            }
            for (let hops=0; hops<4 && el; hops++) {
              el=el.parentElement; if(!el) break;
              let clone=el.cloneNode(true);
              clone.querySelectorAll('input,select,textarea,button,script,style').forEach(n=>n.remove());
              let t=(clone.innerText||'').trim().replace(/\\s+/g,' ');
              if(t && t.length<120) return t;
            }
            return '';
        """, el) or ""
    except Exception:
        return ""


def _dump_fields(driver):
    rows=[]
    for tag in _TAGS:
        for el in driver.find_elements(By.TAG_NAME, tag):
            try:
                rows.append({
                    "tag": tag,
                    "id": el.get_attribute("id") or "",
                    "name": el.get_attribute("name") or "",
                    "type": "link" if tag=="a" else (el.get_attribute("type") or ""),
                    "visible": bool(el.is_displayed()),
                    "enabled": bool(el.is_enabled()),
                    "readonly": el.get_attribute("readonly") or "",
                    "disabled": el.get_attribute("disabled") or "",
                    "value": '[redacted]' if _private(el, tag) else (el.get_attribute("value") or "")[:200],
                    "text": '[redacted]' if _private(el, tag) else (el.text or "")[:200],
                    "placeholder_or_href": _safe_href(el.get_attribute("href")) if tag == 'a' else (el.get_attribute("placeholder") or ''),
                    "onchange": '[redacted]' if _private(el, tag) else (el.get_attribute("onchange") or ''),
                    "onclick": '[redacted]' if _private(el, tag) else (el.get_attribute("onclick") or ''),
                    "nearby_label_guess": '' if _private(el, tag) else _nearby_label(driver, el),
                })
            except Exception:
                pass
    return rows


def _dump_options(driver):
    rows=[]
    for el in driver.find_elements(By.CSS_SELECTOR, "select"):
        try:
            sid=el.get_attribute("id") or ""; sname=el.get_attribute("name") or ""
            for pos,opt in enumerate(el.find_elements(By.TAG_NAME,"option")):
                rows.append({"control":"select","parent_id":sid,"parent_name":sname,"group":"",
                             "index":pos,"label":(opt.text or "").strip(),"value":opt.get_attribute("value") or "",
                             "selected":bool(opt.is_selected()),"enabled":bool(opt.is_enabled())})
        except Exception: pass
    for el in driver.find_elements(By.CSS_SELECTOR, "input[type='radio'],input[type='checkbox']"):
        try:
            eid=el.get_attribute("id") or ""; name=el.get_attribute("name") or ""
            label=""
            if eid:
                labs=driver.find_elements(By.CSS_SELECTOR, f"label[for='{eid}']")
                if labs: label=(labs[0].text or "").strip()
            rows.append({"control":el.get_attribute("type") or "input","parent_id":eid,"parent_name":name,
                         "group":name,"index":"","label":label,"value":el.get_attribute("value") or "",
                         "selected":bool(el.is_selected()),"enabled":bool(el.is_enabled())})
        except Exception: pass
    return rows


def _stream_subjects_current(driver, stream_text, stream_value):
    out=[]
    grid=driver.find_elements(By.ID, config.OPTIONAL_SUBJECT_GRID_ID)
    if not grid: return out
    # Each row's first td is Group No; labels/radios live in second td.
    for tr in grid[0].find_elements(By.CSS_SELECTOR,"tr"):
        tds=tr.find_elements(By.CSS_SELECTOR,":scope > td")
        if len(tds)<2: continue
        group=(tds[0].text or "").strip()
        for radio in tds[1].find_elements(By.CSS_SELECTOR,"input[type='radio']"):
            rid=radio.get_attribute("id") or ""; label=""
            if rid:
                labs=driver.find_elements(By.CSS_SELECTOR, f"label[for='{rid}']")
                if labs: label=(labs[0].text or "").strip()
            out.append({"stream":stream_text,"stream_value":stream_value,"group_no":group,
                        "subject":label,"subject_code":radio.get_attribute("value") or "",
                        "radio_id":rid,"radio_name":radio.get_attribute("name") or ""})
    return out


def _inspect_all_streams(driver):
    sel_nodes=driver.find_elements(By.ID, config.STREAM_SELECT_ID)
    if not sel_nodes: return []
    sel=Select(sel_nodes[0])
    options=[((o.text or "").strip(), o.get_attribute("value") or "") for o in sel.options]
    options=[x for x in options if x[1] and x[1] not in ("0","-1")]
    try: original=sel.first_selected_option.get_attribute("value") or ""
    except Exception: original=""
    rows=[]
    for text,value in options:
        try:
            node=driver.find_element(By.ID, config.STREAM_SELECT_ID); cur=Select(node)
            current=cur.first_selected_option.get_attribute("value") or ""
            if current != value:
                before=page_change_token(driver); cur.select_by_value(value); wait_for_postback(driver,before)
            rows.extend(_stream_subjects_current(driver,text,value))
            print(f"[INFO] Inspected Stream {text}: {sum(1 for r in rows if r['stream_value']==value)} subjects")
        except Exception as e:
            print(f"[WARN] Could not inspect Stream {text}: {e}")
    if original and original not in ("0","-1"):
        try:
            node=driver.find_element(By.ID, config.STREAM_SELECT_ID); cur=Select(node)
            if cur.first_selected_option.get_attribute("value") != original:
                before=page_change_token(driver); cur.select_by_value(original); wait_for_postback(driver,before)
        except Exception: pass
    return rows


def _write_csv(path, rows, fieldnames):
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames); w.writeheader()
        for row in rows:
            w.writerow({key: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value for key, value in row.items()})


def run(driver, url: str=None, output_csv: str="fields.csv", inspect_streams: bool=False):
    if url:
        official_url(url)
        driver.get(url)
    official_url(driver.current_url)
    base=Path(output_csv); base.parent.mkdir(parents=True,exist_ok=True)
    fields=_dump_fields(driver)
    _write_csv(base,fields,["tag","id","name","type","visible","enabled","readonly","disabled","value","text","placeholder_or_href","onchange","onclick","nearby_label_guess"])

    options=_dump_options(driver)
    opt_path=base.with_name(base.stem+"_options.csv")
    _write_csv(opt_path,options,["control","parent_id","parent_name","group","index","label","value","selected","enabled"])

    stream_rows=_inspect_all_streams(driver) if inspect_streams else []
    stream_path=base.with_name(base.stem+"_stream_subjects.csv")
    _write_csv(stream_path,stream_rows,["stream","stream_value","group_no","subject","subject_code","radio_id","radio_name"])

    print(f"[INFO] Page URL: {driver.current_url}")
    print(f"[OK] Elements: {len(fields)} -> {base.resolve()}")
    print(f"[OK] Dropdown/radio options: {len(options)} -> {opt_path.resolve()}")
    print(f"[OK] Stream-dependent subjects: {len(stream_rows)} -> {stream_path.resolve()}")
    return {"fields":fields,"options":options,"stream_subjects":stream_rows}
