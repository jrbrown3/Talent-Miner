"""Use-case builder: generate and store an AI use-case document for a roadmap item."""
from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

import ui_common as ui
from core import analysis, scoring, storage
from core.providers import ProviderError

st.set_page_config(page_title="Use Case · Talent Miner", page_icon="⛏️", layout="wide")
ui.page_chrome("AI use-case builder")
ui.render_sidebar("usecase")

opp_id = st.session_state.get("build_opp_id")

if not opp_id:
    st.info("Pick a roadmap item to build. Open the Roadmap and click **Build use case** on "
            "any opportunity.")
    st.page_link("pages/2_Roadmap_View.py", label="Go to Roadmap", icon="🗺️")
    st.stop()

opp = storage.get_opportunity(opp_id)
if opp is None:
    st.error("That opportunity no longer exists. It may have been removed.")
    st.page_link("pages/2_Roadmap_View.py", label="Back to Roadmap", icon="🗺️")
    st.stop()

# ---------------------------------------------------------------------------
# Opportunity summary
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown(f"### {opp.title}")
    st.markdown(ui.opportunity_header_html(opp), unsafe_allow_html=True)
    if opp.context:
        st.write(opp.context)
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Impact** {opp.impact}/5")
    c2.markdown(f"**Effort** {opp.effort}/5")
    c3.markdown(f"**Priority** {round(scoring.combined_score(opp, ui.get_config().get('weights')), 2)}")
    if opp.source_name:
        st.caption(f"From: {opp.source_name}"
                   + (f" · {opp.role_title}" if opp.role_title else ""))

st.divider()

# Pull the original job description text (if still stored) to ground the brief.
def _source_text() -> str:
    for d in storage.list_documents():
        if d.id == opp.source_document_id:
            return d.raw_text
    return ""


def _generate() -> None:
    try:
        provider = ui.build_active_provider()
    except ProviderError as exc:
        st.error(f"{exc} Configure it on the Settings page.")
        return
    with st.spinner(f"Generating use-case document with {provider.name}…"):
        try:
            doc = analysis.generate_use_case(opp, provider, source_text=_source_text())
        except ProviderError as exc:
            st.error(f"Generation failed: {exc}")
            return
    storage.set_use_case_doc(opp.id, doc, provider=provider.name)
    st.session_state["just_generated"] = True
    st.rerun()


# ---------------------------------------------------------------------------
# Generate / view
# ---------------------------------------------------------------------------
if not opp.use_case_doc:
    st.subheader("Generate the use-case document")
    st.write("Use AI to draft a decision-ready brief for this opportunity — covering the "
             "problem, proposed solution, how it works, data needs, business impact, an "
             "implementation plan, risks, and success metrics. It's saved to this roadmap "
             "item so you can revisit it anytime.")
    provider_name = ui.get_config().get("provider", "Demo (offline)")
    st.caption(f"Model: **{provider_name}**  ·  change it on the Settings page.")
    if st.button("✨ Generate use-case document", type="primary"):
        _generate()
else:
    if st.session_state.pop("just_generated", False):
        st.success("Use-case document generated and saved to this opportunity.")

    meta = []
    if opp.use_case_generated_at:
        try:
            ts = datetime.fromisoformat(opp.use_case_generated_at)
            meta.append("Generated " + ts.strftime("%Y-%m-%d %H:%M UTC"))
        except ValueError:
            pass
    if opp.use_case_provider:
        meta.append(f"via {opp.use_case_provider}")
    if meta:
        st.caption(" · ".join(meta))

    a1, a2, a3, a4 = st.columns(4)
    safe_name = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in opp.title)[:60].strip() or "use_case"
    a1.download_button("⬇️ Markdown", opp.use_case_doc,
                       file_name=f"{safe_name}.md", mime="text/markdown",
                       use_container_width=True)

    # PDF export — built on demand and cached per document version.
    meta_line = (f"{opp.category} · {opp.ai_pattern.title()} · "
                 f"Impact {opp.impact}/5 · Effort {opp.effort}/5")
    try:
        import hashlib
        from core import exporting
        cache_key = "pdf:" + hashlib.md5((opp.id + opp.use_case_doc).encode("utf-8")).hexdigest()
        pdf_bytes = st.session_state.get(cache_key)
        if pdf_bytes is None:
            pdf_bytes = exporting.markdown_to_pdf(
                opp.use_case_doc, meta_line=meta_line,
                doc_title=opp.title or "Use Case Brief")
            st.session_state[cache_key] = pdf_bytes
        a2.download_button("⬇️ PDF", pdf_bytes, file_name=f"{safe_name}.pdf",
                           mime="application/pdf", use_container_width=True)
    except ImportError:
        a2.button("⬇️ PDF", disabled=True, use_container_width=True,
                  help="Run `pip install reportlab` to enable PDF export.")
    except Exception as exc:
        a2.button("⬇️ PDF", disabled=True, use_container_width=True,
                  help=f"PDF export failed: {exc}")

    if a3.button("🔄 Regenerate", use_container_width=True):
        _generate()
    if a4.button("🗑️ Clear", use_container_width=True):
        storage.set_use_case_doc(opp.id, "", provider="")
        st.rerun()

    st.divider()
    with st.container(border=True):
        st.markdown(opp.use_case_doc)

st.divider()
st.page_link("pages/2_Roadmap_View.py", label="← Back to Roadmap", icon="🗺️")
