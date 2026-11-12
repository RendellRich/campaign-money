"""Shared data, labels and chart code for the Campaign Money pages."""
from __future__ import annotations

from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

CYCLE = 2024
CYCLES = [2024, 2022]  # newest first
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

# Each kind of money has its own color, so the "where it came from" bars read at a glance. Checked with the dataviz
# palette validator: adjacent pairs pass for normal and color-blind vision. "No information" is gray on purpose, it
# should read as an absence. Every bar is also labeled in words.
CATEGORY_COLORS = {
    "light": {"industry": "#16805F", "unknown": "#3D74B8", "retired": "#B7791F", "not employed": "#8B5CB8",
              "no information": "#5F5A55", "unitemized": "#C65A3E"},
    "dark": {"industry": "#2E9F79", "unknown": "#5E8DD0", "retired": "#BF8528", "not employed": "#9A74CB",
             "no information": "#A39D96", "unitemized": "#D9694B"},
}
UI = {
    "light": {"text": "#1B1D21", "muted": "#5A6068", "tick": "#1B1D21", "hero": "#0F3B30", "hero_text": "#F4EFE3",
              "gold": "#C8A24A", "surface": "#FFFFFF", "tone1": "#16805F", "tone2": "#B7791F", "tone3": "#3D74B8"},
    "dark": {"text": "#FAFAFA", "muted": "#B5AFA8", "tick": "#FAFAFA", "hero": "#123F33", "hero_text": "#F4EFE3",
             "gold": "#D9B45E", "surface": "#21201D", "tone1": "#2E9F79", "tone2": "#BF8528", "tone3": "#5E8DD0"},
}


@st.cache_data
def load(cycle: int = CYCLE) -> tuple[pd.DataFrame, pd.DataFrame]:
    members = pd.read_csv(DATA / f"members_{cycle}.csv")
    money = pd.read_csv(DATA / f"member_money_{cycle}.csv")
    money = money.merge(members[["bioguide_id", "individual"]], on="bioguide_id")
    money["share"] = money["dollars"] / money["individual"]
    return members, money


def theme() -> str:
    return "dark" if getattr(getattr(st.context, "theme", None), "type", "light") == "dark" else "light"


def colors() -> dict[str, str]:
    return {**UI[theme()], "cat": CATEGORY_COLORS[theme()]}


def money_fmt(x: float) -> str:
    if x >= 1e9:
        return f"${x / 1e9:,.2f}B"
    return f"${x / 1e6:,.1f}M" if x >= 1e6 else f"${x / 1e3:,.0f}K"


def pick_cycle(key: str = "cycle") -> int:
    """The cycle control, shared by both pages through ?cycle=. Newest cycle by default."""
    asked = st.query_params.get("cycle", str(CYCLE))
    default = asked if asked in [str(c) for c in CYCLES] else str(CYCLE)
    choice = st.segmented_control("Election cycle", [str(c) for c in CYCLES], default=default, key=key,
                                  format_func=lambda c: f"{int(c) - 1} to {c}")
    cycle = int(choice or default)
    if cycle == CYCLE:
        st.query_params.pop("cycle", None)
    else:
        st.query_params["cycle"] = str(cycle)
    return cycle


def inject_css() -> None:
    c = colors()
    st.markdown(f"""<style>
:root {{ --cm-hero: {c['hero']}; --cm-hero-text: {c['hero_text']}; --cm-gold: {c['gold']}; --cm-surface: {c['surface']};
        --cm-muted: {c['muted']}; --cm-tone1: {c['tone1']}; --cm-tone2: {c['tone2']}; --cm-tone3: {c['tone3']}; }}
.cm-panel {{ background: var(--cm-hero); color: var(--cm-hero-text); border-radius: 16px; padding: 30px 32px 24px 32px;
            margin: 0.25rem 0 1.5rem 0; }}
.cm-title {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 2.5rem; font-weight: 700; line-height: 1.12;
            letter-spacing: -0.01em; margin: 0 0 10px 0; max-width: 20ch; }}
.cm-intro {{ font-size: 1.05rem; line-height: 1.6; max-width: 66ch; opacity: 0.86; margin-bottom: 20px; }}
.cm-strip {{ display: flex; height: 22px; border-radius: 6px; overflow: hidden; gap: 2px; background: var(--cm-hero); }}
.cm-strip span {{ display: block; height: 100%; }}
.cm-strip-caption {{ font-size: 0.85rem; opacity: 0.8; margin: 8px 0 10px 0; }}
.cm-legend {{ display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 0.88rem; }}
.cm-legend b {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
.cm-legend i {{ display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; }}
.cm-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 8px 0 18px 0; }}
.cm-card {{ border-radius: 12px; padding: 14px 16px; border-top: 4px solid var(--cm-tone);
           background: color-mix(in srgb, var(--cm-tone) 9%, var(--cm-surface)); }}
.cm-card:nth-child(3n+1) {{ --cm-tone: var(--cm-tone1); }}
.cm-card:nth-child(3n+2) {{ --cm-tone: var(--cm-tone2); }}
.cm-card:nth-child(3n) {{ --cm-tone: var(--cm-tone3); }}
.cm-card-label {{ font-size: 0.85rem; font-weight: 600; color: var(--cm-tone); }}
.cm-card-value {{ font-size: 1.75rem; font-weight: 700; line-height: 1.25; margin: 4px 0; font-variant-numeric: tabular-nums; }}
.cm-card-note {{ font-size: 0.85rem; color: var(--cm-muted); }}
.stApp h4 {{ border-left: 4px solid var(--cm-tone1); padding-left: 10px; }}
@media (max-width: 640px) {{ .cm-title {{ font-size: 1.9rem; }} .cm-panel {{ padding: 22px 20px 18px 20px; }} }}
</style>""", unsafe_allow_html=True)


def hero(title_html: str, intro: str, composition: dict[str, float] | None = None, caption: str = "") -> None:
    """The green panel. With a composition (category -> dollars) it draws the ledger strip: every dollar, by kind."""
    c = colors()
    strip = ""
    if composition:
        total = sum(composition.values())
        labels = dict(OTHER)
        segs = "".join(f'<span style="width:{v / total * 100:.2f}%;background:{c["cat"][k]}" title="{escape(labels[k])}"></span>'
                       for k, v in composition.items() if v > 0)
        legend = "".join(f'<span><i style="background:{c["cat"][k]}"></i>{escape(labels[k].split(" (")[0])} '
                         f'<b>{v / total:.0%}</b></span>' for k, v in composition.items() if v > 0)
        strip = (f'<div class="cm-strip" role="img" aria-label="{escape(caption)}">{segs}</div>'
                 f'<div class="cm-strip-caption">{escape(caption)}</div><div class="cm-legend">{legend}</div>')
    st.markdown(f'<div class="cm-panel"><div class="cm-title">{title_html}</div>'
                f'<div class="cm-intro">{escape(intro)}</div>{strip}</div>', unsafe_allow_html=True)


def cards(items: list[tuple[str, str, str]]) -> None:
    st.markdown('<div class="cm-cards">' + "".join(
        f'<div class="cm-card"><div class="cm-card-label">{escape(a)}</div><div class="cm-card-value">{escape(b)}</div>'
        f'<div class="cm-card-note">{escape(n)}</div></div>' for a, b, n in items) + "</div>", unsafe_allow_html=True)


def composition(money: pd.DataFrame) -> dict[str, float]:
    """All members' individual money by kind, in the fixed order of OTHER."""
    s = money.groupby("category")["dollars"].sum()
    out = {"industry": float(s[s.index.isin(INDUSTRY_NAMES)].sum())}
    out.update({k: float(s.get(k, 0)) for k, _ in OTHER[1:]})
    return out


def bar_chart(df: pd.DataFrame, c: dict, order: list[str], median: bool) -> alt.Chart:
    """Horizontal bars of share of individual money. df has label, key (category), share, dollars_fmt, median."""
    df = df.assign(label_x=df[["share", "median"]].max(axis=1) if median else df["share"])
    base = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=13, ticks=False, domain=False)),
        tooltip=[alt.Tooltip("label:N", title="Category"), alt.Tooltip("dollars_fmt:N", title="Dollars"),
                 alt.Tooltip("share:Q", title="Share of individual money", format=".1%")]
                + ([alt.Tooltip("median:Q", title="Median, same party and chamber", format=".1%")] if median else []),
    )
    x = alt.X("share:Q", title=None, axis=alt.Axis(format="%", grid=True, gridOpacity=0.25, domain=False, ticks=False,
                                                   labelFontSize=11), scale=alt.Scale(domainMin=0))
    keys = list(c["cat"])
    bars = base.mark_bar(height=16, cornerRadiusEnd=4).encode(
        x=x, color=alt.Color("key:N", scale=alt.Scale(domain=keys, range=[c["cat"][k] for k in keys]), legend=None))
    text = base.mark_text(align="left", dx=7, fontSize=12, color=c["text"]).encode(
        x=alt.X("label_x:Q"), text=alt.Text("share:Q", format=".1%"))
    layers = [bars, text]
    if median:
        layers.append(base.mark_tick(thickness=2, size=22, color=c["tick"]).encode(x=alt.X("median:Q")))
    return alt.layer(*layers).properties(height=alt.Step(28)).configure_view(stroke=None).configure(background="transparent")


def change_chart(df: pd.DataFrame, c: dict, order: list[str], before: int, after: int) -> alt.Chart:
    """Dumbbell: a hollow dot for the earlier cycle, a filled dot for the later one, joined by a line.
    df has label, key, share_before, share_after."""
    df = df.assign(right=df[["share_before", "share_after"]].max(axis=1))
    keys = list(c["cat"])
    color = alt.Color("key:N", scale=alt.Scale(domain=keys, range=[c["cat"][k] for k in keys]), legend=None)
    y = alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=13, ticks=False, domain=False))
    x_axis = alt.Axis(format="%", grid=True, gridOpacity=0.25, domain=False, ticks=False, labelFontSize=11)
    tip = [alt.Tooltip("label:N", title="Category"), alt.Tooltip("share_before:Q", title=f"{before - 1} to {before}", format=".1%"),
           alt.Tooltip("share_after:Q", title=f"{after - 1} to {after}", format=".1%")]
    base = alt.Chart(df).encode(y=y, tooltip=tip)
    rule = base.mark_rule(strokeWidth=3, opacity=0.55).encode(
        x=alt.X("share_before:Q", title=None, axis=x_axis, scale=alt.Scale(domainMin=0)), x2="share_after:Q", color=color)
    was = base.mark_point(size=110, filled=False, strokeWidth=2).encode(x="share_before:Q", color=color)
    now = base.mark_point(size=140, filled=True, opacity=1).encode(x="share_after:Q", color=color)
    text = base.mark_text(align="left", dx=10, fontSize=12, color=c["text"]).encode(
        x=alt.X("right:Q"), text=alt.Text("share_after:Q", format=".1%"))
    return (alt.layer(rule, was, now, text).properties(height=alt.Step(30))
            .configure_view(stroke=None).configure(background="transparent"))
