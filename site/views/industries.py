"""Industries: where money from people in one industry went, by party and chamber, and for which members it made up
the largest share. Same data as the Members page; nothing here pairs a donation with a vote."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from common import (CYCLES, current_only, INDUSTRY_NAMES, PARTY_COLORS, PARTY_LETTER, colors, hero, inject_css, load, money_fmt,
                    pick_cycle, theme)

# Members with less individual money than this are left out of the "largest share" chart, where a few small gifts
# could otherwise top the list. They stay in the table.
MIN_FOR_RANKING = 250_000
TOP = 15

inject_css()
c = colors()
party_colors = PARTY_COLORS[theme()]

top_slot = st.container()
cycle = pick_cycle()
members, money = current_only(*load(cycle))
with top_slot:
    hero("Where each industry's money went",
         f"Money from people who listed employers in one industry, in the {cycle - 1} to {cycle} cycle: its share of each "
         "party's money in each chamber, and the members for whom it made up the largest share.")

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
    """Party-colored bars. If df has a "prev" column, a tick marks the other cycle's value on each bar."""
    x = alt.X("share:Q", title=None, scale=alt.Scale(domainMin=0),
              axis=alt.Axis(format="%", grid=True, gridOpacity=0.25, domain=False, ticks=False, labelFontSize=11))
    base = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=order, title=None,
                axis=alt.Axis(labelLimit=260, labelFontSize=13, ticks=False, domain=False)),
        tooltip=tooltip)
    color = alt.Color("party:N", title=None, legend=alt.Legend(orient="top", labelFontSize=12),
                      scale=alt.Scale(domain=list(party_colors), range=list(party_colors.values())))
    layers = [base.mark_bar(height=16, cornerRadiusEnd=4).encode(x=x, color=color)]
    label_x = x
    if "prev" in df:
        layers.append(base.mark_tick(thickness=2, size=24, color=c["tick"]).encode(x=alt.X("prev:Q")))
        df["label_x"] = df[["share", "prev"]].max(axis=1)
        label_x = alt.X("label_x:Q")
    layers.append(base.mark_text(align="left", dx=7, fontSize=12, color=c["text"]).encode(
        x=label_x, text=alt.Text("share:Q", format=".1%")))
    return (alt.layer(*layers)
            .properties(height=alt.Step(28)).configure_view(stroke=None).configure(background="transparent"))


# 1. By party and chamber: each group's own total, so a big caucus doesn't look bigger just by being big.
g = (m.groupby(["chamber", "party"], as_index=False)
     .agg(dollars=("dollars", "sum"), individual=("individual", "sum"), n=("bioguide_id", "size"))
     .query("dollars > 0"))
g["share"] = g["dollars"] / g["individual"]
g["label"] = [f"{p}s in the {ch} ({n})" for p, ch, n in zip(g["party"], g["chamber"], g["n"])]
g["dollars_fmt"] = g["dollars"].map(money_fmt)
g = g.sort_values("share", ascending=False)
# The other cycle, as a tick on each bar, for the same groups of current members.
other = next((x for x in CYCLES if x != cycle), None)
if other:
    om, omoney = current_only(*load(other))
    od = om.merge(omoney[omoney["category"] == key][["bioguide_id", "dollars"]], on="bioguide_id", how="left")
    og = od.fillna({"dollars": 0}).groupby(["chamber", "party"])[["dollars", "individual"]].sum()
    g["prev"] = [og.loc[(ch, p), "dollars"] / og.loc[(ch, p), "individual"] if (ch, p) in og.index else None
                 for ch, p in zip(g["chamber"], g["party"])]
st.markdown("#### By party and chamber")
st.caption(f"Money from people in {label.lower()} as a share of each group's total individual money. "
           "Members in each group in brackets, grouped by their current party."
           + (f" The tick shows the same group in {other - 1} to {other}." if other else ""))
st.altair_chart(bars(g, list(g["label"]), [alt.Tooltip("label:N", title="Group"),
                                           alt.Tooltip("dollars_fmt:N", title="From this industry"),
                                           alt.Tooltip("share:Q", title="Share of individual money", format=".1%")]
                + ([alt.Tooltip("prev:Q", title=f"{other - 1} to {other}", format=".1%")] if other else [])),
                width="stretch")

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
                    width="stretch")

with st.expander("All members"):
    t = m[m["dollars"] > 0].sort_values("dollars", ascending=False)
    t = t.assign(profile="/?member=" + t["bioguide_id"])
    st.dataframe(
        t[["name", "party", "chamber", "state", "dollars", "share", "profile"]].rename(columns={
            "name": "Member", "party": "Party", "chamber": "Chamber", "state": "State", "dollars": "From this industry",
            "share": "Share of individual money", "profile": "Profile"}),
        hide_index=True, width="stretch",
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
