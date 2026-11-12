"""Members: one member at a time, every dollar of individual money accounted for."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from common import AUDIT, CYCLE, INDUSTRY_NAMES, OTHER, PARTY_LETTER, bar_chart, colors, load, money_fmt

members, money = load()
c = colors()

st.title("Campaign Money by Industry")
st.write(f"Where members of Congress got money from individual donors in the {CYCLE - 1} to {CYCLE} election cycle, "
         "sorted by the industry each donor listed. From the Federal Election Commission's public filings.")

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
        st.info(f"No {CYCLE} campaign committee was found for that member. New members, appointed senators and "
                "members who did not run that cycle have no profile here yet.")
        del st.query_params["member"]
    st.caption(f"{len(members)} current members with a principal campaign committee in the {CYCLE} cycle.")
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
itemized_share = m["itemized"] / m["individual"] if m["individual"] else 0
st.write(f"**{money_fmt(m['individual'])}** from individual donors. Donor details were reported for "
         f"{money_fmt(m['itemized'])} ({itemized_share:.0%}).")

# 1. Who gave: every dollar, with the shares that can't be placed in an industry shown as their own bars.
industry_cats = [k for k in INDUSTRY_NAMES if k in mine.index]
rows = []
for key, label in OTHER:
    if key == "industry":
        dollars = mine.loc[industry_cats, "dollars"].sum()
        med = wide[[k for k in INDUSTRY_NAMES if k in wide]].sum(axis=1).median()
    else:
        dollars = mine["dollars"].get(key, 0)
        med = wide[key].median() if key in wide else 0
    rows.append({"label": label, "dollars": dollars, "share": dollars / m["individual"] if m["individual"] else 0,
                 "median": med, "kind": "industry" if key == "industry" else "other"})
who = pd.DataFrame(rows).assign(dollars_fmt=lambda d: d["dollars"].map(money_fmt))
st.markdown("#### Where the money came from")
st.caption(f"Share of all individual money. The tick is the median for {peer_label}.")
st.altair_chart(bar_chart(who, c, [label for _, label in OTHER], median=True), use_container_width=True)

# 2. By industry, as a share of the same total, so the bars are never read as more than they are.
ind = pd.DataFrame([{"key": k, "label": INDUSTRY_NAMES[k], "dollars": mine.loc[k, "dollars"],
                     "share": mine.loc[k, "share"], "median": wide[k].median() if k in wide else 0, "kind": "industry"}
                    for k in industry_cats])
ind = ind[ind["dollars"] > 0].sort_values("share", ascending=False)
ind["dollars_fmt"] = ind["dollars"].map(money_fmt)
st.markdown("#### By industry")
placed = who.loc[who["label"] == OTHER[0][1], "share"].iloc[0]
st.caption(f"Received from people who listed employers in each industry, as a share of all individual money. "
           f"Together these are {placed:.0%}; the rest is in the chart above. The tick is the median for {peer_label}.")
if ind.empty:
    st.write("No itemized money could be placed in an industry.")
else:
    st.altair_chart(bar_chart(ind, c, list(ind["label"]), median=True), use_container_width=True)

with st.expander("Table"):
    table = pd.concat([who[["label", "dollars", "share", "median"]], ind[["label", "dollars", "share", "median"]]])
    st.dataframe(table.rename(columns={"label": "Category", "dollars": "Dollars", "share": "Share",
                                       "median": f"Median, {peer_label}"}),
                 hide_index=True, use_container_width=True,
                 column_config={"Dollars": st.column_config.NumberColumn(format="$%d"),
                                "Share": st.column_config.NumberColumn(format="percent"),
                                f"Median, {peer_label}": st.column_config.NumberColumn(format="percent")})

links = ", ".join(f"[{cm} on FEC.gov](https://www.fec.gov/data/committee/{cm}/?cycle={CYCLE})"
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
    f"place. It is kept as its own bar instead of being guessed.{accuracy}\n"
    "- This site never pairs a donation with a vote. For voting records, see "
    "[PartyCohesion](https://partycohesion.streamlit.app).\n"
    "- Method, code and the full audit: [github.com/RendellRich/campaign-money](https://github.com/RendellRich/campaign-money)."
)
