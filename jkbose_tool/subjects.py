"""Subject vocabulary and helpers for JKBOSE XI/XII forms.

The submitter primarily matches subjects by *visible label text* on the live
page, so numeric codes are not required in Excel.  This catalog is a local
validation/fallback snapshot built from inspected JKBOSE markup.  The live DOM
remains authoritative because subject codes/options can change.
"""
import re

STREAM_ALIASES = {
    "s": "Science", "science": "Science",
    "c": "Commerce", "commerce": "Commerce",
    "h": "Humanities", "humanities": "Humanities", "arts": "Humanities",
    "hs": "Home Science", "home science": "Home Science", "homescience": "Home Science",
}
STREAM_VALUES = {"Science": "S", "Commerce": "C", "Humanities": "H", "Home Science": "HS"}

# Confirmed from markup supplied/inspected on 2026-08-31.
SUBJECT_CODES = {
    "Science": {
        "Mathematics": "135", "Applied Mathematics": "141",
        "Biology": "142", "Statistics": "143", "Geography": "144",
        "Biotechnology": "146", "Microbiology": "147", "Biochemistry": "148", "Geology": "145",
        "Physical Education": "149", "Food Technology": "150", "Computer Science": "201",
        "Information Practices": "202", "Environmental Science": "203", "Functional English": "204",
        "Vedic Studies": "205", "Buddhist Studies": "206", "Electronics": "207", "Islamic Studies": "222",
    },
    "Humanities": {
        "Urdu": "101", "Hindi": "102", "Kashmiri": "103", "Dogri": "104", "Punjabi": "105", "Bhoti": "106",
        "Arabic": "107", "Sanskrit": "108", "Persian": "109", "Economics": "110",
        "Mathematics": "111", "Applied Mathematics": "112", "Sociology": "113",
        "Psychology": "114", "Music": "115", "Geography": "116", "Philosophy": "117", "Education": "118",
        "History": "119", "Home Science (Elective)": "120", "Public Administration": "121",
        "Statistics": "122", "Political Science": "123",
        "Islamic Studies": "99", "Food Technology": "100", "Computer Science": "217",
        "Information Practices": "218", "Environmental Science": "219", "Functional English": "220",
        "Physical Education": "221", "Vedic Studies": "223", "Buddhist Studies": "224",
        "Travel Tourism And Hotel Mgmt": "225", "English Literature": "226",
    },
}

VOCATIONAL_CODES = {
    "IT And ITES": "124", "Retail": "125", "Healthcare": "126", "Security": "128",
    "Agriculture": "129", "Telecommunication": "130", "Media And Entertainment": "131",
    "Beauty And Wellness": "132", "Physical Education And Sports": "133",
    "Apparels Made Ups And Home Furnishing": "379", "Automotive": "383",
    "Electronics And Hardware": "387", "Plumber": "391", "Power": "488",
    "Tourism And Hospitality": "496",
}

# Common compulsory subjects. These are displayed by JKBOSE but are not
# radio choices in the optional-subject grid.  The live page is still the
# final authority; these names are mainly used to avoid treating obvious
# compulsory subjects as missing optional radios during preflight.
COMPULSORY_BY_STREAM = {
    "Science": {"General English", "Physics", "Chemistry"},
}
# General English is treated as compulsory even if a stream-specific catalog
# has not yet been inspected. Other subjects are stream-scoped to avoid false
# assumptions for Commerce/Humanities/Home Science.
GENERIC_COMPULSORY = {"General English"}

# Friendly input-header aliases. Users often already have admissions data
# with shorter headings; normalize those once instead of forcing them to
# rename columns before every run. Canonical names match config.FIELD_MAP.
COLUMN_ALIASES = {
    "addressline1": "CurrAddress1",
    "currentaddress1": "CurrAddress1",
    "address1": "CurrAddress1",
    "addressline2": "CurrAddress2",
    "currentaddress2": "CurrAddress2",
    "address2": "CurrAddress2",
    "village town": "CurrVillage",
    "village": "CurrVillage",
    "town": "CurrVillage",
    "pincode": "CurrPincode",
    "pin": "CurrPincode",
    "district": "CurrDistrict",
    "area": "CurrArea",
}

ALIASES = {
    "physical education": "Physical Education",
    "pe": "Physical Education",
    "computer": "Computer Science", "cs": "Computer Science",
    "information practice": "Information Practices", "informatics practices": "Information Practices", "ip": "Information Practices",
    "environment science": "Environmental Science", "evs": "Environmental Science",
    "islamic study": "Islamic Studies",
    "political sci": "Political Science", "pol science": "Political Science",
    "home science elective": "Home Science (Elective)",
    "travel tourism hotel management": "Travel Tourism And Hotel Mgmt",
    "travel tourism and hotel management": "Travel Tourism And Hotel Mgmt",
    "it & ites": "IT And ITES", "it and ites": "IT And ITES",
}

def norm(text):
    text = str(text or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())

def canonical_stream(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    return STREAM_ALIASES.get(norm(raw), raw)

def stream_value(value):
    c = canonical_stream(value)
    return STREAM_VALUES.get(c, str(value or "").strip())

def canonical_subject(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    n = norm(raw)
    if n in ALIASES:
        return ALIASES[n]
    # Find exact normalized catalog name across streams/vocational.
    for mapping in list(SUBJECT_CODES.values()) + [VOCATIONAL_CODES]:
        for name in mapping:
            if norm(name) == n:
                return name
    return raw

def subject_columns(columns):
    """Return Excel columns that can carry ordinary subject names."""
    out = []
    for c in columns:
        n = norm(c)
        if n == "subjects" or re.fullmatch(r"(optional )?subject ?\d*", n) or re.fullmatch(r"sub ?\d+", n):
            out.append(c)
    return out

def subjects_from_row(row):
    values = []
    for col in subject_columns(row.index if hasattr(row, "index") else row.keys()):
        raw = str(row.get(col, "") or "").strip()
        if not raw:
            continue
        parts = re.split(r"[,;|\n]+", raw) if norm(col) == "subjects" else [raw]
        for part in parts:
            part = canonical_subject(part)
            if part and norm(part) not in {norm(x) for x in values}:
                values.append(part)
    return values


def canonicalize_row_columns(row):
    """Return a copy with friendly/legacy headings mirrored to canonical ones.

    Existing canonical columns always win. This keeps old workbooks working
    while allowing simpler headings such as AddressLine1 and Village/Town.
    """
    out = row.copy() if hasattr(row, "copy") else dict(row)
    keys = list(row.index if hasattr(row, "index") else row.keys())
    existing_norm = {norm(k): k for k in keys}
    for alias_norm, canonical in COLUMN_ALIASES.items():
        source = existing_norm.get(alias_norm)
        if source is None:
            continue
        current = str(out.get(canonical, "") or "").strip()
        if not current:
            out[canonical] = row.get(source, "")
    return out

def split_subject_roles(subjects, stream=""):
    """Split friendly subject names into compulsory / vocational / optional.

    Vocational names may be supplied directly in sub1/sub2/...; they are
    routed to the vocational dropdown automatically. Compulsory names are
    retained for preview but are not clicked as optional radios.
    """
    compulsory, vocational, optional = [], [], []
    voc_norm = {norm(k): k for k in VOCATIONAL_CODES}
    stream_name = canonical_stream(stream)
    compulsory_names = set(GENERIC_COMPULSORY) | set(COMPULSORY_BY_STREAM.get(stream_name, set()))
    comp_norm = {norm(k): k for k in compulsory_names}
    for raw in subjects:
        name = canonical_subject(raw)
        n = norm(name)
        if n in voc_norm:
            vocational.append(voc_norm[n])
        elif n in comp_norm:
            compulsory.append(comp_norm[n])
        else:
            optional.append(name)
    return compulsory, vocational, optional
