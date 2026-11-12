"""Campaign Money by Industry. Run with:  streamlit run site/app.py

Two pages: Members (the default, so ?member=<Bioguide ID> links open a profile) and Industries.
"""
import streamlit as st

st.set_page_config(page_title="Campaign Money by Industry", layout="centered")
nav = st.navigation([
    st.Page("views/members.py", title="Members", default=True),
    st.Page("views/industries.py", title="Industries", url_path="industries"),
], position="top")
nav.run()
