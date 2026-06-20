"""Opportunity clustering / dedup.

Groups opportunities that describe the same use case across different roles, using
a local lexical similarity (no extra model calls, works fully offline). Each
group becomes a "theme" with a canonical title and a **reach** = the number of
distinct roles it touches, which feeds the RICE score.

This is intentionally lightweight and deterministic. A future upgrade could swap
the similarity function for embedding-based cosine similarity.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from .models import Opportunity

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by",
    "from", "into", "ai", "use", "using", "based", "via", "data", "automated",
    "automation", "augmentation", "assisted", "assistance", "generation",
    "routine", "support", "system", "tool", "tools", "across", "this", "that",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def similarity(o1: Opportunity, o2: Opportunity) -> float:
    """Return a 0..1 similarity between two opportunities.

    A weighted blend of four signals. The weights reflect how reliably each one
    indicates that two opportunities are *the same use case* recurring across
    roles, and they sum to 1.0 so the result stays in [0, 1]:

      * title token overlap (0.45) - the strongest signal; near-duplicate use
        cases tend to share head nouns ("automated reporting", "data cleaning").
      * context token overlap (0.20) - softer corroboration; supporting detail
        varies more between roles, so it is weighted below the title.
      * same functional category (0.25) - a strong structural gate; two items in
        different categories are rarely the same theme even with similar wording.
      * same AI pattern (0.10) - a light tie-breaker (automation vs augmentation).

    Tune alongside the ``cluster`` threshold: raising title/category weight makes
    clustering stricter, raising context weight makes it more permissive.
    """
    title_sim = _jaccard(_tokens(o1.title), _tokens(o2.title))
    ctx_sim = _jaccard(_tokens(o1.context), _tokens(o2.context))
    same_cat = 1.0 if o1.category.strip().lower() == o2.category.strip().lower() else 0.0
    same_pattern = 1.0 if o1.ai_pattern == o2.ai_pattern else 0.0
    return 0.45 * title_sim + 0.20 * ctx_sim + 0.25 * same_cat + 0.10 * same_pattern


def cluster(opportunities: list[Opportunity],
            threshold: float = 0.52) -> list[list[Opportunity]]:
    """Group opportunities whose pairwise ``similarity`` >= ``threshold``.

    Uses union-find so transitive matches merge into one group (A~B and B~C put
    A, B and C in the same theme). The default ``threshold`` of 0.52 was chosen so
    that a shared title plus the same category clears the bar (roughly
    0.45*~0.5 + 0.25 + ...), while merely sharing a category does not. Lower it to
    merge more aggressively (fewer, broader themes); raise it to keep themes
    tighter. The default is sourced from ``config["clustering"]["threshold"]`` by
    ``recompute_and_persist`` and can be edited in Settings.
    """
    n = len(opportunities)
    parent = list(range(n))

    def find(i: int) -> int:
        # Path-halving find: flattens the tree as it walks up to the root.
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    # O(n^2) pairwise comparison; fine for the hundreds-of-opportunities scale
    # this app targets. Swap in blocking/embeddings if the backlog grows large.
    for i in range(n):
        for j in range(i + 1, n):
            if similarity(opportunities[i], opportunities[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[Opportunity]] = {}
    for i, opp in enumerate(opportunities):
        groups.setdefault(find(i), []).append(opp)
    return list(groups.values())


def _role_key(opp: Opportunity) -> str:
    return opp.source_document_id or opp.source_name or opp.role_title or opp.id


def reach_of(members: list[Opportunity]) -> int:
    """Distinct roles (source documents) covered by a group."""
    return len({_role_key(m) for m in members}) or 1


def canonical_title(members: list[Opportunity]) -> str:
    """Pick a representative title: most common normalized title, then highest impact."""
    if len(members) == 1:
        return members[0].title
    counts: dict[str, int] = {}
    for m in members:
        key = re.sub(r"\s+", " ", m.title.strip().lower())
        counts[key] = counts.get(key, 0) + 1
    best_norm = max(counts, key=counts.get)
    candidates = [m for m in members
                  if re.sub(r"\s+", " ", m.title.strip().lower()) == best_norm]
    return max(candidates, key=lambda m: m.impact).title


def cluster_id_for(members: list[Opportunity]) -> str:
    if len(members) == 1:
        return members[0].id
    h = hashlib.md5("|".join(sorted(m.id for m in members)).encode()).hexdigest()[:10]
    return f"cl_{h}"


def compute_assignments(opportunities: list[Opportunity],
                        threshold: float = 0.52) -> dict[str, dict[str, Any]]:
    """Return {opp_id: {cluster_id, theme_title, reach}} for the given set."""
    assignments: dict[str, dict[str, Any]] = {}
    for members in cluster(opportunities, threshold):
        cid = cluster_id_for(members)
        title = canonical_title(members)
        reach = reach_of(members)
        for m in members:
            assignments[m.id] = {"cluster_id": cid, "theme_title": title, "reach": reach}
    return assignments


def recompute_and_persist(cfg: dict[str, Any] | None = None,
                          threshold: float | None = None) -> int:
    """Re-cluster all approved opportunities and persist cluster_id/theme_title/reach."""
    from . import config as cfgmod
    from . import storage

    cfg = cfg or cfgmod.load_config()
    if threshold is None:
        threshold = float((cfg.get("clustering") or {}).get("threshold", 0.52))
    opps = storage.list_opportunities(status="approved")
    assignments = compute_assignments(opps, threshold)
    return storage.apply_cluster_assignments(assignments)


def grouped(opportunities: list[Opportunity]) -> list[list[Opportunity]]:
    """Group an already-clustered set by stored cluster_id (no recompute)."""
    groups: dict[str, list[Opportunity]] = {}
    for o in opportunities:
        key = o.cluster_id or o.id
        groups.setdefault(key, []).append(o)
    return list(groups.values())


def collapse_to_themes(opportunities: list[Opportunity]) -> list[Opportunity]:
    """Collapse clustered duplicates into one display representative per theme.

    The representative is a copy of the highest-impact member, with:
      * title  = the canonical theme title
      * reach  = number of distinct roles in the theme
      * votes  = summed across members (aggregate consensus)
      * evidence = merged unique quotes
    A private ``_members`` list is attached for drill-down and bulk actions.
    Representatives are display objects and are never persisted.
    """
    import copy

    reps: list[Opportunity] = []
    for members in grouped(opportunities):
        rep = copy.copy(max(members, key=lambda m: m.impact))
        rep.title = (rep.theme_title or rep.title)
        rep.reach = reach_of(members)
        rep.votes_up = sum(m.votes_up for m in members)
        rep.votes_down = sum(m.votes_down for m in members)
        seen: set[str] = set()
        merged_ev: list[dict] = []
        for m in members:
            for e in (m.evidence or []):
                key = str(e.get("quote", ""))[:60]
                if key and key not in seen:
                    seen.add(key)
                    merged_ev.append(e)
        rep.evidence = merged_ev[:5]
        rep._members = members  # type: ignore[attr-defined]
        reps.append(rep)
    return reps

