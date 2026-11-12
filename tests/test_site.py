from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "site" / "app.py")


@pytest.mark.parametrize("cycle", [2024, 2022])
def test_money_adds_up_to_each_members_total(cycle):
    members = pd.read_csv(ROOT / "site" / "data" / f"members_{cycle}.csv")
    money = pd.read_csv(ROOT / "site" / "data" / f"member_money_{cycle}.csv")
    sums = money.groupby("bioguide_id")["dollars"].sum()
    gap = (sums - members.set_index("bioguide_id")["individual"]).abs()
    assert gap.max() <= 30  # rounding to whole dollars, about 25 categories


@pytest.mark.parametrize("cycle", [2024, 2022])
def test_one_committee_per_member(cycle):
    members = pd.read_csv(ROOT / "site" / "data" / f"members_{cycle}.csv")
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


def test_2022_cycle_and_change_section():
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["member"] = "G000583"
    at.run()
    assert not at.exception
    assert any("Since the 2022 cycle" in m.value for m in at.markdown)
    at = AppTest.from_file(APP, default_timeout=30)  # a fresh visit, as from a shared link
    at.query_params["member"] = "G000583"
    at.query_params["cycle"] = "2022"
    at.run()
    assert not at.exception
    assert any("Into the 2024 cycle" in m.value for m in at.markdown)


def test_2022_itemized_share_is_in_line_with_2024():
    # Guards against reading the incomplete itcont.txt in the 2022 zip again (it held about a third of the rows).
    for cycle in (2022, 2024):
        m = pd.read_csv(ROOT / "site" / "data" / f"members_{cycle}.csv")
        assert 0.5 < m["itemized"].sum() / m["individual"].sum() < 0.8


def test_filters_narrow_the_member_list():
    at = AppTest.from_file(APP, default_timeout=30).run()
    everyone = len(at.selectbox[0].options)
    at.session_state["f_chamber"] = ["Senate"]
    at.session_state["f_status"] = ["Former member"]
    at.run()
    assert not at.exception
    senators = at.selectbox[0].options
    assert 0 < len(senators) < everyone
    assert all("Senate, former" in o for o in senators)


def test_former_member_has_a_profile_and_totals_stay_current_only():
    members = pd.read_csv(ROOT / "site" / "data" / "members_2024.csv")
    assert (~members["current"]).sum() > 50
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["member"] = "T000464"  # Jon Tester, no longer serving
    at.run()
    assert not at.exception
    assert any("no longer serving" in m.value for m in at.markdown)
    assert any(f"that {members['current'].sum()} current members raised" in m.value for m in at.markdown)


def test_filter_changes_the_numbers_not_just_the_list():
    members = pd.read_csv(ROOT / "site" / "data" / "members_2024.csv")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any(f"that {members['current'].sum()} current members raised" in m.value for m in at.markdown)
    assert at.dataframe and len(at.dataframe[0].value) == members["current"].sum()
    at.session_state["f_chamber"] = ["Senate"]
    at.session_state["f_party"] = ["Republican"]
    at.run()
    assert not at.exception
    n = (members["current"] & (members["chamber"] == "Senate") & (members["party"] == "Republican")).sum()
    assert any(f"that {n} current Republican senators raised" in m.value for m in at.markdown)
    assert len(at.dataframe[0].value) == n
    assert any("The tick is all current members of Congress" in c.value for c in at.caption)


def test_filter_with_no_matches_explains_itself():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.session_state["f_party"] = ["Independent"]
    at.session_state["f_min"] = "$10M or more"
    at.run()
    assert not at.exception
    assert any("No members match these filters" in m.value for m in at.markdown)
