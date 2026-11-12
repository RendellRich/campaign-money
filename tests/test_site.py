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


def test_member_query_param_opens_that_member():
    members = pd.read_csv(ROOT / "site" / "data" / "members_2024.csv")
    bio = members["bioguide_id"].iloc[5]
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["member"] = bio
    at.run()
    assert not at.exception
    assert members["name"].iloc[5] in at.selectbox[0].value
    assert any(f"Member_Explorer?member={bio}" in m.value for m in at.markdown)


def test_unknown_member_param_explains_itself():
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["member"] = "X000000"
    at.run()
    assert not at.exception
    assert at.info and "No 2024 campaign committee" in at.info[0].value


def test_industry_page_renders_every_industry():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page("views/industries.py").run()
    assert not at.exception
    box = at.selectbox[0]
    for option in box.options[:3] + box.options[-2:]:
        box.select(option).run()
        assert not at.exception
        assert any("to current members from people who listed employers in" in m.value for m in at.markdown)
