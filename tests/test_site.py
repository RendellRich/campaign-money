from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "site" / "app.py")


def test_money_adds_up_to_each_members_total():
    members = pd.read_csv(ROOT / "site" / "data" / "members_2024.csv")
    money = pd.read_csv(ROOT / "site" / "data" / "member_money_2024.csv")
    sums = money.groupby("bioguide_id")["dollars"].sum()
    gap = (sums - members.set_index("bioguide_id")["individual"]).abs()
    assert gap.max() <= 30  # rounding to whole dollars, about 25 categories


def test_one_committee_per_member():
    members = pd.read_csv(ROOT / "site" / "data" / "members_2024.csv")
    cm = members["committees"].str.split(";").explode()
    assert not cm.duplicated().any()


def test_app_starts_and_shows_a_member():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    option = at.selectbox[0].options[0]
    at.selectbox[0].select(option).run()
    assert not at.exception
    assert any("from individual donors" in m.value for m in at.markdown)
