"""Assign an industry to a contribution: the reviewed employer list first, then the rules, then (when the employer
says nothing) the reviewed occupation list, else "unknown".

data/employer_industry.csv covers the 1,000 employers with the most itemized dollars to current members in the 2024
cycle (25% of named-employer dollars). Its labels came from pipeline/industry_rules.py and were then reviewed one by
one by an AI assistant (Claude), which changed or filled in 291 of them; the `source` column says which.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from employer_status import HAS_INDUSTRY_SIGNAL, status
from industry_rules import GENERIC_TITLE, classify, norm

MAPPING = Path(__file__).resolve().parents[1] / "data" / "employer_industry.csv"
# The 800 occupations with the most still-unclear dollars in 2024, reviewed by Claude. An occupation names an industry
# only when the job alone implies one (attorney, optometrist, landman); titles like CEO or engineer stay unknown.
OCCUPATIONS = Path(__file__).resolve().parents[1] / "data" / "occupation_industry.csv"


@lru_cache(maxsize=1)
def mapping() -> dict[str, str]:
    m = pd.read_csv(MAPPING, dtype=str)
    return dict(zip(m["employer"], m["industry"]))


@lru_cache(maxsize=1)
def occupations() -> dict[str, str]:
    m = pd.read_csv(OCCUPATIONS, dtype=str, keep_default_na=False)
    return {o: i for o, i in zip(m["occupation"], m["industry"]) if i != "unknown"}


def industry(employer, occupation) -> tuple[str, str]:
    """(industry, how it was decided). Retired, not employed and missing get their status, not an industry."""
    st = status(employer, occupation)
    if st not in HAS_INDUSTRY_SIGNAL:
        return st.replace(" or requested", "").replace(", no occupation", ""), "status"
    # The list is for named employers. "SELF EMPLOYED" is on it (as unknown) only because it is a top-1,000 string;
    # for the self-employed the occupation decides.
    known = mapping().get(norm(employer)) if st == "named employer" else None
    if not known and st == "named employer" and GENERIC_TITLE.match(norm(employer)):
        known = mapping().get(norm(occupation))  # swapped fields: "CO-FOUNDER" / "ARES MANAGEMENT"
    if known and known != "unknown":
        return known, "list"
    ind, how = (known, "list") if known else classify(employer if st == "named employer" else "", occupation)
    employer_silent = st != "named employer" or bool(GENERIC_TITLE.match(norm(employer)))
    if (not ind or ind == "unknown") and employer_silent:
        # Last resort, when the employer says nothing (self-employed, left blank, or a bare title): the reviewed
        # occupation list, for jobs that name the industry on their own.
        by_job = occupations().get(norm(occupation))
        if by_job:
            return by_job, "occupation list"
    return (ind or "unknown"), how
