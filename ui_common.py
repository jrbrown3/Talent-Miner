"""Shared Streamlit helpers used across pages.

Kept separate from ``core`` because everything here imports streamlit and is
purely about presentation / session wiring.
"""
from __future__ import annotations

import os
import sys

# Make ``core`` importable regardless of which page Streamlit launches.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import streamlit.components.v1 as _components

from core import config as cfgmod
from core import clustering, providers, roi, scoring, storage
from core.models import Opportunity

QUADRANT_COLORS = {
    "Quick Win": "#16a34a",
    "Big Bet": "#2563eb",
    "Fill-In": "#d97706",
    "Money Pit": "#dc2626",
}

PATTERN_BADGE = {
    "automation": ("Automation", "#7c3aed"),
    "augmentation": ("Augmentation", "#0891b2"),
}


# ---------------------------------------------------------------------------
# Theming (light / dark)
# ---------------------------------------------------------------------------

LIGHT = {
    "bg": "#f5f7fa", "bg2": "#ffffff", "card": "#ffffff",
    "text": "#1f2937", "muted": "#6b7280", "border": "#e5e7eb",
    "primary": "#4f46e5", "primary2": "#7c3aed", "input": "#ffffff",
    "chart_text": "#475569", "chart_grid": "#e5e7eb", "shadow": "rgba(0,0,0,0.06)",
}
DARK = {
    "bg": "#0f172a", "bg2": "#111827", "card": "#1e293b",
    "text": "#e2e8f0", "muted": "#94a3b8", "border": "#334155",
    "primary": "#818cf8", "primary2": "#a78bfa", "input": "#1e293b",
    "chart_text": "#cbd5e1", "chart_grid": "#334155", "shadow": "rgba(0,0,0,0.4)",
}

# A modern faceted-gem mark — "mining" gems of talent. White facets read on the
# gradient tile in both light and dark themes.
LOGO_SVG = """
<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" aria-label="Talent Miner logo">
  <path d="M16 3.5 L4.5 12 L16 12 Z" fill="#ffffff" fill-opacity="0.62"/>
  <path d="M16 3.5 L16 12 L27.5 12 Z" fill="#ffffff" fill-opacity="0.82"/>
  <path d="M4.5 12 L16 12 L16 28.5 Z" fill="#ffffff" fill-opacity="0.96"/>
  <path d="M16 12 L27.5 12 L16 28.5 Z" fill="#ffffff" fill-opacity="0.74"/>
  <circle cx="23.5" cy="7" r="1.5" fill="#ffffff"/>
  <circle cx="27" cy="10" r="0.9" fill="#ffffff" fill-opacity="0.8"/>
</svg>
"""

# Static stylesheet that references the CSS variables set per-theme below.
_STATIC_CSS = """
<style>
/* ---- hide the auto-generated Streamlit pages nav ---- */
[data-testid="stSidebarNav"] { display: none !important; }

/* ---- app background ---- */
.stApp { background: var(--tm-bg); color: var(--tm-text); }
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--tm-bg); }

/* ---- remove top whitespace ---- */
[data-testid="stHeader"] { display: none !important; }
.block-container { padding-top: 1.5rem !important; }
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
section[data-testid="stSidebar"] > div:first-child > div:first-child { padding-top: 0 !important; }
[data-testid="stSidebarCollapseButton"] { height: 0 !important; min-height: 0 !important; padding: 0 !important; margin: 0 !important; overflow: hidden !important; }
[data-testid="stSidebarHeader"] { height: 0 !important; min-height: 0 !important; padding: 0 !important; margin: 0 !important; overflow: hidden !important; }

/* ---- sidebar ---- */
section[data-testid="stSidebar"] {
  background: var(--tm-bg2);
  border-right: 1px solid var(--tm-border);
}
/* all text inside the sidebar inherits the theme text colour */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] [data-testid="stMetricValue"],
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] {
  color: var(--tm-text) !important;
}
/* page_link items */
section[data-testid="stSidebar"] [data-testid="stPageLink"] span,
section[data-testid="stSidebar"] [data-testid="stPageLink"] p {
  color: var(--tm-text) !important;
}

/* ---- metrics ---- */
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
  color: var(--tm-text) !important;
}

/* ---- bordered containers -> themed cards ---- */
[data-testid="stVerticalBlockBorderWrapper"] > div {
  background: var(--tm-card) !important;
  border: 1px solid var(--tm-border) !important;
  border-radius: 14px !important;
  box-shadow: 0 4px 12px var(--tm-shadow) !important;
  transition: box-shadow 0.15s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover > div {
  box-shadow: 0 6px 18px var(--tm-shadow) !important;
}

/* ---- form controls ---- */
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] {
  background: var(--tm-input) !important;
  color: var(--tm-text) !important;
  border-color: var(--tm-border) !important;
}
[data-testid="stFileUploaderDropzone"] { background: var(--tm-bg2) !important; }

/* ---- buttons (primary and secondary) ----
   Covers every button variant so none falls back to the light base theme and
   renders as a white tile in dark mode (file-uploader "Browse files", the
   Settings popover trigger, form submit buttons, etc.). */
.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button,
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stPopover"] button,
[data-testid="stBaseButton-secondary"] {
  border: 1px solid var(--tm-border) !important;
  background: var(--tm-card) !important;
  color: var(--tm-text) !important;
  transition: background 0.15s, border-color 0.15s;
}
/* button labels inherit the (themed) button colour rather than the main-area
   prose colour, so they stay legible on every button background */
.stButton > button [data-testid="stMarkdownContainer"] p,
.stDownloadButton > button [data-testid="stMarkdownContainer"] p,
[data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"] p,
[data-testid="stPopover"] button [data-testid="stMarkdownContainer"] p {
  color: inherit !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover,
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stPopover"] button:hover {
  border-color: var(--tm-primary) !important;
  background: var(--tm-bg) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: var(--tm-primary) !important;
  border-color: var(--tm-primary) !important;
  color: #ffffff !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--tm-primary2) !important;
  border-color: var(--tm-primary2) !important;
}

/* ---- download buttons ---- */
.stDownloadButton > button {
  border: 1px solid var(--tm-border) !important;
  background: var(--tm-card) !important;
  color: var(--tm-text) !important;
}

/* ---- Use Case Feedback: upvote / downvote buttons ----
   Targeted via Streamlit's per-key class (st-key-<key>). The arrow glyph inherits
   the button colour, so colouring the button colours the arrow: green for up, red
   for down, with a tinted background on hover. */
[class*="st-key-fb_up_"] button,
[class*="st-key-fb_down_"] button {
  border-radius: 10px !important;
  background: var(--tm-bg) !important;
  font-size: 1.15rem !important;
  font-weight: 700 !important;
  line-height: 1 !important;
  /* keep the buttons compact so they don't stretch on wide/full-screen layouts */
  max-width: 2.8rem !important;
  min-width: 2.2rem !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
}
/* group the pair toward the centre: up hugs the right edge of its half,
   down hugs the left edge of its half, so they sit together regardless of width */
[class*="st-key-fb_up_"] button {
  color: #16a34a !important;
  margin-left: auto !important;
  margin-right: 0 !important;
}
[class*="st-key-fb_down_"] button {
  color: #dc2626 !important;
  margin-left: 0 !important;
  margin-right: auto !important;
}
[class*="st-key-fb_up_"] button:hover {
  border-color: #16a34a !important;
  background: rgba(22, 163, 74, 0.14) !important;
}
[class*="st-key-fb_down_"] button:hover {
  border-color: #dc2626 !important;
  background: rgba(220, 38, 38, 0.14) !important;
}

/* ---- expanders ---- */
[data-testid="stExpander"] {
  border: 1px solid var(--tm-border) !important;
  border-radius: 8px !important;
  background: var(--tm-card) !important;
}
[data-testid="stExpander"] summary { color: var(--tm-text) !important; }

/* ---- radio / checkbox / toggle ---- */
.stRadio label, .stRadio label p, .stRadio label span,
.stCheckbox label, .stCheckbox label p,
.stToggle label, .stToggle label p { color: var(--tm-text) !important; }

/* ---- select boxes ---- */
[data-baseweb="select"] span { color: var(--tm-text) !important; }

/* ---- main-area text colour (dark-mode legibility) ----
   Streamlit's base theme (config.toml) is light, so without these rules the body
   text, headings, widget labels and tab labels in the main area stay dark on the
   dark background. We colour text-bearing block elements from the theme variables
   and deliberately leave inline-coloured spans alone (badges and the ROI/RICE
   numbers carry their own inline colour). No !important here, so those inline
   colours still win over these rules. */
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] p,
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] li,
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] h1,
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] h2,
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] h3,
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] h4,
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] h5,
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] h6,
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] strong,
[data-testid="stMain"] [data-testid="stHeading"],
[data-testid="stMain"] [data-testid="stWidgetLabel"],
[data-testid="stMain"] [data-testid="stWidgetLabel"] p,
[data-testid="stMain"] button[data-baseweb="tab"] {
  color: var(--tm-text);
}
/* captions read as secondary text in both themes */
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] p {
  color: var(--tm-muted);
}
/* file-uploader dropzone sits on the themed (dark) background, so its
   "Drag and drop" instructions need the theme text colour too */
[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small,
[data-testid="stFileUploaderDropzoneInstructions"] div {
  color: var(--tm-text);
}
/* slider value bubble and min/max tick labels */
[data-testid="stMain"] [data-testid="stSliderThumbValue"],
[data-testid="stMain"] [data-testid="stSliderTickBar"],
[data-testid="stMain"] [data-testid="stSliderTickBar"] div {
  color: var(--tm-text);
}

/* ---- header ---- */
.tm-header { display: flex; align-items: center; gap: 14px; padding: 2px 0 0; }
.tm-logo {
  width: 48px; height: 48px; border-radius: 14px; flex: 0 0 auto;
  background: linear-gradient(135deg, var(--tm-primary), var(--tm-primary2));
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 8px 22px -6px rgba(99,102,241,0.55);
}
.tm-logo svg { width: 30px; height: 30px; display: block; }
.tm-title {
  font-size: 1.7rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.05;
  background: linear-gradient(92deg, var(--tm-primary), var(--tm-primary2));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.tm-sub { color: var(--tm-muted); font-size: 0.9rem; margin-top: 2px; }
.tm-divider { height: 1px; background: var(--tm-border); border: 0; margin: 12px 0 6px; }

/* ---- processing indicator ----
   Replace Streamlit's animated "running man / cyclist" status icon (top-right
   while the app is busy) with a simple circular spinner. */
[data-testid="stStatusWidgetRunningIcon"] {
  width: 1.15rem !important;
  height: 1.15rem !important;
  box-sizing: border-box;
  border: 2px solid var(--tm-border);
  border-top-color: var(--tm-primary);
  border-radius: 50%;
  animation: tm-spin 0.7s linear infinite;
}
/* hide the inner running-man glyph/image so only the circle shows */
[data-testid="stStatusWidgetRunningIcon"] > * { display: none !important; }
@keyframes tm-spin { to { transform: rotate(360deg); } }
</style>
"""


def init_theme_state() -> None:
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False
    else:
        # In a multipage app, Streamlit drops widget-backed session state when you
        # navigate to a new page, which would reset the dark-mode toggle. Re-binding
        # the key to itself here — before the toggle widget is instantiated in
        # render_sidebar() — keeps the chosen theme sticky across page switches.
        st.session_state["dark_mode"] = st.session_state["dark_mode"]


def apply_theme() -> None:
    """Inject the active theme's CSS. Reads ``session_state['dark_mode']``."""
    init_theme_state()
    p = DARK if st.session_state["dark_mode"] else LIGHT
    root = (
        f"--tm-bg:{p['bg']};--tm-bg2:{p['bg2']};--tm-card:{p['card']};"
        f"--tm-text:{p['text']};--tm-muted:{p['muted']};--tm-border:{p['border']};"
        f"--tm-primary:{p['primary']};--tm-primary2:{p['primary2']};--tm-input:{p['input']};"
        f"--tm-shadow:{p['shadow']};"
    )
    st.markdown(f"<style>:root{{{root}}}</style>{_STATIC_CSS}", unsafe_allow_html=True)


def chart_colors() -> dict:
    return DARK if st.session_state.get("dark_mode") else LIGHT


def _disable_enter_in_text_inputs() -> None:
    """Prevent the Enter key from triggering Streamlit reruns inside text inputs.

    Adds a capture-phase keydown listener on the parent document so we intercept
    the event before React's root-level handler (React 17+ attaches to the app
    root div, below document in the capture chain).  A guard flag ensures the
    listener is only wired once per browser session even though components.html
    re-executes on each Streamlit rerun.
    """
    _components.html("""
<script>
(function () {
  if (window.parent._tmEnterDisabled) return;
  window.parent._tmEnterDisabled = true;
  window.parent.document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter') return;
    var t = e.target;
    if (t && t.tagName === 'INPUT' && (t.type === 'text' || t.type === '')) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  }, true);
})();
</script>
""", height=0, scrolling=False)


def page_chrome(subtitle: str = "AI Opportunity Finder") -> None:
    """One call per page: apply theme CSS. Branding is rendered in the sidebar."""
    apply_theme()
    _disable_enter_in_text_inputs()


# ---------------------------------------------------------------------------
# Config / provider wiring
# ---------------------------------------------------------------------------

def get_config() -> dict:
    if "config" not in st.session_state:
        st.session_state["config"] = cfgmod.load_config()
    return st.session_state["config"]


def get_api_key(provider: str) -> str:
    session_keys = st.session_state.get("api_keys", {})
    return cfgmod.get_api_key(provider, session_keys.get(provider))


def build_active_provider():
    cfg = get_config()
    key = get_api_key(cfg.get("provider", "Demo (offline)"))
    return providers.build_provider(cfg, key)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(active_page: str = "") -> None:
    cfg = get_config()
    with st.sidebar:
        st.markdown(
            f"""
            <div class="tm-header">
              <div class="tm-logo">{LOGO_SVG}</div>
              <div>
                <div class="tm-title">Talent Miner</div>
                <div class="tm-sub">AI Opportunity Finder</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        st.page_link("app.py", label="Analyze", icon="🔍")
        st.page_link("pages/1_Manage_Use_Cases.py", label="Manage Use Cases", icon="🗂️")
        st.page_link("pages/7_Use_Case_Feedback.py", label="Use Case Feedback", icon="🗳️")
        st.page_link("pages/2_Roadmap_View.py", label="Roadmap View", icon="🗺️")
        st.page_link("pages/5_Business_View.py", label="Business View", icon="🏢")
        #st.page_link("pages/4_Use_Case.py", label="Use-case builder", icon="🛠️")
        st.page_link("pages/3_Settings.py", label="Settings", icon="⚙️")
        st.page_link("pages/6_About.py", label="About", icon="ℹ️")
        st.toggle("🌙 Dark", key="dark_mode", help="Switch between light and dark mode")

        st.divider()
        all_opps = storage.list_opportunities()
        approved = sum(1 for o in all_opps if o.status == "approved")
        pending = sum(1 for o in all_opps if o.status == "proposed")
        c1, c2 = st.columns(2)
        c1.metric("Approved", approved, help="Use cases approved for prioritization")
        c2.metric("Pending", pending, help="Use cases awaiting approval in Manage Use Cases")


# ---------------------------------------------------------------------------
# Opportunity rendering
# ---------------------------------------------------------------------------

def _badge(text: str, color: str) -> str:
    return (f"<span style='background:{color};color:white;padding:2px 8px;"
            f"border-radius:10px;font-size:0.72rem;font-weight:600;'>{text}</span>")


CONFIDENCE_COLORS = {"High": "#16a34a", "Medium": "#d97706", "Low": "#dc2626"}


def opportunity_header_html(opp: Opportunity) -> str:
    quad = scoring.quadrant(opp)
    pat_label, pat_color = PATTERN_BADGE.get(opp.ai_pattern, (opp.ai_pattern, "#64748b"))
    conf = scoring.confidence_label(getattr(opp, "confidence_pct", 70))
    badges = [
        _badge(opp.category, "#475569"),
        _badge(pat_label, pat_color),
        _badge(quad, QUADRANT_COLORS.get(quad, "#475569")),
        _badge(f"{conf} confidence", CONFIDENCE_COLORS.get(conf, "#475569")),
    ]
    reach = max(1, int(getattr(opp, "reach", 1) or 1))
    if reach > 1:
        badges.insert(0, _badge(f"👥 {reach} roles", "#4f46e5"))
    return " ".join(badges)


def render_evidence(opp: Opportunity) -> None:
    """Show grounded evidence quotes with verification markers."""
    ev = getattr(opp, "evidence", None) or []
    if not ev:
        return
    with st.expander(f"Evidence from the job description ({len(ev)})"):
        for e in ev:
            quote = e.get("quote", "") if isinstance(e, dict) else str(e)
            ok = bool(e.get("verified")) if isinstance(e, dict) else False
            mark = "✅" if ok else "⚠️"
            tip = "verified against the source text" if ok else "not found verbatim — review"
            st.markdown(f"{mark} *“{quote}”*  \n<span style='color:#94a3b8;font-size:0.8rem'>"
                        f"{tip}</span>", unsafe_allow_html=True)


def roi_caption(opp: Opportunity, cfg: dict) -> str:
    e = roi.estimate(opp, cfg)

    def _stat(icon: str, label: str, value: str, value_color: str = "var(--tm-text)") -> str:
        return (
            f"<div style='display:flex;flex-direction:column;padding:8px 14px;"
            f"background:var(--tm-bg);border:1px solid var(--tm-border);border-radius:8px;"
            f"min-width:80px;'>"
            f"<span style='font-size:0.67rem;font-weight:600;text-transform:uppercase;"
            f"letter-spacing:0.07em;color:var(--tm-muted);white-space:nowrap;'>{icon}&nbsp;{label}</span>"
            f"<span style='font-size:0.95rem;font-weight:700;color:{value_color};"
            f"margin-top:3px;white-space:nowrap;'>{value}</span>"
            f"</div>"
        )

    tiles = [
        _stat("💰", "Annual Value", f"{roi.fmt_money(e['annual_value'])}/yr", "#16a34a"),
        _stat("⏱", "Time Saved", roi.fmt_hours(e["annual_hours"])),
        _stat("🔧", "Build Cost", roi.fmt_money(e["impl_cost"])),
        _stat("↩", "Payback", roi.fmt_payback(e["payback_months"])),
    ]
    return (
        "<div style='display:flex;flex-wrap:wrap;gap:8px;margin:10px 0;'>"
        + "".join(tiles)
        + "</div>"
    )


def _metric_html(label: str, filled: int, total: int, value_label: str) -> str:
    dots = (
        f"<span style='color:var(--tm-primary);letter-spacing:1px;'>{'●' * filled}</span>"
        f"<span style='color:var(--tm-border);letter-spacing:1px;'>{'●' * (total - filled)}</span>"
    )
    return (
        f"<div style='padding:10px 14px;background:var(--tm-bg);border:1px solid var(--tm-border);"
        f"border-radius:10px;'>"
        f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.07em;color:var(--tm-muted);margin-bottom:4px;'>{label}</div>"
        f"<div style='font-size:0.95rem;line-height:1.2;'>{dots}</div>"
        f"<div style='font-size:0.78rem;color:var(--tm-muted);margin-top:3px;'>{value_label}</div>"
        f"</div>"
    )


def render_opportunity_card(opp: Opportunity, *, votable: bool = True,
                            show_source: bool = True, key_prefix: str = "",
                            members: list | None = None, deletable: bool = True) -> None:
    """Render a single opportunity (or collapsed theme) with optional voting.

    ``deletable`` controls the trash-can remove button in the vote column (only
    relevant when ``votable``); pages that are read/vote-only pass ``False``.
    """
    cfg = get_config()
    members = members if members is not None else getattr(opp, "_members", None)

    with st.container(border=True):
        if votable:
            # Lay the card out as a horizontal row with a FIXED-width vote box so it
            # stays compact instead of growing with the viewport (proportional
            # st.columns expand and leave whitespace on wide screens).
            row = st.container(horizontal=True, gap="medium", vertical_alignment="top")
            vote_col = row.container(width=104)
            content_col = row.container(width="stretch")

            with vote_col:
                vote_color = (
                    "#16a34a" if opp.net_votes > 0
                    else "#dc2626" if opp.net_votes < 0
                    else "#94a3b8"
                )
                # Score on top, then the up/down buttons side by side beneath it.
                st.markdown(
                    f"<div style='display:flex;flex-direction:column;align-items:center;"
                    f"justify-content:center;width:100%;text-align:center;padding:2px 0 6px;'>"
                    f"<div style='font-weight:700;font-size:1.3rem;color:{vote_color};line-height:1;'>"
                    f"{opp.net_votes}</div>"
                    f"<div style='font-size:0.65rem;color:#94a3b8;margin-top:3px;letter-spacing:0.02em;'>"
                    f"▲{opp.votes_up}&nbsp;▼{opp.votes_down}</div></div>",
                    unsafe_allow_html=True,
                )

                up_col, down_col = st.columns(2, gap="small")
                if up_col.button("▲", key=f"{key_prefix}up_{opp.id}",
                                 help="Upvote", use_container_width=True):
                    storage.vote(opp.id, +1)
                    st.rerun()
                if down_col.button("▼", key=f"{key_prefix}down_{opp.id}",
                                   help="Downvote", use_container_width=True):
                    storage.vote(opp.id, -1)
                    st.rerun()

                if deletable:
                    st.markdown(
                        "<div style='border-top:1px solid var(--tm-border);margin:12px 0 8px;'></div>",
                        unsafe_allow_html=True,
                    )

                    if st.button("🗑️", key=f"{key_prefix}del_{opp.id}",
                                 help="Remove", use_container_width=True):
                        if members and len(members) > 1:
                            storage.delete_opportunities([m.id for m in members])
                        else:
                            storage.delete_opportunity(opp.id)
                        st.rerun()

            content_ctx = content_col
        else:
            content_ctx = st.container()

        with content_ctx:
            st.markdown(f"#### {opp.title}")
            st.markdown(opportunity_header_html(opp), unsafe_allow_html=True)

            if opp.context:
                st.write(opp.context)

            rice = round(scoring.score(opp, cfg), 2)
            m1, m2, m3 = st.columns(3)
            m1.markdown(_metric_html("Impact", opp.impact, 5, f"{opp.impact} / 5"),
                        unsafe_allow_html=True)
            m2.markdown(_metric_html("Effort", opp.effort, 5, f"{opp.effort} / 5"),
                        unsafe_allow_html=True)
            m3.markdown(
                f"<div style='padding:10px 14px;background:var(--tm-bg);border:1px solid var(--tm-border);"
                f"border-radius:10px;'>"
                f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
                f"letter-spacing:0.07em;color:var(--tm-muted);margin-bottom:4px;'>RICE Score</div>"
                f"<div style='font-size:1.3rem;font-weight:700;color:var(--tm-primary);line-height:1.2;'>"
                f"{rice}</div>"
                f"<div style='font-size:0.78rem;color:var(--tm-muted);margin-top:3px;'>"
                f"reach × impact × conf / effort</div></div>",
                unsafe_allow_html=True,
            )

            st.markdown(roi_caption(opp, cfg), unsafe_allow_html=True)

            render_evidence(opp)

            if members and len(members) > 1:
                with st.expander(f"Appears in {len(members)} roles"):
                    for m in members:
                        st.markdown(
                            f"- {m.role_title or m.source_name} "
                            f"<span style='color:#94a3b8'>(I{m.impact}/E{m.effort})</span>",
                            unsafe_allow_html=True,
                        )

            if opp.impact_rationale or opp.effort_rationale:
                with st.expander("Scoring rationale"):
                    if opp.impact_rationale:
                        st.markdown(f"*Impact:* {opp.impact_rationale}")
                    if opp.effort_rationale:
                        st.markdown(f"*Effort:* {opp.effort_rationale}")
                    if opp.example_tools:
                        st.markdown("*Techniques/tools:* " + ", ".join(opp.example_tools))

            if show_source and opp.source_name and not (members and len(members) > 1):
                st.caption(
                    f"From: {opp.source_name}"
                    + (f" · {opp.role_title}" if opp.role_title else "")
                    + (f" · via {opp.provider}" if opp.provider else "")
                )
