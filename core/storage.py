"""File-level persistence (no external database).

State lives in two JSON files under ``data/``:
  * documents.json     - processed source documents (metadata + normalized text)
  * opportunities.json - all kept/proposed opportunities

Writes are atomic (temp file + os.replace) and guarded by a process-level lock,
which is sufficient for a single Streamlit server serving up to ~20 concurrent
sessions.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .models import Opportunity, SourceDocument

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_PATH = DATA_DIR / "documents.json"
OPPS_PATH = DATA_DIR / "opportunities.json"

_LOCK = threading.RLock()


def _ensure() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for p in (DOCS_PATH, OPPS_PATH):
        if not p.exists():
            _atomic_write(p, [])


def _atomic_write(path: Path, data: Any) -> None:
    """Write JSON atomically: dump to a temp file in the same dir, then os.replace.

    os.replace is atomic on POSIX and Windows, so a reader never observes a
    half-written file and a crash mid-write leaves the previous file intact.
    Writes are serialized by the module-level ``_LOCK`` in the calling mutators.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _read(path: Path) -> list[dict[str, Any]]:
    """Read a JSON list, returning [] for a missing, empty, or corrupt file.

    Failing soft (rather than raising) keeps the app usable if a data file is
    absent on first run or gets truncated; the next write rewrites it cleanly.
    """
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def save_document(doc: SourceDocument) -> None:
    with _LOCK:
        _ensure()
        docs = _read(DOCS_PATH)
        docs = [d for d in docs if d.get("id") != doc.id]
        docs.append(doc.to_dict())
        _atomic_write(DOCS_PATH, docs)


def list_documents() -> list[SourceDocument]:
    with _LOCK:
        _ensure()
        return [SourceDocument.from_dict(d) for d in _read(DOCS_PATH)]


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

def list_opportunities(status: str | None = None) -> list[Opportunity]:
    with _LOCK:
        _ensure()
        opps = [Opportunity.from_dict(o) for o in _read(OPPS_PATH)]
    if status:
        opps = [o for o in opps if o.status == status]
    return opps


def add_opportunities(opps: list[Opportunity]) -> int:
    with _LOCK:
        _ensure()
        existing = _read(OPPS_PATH)
        ids = {o.get("id") for o in existing}
        added = 0
        for o in opps:
            if o.id in ids:
                continue
            existing.append(o.to_dict())
            ids.add(o.id)
            added += 1
        _atomic_write(OPPS_PATH, existing)
        return added


def _update(opp_id: str, mutate) -> bool:
    with _LOCK:
        _ensure()
        rows = _read(OPPS_PATH)
        changed = False
        for row in rows:
            if row.get("id") == opp_id:
                mutate(row)
                changed = True
                break
        if changed:
            _atomic_write(OPPS_PATH, rows)
        return changed


def vote(opp_id: str, direction: int) -> bool:
    """direction > 0 is an upvote, < 0 is a downvote."""
    field = "votes_up" if direction > 0 else "votes_down"

    def _mut(row: dict[str, Any]) -> None:
        row[field] = int(row.get(field, 0)) + 1

    return _update(opp_id, _mut)


def set_status(opp_id: str, status: str) -> bool:
    def _mut(row: dict[str, Any]) -> None:
        row["status"] = status

    return _update(opp_id, _mut)


def set_use_case_doc(opp_id: str, doc: str, provider: str = "") -> bool:
    """Persist a generated use-case brief onto an opportunity."""
    from datetime import datetime, timezone

    def _mut(row: dict[str, Any]) -> None:
        row["use_case_doc"] = doc
        row["use_case_generated_at"] = datetime.now(timezone.utc).isoformat()
        row["use_case_provider"] = provider

    return _update(opp_id, _mut)


def get_opportunity(opp_id: str) -> Opportunity | None:
    for o in list_opportunities():
        if o.id == opp_id:
            return o
    return None


def apply_cluster_assignments(assignments: dict[str, dict[str, Any]]) -> int:
    """Bulk-write cluster_id / theme_title / reach onto opportunities.

    ``assignments`` maps opportunity id -> {"cluster_id", "theme_title", "reach"}.
    """
    if not assignments:
        return 0
    with _LOCK:
        _ensure()
        rows = _read(OPPS_PATH)
        changed = 0
        for row in rows:
            a = assignments.get(row.get("id"))
            if a:
                row["cluster_id"] = a.get("cluster_id", row.get("cluster_id", ""))
                row["theme_title"] = a.get("theme_title", row.get("theme_title", ""))
                row["reach"] = int(a.get("reach", row.get("reach", 1)))
                changed += 1
        if changed:
            _atomic_write(OPPS_PATH, rows)
        return changed


def delete_opportunity(opp_id: str) -> bool:
    with _LOCK:
        _ensure()
        rows = _read(OPPS_PATH)
        new_rows = [r for r in rows if r.get("id") != opp_id]
        if len(new_rows) == len(rows):
            return False
        _atomic_write(OPPS_PATH, new_rows)
        return True


def delete_opportunities(ids: list[str]) -> int:
    idset = set(ids)
    with _LOCK:
        _ensure()
        rows = _read(OPPS_PATH)
        new_rows = [r for r in rows if r.get("id") not in idset]
        removed = len(rows) - len(new_rows)
        if removed:
            _atomic_write(OPPS_PATH, new_rows)
        return removed


def clear_all() -> None:
    with _LOCK:
        _atomic_write(DOCS_PATH, [])
        _atomic_write(OPPS_PATH, [])
