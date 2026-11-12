import sys
from pathlib import Path

import pandas as pd
import pytest

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
    # MEHLMAN CONSULTING is a lobbying firm; the rules alone would call it business services.
    assert classify("MEHLMAN CONSULTING", "PARTNER")[0] == "business_services"
    assert industry("MEHLMAN CONSULTING", "PARTNER") == ("lobbying", "list")


def test_dev_audit_rule_fixes():
    assert classify("POWER ROGERS AND SMITH", "ATTORNEY")[0] == "law"            # POWER only as a utility
    assert classify("FLORIDA POWER & LIGHT", "")[0] == "energy"
    assert classify("CITY OF HOPE", "PHYSICIAN")[0] == "health"
    assert classify("LOUDOUN COUNTY PUBLIC SCHOOLS", "TEACHER")[0] == "education"
    assert classify("COLLEGE PARK CAR WASH", "PRESIDENT")[0] != "education"
    assert classify("CONSULTING", "GENERAL CONTRACTOR")[0] == "real_estate"      # generic employer falls through
    assert industry("CO-FOUNDER", "ARES MANAGEMENT") == ("finance", "list")      # swapped fields
    assert classify("IGNITE", "FINANCE DIRECTOR")[0] is None                    # a finance job, not a finance firm
    assert status("N/A", "N/A") == "missing or requested"
    assert status("UNIVERSITY OF TENNESSEE", "LAW STUDENT") == "not employed"


def test_status_comes_before_industry():
    assert industry("RETIRED", "RETIRED")[0] == "retired"
    assert industry("", "")[0] == "missing"


def test_mapping_file_is_valid():
    m = pd.read_csv(ROOT / "data" / "employer_industry.csv")
    assert len(m) >= 1000 and m["employer"].is_unique
    assert set(m["industry"]) <= set(INDUSTRIES) | {"not_employed"}
    assert set(m["source"]) <= {"rule", "review"}


def test_self_employed_uses_occupation_not_the_list():
    # "SELF EMPLOYED" is on the employer list as unknown; the occupation must still decide.
    assert industry("SELF EMPLOYED", "DENTIST")[0] == "health"
    assert industry("SELF-EMPLOYED", "ATTORNEY")[0] == "law"


@pytest.mark.parametrize("tag", ["2024", "2024_test"])
def test_audit_files_line_up(tag):
    sample = pd.read_csv(ROOT / "data" / f"audit_{tag}_sample.csv", dtype=str, keep_default_na=False)
    labels = pd.read_csv(ROOT / "data" / f"audit_{tag}_labels.csv", dtype=str, keep_default_na=False)
    assert set(sample["id"]) == set(labels["id"])
    allowed = set(INDUSTRIES) | {"retired", "not employed", "missing"}
    assert set(labels["label"]) <= allowed
    assert set(labels["confidence"]) <= {"high", "low"}
    assert {"employer", "occupation"} <= set(sample.columns) and "label" not in sample.columns


def test_occupation_list_places_self_employed_jobs():
    assert industry("SELF-EMPLOYED", "TUTOR") == ("education", "occupation list")
    assert industry("SELF EMPLOYED", "POET") == ("media", "occupation list")
    assert industry("", "OPTOMETRIST") == ("health", "occupation list")
    assert industry("OWNER", "LANDMAN") == ("energy", "occupation list")  # a bare title as employer says nothing


def test_occupation_list_does_not_override_a_named_employer():
    # A property manager at a bus company works in transportation; the job alone can't say so.
    assert industry("MN COACHES", "PROPERTY MANAGER")[0] == "unknown"
    assert industry("SELF EMPLOYED", "CEO")[0] == "unknown"  # titles stay unknown


def test_occupation_list_labels_are_valid():
    m = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "occupation_industry.csv", keep_default_na=False)
    assert set(m["industry"]) <= set(INDUSTRIES) | {"unknown"}
    assert not m["occupation"].duplicated().any()


def test_fresh_prompt_is_blind_and_complete():
    root = Path(__file__).resolve().parents[1] / "data"
    prompt = (root / "audit_2024_fresh_prompt.txt").read_text()
    sample = pd.read_csv(root / "audit_2024_fresh_sample.csv", dtype=str, keep_default_na=False)
    assert len(sample) == 100 and all(i in prompt for i in sample["id"])
    for leak in ("predicted", "pipeline says", "stratum", "dollars"):
        assert leak not in prompt  # raters see only what the donor wrote


def test_compare_rejects_labels_outside_the_list(tmp_path):
    from audit_compare import read_labels
    bad = tmp_path / "audit_2024_fresh_labels_x.csv"
    bad.write_text("id,label,confidence\nC001,banking,high\n")
    with pytest.raises(SystemExit):
        read_labels(bad)
    ok = tmp_path / "audit_2024_fresh_labels_y.csv"
    ok.write_text("id,label,confidence\nC001,Real Estate,HIGH\nC002,Not Employed,low\n")
    assert list(read_labels(ok)["label"]) == ["real_estate", "not employed"]
