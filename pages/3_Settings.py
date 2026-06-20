"""Settings page: choose and test the AI provider, tune defaults."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

import ui_common as ui
from core import config as cfgmod
from core import providers, storage

st.set_page_config(page_title="Settings · Talent Miner", page_icon="⛏️", layout="wide")
ui.page_chrome("Settings")
ui.render_sidebar("settings")

cfg = ui.get_config()
if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = {}

# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------
st.subheader("AI provider & model")

provider = st.selectbox("Provider", cfgmod.PROVIDERS,
                        index=cfgmod.PROVIDERS.index(cfg.get("provider", "Demo (offline)")))

models = dict(cfg.get("models", {}))
col1, col2 = st.columns(2)

if provider == "Demo (offline)":
    st.info("Demo mode needs no configuration. It generates opportunities with a local "
            "heuristic so you can try the whole workflow offline.")
elif provider == "Ollama":
    models["Ollama"] = col1.text_input("Model", value=models.get("Ollama", "llama3.1"),
                                       help="A model you have pulled locally, e.g. llama3.1, mistral.")
    cfg["ollama_base_url"] = col2.text_input("Ollama base URL",
                                             value=cfg.get("ollama_base_url", "http://localhost:11434"))
elif provider == "Claude":
    models["Claude"] = col1.text_input("Model", value=models.get("Claude", "claude-sonnet-4-6"))
    env_present = bool(os.environ.get(cfgmod.ENV_KEYS["Claude"]))
    key = col2.text_input("Anthropic API key", type="password",
                          value=st.session_state["api_keys"].get("Claude", ""),
                          placeholder="set here or via ANTHROPIC_API_KEY env var")
    if key:
        st.session_state["api_keys"]["Claude"] = key
    if env_present:
        col2.caption("✓ ANTHROPIC_API_KEY detected in environment.")
elif provider == "OpenAI":
    models["OpenAI"] = col1.text_input("Model", value=models.get("OpenAI", "gpt-4o"))
    env_present = bool(os.environ.get(cfgmod.ENV_KEYS["OpenAI"]))
    key = col2.text_input("OpenAI API key", type="password",
                          value=st.session_state["api_keys"].get("OpenAI", ""),
                          placeholder="set here or via OPENAI_API_KEY env var")
    if key:
        st.session_state["api_keys"]["OpenAI"] = key
    if env_present:
        col2.caption("✓ OPENAI_API_KEY detected in environment.")
elif provider == "OpenAI via Azure":
    models["OpenAI via Azure"] = col1.text_input(
        "Model", value=models.get("OpenAI via Azure", "gpt-4o"))
    cfg["azure_deployment"] = col2.text_input(
        "Deployment name", value=cfg.get("azure_deployment", ""),
        help="The Azure deployment name (often equals the model name).")
    cfg["azure_endpoint"] = st.text_input(
        "Azure endpoint", value=cfg.get("azure_endpoint", ""),
        placeholder="https://your-resource.openai.azure.com")
    cfg["azure_api_version"] = st.text_input(
        "API version", value=cfg.get("azure_api_version", "2024-06-01"))
    env_present = bool(os.environ.get(cfgmod.ENV_KEYS["OpenAI via Azure"]))
    key = st.text_input("Azure OpenAI API key", type="password",
                        value=st.session_state["api_keys"].get("OpenAI via Azure", ""),
                        placeholder="set here or via AZURE_OPENAI_API_KEY env var")
    if key:
        st.session_state["api_keys"]["OpenAI via Azure"] = key
    if env_present:
        st.caption("✓ AZURE_OPENAI_API_KEY detected in environment.")

cfg["provider"] = provider
cfg["models"] = models

st.divider()

# ---------------------------------------------------------------------------
# Analysis defaults
# ---------------------------------------------------------------------------
st.subheader("Analysis defaults")
d1, d2 = st.columns(2)
cfg["temperature"] = d1.slider("Temperature", 0.0, 1.0, float(cfg.get("temperature", 0.2)), 0.05,
                               help="Lower = more consistent, higher = more varied.")
cfg["max_opportunities"] = d2.slider("Max opportunities per document", 3, 15,
                                     int(cfg.get("max_opportunities", 8)))

st.subheader("Scoring & ROI")

scoring_method = st.radio(
    "Prioritization method",
    ["rice", "weighted"],
    index=0 if (cfg.get("scoring") or {}).get("method", "rice") == "rice" else 1,
    horizontal=True,
    help="RICE = (Reach × Impact × Confidence) ÷ Effort — accounts for how many roles an "
         "opportunity touches and model confidence. Weighted is the simpler legacy blend.",
)
cfg.setdefault("scoring", {})["method"] = scoring_method

if scoring_method == "rice":
    r1, r2 = st.columns(2)
    vi = float((cfg.get("rice") or {}).get("vote_influence", 0.05))
    cfg.setdefault("rice", {})["vote_influence"] = r1.slider(
        "Vote influence", 0.0, 0.5, vi, 0.01,
        help="How much each net vote nudges the RICE score up or down. "
             "0 = votes have no effect on ranking.")
    th = float((cfg.get("clustering") or {}).get("threshold", 0.52))
    cfg.setdefault("clustering", {})["threshold"] = r2.slider(
        "Clustering threshold", 0.3, 0.9, th, 0.01,
        help="Similarity threshold for merging duplicate opportunities into themes. "
             "Lower = broader themes, higher = tighter/more themes.")
else:
    w = dict(cfg.get("weights", {}))
    w1, w2, w3 = st.columns(3)
    w["impact"] = w1.slider("Impact weight", 0.0, 2.0, float(w.get("impact", 1.0)), 0.1)
    w["effort"] = w2.slider("Effort weight", 0.0, 2.0, float(w.get("effort", 0.6)), 0.1)
    w["votes"] = w3.slider("Votes weight", 0.0, 2.0, float(w.get("votes", 0.4)), 0.1)
    cfg["weights"] = w

st.markdown("**ROI assumptions**")
st.caption("Used to estimate annual value, hours saved, and payback. These are planning "
           "estimates — adjust to match your organisation's cost structure.")
roi_cfg = dict(cfg.get("roi", {}))
ra, rb, rc = st.columns(3)
roi_cfg["loaded_hourly_cost"] = ra.number_input(
    "Loaded hourly cost ($)", 20, 500, int(roi_cfg.get("loaded_hourly_cost", 75)), 5,
    help="Fully-loaded cost per employee hour (salary + benefits + overhead).")
roi_cfg["working_weeks"] = rb.number_input(
    "Productive weeks / year", 30, 52, int(roi_cfg.get("working_weeks", 46)),
    help="Working weeks after leave and holidays.")
roi_cfg["headcount_per_role"] = rc.number_input(
    "Headcount per role", 1, 500, int(roi_cfg.get("headcount_per_role", 1)),
    help="Average number of people in each matched role (scales reach).")
rd, re = st.columns(2)
roi_cfg["augmentation_factor"] = rd.slider(
    "Augmentation efficiency factor", 0.1, 1.0,
    float(roi_cfg.get("augmentation_factor", 0.5)), 0.05,
    help="Augmentation opportunities realise this fraction of the automation hours saved "
         "(0.5 = 50%). Automation opportunities use the full estimate.")
with re.expander("Advanced: hours / cost tables"):
    st.caption("Five values indexed by impact (1→5) or effort (1→5). Comma-separated.")
    def _list_input(label: str, key: str, default: list) -> list:
        raw = ", ".join(str(v) for v in roi_cfg.get(key, default))
        val = st.text_input(label, value=raw, key=f"roi_{key}")
        try:
            return [float(x.strip()) for x in val.split(",") if x.strip()][:5]
        except ValueError:
            return default
    roi_cfg["impact_hours_per_week"] = _list_input(
        "Hours saved/week by impact 1–5", "impact_hours_per_week", [1, 2, 4, 6, 10])
    roi_cfg["effort_cost"] = _list_input(
        "Build cost ($) by effort 1–5", "effort_cost", [5000, 15000, 35000, 60000, 100000])
    roi_cfg["annual_run_cost"] = _list_input(
        "Annual run cost ($) by effort 1–5", "annual_run_cost", [1000, 3000, 6000, 12000, 24000])
cfg["roi"] = roi_cfg

st.divider()
b1, b2, b3 = st.columns(3)

if b1.button("💾 Save settings", type="primary"):
    cfgmod.save_config(cfg)
    st.session_state["config"] = cfg
    st.success("Settings saved to config.yaml (API keys are kept in this session only).")

if b2.button("🔌 Test connection"):
    try:
        prov = ui.build_active_provider()
        if hasattr(prov, "check"):
            ok, msg = prov.check()
            (st.success if ok else st.error)(msg)
        # do a tiny real round-trip for non-demo providers
        if provider != "Demo (offline)":
            with st.spinner("Sending a test prompt…"):
                out = prov.complete("Reply with the single word OK.", "Say OK.",
                                    json_mode=False)
            st.success(f"Model responded: {out[:120]}")
        else:
            st.success("Demo provider is always available.")
    except providers.ProviderError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Test failed: {exc}")

with b3:
    with st.popover("🗑️ Danger zone"):
        st.warning("This permanently deletes all stored documents and opportunities.")
        if st.button("Delete all data", type="primary"):
            storage.clear_all()
            st.success("All data cleared.")

st.divider()
st.caption("Settings (except API keys) are stored in `config.yaml`. API keys you enter here live "
           "only for this browser session; for shared deployments set them as environment "
           "variables instead.")
