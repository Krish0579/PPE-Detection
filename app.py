"""
===============================================================================
 SAFE SIGHT AI · Industrial Shopfloor Computer Vision Platform
===============================================================================
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure workspace cache directories before importing ML libraries
CACHE_DIR = PROJECT_ROOT / ".cache" / "ultralytics"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
MPL_CACHE_DIR = PROJECT_ROOT / ".cache" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

os.environ["YOLO_CONFIG_DIR"] = str(CACHE_DIR)
os.environ["ULTRALYTICS_CONFIG_DIR"] = str(CACHE_DIR)
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

# Logging Bootstrap
from src.observability.logging_setup import configure_logging

configure_logging()

# Streamlit Config
st.set_page_config(
    page_title="SAFE SIGHT AI · Industrial Vision Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Theme and CSS
from src.ui.theme import get_safesight_css, render_motion_bridge

css_payload = get_safesight_css("light")
app_ui_css = """
<style>
/* App-level UX polish. Keep this local to app.py so the page shell can evolve
   independently from the reusable component library. */
.stApp {
    font-size: 17px !important;
}
.stApp p,
.stApp li,
.stApp label,
.stApp [data-testid="stCaptionContainer"] {
    font-size: 16px !important;
}
.stApp h1 { font-size: 32px !important; }
.stApp h2 { font-size: 26px !important; }
.stApp h3 { font-size: 21px !important; }
.stApp h4 { font-size: 18px !important; }
.stApp button,
.stApp input,
.stApp textarea,
.stApp [data-baseweb="select"] {
    font-size: 15px !important;
}
.app-context-strip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin: -8px 0 18px;
    padding: 9px 12px;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: color-mix(in srgb, var(--panel) 94%, var(--green-soft));
    color: var(--secondary);
    font-size: 11px;
}
.app-context-main, .app-context-meta {
    display: flex;
    align-items: center;
    gap: 9px;
    min-width: 0;
}
.app-context-main strong { color: var(--heading); font-size: 12px; }
.app-context-divider { color: var(--line); }
.app-context-meta { justify-content: flex-end; flex-wrap: wrap; }
.app-context-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 8px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--bg);
    white-space: nowrap;
}
.sidebar-section-label {
    margin: 4px 0 7px;
    color: var(--muted);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}
@media (max-width: 768px) {
    .app-context-strip { align-items: flex-start; flex-direction: column; }
    .app-context-meta { justify-content: flex-start; }
}
</style>
"""
if hasattr(st, "html"):
    st.html(css_payload)
    st.html(app_ui_css)
else:
    st.markdown(css_payload, unsafe_allow_html=True)
    st.markdown(app_ui_css, unsafe_allow_html=True)

render_motion_bridge()

# Automatic Secure Context bridge: redirect 0.0.0.0 to localhost for browser webcam access
import streamlit.components.v1 as st_components

st_components.html(
    """
    <script>
    try {
        if (window.parent && window.parent.location.hostname === "0.0.0.0") {
            window.parent.location.hostname = "localhost";
        } else if (window.location.hostname === "0.0.0.0") {
            window.location.hostname = "localhost";
        }
    } catch(e) {}
    </script>
    """,
    height=0,
    width=0,
)

# Optional Auth Gate
from src.config.runtime import load_runtime_config
from src.security.auth import is_auth_configured, verify_password

_runtime_cfg = load_runtime_config()
if is_auth_configured(_runtime_cfg.auth_required, _runtime_cfg.operator_password_sha256):
    if not st.session_state.get("authenticated"):
        st.title("🛡️ SAFE SIGHT AI Login")
        with st.form("login_form"):
            password = st.text_input("Operator Password", type="password")
            if st.form_submit_button("Log In"):
                if verify_password(password, _runtime_cfg.operator_password_sha256):
                    st.session_state["authenticated"] = True
                    st.session_state["user_role"] = "operator"
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        st.stop()

# Build Context
from src.ui.app_context import build_context

ctx = build_context()

# UI Components and Navigation
from src.ui.components import render_html, render_sidebar_header
from src.ui.pages import evidence_log, image_analysis, live_feed, system_settings, video_file

with st.sidebar:
    render_sidebar_header()

    NAV_PAGES = {
        "Live operations": "Live Feed",
        "Review footage": "Video File",
        "Analyze image": "Image Analysis",
        "Incident evidence": "Evidence Log",
        "System policy": "System Settings",
    }
    NAV_LABELS = {
        "Live operations": "📹  Live Feed",
        "Review footage": "🎬  Video File",
        "Analyze image": "🖼️  Image Analysis",
        "Incident evidence": "📋  Evidence Log",
        "System policy": "⚙️  System Settings",
    }
    active_nav = st.radio(
        "Navigation",
        list(NAV_PAGES.keys()),
        format_func=lambda k: NAV_LABELS.get(k, k),
        key="workspace_navigation",
        label_visibility="collapsed",
    )
    active_page = NAV_PAGES.get(active_nav, "Live Feed")

# Stop hardware camera when navigating away from Live Feed
if active_page != "Live Feed" and ctx.camera_manager.is_running:
    ctx.camera_manager.stop()
    st.session_state.cam_stream_active = False

if ctx.load_error:
    st.error(f"⚠️ Model loading error: {ctx.load_error}")
    st.info("System running in demo mode without AI inference.")

# Page Routing
_PAGES = {
    "Live Feed": live_feed.render,
    "Video File": video_file.render,
    "Image Analysis": image_analysis.render,
    "Evidence Log": evidence_log.render,
    "System Settings": system_settings.render,
}
_PAGES[active_page](ctx)

# Footer
render_html(
    """
    <div style="margin-top: 50px; padding: 20px 0; border-top: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--muted);">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="color: var(--green); font-weight: 700;">SAFE SIGHT AI</span>
            <span>·</span>
            <span>Shopfloor Vision & Safety Intelligence Platform</span>
        </div>
        <div>
            <span>Model: <strong>Custom PPE Neural Checkpoint (11 Classes)</strong> · Production Certified</span>
        </div>
    </div>
    """
)
