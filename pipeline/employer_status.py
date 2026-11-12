"""Sort each itemized contribution by what the donor put in the employer and occupation fields, before any industry
is assigned. Retired and not employed are real answers, not missing data, but they carry no industry."""
from __future__ import annotations

import re

MISSING = re.compile(r"^(|N ?A|NONE PROVIDED|INFO(RMATION)? REQUESTED.*|REQUESTED.*|BEST EFFORTS?.*|UNKNOWN|"
                     r"NOT PROVIDED|REFUSED|-|\.|X+)$")
RETIRED = re.compile(r"^RETIRED\b|^RET\.?$")
NOT_EMPLOYED = re.compile(r"^(NOT ?EMPLOYED|NONE|UNEMPLOYED|HOMEMAKER|HOME ?MAKER|HOUSEWIFE|HOUSEHUSBAND|STUDENT|"
                          r"DISABLED|NOT CURRENTLY EMPLOYED|NO EMPLOYER)$")
SELF = re.compile(r"^(SELF|SELF ?EMPLOYED|SELF EMPLOYED.*|OWNER|SELF/.*)$")

STATUSES = ["named employer", "self-employed, occupation given", "occupation only", "retired", "not employed",
            "self-employed, no occupation", "missing or requested"]
HAS_INDUSTRY_SIGNAL = {"named employer", "self-employed, occupation given", "occupation only"}


def _clean(text) -> str:
    text = text if isinstance(text, str) else ""
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", text.upper())).strip()


def status(employer, occupation) -> str:
    e, o = _clean(employer), _clean(occupation)
    if RETIRED.match(e) or RETIRED.match(o):
        return "retired"
    if NOT_EMPLOYED.match(e) or NOT_EMPLOYED.match(o):
        return "not employed"
    if SELF.match(e):
        return "self-employed, occupation given" if not MISSING.match(o) else "self-employed, no occupation"
    if MISSING.match(e):
        return "occupation only" if not MISSING.match(o) else "missing or requested"
    return "named employer"
