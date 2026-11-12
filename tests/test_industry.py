import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from employer_status import status  # noqa: E402
from industry import industry  # noqa: E402
from industry_rules import INDUSTRIES, classify, norm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_status_buckets():
    assert status("RETIRED", "RETIRED") == "retired"
    assert status("NOT-EMPLOYED", "NOT EMPLOYED") == "not employed"
    assert status("HOUSEWIFE", "HOUSEWIFE") == "not employed"
    assert status("SELF-EMPLOYED", "ATTORNEY") == "self-employed, occupation given"
    assert status("INFORMATION REQUESTED", "INFORMATION REQUESTED") == "missing or requested"
    assert status(None, None) == "missing or requested"
    assert status("", "PHYSICIAN") == "occupation only"
    assert status("EXXON MOBIL CORP", "ENGINEER") == "named employer"


def test_norm_drops_corporate_suffixes():
    assert norm("Goldman Sachs & Co., LLC") == "GOLDMAN SACHS"
    assert norm(None) == ""


def test_employer_rules_beat_occupation():
    # A lawyer at a tech company is in tech; a lawyer at a law firm is in law.
    assert classify("MICROSOFT CORP", "ATTORNEY")[0] == "tech"
    assert classify("SMITH & JONES", "ATTORNEY")[0] == "law"
    assert classify("FIERCE GOVERNMENT RELATIONS", "CONSULTANT")[0] == "lobbying"
    assert classify("UNIVERSITY OF MICHIGAN", "PROFESSOR")[0] == "education"


def test_swapped_fields():
    assert classify("CEO", "ACME CAPITAL PARTNERS")[0] == "finance"


def test_list_wins_over_rules():
    # POWER ROGERS is a law firm; the rules alone would call it energy.
    assert classify("POWER ROGERS", "ATTORNEY")[0] == "energy"
    assert industry("POWER ROGERS", "ATTORNEY") == ("law", "list")


def test_status_comes_before_industry():
    assert industry("RETIRED", "RETIRED")[0] == "retired"
    assert industry("", "")[0] == "missing"


def test_mapping_file_is_valid():
    m = pd.read_csv(ROOT / "data" / "employer_industry.csv")
    assert len(m) == 1000 and m["employer"].is_unique
    assert set(m["industry"]) <= set(INDUSTRIES) | {"not_employed"}
    assert set(m["source"]) <= {"rule", "review"}


def test_self_employed_uses_occupation_not_the_list():
    # "SELF EMPLOYED" is on the employer list as unknown; the occupation must still decide.
    assert industry("SELF EMPLOYED", "DENTIST")[0] == "health"
    assert industry("SELF-EMPLOYED", "ATTORNEY")[0] == "law"


def test_audit_files_line_up():
    sample = pd.read_csv(ROOT / "data" / "audit_2024_sample.csv", dtype=str, keep_default_na=False)
    labels = pd.read_csv(ROOT / "data" / "audit_2024_labels.csv", dtype=str, keep_default_na=False)
    assert set(sample["id"]) == set(labels["id"])
    allowed = set(INDUSTRIES) | {"retired", "not employed"}
    assert set(labels["label"]) <= allowed
    assert set(labels["confidence"]) <= {"high", "low"}
    assert {"employer", "occupation"} <= set(sample.columns) and "label" not in sample.columns
