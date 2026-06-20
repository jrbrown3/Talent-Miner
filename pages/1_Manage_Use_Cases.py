"""Manage Use Cases.

The control room for every derived use case. Lists all use cases (across roles
and documents), shows their lifecycle status, and lets you **approve** the ones
worth pursuing — approval is what promotes a use case into feedback, the roadmap,
and the business view. You can also reject or delete use cases here.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

import ui_common as ui
from core import clustering, scoring, storage

st.set_page_config(page_title="Manage Use Cases · Talent Miner", page_icon="⛏️", layout="wide")
ui.page_chrome("Manage use cases")
ui.render_sidebar("review")

STATUS_META = {
    "proposed": ("⏳ Pending", "#d97706"),
    "approved": ("✅ Approved", "#16a34a"),
    "rejected": ("🚫 Rejected", "#dc2626"),
}


def _recluster() -> None:
    """Keep themes/reach current after an approval set changes."""
    clustering.recompute_and_persist(ui.get_config())


all_opps = storage.list_opportunities()

if not all_opps:
    st.info("No use cases yet. Analyze a job description on the Analyze page to derive some.")
    st.page_link("app.py", label="Go to Analyze", icon="🔍")
    st.stop()

counts = {s: sum(1 for o in all_opps if o.status == s) for s in STATUS_META}

st.write("Approve the use cases worth pursuing. Approved use cases flow into "
         "**Use Case Feedback**, the **Roadmap View**, and the **Business View**.")

c1, c2, c3 = st.columns(3)
c1.metric("⏳ Pending", counts.get("proposed", 0))
c2.metric("✅ Approved", counts.get("approved", 0))
c3.metric("🚫 Rejected", counts.get("rejected", 0))

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
f1, f2 = st.columns([2, 3])
view = f1.radio(
    "Show",
    ["Pending", "Approved", "Rejected", "All"],
    horizontal=True,
    help="Filter the list by lifecycle status.",
)
categories = sorted({o.category for o in all_opps})
cat_filter = f2.multiselect("Business function", categories, default=[], placeholder="All functions")

status_for_view = {"Pending": "proposed", "Approved": "approved", "Rejected": "rejected"}
rows = all_opps
if view != "All":
    rows = [o for o in rows if o.status == status_for_view[view]]
if cat_filter:
    rows = [o for o in rows if o.category in cat_filter]

# ---------------------------------------------------------------------------
# Bulk actions (only meaningful while looking at pending items)
# ---------------------------------------------------------------------------
pending_rows = [o for o in rows if o.status == "proposed"]
if pending_rows:
    b1, b2, _ = st.columns([2, 2, 4])
    if b1.button(f"✅ Approve all shown ({len(pending_rows)})", type="primary"):
        for o in pending_rows:
            storage.set_status(o.id, "approved")
        _recluster()
        st.rerun()
    if b2.button(f"🚫 Reject all shown ({len(pending_rows)})"):
        for o in pending_rows:
            storage.set_status(o.id, "rejected")
        _recluster()
        st.rerun()

st.caption(f"Showing {len(rows)} use case(s).")
st.divider()

if not rows:
    st.info("Nothing matches the current filter.")
    st.stop()

# ---------------------------------------------------------------------------
# Use-case list, grouped by role / document
# ---------------------------------------------------------------------------
rows.sort(key=lambda o: scoring.combined_score(o), reverse=True)

groups: dict[str, list] = {}
for o in rows:
    key = o.role_title or o.source_name or "Unattributed"
    groups.setdefault(key, []).append(o)

for role, items in groups.items():
    st.markdown(f"### {role}")
    if items[0].source_name and items[0].source_name != role:
        st.caption(f"Source: {items[0].source_name}")

    for opp in items:
        label, color = STATUS_META.get(opp.status, (opp.status, "#475569"))
        with st.container(border=True):
            head, actions = st.columns([5, 2])
            with head:
                st.markdown(
                    f"#### {opp.title} "
                    f"<span style='background:{color};color:white;padding:2px 8px;"
                    f"border-radius:10px;font-size:0.7rem;font-weight:600;"
                    f"vertical-align:middle;'>{label}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(ui.opportunity_header_html(opp), unsafe_allow_html=True)
                if opp.context:
                    st.write(opp.context)
                cc1, cc2 = st.columns(2)
                cc1.markdown(f"**Impact** {opp.impact}/5 — {opp.impact_rationale or '—'}")
                cc2.markdown(f"**Effort** {opp.effort}/5 — {opp.effort_rationale or '—'}")
                ui.render_evidence(opp)

            with actions:
                if opp.status != "approved":
                    if st.button("✅ Approve", key=f"appr_{opp.id}", type="primary",
                                 use_container_width=True):
                        storage.set_status(opp.id, "approved")
                        _recluster()
                        st.rerun()
                else:
                    if st.button("↩ Un-approve", key=f"unappr_{opp.id}",
                                 use_container_width=True):
                        storage.set_status(opp.id, "proposed")
                        _recluster()
                        st.rerun()
                if opp.status != "rejected":
                    if st.button("🚫 Reject", key=f"rej_{opp.id}", use_container_width=True):
                        storage.set_status(opp.id, "rejected")
                        _recluster()
                        st.rerun()
                if st.button("🗑️ Delete", key=f"del_{opp.id}", use_container_width=True):
                    storage.delete_opportunity(opp.id)
                    _recluster()
                    st.rerun()

st.divider()
nav1, nav2 = st.columns(2)
nav1.page_link("pages/7_Use_Case_Feedback.py", label="Use Case Feedback →", icon="🗳️")
nav2.page_link("pages/2_Roadmap_View.py", label="Roadmap View →", icon="🗺️")
