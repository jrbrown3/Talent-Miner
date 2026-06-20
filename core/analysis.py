"""Analysis engine.

Takes a normalized ``SourceDocument`` plus an ``AIProvider`` and returns a list
of ``Opportunity`` objects. Owns the prompt, the JSON contract, and validation
of the model's output.
"""
from __future__ import annotations

import re
from typing import Any

from .models import Opportunity, SourceDocument
from .providers import AIProvider, ProviderError, extract_json

SYSTEM_PROMPT = """You are an AI transformation consultant. Given a single job \
description, identify concrete opportunities where AI (either full automation or \
human augmentation) could perform or assist the work of this role.

Rules:
- Focus on realistic, specific use cases tied to the actual responsibilities described.
- Group each opportunity into a short functional category (e.g. "Reporting & Analytics", \
"Document Processing", "Communication", "Data & Analysis").
- For each opportunity write a single-paragraph context (no more than ~80 words).
- Score impact 1-5 (business value if implemented) and effort 1-5 (implementation \
cost/complexity). Use the full range; do not make everything a 3.
- Classify each as "automation" (AI does the task) or "augmentation" (AI assists a human).
- Rate confidence "high", "medium" or "low" that the opportunity is real and worthwhile \
given the job description.
- Provide 1-3 evidence quotes copied VERBATIM from the job description that justify the \
opportunity. Each quote must appear word-for-word in the text. Do not paraphrase or invent.
- Estimate weekly hours this could save per person in the role (a number, 0 if unclear).

Respond with ONLY valid JSON, no prose, in exactly this shape:
{
  "role_summary": "one sentence describing the role",
  "opportunities": [
    {
      "title": "short headline",
      "category": "functional category",
      "context": "one paragraph, <= 80 words",
      "ai_pattern": "automation" | "augmentation",
      "impact": 1-5,
      "impact_rationale": "brief reason",
      "effort": 1-5,
      "effort_rationale": "brief reason",
      "confidence": "high" | "medium" | "low",
      "evidence": ["verbatim quote from the JD", "..."],
      "est_weekly_hours_saved": number,
      "example_tools": ["technique or tool", "..."]
    }
  ]
}"""


def _build_user_prompt(doc: SourceDocument, max_items: int) -> str:
    body = doc.raw_text
    if len(body) > 12000:  # keep prompts bounded
        body = body[:12000] + "\n...[truncated]..."
    return (
        f"Role title (best guess): {doc.role_title}\n"
        f"Source: {doc.source_name}\n\n"
        f"Return at most {max_items} of the strongest opportunities.\n\n"
        f"JOB DESCRIPTION:\n\"\"\"\n{body}\n\"\"\""
    )


def _coerce_score(value: Any, default: int = 3) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(1, min(5, n))


# Maps the model's qualitative confidence to a percentage. This becomes
# ``Opportunity.confidence_pct``, which scoring.rice_score() uses as the RICE
# confidence multiplier (pct/100) and scoring.confidence_label() buckets back
# into High/Medium/Low for display. Keep the buckets in sync with that label fn.
_CONFIDENCE_MAP = {"high": 90, "medium": 70, "med": 70, "low": 50}


def _coerce_confidence(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    return _CONFIDENCE_MAP.get(str(value).strip().lower(), 70)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _verify_evidence(quotes: Any, source_text: str) -> list[dict]:
    """Return [{"quote","verified"}] checking each quote against the source text."""
    if isinstance(quotes, str):
        quotes = [quotes]
    if not isinstance(quotes, list):
        return []
    norm_src = _norm(source_text)
    out: list[dict] = []
    for q in quotes:
        qs = str(q).strip()
        if not qs:
            continue
        nq = _norm(qs)
        verified = bool(nq) and nq in norm_src
        if not verified:
            words = [w for w in nq.split() if len(w) > 3]
            if words:
                hits = sum(1 for w in words if w in norm_src)
                verified = hits / len(words) >= 0.7
        out.append({"quote": qs[:280], "verified": bool(verified)})
        if len(out) >= 3:
            break
    return out


def analyze_document(doc: SourceDocument, provider: AIProvider,
                     max_items: int = 8) -> tuple[str, list[Opportunity]]:
    """Run the analysis. Returns (role_summary, opportunities)."""
    user_prompt = _build_user_prompt(doc, max_items)
    raw = provider.complete(SYSTEM_PROMPT, user_prompt)
    data = extract_json(raw)

    role_summary = str(data.get("role_summary", "")).strip()
    items = data.get("opportunities", []) or []
    opportunities: list[Opportunity] = []
    for item in items[:max_items]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        pattern = str(item.get("ai_pattern", "augmentation")).strip().lower()
        if pattern not in ("automation", "augmentation"):
            pattern = "augmentation"
        tools = item.get("example_tools", [])
        if isinstance(tools, str):
            tools = [tools]
        try:
            hours = max(0.0, min(40.0, float(item.get("est_weekly_hours_saved", 0) or 0)))
        except (TypeError, ValueError):
            hours = 0.0
        opportunities.append(Opportunity(
            title=title[:140],
            category=str(item.get("category", "General")).strip() or "General",
            context=str(item.get("context", "")).strip(),
            ai_pattern=pattern,
            impact=_coerce_score(item.get("impact")),
            impact_rationale=str(item.get("impact_rationale", "")).strip(),
            effort=_coerce_score(item.get("effort")),
            effort_rationale=str(item.get("effort_rationale", "")).strip(),
            confidence_pct=_coerce_confidence(item.get("confidence")),
            evidence=_verify_evidence(item.get("evidence", []), doc.raw_text),
            est_weekly_hours_saved=hours,
            reach=1,
            example_tools=[str(t).strip() for t in tools if str(t).strip()][:6],
            source_document_id=doc.id,
            source_name=doc.source_name,
            role_title=doc.role_title,
            provider=provider.name,
            status="proposed",
        ))
    return role_summary, opportunities

# ---------------------------------------------------------------------------
# Use-case document generation
# ---------------------------------------------------------------------------

USE_CASE_SYSTEM_PROMPT = """You are an AI solutions consultant writing a concise, \
decision-ready use-case brief for a single AI opportunity. Write in clear markdown for a \
mixed business and technical audience. Be specific and practical; avoid filler and hype.

Use exactly these markdown sections (## headings), in order:
## Executive summary
## Problem / current state
## Proposed AI solution
## How it works
## Data & integration requirements
## Expected business impact
## Implementation plan & effort
## Risks & mitigations
## Success metrics
## Next steps

Keep it to roughly 400-700 words. Do not invent specific vendor names, prices, or precise \
figures that are not supported by the inputs; use ranges and qualifiers where needed."""


def generate_use_case(opp: Opportunity, provider: AIProvider,
                      source_text: str = "") -> str:
    """Generate a markdown use-case brief for a single opportunity."""
    context_block = ""
    if source_text:
        snippet = source_text[:6000]
        context_block = f"\n\nORIGINAL JOB DESCRIPTION (for grounding):\n\"\"\"\n{snippet}\n\"\"\""

    user_prompt = (
        f"Write a use-case brief for this AI opportunity.\n\n"
        f"Title: {opp.title}\n"
        f"Category: {opp.category}\n"
        f"AI pattern: {opp.ai_pattern}\n"
        f"Impact (1-5): {opp.impact} - {opp.impact_rationale}\n"
        f"Effort (1-5): {opp.effort} - {opp.effort_rationale}\n"
        f"Role: {opp.role_title}\n"
        f"Source: {opp.source_name}\n"
        f"Example techniques/tools: {', '.join(opp.example_tools) or 'n/a'}\n"
        f"Context: {opp.context}"
        f"{context_block}"
    )
    text = provider.complete(USE_CASE_SYSTEM_PROMPT, user_prompt, json_mode=False)
    text = (text or "").strip()
    if not text:
        raise ProviderError("The model returned an empty use-case document.")
    # strip an accidental code fence if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    # ensure the brief leads with the opportunity title as an H1
    if not text.lstrip().startswith("# "):
        text = f"# {opp.title}\n\n{text}"
    return text
