"""Members: one member at a time, every dollar of individual money accounted for, and how it changed between cycles."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from common import (AUDIT, CYCLES, INDUSTRY_NAMES, OTHER, PARTY_LETTER, bar_chart, cards, change_chart, colors,
                    composition, hero, inject_css, load, money_fmt, pick_cycle)

inject_css()
c = colors()

top_slot = st.container()  # the hero goes first on the page, but needs the cycle chosen below it
cycle = pick_cycle()
members, money = load(cycle)
comp = composition(money)
with top_slot:
    hero('Where Congress gets its campaign money',
         f"Money from individual donors to current members of Congress in the {cycle - 1} to {cycle} election cycle, "
         "sorted by the industry each donor listed. From the Federal Election Commission's public filings.",
         comp, f"Every dollar of the {money_fmt(sum(comp.values()))} that {len(members)} current members raised from "
               "individuals, by where it came from.")

members["option"] = [f"{n} ({PARTY_LETTER.get(p, p[:1])}-{s}, {ch})"
                     for n, p, s, ch in zip(members["name"], members["party"], members["state"], members["chamber"])]
# ?member=<Bioguide ID> opens a member directly, so PartyCohesion and shared links can point at one profile.
options = list(members["option"])
by_bioguide = dict(zip(members["bioguide_id"], options))
linked = by_bioguide.get(st.query_params.get("member", ""))
pick = st.selectbox("Member", options, index=options.index(linked) if linked else None,
                    placeholder="Search for a member of Congress")
if pick is None:
    asked = st.query_params.get("member", "")
    if asked:
        st.info(f"No {cycle} campaign committee was found for that member. New members, appointed senators and "
                "members who did not run that cycle have no profile here for it.")
        del st.query_params["member"]
    st.caption(f"{len(members)} current members with a principal campaign committee in the {cycle} cycle.")
    st.stop()

m = members[members["option"] == pick].iloc[0]
st.query_params["member"] = m["bioguide_id"]
voting_record = f"https://partycohesion.streamlit.app/Member_Explorer?member={m['bioguide_id']}"
mine = money[money["bioguide_id"] == m["bioguide_id"]].set_index("category")

# Peers: same party and same chamber. Medians of each member's own share, so a few large campaigns don't set them.
peers = members[(members["party"] == m["party"]) & (members["chamber"] == m["chamber"])]["bioguide_id"]
wide = money[money["bioguide_id"].isin(peers)].pivot_table(index="bioguide_id", columns="category", values="share",
                                                           fill_value=0)
peer_label = f"{m['party']}s in the {m['chamber']}"

st.subheader(m["name"])
industry_cats = [k for k in INDUSTRY_NAMES if k in mine.index]
ind_dollars = mine.loc[industry_cats, "dollars"] if industry_cats else pd.Series(dtype=float)
top = ind_dollars.idxmax() if len(ind_dollars) and ind_dollars.max() > 0 else None
cards([
    ("From individual donors", money_fmt(m["individual"]), f"{m['party']}, {m['state']}, {m['chamber']}"),
    ("Itemized", f"{m['itemized'] / m['individual']:.0%}" if m["individual"] else "n/a",
     f"{money_fmt(m['itemized'])} with donor details"),
    ("Largest industry", INDUSTRY_NAMES[top] if top else "None",
     f"{ind_dollars[top] / m['individual']:.1%} of individual money" if top else "No itemized money placed"),
])

# 1. Who gave: every dollar, with the shares that can't be placed in an industry shown as their own bars.
rows = []
for key, label in OTHER:
    if key == "industry":
        dollars = ind_dollars.sum()
        med = wide[[k for k in INDUSTRY_NAMES if k in wide]].sum(axis=1).median()
    else:
        dollars = mine["dollars"].get(key, 0)
        med = wide[key].median() if key in wide else 0
    rows.append({"key": key, "label": label, "dollars": dollars,
                 "share": dollars / m["individual"] if m["individual"] else 0, "median": med})
who = pd.DataFrame(rows).assign(dollars_fmt=lambda d: d["dollars"].map(money_fmt))
st.markdown("#### Where the money came from")
st.caption(f"Share of all individual money. The tick is the median for {peer_label}.")
st.altair_chart(bar_chart(who, c, [label for _, label in OTHER], median=True), width="stretch")

# 2. By industry, as a share of the same total, so the bars are never read as more than they are.
ind = pd.DataFrame([{"key": "industry", "label": INDUSTRY_NAMES[k], "dollars": mine.loc[k, "dollars"],
                     "share": mine.loc[k, "share"], "median": wide[k].median() if k in wide else 0}
                    for k in industry_cats])
st.markdown("#### By industry")
placed = who.loc[who["key"] == "industry", "share"].iloc[0]
st.caption(f"Received from people who listed employers in each industry, as a share of all individual money. "
           f"Together these are {placed:.0%}; the rest is in the chart above. The tick is the median for {peer_label}.")
if ind.empty or ind["dollars"].sum() == 0:
    st.write("No itemized money could be placed in an industry.")
else:
    ind = ind[ind["dollars"] > 0].sort_values("share", ascending=False)
    ind["dollars_fmt"] = ind["dollars"].map(money_fmt)
    st.altair_chart(bar_chart(ind, c, list(ind["label"]), median=True), width="stretch")

# 3. Change between cycles, when the member had a committee in both.
other_cycle = next((x for x in CYCLES if x != cycle), None)
if other_cycle:
    before, after = sorted((cycle, other_cycle))
    mem_b, mon_b = load(before)
    mem_a, mon_a = load(after)
    bio = m["bioguide_id"]
    if bio in set(mem_b["bioguide_id"]) and bio in set(mem_a["bioguide_id"]):
        def shares(mon: pd.DataFrame) -> pd.Series:
            s = mon[mon["bioguide_id"] == bio].set_index("category")["share"]
            out = {"industry": s[s.index.isin(INDUSTRY_NAMES)].sum()}
            out.update({k: s.get(k, 0.0) for k, _ in OTHER[1:]})
            out.update({k: s.get(k, 0.0) for k in INDUSTRY_NAMES})
            return pd.Series(out)
        sb, sa = shares(mon_b), shares(mon_a)
        top_ind = sa[list(INDUSTRY_NAMES)].add(sb[list(INDUSTRY_NAMES)], fill_value=0).nlargest(5).index
        labels = dict(OTHER) | {k: INDUSTRY_NAMES[k] for k in top_ind}
        keys = [k for k, _ in OTHER] + list(top_ind)
        ch = pd.DataFrame({"key": [k if k in dict(OTHER) else "industry" for k in keys], "label": [labels[k] for k in keys],
                           "share_before": [sb[k] for k in keys], "share_after": [sa[k] for k in keys]})
        tb = mem_b.set_index("bioguide_id").loc[bio, "individual"]
        ta = mem_a.set_index("bioguide_id").loc[bio, "individual"]
        st.markdown(f"#### Since the {before} cycle" if cycle == after else f"#### Into the {after} cycle")
        st.caption(f"Individual money went from {money_fmt(tb)} to {money_fmt(ta)}. Hollow dot: {before - 1} to {before}. "
                   f"Filled dot: {after - 1} to {after}. The last five rows are this member's largest industries across "
                   "both cycles.")
        st.altair_chart(change_chart(ch, c, list(ch["label"]), before, after), width="stretch")

with st.expander("Table"):
    table = pd.concat([who[["label", "dollars", "share", "median"]],
                       ind[["label", "dollars", "share", "median"]] if not ind.empty else None])
    st.dataframe(table.rename(columns={"label": "Category", "dollars": "Dollars", "share": "Share",
                                       "median": f"Median, {peer_label}"}),
                 hide_index=True, width="stretch",
                 column_config={"Dollars": st.column_config.NumberColumn(format="$%d"),
                                "Share": st.column_config.NumberColumn(format="percent"),
                                f"Median, {peer_label}": st.column_config.NumberColumn(format="percent")})

links = ", ".join(f"[{cm} on FEC.gov](https://www.fec.gov/data/committee/{cm}/?cycle={cycle})"
                  for cm in str(m["committees"]).split(";"))
st.markdown(f"Filings behind these numbers: {links}. Voting record: "
            f"[{m['name']} on PartyCohesion]({voting_record}), a separate site.")

st.divider()
st.markdown("#### How to read this")
audit = json.loads(AUDIT.read_text())["all"] if AUDIT.exists() else None
accuracy = (f" In a blind audit on a held-out sample, {audit['correct'] / (audit['correct'] + audit['wrong']):.0%} of "
            "the dollars given an industry were placed in the right one.") if audit else ""
st.markdown(
    "- Industry comes from the employer and occupation each donor typed on their contribution. It describes where "
    "donors work, not who they speak for, and a donation is not a vote or a promise.\n"
    "- Donors who gave $200 or less in the cycle are not itemized, so their industry can't be known.\n"
    "- \"Points to an industry, but which is unclear\" means the donor named an employer or job the method couldn't "
    f"place. It is kept as its own bar instead of being guessed.{accuracy} The reviewed employer list was built from "
    "2024 donors, so slightly more 2022 money is unclear.\n"
    "- This site never pairs a donation with a vote. For voting records, see "
    "[PartyCohesion](https://partycohesion.streamlit.app).\n"
    "- Method, code and the full audit: [github.com/RendellRich/campaign-money](https://github.com/RendellRich/campaign-money)."
)
