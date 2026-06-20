"""Home page: submit a job description for analysis.

The home page is intentionally focused on one job: take in a job description
(file, URL, or pasted text), capture its job title, and derive candidate AI use
cases. Derived use cases are saved as **proposed** and the user is sent to
*Manage Use Cases* to approve the ones worth pursuing.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

import ui_common as ui
from core import analysis, ingestion, storage
from core.providers import ProviderError

st.set_page_config(page_title="Talent Miner", page_icon="⛏️", layout="wide")
ui.page_chrome("AI Opportunity Finder")
ui.render_sidebar("home")

st.write(
    "Upload a job description (PDF or Word) or paste a link to a job posting. "
    "The app extracts the text locally, then uses your configured AI model to surface "
    "where AI could **automate** or **augment** the role — scored by impact and effort. "
    "Derived use cases land in **Manage Use Cases** for approval, then feed feedback, "
    "the roadmap, and the business view."
)

# ---------------------------------------------------------------------------
# Analyze section
# ---------------------------------------------------------------------------
st.subheader("Analyze a job description")

with st.container(border=True):
    job_title = st.text_input(
        "Job title",
        placeholder="e.g. Senior Quant Analyst",
        help="Tracked with the analysis and carried onto every use case it produces. "
             "Leave blank to let the app infer it from the document.",
    )

    tab_file, tab_url, tab_paste = st.tabs(["📄 Upload file", "🔗 From URL", "📝 Paste text"])

    pending_doc = None
    with tab_file:
        up = st.file_uploader("PDF or Word document", type=["pdf", "docx", "txt", "md"],
                              label_visibility="collapsed")
        if up is not None:
            st.caption(f"Selected: {up.name} ({up.size/1024:.0f} KB)")
        if st.button("Analyze file", type="primary", disabled=up is None, key="btn_file"):
            try:
                suffix = os.path.splitext(up.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(up.getbuffer())
                    tmp_path = tmp.name
                pending_doc = ingestion.ingest_file(tmp_path, source_name=up.name)
                os.unlink(tmp_path)
            except Exception as exc:
                st.error(f"Could not read that file: {exc}")

    with tab_url:
        url = st.text_input("Job posting URL", placeholder="https://company.com/careers/job-123")
        st.caption("Some job boards block scraping. If a URL fails, paste the text instead.")
        if st.button("Fetch & analyze", type="primary", disabled=not url, key="btn_url"):
            try:
                with st.spinner("Fetching page…"):
                    pending_doc = ingestion.ingest_url(url.strip())
            except Exception as exc:
                st.error(f"Could not fetch that URL: {exc}")

    with tab_paste:
        pasted = st.text_area("Paste the job description", height=200,
                              placeholder="Paste the full job description here…")
        if st.button("Analyze text", type="primary", disabled=not pasted.strip(), key="btn_paste"):
            try:
                label = job_title.strip() or "Pasted job description"
                pending_doc = ingestion.ingest_text(pasted, label)
            except Exception as exc:
                st.error(f"Could not process the text: {exc}")

# Run analysis if we successfully ingested a document this run
if pending_doc is not None:
    # An explicit job title always wins over the heuristic guess so the analysis
    # data tracks the title the user actually cares about.
    if job_title.strip():
        pending_doc.role_title = job_title.strip()

    cfg = ui.get_config()
    provider_name = cfg.get("provider", "Demo (offline)")
    try:
        provider = ui.build_active_provider()
    except ProviderError as exc:
        st.error(f"{exc} Configure it on the Settings page.")
        st.stop()

    with st.spinner(f"Analyzing with {provider_name}…"):
        try:
            summary, opps = analysis.analyze_document(
                pending_doc, provider, max_items=int(cfg.get("max_opportunities", 8)))
        except ProviderError as exc:
            st.error(f"Analysis failed: {exc}")
            st.stop()

    if not opps:
        st.warning("The model did not return any opportunities. Try a different document or model.")
    else:
        storage.save_document(pending_doc)
        # Persist every derived use case as "proposed" — approval happens per item
        # on the Manage Use Cases page.
        added = storage.add_opportunities(opps)
        st.success(
            f"Found {len(opps)} candidate use cases for “{pending_doc.role_title}”. "
            f"They're saved as proposed — approve the ones worth pursuing in Manage Use Cases →"
        )
        try:
            st.switch_page("pages/1_Manage_Use_Cases.py")
        except Exception:
            st.page_link("pages/1_Manage_Use_Cases.py", label="Go to Manage Use Cases", icon="🗂️")

# ---------------------------------------------------------------------------
# At-a-glance status
# ---------------------------------------------------------------------------
st.divider()

all_opps = storage.list_opportunities()
pending = [o for o in all_opps if o.status == "proposed"]
approved = [o for o in all_opps if o.status == "approved"]
docs = storage.list_documents()

m1, m2, m3 = st.columns(3)
m1.metric("Documents analyzed", len(docs))
m2.metric("Pending approval", len(pending))
m3.metric("Approved use cases", len(approved))

if pending:
    st.info(f"You have **{len(pending)}** use cases waiting for approval.")
    st.page_link("pages/1_Manage_Use_Cases.py", label="**Review & approve use cases →**", icon="🗂️")
elif approved:
    st.page_link("pages/7_Use_Case_Feedback.py", label="**Vote on approved use cases →**", icon="🗳️")
    st.page_link("pages/2_Roadmap_View.py", label="**View the roadmap →**", icon="🗺️")
else:
    st.caption("Analyze a job description above to start building your AI use-case backlog.")
