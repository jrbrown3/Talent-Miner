"""Roadmap page: filters + ROI summary + impact/effort matrix + Now/Near/Far lanes."""
from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

import ui_common as ui
from core import clustering, roi, scoring, storage

st.set_page_config(page_title="Roadmap View · Talent Miner", page_icon="⛏️", layout="wide")
ui.page_chrome("Roadmap View")
ui.render_sidebar("roadmap")

st.title("Roadmap View")

accepted = storage.list_opportunities(status="approved")
if not accepted:
    st.info("The roadmap is empty. Approve some use cases on the Manage Use Cases page first.")
    st.page_link("pages/1_Manage_Use_Cases.py", label="Go to Manage Use Cases", icon="🗂️")
    st.stop()

cfg = ui.get_config()
method = (cfg.get("scoring") or {}).get("method", "rice")

# Collapse duplicate opportunities into themes so reach/ROI aren't double counted.
themes = clustering.collapse_to_themes(accepted)

st.write("This roadmap is **generated automatically** from your approved use cases. "
         "Prioritization uses **RICE** (reach × impact × confidence ÷ effort) plus your "
         "team's **votes** from Use Case Feedback. Filter the view and tune below to see "
         "the roadmap shift.")

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
CAPABILITIES = ["Automation", "Augmentation"]
QUADRANTS = list(scoring.QUADRANTS.keys())

f1, f2, f3 = st.columns(3)
categories = sorted({o.category for o in themes})
area_filter = f1.multiselect("Functional area", categories, default=[],
                             placeholder="All areas")
cap_filter = f2.multiselect("Capability", CAPABILITIES, default=[],
                            placeholder="All capabilities")
impact_filter = f3.multiselect("Impact", QUADRANTS, default=[],
                               placeholder="All impact tiers",
                               help="Impact/effort tier: e.g. Big Bet = high impact, high effort.")

filtered = themes
if area_filter:
    filtered = [o for o in filtered if o.category in area_filter]
if cap_filter:
    filtered = [o for o in filtered if o.ai_pattern.title() in cap_filter]
if impact_filter:
    filtered = [o for o in filtered if scoring.quadrant(o) in impact_filter]

st.caption(f"Showing **{len(filtered)}** of {len(themes)} themes "
           f"({len(accepted)} underlying opportunities).")

# Live tuning (does not persist; defaults live in Settings)
live_cfg = copy.deepcopy(cfg)
with st.expander("Tune prioritization"):
    if method == "weighted":
        w = cfg.get("weights", {})
        c = st.columns(3)
        live_cfg["weights"] = {
            "impact": c[0].slider("Impact weight", 0.0, 2.0, float(w.get("impact", 1.0)), 0.1),
            "effort": c[1].slider("Effort weight", 0.0, 2.0, float(w.get("effort", 0.6)), 0.1),
            "votes": c[2].slider("Votes weight", 0.0, 2.0, float(w.get("votes", 0.4)), 0.1),
        }
        st.caption("Weighted method active. Switch to RICE in Settings for reach-aware scoring.")
    else:
        vi = st.slider("Vote influence", 0.0, 0.5,
                       float((cfg.get("rice") or {}).get("vote_influence", 0.05)), 0.01,
                       help="How much each net vote shifts the RICE score.")
        live_cfg.setdefault("rice", {})["vote_influence"] = vi
        st.caption("RICE active: (reach × impact × confidence) ÷ effort. "
                   "Edit ROI and clustering assumptions in Settings.")

if not filtered:
    st.warning("No opportunities match the current filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Portfolio ROI summary
# ---------------------------------------------------------------------------
st.subheader("Portfolio business case")
pf = roi.portfolio(filtered, cfg)
b = st.columns(6)
b[0].metric("Est. annual value", roi.fmt_money(pf["annual_value"]))
b[1].metric("Hours saved / yr", roi.fmt_hours(pf["annual_hours"]))
b[2].metric("One-time build cost", roi.fmt_money(pf["impl_cost"]))
b[3].metric("Net (year 1)", roi.fmt_money(pf["net_year1"]))
b[4].metric("Net (year 2)", roi.fmt_money(pf["net_year2"]))
b[5].metric("Net (year 3)", roi.fmt_money(pf["net_year3"]))
st.caption("Estimates from configurable assumptions (Settings → Scoring & ROI). "
           "Themes are counted once; reach scales value by the number of roles affected.")

# ---------------------------------------------------------------------------
# Impact / effort matrix (bubble size = reach)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Impact vs. effort")

points = scoring.matrix_points(filtered, live_cfg)
df = pd.DataFrame(points)
palette = ui.chart_colors()

try:
    import altair as alt

    base = alt.Chart(df).encode(
        x=alt.X("effort:Q", scale=alt.Scale(domain=[0.5, 5.5]), title="Effort  (low → high)"),
        y=alt.Y("impact:Q", scale=alt.Scale(domain=[0.5, 5.5]), title="Impact  (low → high)"),
    )
    points_layer = base.mark_circle(opacity=0.82).encode(
        size=alt.Size("score:Q", title="RICE score",
                      scale=alt.Scale(range=[80, 1200])),
        color=alt.Color("quadrant:N", title="Impact tier",
                        scale=alt.Scale(domain=list(ui.QUADRANT_COLORS.keys()),
                                        range=list(ui.QUADRANT_COLORS.values()))),
        tooltip=["title", "category", "impact", "effort", "reach", "confidence",
                 "net_votes", "score"],
    )
    rule_v = alt.Chart(pd.DataFrame({"x": [3]})).mark_rule(
        strokeDash=[4, 4], color="#94a3b8").encode(x="x:Q")
    rule_h = alt.Chart(pd.DataFrame({"y": [3]})).mark_rule(
        strokeDash=[4, 4], color="#94a3b8").encode(y="y:Q")
    chart = (rule_v + rule_h + points_layer).properties(height=420, background="transparent")
    chart = (chart
             .configure_view(strokeWidth=0)
             .configure_axis(labelColor=palette["chart_text"], titleColor=palette["chart_text"],
                             gridColor=palette["chart_grid"], domainColor=palette["chart_grid"])
             .configure_legend(labelColor=palette["chart_text"], titleColor=palette["chart_text"]))
    st.altair_chart(chart, use_container_width=True)
except Exception:
    st.scatter_chart(df, x="effort", y="impact", color="quadrant")

cols = st.columns(4)
for col, (quad, desc) in zip(cols, scoring.QUADRANTS.items()):
    col.markdown(f"<span style='color:{ui.QUADRANT_COLORS[quad]};font-weight:700'>{quad}</span>",
                 unsafe_allow_html=True)
    col.caption(desc)

# ---------------------------------------------------------------------------
# Now / Near / Far
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Recommended roadmap")

lanes = scoring.assign_lanes(filtered, live_cfg)
lane_meta = {
    "Now": ("🟢 Now", "Quick wins & high-consensus items to start immediately."),
    "Near": ("🔵 Near", "Valuable items to schedule after the quick wins."),
    "Far": ("⚪ Far", "Lower priority, costly, or low-consensus items."),
}

lane_cols = st.columns(3)
for col, lane in zip(lane_cols, ["Now", "Near", "Far"]):
    label, desc = lane_meta[lane]
    with col:
        st.markdown(f"### {label}")
        st.caption(desc)
        items = lanes[lane]
        if not items:
            st.caption("_Nothing here yet._")
        for opp in items:
            est = roi.estimate(opp, cfg)
            with st.container(border=True):
                st.markdown(f"**{opp.title}**")
                st.markdown(ui.opportunity_header_html(opp), unsafe_allow_html=True)
                st.caption(
                    f"RICE {round(scoring.score(opp, live_cfg), 2)} · "
                    f"I{opp.impact}/E{opp.effort} · votes {opp.net_votes} · "
                    f"{roi.fmt_money(est['annual_value'])}/yr · "
                    f"payback {roi.fmt_payback(est['payback_months'])}")
                has_doc = bool(opp.use_case_doc)
                btn = "📄 View use case" if has_doc else "🛠️ Build use case"
                if st.button(btn, key=f"build_{opp.id}", use_container_width=True):
                    st.session_state["build_opp_id"] = opp.id
                    st.switch_page("pages/4_Use_Case.py")
                if has_doc:
                    st.caption("✓ Use-case document ready")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Export")

export_rows = []
for lane in ["Now", "Near", "Far"]:
    for opp in lanes[lane]:
        est = roi.estimate(opp, cfg)
        export_rows.append({
            "lane": lane,
            "theme": opp.title,
            "category": opp.category,
            "ai_pattern": opp.ai_pattern,
            "impact": opp.impact,
            "effort": opp.effort,
            "reach_roles": opp.reach,
            "confidence_pct": opp.confidence_pct,
            "quadrant": scoring.quadrant(opp),
            "net_votes": opp.net_votes,
            "rice_score": round(scoring.score(opp, live_cfg), 2),
            "annual_value_usd": round(est["annual_value"]),
            "impl_cost_usd": round(est["impl_cost"]),
            "payback_months": round(est["payback_months"], 1) if est["payback_months"] else None,
        })
export_df = pd.DataFrame(export_rows)
c1, c2 = st.columns(2)
c1.download_button("⬇️ Download roadmap (CSV)", export_df.to_csv(index=False),
                   file_name="talent_miner_roadmap.csv", mime="text/csv")
c2.download_button("⬇️ Download roadmap (JSON)", export_df.to_json(orient="records", indent=2),
                   file_name="talent_miner_roadmap.json", mime="application/json")
