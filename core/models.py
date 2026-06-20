"""Data models for the AI Opportunity Finder.

These are plain dataclasses with explicit (de)serialization so that everything
can live in flat JSON files - no external database required.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class SourceDocument:
    """A normalized representation of an uploaded/linked job description."""

    id: str = field(default_factory=_new_id)
    source_type: str = "text"          # pdf | docx | url | text
    source_name: str = ""              # filename or URL
    role_title: str = ""               # best-effort extracted job title
    raw_text: str = ""                 # cleaned full text
    sections: dict[str, str] = field(default_factory=dict)  # heuristic sections
    char_count: int = 0
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SourceDocument":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Opportunity:
    """A single AI use-case derived from a job description."""

    id: str = field(default_factory=_new_id)
    title: str = ""                    # short headline
    category: str = "General"          # functional category
    context: str = ""                  # one-paragraph explanation
    ai_pattern: str = "augmentation"   # automation | augmentation
    impact: int = 3                    # 1 (low) .. 5 (high) business value
    impact_rationale: str = ""
    effort: int = 3                    # 1 (low) .. 5 (high) implementation cost
    effort_rationale: str = ""
    example_tools: list[str] = field(default_factory=list)

    # provenance
    source_document_id: str = ""
    source_name: str = ""
    role_title: str = ""
    provider: str = ""                 # which AI model produced it

    # lifecycle / prioritization
    status: str = "proposed"           # proposed | approved | rejected
    votes_up: int = 0
    votes_down: int = 0
    created_at: str = field(default_factory=_now)

    # RICE inputs (reach derived from clustering; confidence & hours from the model)
    reach: int = 1                     # number of roles this opportunity affects
    confidence_pct: int = 70           # model confidence 0-100 (RICE multiplier)
    est_weekly_hours_saved: float = 0.0  # per role/person; 0 -> derive from impact
    evidence: list = field(default_factory=list)  # [{"quote": str, "verified": bool}]

    # clustering / theming
    cluster_id: str = ""
    theme_title: str = ""

    # generated AI use-case brief (markdown), stored with the opportunity
    use_case_doc: str = ""
    use_case_generated_at: str = ""
    use_case_provider: str = ""

    @property
    def net_votes(self) -> int:
        return self.votes_up - self.votes_down

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Opportunity":
        """Rebuild an Opportunity from a stored dict, tolerating older/partial rows.

        Only known dataclass fields are kept (so the schema can grow without
        breaking old data), numeric fields are coerced with sane fallbacks, and
        ``evidence`` is normalized to a list of ``{"quote", "verified"}`` dicts —
        accepting the legacy form where evidence was a plain list of strings.
        """
        clean = {k: d.get(k) for k in cls.__dataclass_fields__ if k in d}
        # migrate the legacy "accepted" status to its current name "approved" so
        # data written before the approval workflow keeps flowing into the views.
        if clean.get("status") == "accepted":
            clean["status"] = "approved"
        # defensive coercion for the numeric fields (bad/legacy values -> defaults)
        for k in ("impact", "effort", "votes_up", "votes_down", "reach", "confidence_pct"):
            if k in clean and clean[k] is not None:
                try:
                    clean[k] = int(clean[k])
                except (TypeError, ValueError):
                    clean[k] = {"impact": 3, "effort": 3, "reach": 1,
                                "confidence_pct": 70}.get(k, 0)
        if "est_weekly_hours_saved" in clean and clean["est_weekly_hours_saved"] is not None:
            try:
                clean["est_weekly_hours_saved"] = float(clean["est_weekly_hours_saved"])
            except (TypeError, ValueError):
                clean["est_weekly_hours_saved"] = 0.0
        # normalize evidence into a list of {"quote","verified"} dicts
        ev = clean.get("evidence")
        if ev:
            norm = []
            for item in ev:
                if isinstance(item, dict) and item.get("quote"):
                    norm.append({"quote": str(item["quote"]),
                                 "verified": bool(item.get("verified", False))})
                elif isinstance(item, str) and item.strip():
                    norm.append({"quote": item.strip(), "verified": False})
            clean["evidence"] = norm
        return cls(**clean)
