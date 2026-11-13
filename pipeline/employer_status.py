"""Sort each itemized contribution by what the donor put in the employer and occupation fields, before any industry
is assigned. Retired and not employed are real answers, not missing data, but they carry no industry."""
from __future__ import annotations

import re

MISSING = re.compile(r"^(|N ?/? ?A|NONE PROVIDED|NONE GIVEN|INFO(RMATION)? REQUESTED.*|REQUESTED.*|BEST EFFORTS?.*|UNKNOWN|"
                     r"NOT PROVIDED|REFUSED|-|\.|X+|"
                     # misspelled or shortened "information requested", and other ways of saying the field was not filled in
                     r"INFO[A-Z]* RE(?!QUIREMENTS)(Q|U)[A-Z0-9]*( [A-Z]+)*|REQ\d*|(SECOND|2ND) REQUEST.*|UNABLE TO COLLECT|NEED TO ENTER|"
                     r"NOT APPLI[A-Z]*|DECLINED( TO PROVIDE)?|(WILL NOT|PREFER NOT TO|DID NOT) DISCLOSE|NO DISCLOS[A-Z]*|"
                     r"NO RESPON[A-Z]*|BLANK|NOT FOUND|OTHER)$")
# RETIRED at the start (RETIRED TEACHER) or the end (FIRE FIGHTER RETIRED, USPSRETIRED), plus common misspellings
RETIRED = re.compile(r"^RETIRED\b|^RET\.?$|RETIRED$|^(RETIRD|REIRED|RETIED|RETIRE|RETIREE|RETRIED|REITRED|RETIERD|RETIIRED|"
                     r"RETIRADO|JUBILADO|SEMI RETIRED)$")
NOT_EMPLOYED = re.compile(r"^(NOT ?EMPLOYED|NONE|UNEMPLOYED|HOMEMAKER|HOME ?MAKER|HOUSEWIFE|HOUSEHUSBAND|STUDENT|"
                          r"DISABLED|NOT CURRENTLY EMPLOYED|NO EMPLOYER|HOME MANAGER|[A-Z ]*STUDENT|"
                          r"NOT IN (THE )?WORK ?FORCE|NOT WORKING?|NOT EMPL[A-Z]*|CURRENTLY UNEMPLOYED|HOUSE ?WIFE|"
                          r"HOUSE ?MAKER|[A-Z ]*\bHOMEMAKER\b[A-Z ]*|SAHM|SAHD|STAY (AT )?HOME[A-Z ]*)$")
# Words that mean "not employed" only when the other field adds nothing: HOME or MOTHER next to a real employer
# could be a job (a home health aide, a company named Mother), so they count only next to blank, self or each other.
HOME_WORDS = re.compile(r"^(HOME|AT HOME|MOTHER|MOM|HOME MOTHER|HOMESCHOOL MOM|HOUSEHOLD|HOUSEHOLD MANAGEMENT)$")
SELF = re.compile(r"^(SELF|SELF ?EMPLOYED|SELF EMPLOYED.*|OWNER|SELF/.*|SEFL)$")

STATUSES = ["named employer", "self-employed, occupation given", "occupation only", "retired", "not employed",
            "self-employed, no occupation", "missing or requested"]
HAS_INDUSTRY_SIGNAL = {"named employer", "self-employed, occupation given", "occupation only"}


def _clean(text) -> str:
    text = text if isinstance(text, str) else ""
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", text.upper())).strip()


def status(employer, occupation) -> str:
    e, o = _clean(employer), _clean(occupation)
    if RETIRED.search(e) or RETIRED.search(o):
        return "retired"
    if NOT_EMPLOYED.match(e) or NOT_EMPLOYED.match(o) or NOT_EMPLOYED.match(f"{e} {o}".strip()):
        return "not employed"
    if any(HOME_WORDS.match(a) and (HOME_WORDS.match(b) or SELF.match(b) or MISSING.match(b)) for a, b in ((e, o), (o, e))):
        return "not employed"
    if SELF.match(e):
        return "self-employed, occupation given" if not MISSING.match(o) else "self-employed, no occupation"
    if MISSING.match(e):
        return "occupation only" if not MISSING.match(o) else "missing or requested"
    return "named employer"
