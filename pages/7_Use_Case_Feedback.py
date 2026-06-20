"""Use Case Feedback.

Where the team reviews and votes on use cases that have been **approved**. Votes
shape prioritization (RICE + vote influence) that drives the Roadmap View.
Approved use cases are collapsed into cross-role themes so a recurring use case is
voted on once, with its reach shown.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

import ui_common as ui
from core import clustering, roi, scoring, storage

st.set_page_config(page_title="Use Case Feedback · Talent Miner", page_icon="⛏️", layout="wide")
ui.page_chrome("Use case feedback")
ui.render_sidebar("feedback")

approved = storage.list_opportunities(status="approved")

if not approved:
    st.info("No approved use cases to vote on yet. Approve some on the Manage Use Cases page first.")
    st.page_link("pages/1_Manage_Use_Cases.py", label="Go to Manage Use Cases", icon="🗂️")
    st.stop()

cfg = ui.get_config()
themes = clustering.collapse_to_themes(approved)

st.write("Upvote the use cases your team wants to see prioritized and downvote the ones that "
         "miss the mark. Votes feed the RICE ranking on the **Roadmap View**.")

top = st.columns([3, 1])
top[0].caption(f"{len(approved)} approved use cases across {len(themes)} themes "
               f"(recurring use cases merged, with reach shown as 👥 roles).")
if top[1].button("🔗 Refresh themes", use_container_width=True,
                 help="Re-cluster approved use cases to merge duplicates and update reach"):
    clustering.recompute_and_persist(cfg)
    st.rerun()

# ---------------------------------------------------------------------------
# Filters and sort
# ---------------------------------------------------------------------------
f1, f2, f3 = st.columns(3)
categories = sorted({o.category for o in themes})
cat_filter = f1.multiselect("Business function", categories, default=[], placeholder="All")
pattern_filter = f2.multiselect("Pattern", ["automation", "augmentation"],
                                default=[], placeholder="All")
sort_by = f3.selectbox("Sort by", ["Net votes", "RICE score", "ROI (annual value)",
                                   "Reach", "Impact", "Newest"])

rows = themes
if cat_filter:
    rows = [o for o in rows if o.category in cat_filter]
if pattern_filter:
    rows = [o for o in rows if o.ai_pattern in pattern_filter]

if sort_by == "Net votes":
    rows.sort(key=lambda o: o.net_votes, reverse=True)
elif sort_by == "RICE score":
    rows.sort(key=lambda o: scoring.score(o, cfg), reverse=True)
elif sort_by == "ROI (annual value)":
    rows.sort(key=lambda o: roi.estimate(o, cfg)["annual_value"], reverse=True)
elif sort_by == "Reach":
    rows.sort(key=lambda o: o.reach, reverse=True)
elif sort_by == "Impact":
    rows.sort(key=lambda o: o.impact, reverse=True)
else:
    rows.sort(key=lambda o: o.created_at, reverse=True)

st.caption(f"Showing {len(rows)} of {len(themes)} themes.")
st.divider()

for opp in rows:
    members = getattr(opp, "_members", None)
    ui.render_opportunity_card(opp, votable=True, key_prefix="fb_", members=members,
                               deletable=False)

st.divider()
st.page_link("pages/2_Roadmap_View.py", label="See how votes shape the roadmap →", icon="🗺️")
