"""Business View.

Groups approved use cases by **business function** so leaders can see how each
function is impacted by AI — how many use cases it has, its estimated value, and
the underlying themes. Recurring use cases are collapsed across roles, with reach
showing how many roles each touches.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

import ui_common as ui
from core import clustering, roi, scoring, storage

st.set_page_config(page_title="Business View · Talent Miner", page_icon="⛏️", layout="wide")
ui.page_chrome("Business View")
ui.render_sidebar("themes")

st.title("Business View")

# ---------------------------------------------------------------------------
# Load and collapse
# ---------------------------------------------------------------------------
approved = storage.list_opportunities(status="approved")

if not approved:
    st.info("No approved use cases yet. Approve some on the Manage Use Cases page first.")
    st.page_link("pages/1_Manage_Use_Cases.py", label="Go to Manage Use Cases →", icon="🗂️")
    st.stop()

cfg = ui.get_config()
themes = clustering.collapse_to_themes(approved)

# ---------------------------------------------------------------------------
# Header and refresh
# ---------------------------------------------------------------------------
functions = sorted({o.category for o in themes})
h1, h2 = st.columns([4, 1])
h1.markdown(
    f"**{len(functions)} business functions** impacted by **{len(themes)} use-case themes** "
    f"across **{len(approved)} approved use cases**. "
    f"See where AI lands in the organisation and the value at stake per function."
)
if h2.button("🔗 Refresh themes", use_container_width=True,
             help="Re-run clustering to merge any newly approved use cases."):
    clustering.recompute_and_persist(cfg)
    st.rerun()

# ---------------------------------------------------------------------------
# Portfolio ROI banner (whole organisation)
# ---------------------------------------------------------------------------
pf = roi.portfolio(themes, cfg)
b = st.columns(4)
b[0].metric("Est. annual value", roi.fmt_money(pf["annual_value"]))
b[1].metric("Hours saved / yr", roi.fmt_hours(pf["annual_hours"]))
b[2].metric("One-time build cost", roi.fmt_money(pf["impl_cost"]))
b[3].metric("Net (year 1)", roi.fmt_money(pf["net_year1"]))
st.caption("Themes counted once; reach scales value by the number of roles affected. "
           "Assumptions editable in Settings → Scoring & ROI.")

# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------
func_filter = st.multiselect("Business function", functions, default=[],
                             placeholder="All functions")
shown_functions = func_filter or functions

# Group themes by function — used by both the overview chart and the sections.
by_function: dict[str, list] = {}
for t in themes:
    by_function.setdefault(t.category, []).append(t)

# ---------------------------------------------------------------------------
# High-level overview chart: value per function, split by automation/augmentation
# ---------------------------------------------------------------------------
st.subheader("How AI impact lands across business functions")
st.caption("Estimated annual value per business function, split by automation vs. "
           "augmentation — a high-level read on where AI value concentrates and how.")

chart_rows = []
for func in shown_functions:
    for pattern in ("automation", "augmentation"):
        subset = [t for t in by_function.get(func, []) if t.ai_pattern == pattern]
        if subset:
            chart_rows.append({
                "Business function": func,
                "AI pattern": pattern.title(),
                "Annual value": round(roi.portfolio(subset, cfg)["annual_value"]),
                "Themes": len(subset),
            })

if chart_rows:
    cdf = pd.DataFrame(chart_rows)
    palette = ui.chart_colors()
    pat_colors = {k: v[1] for k, v in ui.PATTERN_BADGE.items()}
    try:
        import altair as alt

        chart = (
            alt.Chart(cdf)
            .mark_bar()
            .encode(
                y=alt.Y("Business function:N", sort="-x", title=None,
                        # don't truncate long function names; Altair reserves the
                        # left margin needed so labels fit dynamically
                        axis=alt.Axis(labelLimit=1000)),
                x=alt.X("Annual value:Q", title="Estimated annual value ($)",
                        axis=alt.Axis(format="$,.0f")),
                color=alt.Color(
                    "AI pattern:N", title="AI pattern",
                    scale=alt.Scale(domain=["Automation", "Augmentation"],
                                    range=[pat_colors["automation"],
                                           pat_colors["augmentation"]])),
                tooltip=["Business function", "AI pattern", "Themes",
                         alt.Tooltip("Annual value:Q", format="$,.0f")],
            )
            .properties(height=max(220, 40 * len(shown_functions)),
                        background="transparent")
        )
        chart = (chart
                 .configure_view(strokeWidth=0)
                 .configure_axis(labelColor=palette["chart_text"],
                                 titleColor=palette["chart_text"],
                                 gridColor=palette["chart_grid"],
                                 domainColor=palette["chart_grid"])
                 .configure_legend(labelColor=palette["chart_text"],
                                   titleColor=palette["chart_text"]))
        st.altair_chart(chart, width="stretch")
    except Exception:
        st.bar_chart(cdf, x="Business function", y="Annual value", color="AI pattern",
                     horizontal=True)

st.divider()

# ---------------------------------------------------------------------------
# Per-function sections
# ---------------------------------------------------------------------------
# Order functions by estimated annual value (biggest impact first).
def _function_value(func: str) -> float:
    return roi.portfolio(by_function[func], cfg)["annual_value"]

for func in sorted(shown_functions, key=_function_value, reverse=True):
    items = by_function.get(func, [])
    if not items:
        continue
    fpf = roi.portfolio(items, cfg)
    # Distinct roles touched by any theme in this function.
    roles = len({(mm.role_title or mm.source_name)
                 for t in items for mm in (getattr(t, "_members", None) or [t])})

    st.markdown(f"## {func}")
    s = st.columns(4)
    s[0].metric("Use-case themes", len(items))
    s[1].metric("Roles impacted", roles)
    s[2].metric("Est. annual value", roi.fmt_money(fpf["annual_value"]))
    s[3].metric("Hours saved / yr", roi.fmt_hours(fpf["annual_hours"]))

    items.sort(key=lambda o: scoring.score(o, cfg), reverse=True)
    for opp in items:
        members = getattr(opp, "_members", None)
        ui.render_opportunity_card(opp, votable=False, key_prefix="bv_", members=members)

        has_doc = bool(opp.use_case_doc)
        btn_label = "📄 View use-case document" if has_doc else "🛠️ Build use-case document"
        if st.button(btn_label, key=f"bv_build_{opp.id}"):
            st.session_state["build_opp_id"] = opp.id
            st.switch_page("pages/4_Use_Case.py")
        if has_doc:
            st.caption("✓ Use-case document ready — open the builder to view or regenerate.")
        st.write("")

    st.divider()
