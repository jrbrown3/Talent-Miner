"""Prioritization logic.

Two interchangeable scoring methods, selectable in config (``scoring.method``):

* **rice**     – RICE = (Reach x Impact x Confidence) / Effort, the industry-standard
                 prioritization model, with a small optional vote nudge.
* **weighted** – the legacy linear blend of impact, effort and votes.

Both feed the same downstream views: an impact/effort ``quadrant``, a ranked order,
and the Now / Near / Far roadmap lanes (which also respect strong vote consensus).
"""
from __future__ import annotations

from typing import Any

from .models import Opportunity

DEFAULT_WEIGHTS = {"impact": 1.0, "effort": 0.6, "votes": 0.4}

QUADRANTS = {
    "Quick Win": "High impact, low effort - do these first.",
    "Big Bet": "High impact, high effort - plan and resource deliberately.",
    "Fill-In": "Low impact, low effort - easy extras when capacity allows.",
    "Money Pit": "Low impact, high effort - usually defer or drop.",
}


# ---------------------------------------------------------------------------
# Individual scoring methods
# ---------------------------------------------------------------------------

def weighted_score(opp: Opportunity, weights: dict[str, float] | None = None) -> float:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    return (w["impact"] * opp.impact
            - w["effort"] * opp.effort
            + w["votes"] * opp.net_votes)


def confidence_factor(opp: Opportunity) -> float:
    return max(0.0, min(1.0, (getattr(opp, "confidence_pct", 70) or 70) / 100.0))


def confidence_label(pct: int) -> str:
    if pct >= 85:
        return "High"
    if pct >= 65:
        return "Medium"
    return "Low"


def rice_score(opp: Opportunity, cfg: dict[str, Any] | None = None) -> float:
    """RICE = (Reach x Impact x Confidence) / Effort, with an optional vote nudge."""
    cfg = cfg or {}
    reach = max(1, int(getattr(opp, "reach", 1) or 1))
    impact = max(1, int(opp.impact))
    effort = max(1, int(opp.effort))
    base = (reach * impact * confidence_factor(opp)) / effort
    vote_influence = float((cfg.get("rice") or {}).get("vote_influence", 0.05))
    return base * max(0.0, 1.0 + vote_influence * opp.net_votes)


def score(opp: Opportunity, cfg: dict[str, Any] | None = None) -> float:
    """Dispatch to the configured scoring method. ``cfg`` is the full config dict."""
    cfg = cfg or {}
    method = (cfg.get("scoring") or {}).get("method", "rice")
    if method == "weighted":
        return weighted_score(opp, cfg.get("weights"))
    return rice_score(opp, cfg)


# Backwards-compatible alias (older callers).
def combined_score(opp: Opportunity, cfg: dict[str, Any] | None = None) -> float:
    return score(opp, cfg)


# ---------------------------------------------------------------------------
# Quadrant / ranking / lanes
# ---------------------------------------------------------------------------

def quadrant(opp: Opportunity, threshold: int = 3) -> str:
    hi_impact = opp.impact >= threshold
    lo_effort = opp.effort < threshold
    if hi_impact and lo_effort:
        return "Quick Win"
    if hi_impact and not lo_effort:
        return "Big Bet"
    if not hi_impact and lo_effort:
        return "Fill-In"
    return "Money Pit"


def rank(opportunities: list[Opportunity],
         cfg: dict[str, Any] | None = None) -> list[Opportunity]:
    """Return opportunities sorted by the active score (highest first)."""
    return sorted(opportunities, key=lambda o: score(o, cfg), reverse=True)


def assign_lanes(opportunities: list[Opportunity],
                 cfg: dict[str, Any] | None = None) -> dict[str, list[Opportunity]]:
    """Bucket opportunities into Now / Near / Far.

    Ranking is driven by the active score; the impact/effort quadrant biases quick
    wins forward, and strong vote consensus can override the default placement.
    """
    ranked = rank(opportunities, cfg)
    lanes: dict[str, list[Opportunity]] = {"Now": [], "Near": [], "Far": []}
    n = len(ranked)
    if n == 0:
        return lanes
    for idx, opp in enumerate(ranked):
        q = quadrant(opp)
        if opp.net_votes <= -2:
            lanes["Far"].append(opp)
            continue
        if opp.net_votes >= 2 and q != "Money Pit":
            lanes["Now"].append(opp)
            continue
        third = idx / n
        if q == "Quick Win" or third < 1 / 3:
            lanes["Now"].append(opp)
        elif third < 2 / 3:
            lanes["Near"].append(opp)
        else:
            lanes["Far"].append(opp)
    return lanes


def matrix_points(opportunities: list[Opportunity],
                  cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Shape data for an impact/effort scatter chart (size encodes reach)."""
    points = []
    for o in opportunities:
        points.append({
            "title": o.title,
            "category": o.category,
            "impact": o.impact,
            "effort": o.effort,
            "reach": max(1, int(getattr(o, "reach", 1) or 1)),
            "confidence": getattr(o, "confidence_pct", 70),
            "quadrant": quadrant(o),
            "net_votes": o.net_votes,
            "score": round(score(o, cfg), 2),
        })
    return points
