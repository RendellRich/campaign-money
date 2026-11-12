"""Industries: where money from people in one industry went, by party and chamber, and for which members it made up
the largest share. Same data as the Members page; nothing here pairs a donation with a vote."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from common import CYCLE, INDUSTRY_NAMES, PARTY_COLORS, PARTY_LETTER, colors, load, money_fmt, theme

# Members with less individual money than this are left out of the "largest share" chart, where a few small gifts
# could otherwise top the list. They stay in the table.
MIN_FOR_RANKING = 250_000
TOP = 15

members, money = load()
c = colors()
party_colors = PARTY_COLORS[theme()]

st.title("Industries")
st.write(f"Where money from people who listed employers in one industry went in the {CYCLE - 1} to {CYCLE} cycle: "
         "by party and chamber, and the members for whom it made up the largest share.")

names = {v: k for k, v in INDUSTRY_NAMES.items()}
label = st.selectbox("Industry", sorted(names), index=sorted(names).index(INDUSTRY_NAMES["finance"]))
key = names[label]

mine = money[money["category"] == key][["bioguide_id", "dollars"]]
m = members.merge(mine, on="bioguide_id", how="left").fillna({"dollars": 0})
m["share"] = m["dollars"] / m["individual"].where(m["individual"] > 0)
total, everything = m["dollars"].sum(), m["individual"].sum()
not_placed = money[~money["category"].isin(INDUSTRY_NAMES)]["dollars"].sum() / everything

st.write(f"**{money_fmt(total)}** to current members from people who listed employers in "
         f"{label.lower()}, {total / everything:.1%} of all their individual money. "
         f"{(m['dollars'] > 0).sum()} of {len(m)} members received some.")


def bars(df: pd.DataFrame, order: list[str], tooltip: list) -> alt.Chart:
    x = alt.X("share:Q", title=None, scale=alt.Scale(domainMin=0),
              axis=alt.Axis(format="%", grid=True, gridOpacity=0.25, domain=False, ticks=False, labelFontSize=11))
    base = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=order, title=None,
                axis=alt.Axis(labelLimit=260, labelFontSize=13, ticks=False, domain=False)),
        tooltip=tooltip)
    color = alt.Color("party:N", title=None, legend=alt.Legend(orient="top", labelFontSize=12),
                      scale=alt.Scale(domain=list(party_colors), range=list(party_colors.values())))
    return (alt.layer(base.mark_bar(height=16, cornerRadiusEnd=4).encode(x=x, color=color),
                      base.mark_text(align="left", dx=6, fontSize=12, color=c["text"]).encode(
                          x=x, text=alt.Text("share:Q", format=".1%")))
            .properties(height=alt.Step(28)).configure_view(stroke=None).configure(background="transparent"))


# 1. By party and chamber: each group's own total, so a big caucus doesn't look bigger just by being big.
g = (m.groupby(["chamber", "party"], as_index=False)
     .agg(dollars=("dollars", "sum"), individual=("individual", "sum"), n=("bioguide_id", "size"))
     .query("dollars > 0"))
g["share"] = g["dollars"] / g["individual"]
g["label"] = [f"{p}s in the {ch} ({n})" for p, ch, n in zip(g["party"], g["chamber"], g["n"])]
g["dollars_fmt"] = g["dollars"].map(money_fmt)
g = g.sort_values("share", ascending=False)
st.markdown("#### By party and chamber")
st.caption(f"Money from people in {label.lower()} as a share of each group's total individual money. "
           "Members in each group in brackets.")
st.altair_chart(bars(g, list(g["label"]), [alt.Tooltip("label:N", title="Group"),
                                           alt.Tooltip("dollars_fmt:N", title="From this industry"),
                                           alt.Tooltip("share:Q", title="Share of individual money", format=".1%")]),
                use_container_width=True)

# 2. Members for whom it made up the largest share.
r = m[(m["individual"] >= MIN_FOR_RANKING) & (m["dollars"] > 0)].sort_values("share", ascending=False).head(TOP)
r = r.assign(label=[f"{n} ({PARTY_LETTER.get(p, p[:1])}-{s}, {ch})"
                    for n, p, s, ch in zip(r["name"], r["party"], r["state"], r["chamber"])],
             dollars_fmt=r["dollars"].map(money_fmt))
st.markdown("#### Largest share of a member's individual money")
st.caption(f"The {TOP} members for whom this industry made up the largest share, among members who raised at least "
           f"{money_fmt(MIN_FOR_RANKING)} from individuals. Sorted by the data, the same way for every industry.")
if r.empty:
    st.write("No member received money that could be placed in this industry.")
else:
    st.altair_chart(bars(r, list(r["label"]), [alt.Tooltip("label:N", title="Member"),
                                               alt.Tooltip("dollars_fmt:N", title="From this industry"),
                                               alt.Tooltip("share:Q", title="Share of individual money", format=".1%")]),
                    use_container_width=True)

with st.expander("All members"):
    t = m[m["dollars"] > 0].sort_values("dollars", ascending=False)
    t = t.assign(profile="/?member=" + t["bioguide_id"])
    st.dataframe(
        t[["name", "party", "chamber", "state", "dollars", "share", "profile"]].rename(columns={
            "name": "Member", "party": "Party", "chamber": "Chamber", "state": "State", "dollars": "From this industry",
            "share": "Share of individual money", "profile": "Profile"}),
        hide_index=True, use_container_width=True,
        column_config={"From this industry": st.column_config.NumberColumn(format="$%d"),
                       "Share of individual money": st.column_config.NumberColumn(format="percent"),
                       "Profile": st.column_config.LinkColumn(display_text="Open")})

st.divider()
st.markdown(
    "- These are gifts from individual donors who listed an employer or job in this industry, not money from "
    "companies and not PAC money. Where donors work is not who they speak for.\n"
    f"- {not_placed:.0%} of all individual money to current members can't be placed in any industry: it is "
    "unitemized, from retired or not employed donors, or the donor's employer is unclear. Each member's page shows "
    "those shares.\n"
    "- This site never pairs a donation with a vote.")
