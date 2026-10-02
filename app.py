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

# Ensure project root is at the head of sys.path to prevent cross-workspace import bleed
PROJECT_ROOT = Path(__file__).resolve().parent
_root_str = str(PROJECT_ROOT)
if _root_str in sys.path:
    sys.path.remove(_root_str)
sys.path.insert(0, _root_str)

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

# Theme and CSS — honors the sidebar Light/Dark switch (session-persisted;
# falls back to light until the toggle is first rendered)
from src.ui.theme import get_safesight_css, render_motion_bridge

css_payload = get_safesight_css(st.session_state.get("theme_mode", "light"))
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
.ops-kbd {
    display: inline-block;
    min-width: 14px;
    padding: 1px 5px;
    border: 1px solid var(--line);
    border-bottom-width: 2px;
    border-radius: 5px;
    background: var(--bg);
    color: var(--heading);
    font-family: monospace;
    font-size: 10.5px;
    font-weight: 700;
    text-align: center;
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

# Optional Auth Gate — themed operator login card (branded, keyboard accessible)
from src.config.runtime import load_runtime_config
from src.security.auth import is_auth_configured, verify_password
from src.ui.components import render_html

_runtime_cfg = load_runtime_config()
if is_auth_configured(_runtime_cfg.auth_required, _runtime_cfg.operator_password_sha256):
    if not st.session_state.get("authenticated"):
        render_html(
            """
            <div style="max-width:460px;margin:8vh auto 0;background:var(--panel);border:1px solid var(--line);
                        border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,0.08);padding:34px 32px;text-align:center;">
                <div style="background:var(--green-soft);color:var(--green);width:56px;height:56px;border-radius:14px;
                            display:grid;place-items:center;font-size:30px;margin:0 auto;" aria-hidden="true">🛡️</div>
                <h2 style="margin:14px 0 4px !important;">SAFE SIGHT <span style="color:var(--green);">AI</span></h2>
                <p style="margin:0 0 22px !important;font-size:12px;letter-spacing:1.6px;color:var(--muted);font-weight:700;">
                    OPERATOR SIGN-IN REQUIRED
                </p>
            </div>
            """
        )
        with st.container():
            _left, _center, _right = st.columns([1, 2, 1])
            with _center, st.form("login_form"):
                password = st.text_input("Operator Password", type="password")
                if st.form_submit_button("Log In", type="primary", use_container_width=True):
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
from src.ui.components import render_keyboard_shortcuts_script, render_sidebar_header
from src.ui.pages import evidence_log, image_analysis, live_feed, system_settings, video_file
from src.ui.pages import command_center as command_center
from src.ui.pages import camera_wall as camera_wall

# Consume pending hotkey navigation BEFORE the radio widget is instantiated.
# Hotkey buttons set `_pending_nav` then call `st.rerun()`; we consume it here
# so the radio widget picks it up cleanly as its default value.
_pending_nav = st.session_state.pop("_pending_nav", None)
if _pending_nav is not None:
    st.session_state["workspace_navigation"] = _pending_nav

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

    # Appearance: Light/Dark theme switch (X2) — persists for the session
    st.markdown('<div class="nav-section-label">Appearance</div>', unsafe_allow_html=True)
    dark_mode = st.toggle(
        "Dark mode",
        value=st.session_state.get("theme_mode", "light") == "dark",
        key="theme_mode_toggle",
        help="Switch the operations workspace between light and dark themes.",
    )
    desired_mode = "dark" if dark_mode else "light"
    if st.session_state.get("theme_mode", "light") != desired_mode:
        st.session_state["theme_mode"] = desired_mode
        st.rerun()

    # Keyboard shortcut cheat-sheet (U3): operators wear gloves — speed matters
    st.markdown('<div class="nav-section-label">Shortcuts</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:11.5px;color:var(--muted);line-height:1.9;">'
        '<span class="ops-kbd">1</span>–<span class="ops-kbd">5</span> Switch pages &nbsp;·&nbsp; '
        '<span class="ops-kbd">S</span> Start/stop camera<br>'
        '<span class="ops-kbd">?</span> Shortcut help &nbsp;·&nbsp; keys are ignored while typing'
        "</div>",
        unsafe_allow_html=True,
    )

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
            <span>Model: <strong>Custom PPE Neural Checkpoint</strong> · Trusted-checkpoint policy enforced</span>
        </div>
    </div>
    """
)


# Keyboard shortcuts (U3): hidden hotkey buttons clicked by the global keydown
# handler (render_keyboard_shortcuts_script). Clicking triggers a normal
# Streamlit rerun so session state is preserved. They sit below the footer and
# are hidden by the script; invalid presses are safely discarded.
@st.dialog("⌨️ Keyboard Shortcuts")
def _render_shortcuts_help() -> None:
    st.caption("Operators wear gloves — interaction speed matters. Keys are ignored while typing in an input.")
    st.markdown(
        """
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <tr><td style="padding:7px 10px;border-bottom:1px solid var(--line);width:90px;"><span class="ops-kbd">1</span> – <span class="ops-kbd">5</span></td><td style="padding:7px 10px;border-bottom:1px solid var(--line);">Switch workspace pages</td></tr>
            <tr><td style="padding:7px 10px;border-bottom:1px solid var(--line);"><span class="ops-kbd">S</span></td><td style="padding:7px 10px;border-bottom:1px solid var(--line);">Start / stop the live camera (Live Feed)</td></tr>
            <tr><td style="padding:7px 10px;"><span class="ops-kbd">?</span></td><td style="padding:7px 10px;">Open this cheat-sheet</td></tr>
        </table>
        """,
        unsafe_allow_html=True,
    )


_hot_nav, _hot_cam, _hot_help = st.columns(3)
with _hot_nav:
    if st.button("__hk_nav_1", key="hk_nav_1"):
        st.session_state["_pending_nav"] = "Live operations"
        st.rerun()
    if st.button("__hk_nav_2", key="hk_nav_2"):
        st.session_state["_pending_nav"] = "Review footage"
        st.rerun()
    if st.button("__hk_nav_3", key="hk_nav_3"):
        st.session_state["_pending_nav"] = "Analyze image"
        st.rerun()
    if st.button("__hk_nav_4", key="hk_nav_4"):
        st.session_state["_pending_nav"] = "Incident evidence"
        st.rerun()
    if st.button("__hk_nav_5", key="hk_nav_5"):
        st.session_state["_pending_nav"] = "System policy"
        st.rerun()
with _hot_cam:
    if active_page == "Live Feed" and st.button("__hk_cam", key="hk_cam"):
        if ctx.camera_manager.is_running:
            ctx.camera_manager.stop()
            st.session_state["cam_stream_active"] = False
        else:
            dev_id = st.session_state.get("opencv_device_idx", 0)
            ctx.camera_manager.start(device_index=dev_id, pipeline_ref=ctx.pipeline)
            st.session_state["cam_stream_active"] = True
        st.rerun()
with _hot_help:
    if st.button("__hk_help", key="hk_help"):
        _render_shortcuts_help()

render_keyboard_shortcuts_script(list(NAV_PAGES.values()))
