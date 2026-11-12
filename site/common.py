"""Shared data, labels and chart code for the Campaign Money pages."""
from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

CYCLE = 2024
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
AUDIT = HERE.parent / "data" / f"audit_{CYCLE}_test.json"
PARTY_COLORS = {"light": {"Democrat": "#2563A8", "Republican": "#B73A34", "Independent": "#6B655E"},
                "dark": {"Democrat": "#6FA8E8", "Republican": "#E8817B", "Independent": "#A8A29E"}}

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

@st.cache_data
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    members = pd.read_csv(DATA / f"members_{CYCLE}.csv")
    money = pd.read_csv(DATA / f"member_money_{CYCLE}.csv")
    money = money.merge(members[["bioguide_id", "individual"]], on="bioguide_id")
    money["share"] = money["dollars"] / money["individual"]
    return members, money


def theme() -> str:
    return "dark" if getattr(getattr(st.context, "theme", None), "type", "light") == "dark" else "light"


def colors() -> dict[str, str]:
    dark = theme() == "dark"
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


