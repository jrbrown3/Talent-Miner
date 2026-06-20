"""ROI / business-case quantification.

Turns an opportunity's impact, effort, AI pattern and reach into a defensible
dollar/time estimate using a small set of editable assumptions (loaded hourly
cost, working weeks, headcount per role, etc.). Everything is transparent and
configurable in Settings — these are planning estimates, not guarantees.
"""
from __future__ import annotations

from typing import Any

from .models import Opportunity

_DEFAULTS = {
    "loaded_hourly_cost": 75,
    "working_weeks": 46,
    "headcount_per_role": 1,
    "augmentation_factor": 0.5,
    "impact_hours_per_week": [1, 2, 4, 6, 10],
    "effort_cost": [5000, 15000, 35000, 60000, 100000],
    "annual_run_cost": [1000, 3000, 6000, 12000, 24000],
}


def _assumptions(cfg: dict[str, Any] | None) -> dict[str, Any]:
    roi = dict(_DEFAULTS)
    roi.update((cfg or {}).get("roi", {}) or {})
    return roi


def _by_score(table: list, idx_1to5: int, fallback: float) -> float:
    """Look up a value in a 5-element table indexed by a 1..5 impact/effort score.

    The tables (impact_hours_per_week, effort_cost, annual_run_cost) live in
    ``config["roi"]`` and are editable in Settings, so they may be malformed;
    out-of-range or non-numeric entries fall back to ``fallback``.
    """
    try:
        return float(table[max(1, min(5, int(idx_1to5))) - 1])
    except (IndexError, TypeError, ValueError):
        return float(fallback)


def estimate(opp: Opportunity, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a per-opportunity ROI estimate."""
    a = _assumptions(cfg)
    hourly = float(a["loaded_hourly_cost"])
    weeks = float(a["working_weeks"])
    headcount = float(a["headcount_per_role"])
    aug_factor = float(a["augmentation_factor"])

    reach = max(1, int(getattr(opp, "reach", 1) or 1))

    # weekly hours saved per person: prefer the model's estimate, else impact default
    weekly = float(getattr(opp, "est_weekly_hours_saved", 0) or 0)
    if weekly <= 0:
        weekly = _by_score(a["impact_hours_per_week"], opp.impact, 4)
    if opp.ai_pattern == "augmentation":
        weekly *= aug_factor

    people = reach * headcount
    annual_hours = weekly * weeks * people
    annual_value = annual_hours * hourly
    impl_cost = _by_score(a["effort_cost"], opp.effort, 35000)
    run_cost = _by_score(a["annual_run_cost"], opp.effort, 6000)
    net_year1 = annual_value - impl_cost - run_cost
    net_year2 = annual_value - run_cost
    net_year3 = annual_value - run_cost
    monthly_value = annual_value / 12.0
    payback_months = (impl_cost / monthly_value) if monthly_value > 0 else None

    return {
        "weekly_hours_per_role": weekly,
        "people": people,
        "annual_hours": annual_hours,
        "annual_value": annual_value,
        "impl_cost": impl_cost,
        "annual_run_cost": run_cost,
        "net_year1": net_year1,
        "net_year2": net_year2,
        "net_year3": net_year3,
        "payback_months": payback_months,
    }


def portfolio(opportunities: list[Opportunity],
              cfg: dict[str, Any] | None = None) -> dict[str, float]:
    """Aggregate ROI across a set of opportunities."""
    keys = ["annual_hours", "annual_value", "impl_cost", "annual_run_cost",
            "net_year1", "net_year2", "net_year3"]
    total = {k: 0.0 for k in keys}
    for opp in opportunities:
        est = estimate(opp, cfg)
        for k in keys:
            total[k] += est[k]
    return total


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_money(v: float) -> str:
    v = float(v or 0)
    sign = "-" if v < 0 else ""
    n = abs(v)
    if n >= 1_000_000:
        return f"{sign}${n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{sign}${n/1_000:.0f}K"
    return f"{sign}${n:.0f}"


def fmt_hours(v: float) -> str:
    v = float(v or 0)
    if v >= 1000:
        return f"{v/1000:.1f}K hrs/yr"
    return f"{v:.0f} hrs/yr"


def fmt_payback(months: float | None) -> str:
    if not months or months <= 0:
        return "—"
    if months < 1:
        return "< 1 mo"
    if months >= 36:
        return "3+ yrs"
    return f"{months:.0f} mo"
