"""Campaign Money by Industry: one member at a time, every dollar accounted for.

Reads the small files written by pipeline/aggregate.py. Run with:  streamlit run site/app.py
"""
from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

CYCLE = 2024
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
AUDIT = HERE.parent / "data" / f"audit_{CYCLE}_test.json"

INDUSTRY_NAMES = {
    "finance": "Finance and investment", "insurance": "Insurance", "law": "Law", "lobbying": "Lobbying and public affairs",
    "tech": "Technology", "health": "Health care", "pharma": "Pharma, biotech and devices", "energy": "Energy and utilities",
    "real_estate": "Real estate and construction", "defense": "Defense and aerospace", "education": "Education",
    "government": "Government", "media": "Media, entertainment and sports", "manufacturing": "Manufacturing",
    "consumer": "Retail, food and consumer goods", "agriculture": "Agriculture", "transportation": "Transportation",
    "telecom": "Telecom and cable", "nonprofit": "Nonprofits and advocacy", "business_services": "Consulting and business services",
}
# Everything that is not an industry, in a fixed order so every member's chart reads the same way.
OTHER = [
    ("industry", "Placed in an industry"),
    ("unknown", "Points to an industry, but which is unclear"),
    ("retired", "Retired"),
    ("not employed", "Not employed"),
    ("no information", "No employer or occupation given"),
    ("unitemized", "Unitemized (donors who gave $200 or less)"),
]
PARTY_LETTER = {"Democrat": "D", "Republican": "R", "Independent": "I"}

st.set_page_config(page_title="Campaign Money by Industry", layout="centered")


@st.cache_data
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    members = pd.read_csv(DATA / f"members_{CYCLE}.csv")
    money = pd.read_csv(DATA / f"member_money_{CYCLE}.csv")
    money = money.merge(members[["bioguide_id", "individual"]], on="bioguide_id")
    money["share"] = money["dollars"] / money["individual"]
    return members, money


def colors() -> dict[str, str]:
    dark = getattr(getattr(st.context, "theme", None), "type", "light") == "dark"
    return ({"mark": "#7FC8B4", "other": "#77726B", "tick": "#FAFAFA", "text": "#FAFAFA"} if dark else
            {"mark": "#2F6B5E", "other": "#B9B3AB", "tick": "#1B1D21", "text": "#1B1D21"})


def money_fmt(x: float) -> str:
    return f"${x / 1e6:,.1f}M" if x >= 1e6 else f"${x / 1e3:,.0f}K"


def bar_chart(df: pd.DataFrame, c: dict[str, str], order: list[str], median: bool) -> alt.Chart:
    # The value label sits past the bar or the median tick, whichever reaches further, so the two never collide.
    df = df.assign(label_x=df[["share", "median"]].max(axis=1) if median else df["share"])
    base = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=13, ticks=False, domain=False)),
        tooltip=[alt.Tooltip("label:N", title="Category"), alt.Tooltip("dollars_fmt:N", title="Dollars"),
                 alt.Tooltip("share:Q", title="Share of individual money", format=".1%")]
                + ([alt.Tooltip("median:Q", title="Median, same party and chamber", format=".1%")] if median else []),
    )
    x = alt.X("share:Q", title=None, axis=alt.Axis(format="%", grid=True, gridOpacity=0.25, domain=False, ticks=False,
                                                   labelFontSize=11), scale=alt.Scale(domainMin=0))
    bars = base.mark_bar(height=16, cornerRadiusEnd=4).encode(
        x=x, color=alt.Color("kind:N", scale=alt.Scale(domain=["industry", "other"], range=[c["mark"], c["other"]]),
                             legend=None))
    text = base.mark_text(align="left", dx=7, fontSize=12, color=c["text"]).encode(
        x=alt.X("label_x:Q"), text=alt.Text("share:Q", format=".1%"))
    layers = [bars, text]
    if median:
        layers.append(base.mark_tick(thickness=2, size=22, color=c["tick"]).encode(x=alt.X("median:Q")))
    return alt.layer(*layers).properties(height=alt.Step(28)).configure_view(stroke=None).configure(background="transparent")


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
    if "member" in st.query_params:
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
