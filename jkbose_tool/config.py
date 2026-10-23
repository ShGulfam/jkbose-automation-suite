"""
Central configuration for the JKBOSE automation tool.

Nothing here needs to change to add a new feature -- feature modules
import from this file, and you can override any value per-run with a
CLI flag (see main.py --help) instead of editing this file directly.
"""

# ---- Site ----
LOGIN_URL = "https://jkbose.jk.gov.in/utilities/auth_pages/login.aspx"
EXAM_RR_LINK_ID = "HyperLink18"   # the "Exam / RR - 11/12" sidebar link

# The "Class" dropdown on the RR/registration form -- must be set to "11"
# or "12" BEFORE entering the registration number / clicking Get Details,
# otherwise the lookup applies to the wrong class. Confirmed via
# `python main.py inspect` on the renewal/registration form (2026-08-15).
CLASS_SELECT_ID = "bodypH_ddlselectclass"

# The "Stream" dropdown -- selecting it changes which subjects show up
# (used for the Check Students combined screenshot, and already used by
# submit_form.py's FIELD_MAP for the Stream column).
STREAM_SELECT_ID = "bodypH_ddlstream"

# ---- Timeouts (seconds) ----
MANUAL_LOGIN_TIMEOUT = 600     # time allowed for you to log in + solve captcha
ELEMENT_WAIT = 25              # for fields that MUST appear (RegNo, Get Details, Class)
QUICK_WAIT = 1                 # for optional fields that may or may not exist on the
                                # current page -- avoids wasting 25s per absent field
PAGE_CHANGE_TIMEOUT = 20
SHORT_WAIT = 1

# How long to wait for the page to fully settle (e.g. a subjects grid
# populated after Get Details / a Stream change) beyond the initial
# postback detection -- see browser.wait_until_page_stable().
SUBJECTS_STABLE_TIMEOUT = 8    # max extra seconds to wait
SUBJECTS_STABLE_POLL = 0.5     # seconds between checks
SUBJECTS_STABLE_READS = 2      # consecutive unchanged reads = "settled"

# ---- Persistent Chrome profile ----
# Reuse a dedicated Chrome profile folder across runs so, once you log in
# once inside the automated window, cookies persist and later runs skip
# straight past login (until the site session expires). Set to None to
# always start a fresh, logged-out browser.
from pathlib import Path
CHROME_PROFILE_DIR = str(Path.home() / ".jkbose_tool_chrome_profile")

# ---- Screenshot compression ----
# "png"  -> lossless-ish, palette-quantized. Crisp text, much smaller than a
#           raw screenshot PNG. Use this if the page has flat colors/text
#           (which JKBOSE's forms do).
# "jpeg" -> lossy, smallest files, still legible at quality >= 75.
SCREENSHOT_FORMAT = "png"
SCREENSHOT_JPEG_QUALITY = 80
SCREENSHOT_PNG_COLORS = 64        # palette size for PNG quantization
SCREENSHOT_MAX_WIDTH = 1600       # downscale very wide captures; None = no resize

# ---- Form submission ----
UPLOAD_RETRIES = 3
PROGRESS_SAVE_EVERY = 5       # submit pipeline: batch Excel progress writes instead of rewriting every row
RADIO_ATTEMPTS = 6
MAX_SUBJECT_RETRIES = 10

# Field map for the RR Renewal / Exam form (renewalformxixii.aspx), rebuilt
# from a live `inspect` dump on 2026-08-15. Each entry is:
#   (excel_column, element_id, kind)
# kind is one of:
#   "text"            plain text input
#   "select"          <select>, no postback expected after choosing
#   "select_postback" <select> that triggers an ASP.NET postback (page
#                     re-renders / dependent fields change) after choosing
#   "checkbox_postback" checkbox that triggers a postback when checked
#
# "RegNo" is handled separately (it's the lookup field, filled first,
# then 'Get Details' is clicked) -- it's listed here just for reference.
# "Class" is ALSO handled separately and BEFORE RegNo/Get Details: the
# site requires the Class dropdown (11/12) be set first, or the lookup
# targets the wrong class. Its kind is "class_preselect" purely so the
# generic fill loop below skips it (same reason RegNo uses "lookup").
FIELD_MAP = [
    ("RegNo",               "bodypH_txt_rege",       "lookup"),
    ("Class",               "bodypH_ddlselectclass", "class_preselect"),
    ("LastClassAttended",   "bodypH_ddllastclass",   "select"),
    ("Stream",              "bodypH_ddlstream",      "select_postback"),
    ("FirstName",           "bodypH_txtfirstname",   "text"),
    ("MiddleName",          "bodypH_txtmiddlename",  "text"),
    ("LastName",            "bodypH_txtlastname",    "text"),
    ("FatherName",          "bodypH_txtfathername",  "text"),
    ("MotherName",          "bodypH_txtmothername",  "text"),
    ("DOB",                 "bodypH_txtdob",         "text"),
    ("Gender",               "bodypH_ddlgender",     "select"),
    ("Religion",             "bodypH_ddlreligion",   "select"),
    ("Category",             "bodypH_ddlcategory",   "select"),
    ("Landline",             "bodypH_txtlandline",   "text"),
    ("Email",                "bodypH_txtemail1",     "text"),
    ("Mobile",               "bodypH_txtmobile1",    "text"),
    ("CurrAddress1",         "bodypH_txtcurradd1",   "text"),
    ("CurrAddress2",         "bodypH_txtcurradd2",   "text"),
    ("CurrVillage",          "bodypH_txtcurrvillage","text"),
    ("CurrArea",             "bodypH_txtcurrarea",   "text"),
    ("CurrPincode",          "bodypH_ddlcurrpincode","select_postback"),
    ("CurrDistrict",         "bodypH_ddlcurrdistrict","select"),
    ("PermanentSameCurrent", "bodypH_cb1",           "checkbox_postback"),
    ("PermAddress1",         "bodypH_txtperadd1",    "text"),
    ("PermAddress2",         "bodypH_txtperadd2",    "text"),
    ("PermVillage",          "bodypH_txtpervillage", "text"),
    ("PermArea",             "bodypH_txtperarea",    "text"),
    ("PermPincode",          "bodypH_ddlperpincode", "select_postback"),
    ("PermDistrict",         "bodypH_ddlperdistrict","select"),
    ("Disability",           "bodypH_ddldisability", "select_postback"),
    ("DisabilityPercent",    "bodypH_ddldisabilityper","select"),
    ("VocationalCode",       "bodypH_ddlvocational", "select"),
    ("AdditionalSubject",    "bodypH_ddladditional", "select"),
]

# Photo/signature upload inputs (confirmed against live dump -- unchanged).
PHOTO_UPLOAD_ID = "bodypH_FileUpload1"
SIGNATURE_UPLOAD_ID = "bodypH_FileUpload2"

# Lookup / navigation (confirmed against live dump 2026-08-15).
GET_DETAILS_BTN_ID = "bodypH_btnregdetails"
RESET_SUBJECTS_BTN_ID = "bodypH_btnreset"
SUBMIT_BTN_ID = "bodypH_Button3"
CAPTCHA_INPUT_ID = "bodypH_CaptchaCode2"

# Subject grid / inspection helpers.
OPTIONAL_SUBJECT_GRID_ID = "bodypH_grdoptional"
VOCATIONAL_SELECT_ID = "bodypH_ddlvocational"
ADDITIONAL_SUBJECT_SELECT_ID = "bodypH_ddladditional"
