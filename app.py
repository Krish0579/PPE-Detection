"""
===============================================================================
 SAFE SIGHT AI · Safety Workspace Computer Vision Platform
===============================================================================
"""

from __future__ import annotations

import os
import sys
import time
from html import escape
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
    page_title="SAFE SIGHT AI · Safety Vision Workspace",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Theme CSS. Dark mode is the control-room default; operators can switch to a
# low-glare light palette from the navigation rail and the choice persists.
from src.ui.theme import get_safesight_css

if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "dark"
css_payload = get_safesight_css(st.session_state.theme_mode)
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

# Automatic secure-context bridge: redirect 0.0.0.0 to localhost for browser
# webcam access. Streamlit's current HTML primitive avoids the deprecated
# components.v1.html warning while retaining a fallback for older releases.
_secure_context_script = """
<script>
try {
    if (window.parent && window.parent.location.hostname === "0.0.0.0") {
        window.parent.location.hostname = "localhost";
    } else if (window.location.hostname === "0.0.0.0") {
        window.location.hostname = "localhost";
    }
} catch(e) {}
</script>
"""
import streamlit.components.v1 as st_components

st_components.html(_secure_context_script, height=0, width=0)

# Optional Auth Gate — themed operator login card (branded, keyboard accessible)
from src.config.runtime import load_runtime_config
from src.security.auth import (
    effective_role,
    is_auth_configured,
    lockout_remaining,
    register_login_failure,
    register_login_success,
    resolve_role,
    session_expired,
    session_idle_expired,
)
from src.ui.components import render_html

_runtime_cfg = load_runtime_config()
_auth_enabled = is_auth_configured(_runtime_cfg.auth_required, _runtime_cfg.operator_password_sha256)
if _auth_enabled and st.session_state.get("authenticated"):
    _now = time.time()
    _authenticated_at = float(st.session_state.get("authenticated_at", _now))
    _last_seen_at = float(st.session_state.get("last_seen_at", _now))
    if session_expired(_authenticated_at, _now, _runtime_cfg.session_ttl_min * 60) or session_idle_expired(
        _last_seen_at, _now, _runtime_cfg.session_idle_min * 60
    ):
        st.session_state["authenticated"] = False
        st.session_state.pop("user_role", None)
        st.session_state.pop("authenticated_at", None)
        st.session_state.pop("last_seen_at", None)
        st.session_state["auth_expired_notice"] = True
    else:
        st.session_state["last_seen_at"] = _now

if _auth_enabled and not st.session_state.get("authenticated"):
    if st.session_state.pop("auth_expired_notice", False):
        st.warning("Your operator session expired. Sign in again to continue.")
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
            _lockout = lockout_remaining()
            if _lockout > 0:
                st.error(f"Too many failed attempts. Try again in {max(1, int(_lockout + 0.99))} seconds.")
            if st.form_submit_button("Sign in", type="primary", use_container_width=True, disabled=_lockout > 0):
                role = resolve_role(
                    password,
                    operator_sha256=_runtime_cfg.operator_password_sha256,
                    supervisor_sha256=_runtime_cfg.supervisor_password_sha256,
                    admin_sha256=_runtime_cfg.admin_password_sha256,
                )
                if role:
                    register_login_success()
                    _now = time.time()
                    st.session_state["authenticated"] = True
                    st.session_state["user_role"] = effective_role(
                        role,
                        admin_configured=bool(_runtime_cfg.admin_password_sha256),
                        supervisor_configured=bool(_runtime_cfg.supervisor_password_sha256),
                    )
                    st.session_state["authenticated_at"] = _now
                    st.session_state["last_seen_at"] = _now
                    st.rerun()
                else:
                    _new_lockout = register_login_failure()
                    if _new_lockout:
                        st.error(f"Invalid credentials. Sign-in locked for {int(_new_lockout)} seconds.")
                    else:
                        st.error("Invalid credentials.")
    st.stop()

# Build Context
from src.ui.app_context import build_context

ctx = build_context()

# UI Components and Navigation
from src.ui.components import (
    render_sidebar_header,
    render_workspace_context,
)
from src.ui.navigation import NAV_LABELS, NAV_PAGES, navigation_keys
from src.ui.pages import (
    command_center,
    evidence_log,
    image_analysis,
    incidents_page,
    live_feed,
    reports_page,
    system_health,
    system_settings,
    video_file,
)

with st.sidebar:
    render_sidebar_header()

    _theme_selection = st.selectbox(
        "Display theme",
        options=("dark", "light"),
        index=0 if st.session_state.theme_mode == "dark" else 1,
        format_func=lambda value: "Dark control room" if value == "dark" else "Light review",
        key="display_theme_selection",
        help="Choose a display palette for this operator session.",
    )
    if _theme_selection != st.session_state.theme_mode:
        st.session_state.theme_mode = _theme_selection
        st.rerun()

    active_nav = st.radio(
        "Navigation",
        navigation_keys(),
        format_func=lambda k: NAV_LABELS.get(k, k),
        key="workspace_navigation",
        label_visibility="collapsed",
    )
    active_page = NAV_PAGES.get(active_nav, "Command Center")

# Stop hardware camera when navigating away from Live Feed
if active_page != "Live Feed" and ctx.camera_manager.is_running:
    ctx.camera_manager.stop()
    st.session_state.cam_stream_active = False

# The shell reads the same measured status model as System Health so the
# persistent context strip can never drift into a fabricated "live" state.
from src.ui.status import overall_status

_workspace_components = system_health.collect_status(ctx)
_workspace_verdict = overall_status(_workspace_components)
_snapshot = ctx.state.snapshot_ui()
_capture_label = "Capture standby"
if ctx.camera_manager.is_running:
    _capture_label = "Simulated demo feed" if getattr(ctx.camera_manager, "is_simulated", False) else "Live capture"
elif ctx.load_error:
    _capture_label = "Inference unavailable"

with st.sidebar:
    if _auth_enabled and st.button("Sign out", key="sign_out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state.pop("user_role", None)
        st.session_state.pop("authenticated_at", None)
        st.session_state.pop("last_seen_at", None)
        st.rerun()

render_workspace_context(
    status_label=_workspace_verdict.label,
    status_class=_workspace_verdict.badge_class,
    model_name=ctx.model_name,
    device=ctx.device,
    capture_label=_capture_label,
    evidence_label=f"{int(_snapshot.get('snapshots_count', 0) or 0)} captures",
)

if ctx.load_error:
    st.error(f"⚠️ Model loading error: {ctx.load_error}")
    st.info("Inference is unavailable. The workspace remains usable for configuration and evidence review.")

# Page Routing
_PAGES = {
    "Command Center": command_center.render,
    "Live Feed": live_feed.render,
    "Incidents": incidents_page.render,
    "Reports": reports_page.render,
    "Video File": video_file.render,
    "Image Analysis": image_analysis.render,
    "Evidence Log": evidence_log.render,
    "System Settings": system_settings.render,
    "System Health": system_health.render,
}
_PAGES[active_page](ctx)

# Footer
render_html(
    f"""
    <footer class="safesight-footer">
        <div>
            <strong>SAFE SIGHT AI</strong>
            <span>On-premise PPE decision support</span>
        </div>
        <div>
            <span>Checkpoint: <strong>{escape(ctx.model_name or "Unavailable")}</strong></span>
            <span aria-hidden="true"> · </span>
            <span>Compute: <strong>{escape(ctx.device or "Unknown")}</strong></span>
        </div>
    </footer>
    """
)
