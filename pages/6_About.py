"""About page: project background, version, and license."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

import ui_common as ui

st.set_page_config(page_title="About · Talent Miner", page_icon="⛏️", layout="wide")
ui.page_chrome("About")
ui.render_sidebar("about")

st.title("About Talent Miner")
st.divider()

# ---------------------------------------------------------------------------
# Why this project exists
# ---------------------------------------------------------------------------
st.subheader("Why this project exists")
st.write(
    """
    Talent Miner was built to answer a question that keeps coming up across organisations:
    *where, specifically, could AI make a meaningful difference in how people work?*

    Most AI adoption efforts start with technology and work backwards. Talent Miner flips
    that — it starts with a job description and works forward. By analysing the tasks,
    responsibilities, and skills in a role, it surfaces concrete opportunities to automate
    repetitive work or augment human judgement with AI assistance, scored by potential
    impact and implementation effort so teams can prioritise what to build first.

    The goal is to give HR, operations, and technology leaders a fast, repeatable way to
    build an AI opportunity backlog grounded in real work — not vendor promises.
    """
)

st.divider()

# ---------------------------------------------------------------------------
# Version & license
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("Version")
    st.markdown(
        "<div style='padding:16px 20px;background:var(--tm-bg);border:1px solid var(--tm-border);"
        "border-radius:10px;display:inline-block;'>"
        "<span style='font-size:2rem;font-weight:800;color:var(--tm-primary);'>v1.0</span>"
        "<div style='color:var(--tm-muted);font-size:0.85rem;margin-top:4px;'>Initial release</div>"
        "</div>",
        unsafe_allow_html=True,
    )

with col2:
    st.subheader("License")
    st.markdown(
        "<div style='padding:16px 20px;background:var(--tm-bg);border:1px solid var(--tm-border);"
        "border-radius:10px;display:inline-block;'>"
        "<span style='font-size:2rem;font-weight:800;color:var(--tm-primary);'>Apache 2.0</span>"
        "<div style='color:var(--tm-muted);font-size:0.85rem;margin-top:4px;'>"
        "Free to use, modify, and distribute with attribution.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

st.divider()
st.caption("Talent Miner · v1.0 · Apache 2.0 License")
