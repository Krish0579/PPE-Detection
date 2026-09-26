"""SAFE SIGHT AI UI theme system.

Replicates the exact industrial styling, typography, cards, sparklines,
badges, and layout of the SAFE SIGHT AI platform with pleasant, crisp light theme.
"""
from __future__ import annotations

from src.config.settings import THEME_DARK, THEME_LIGHT


def get_safesight_css(theme_mode: str = "light") -> str:
    """Return complete SAFE SIGHT AI CSS stylesheet with pleasant light styling."""
    T = THEME_LIGHT if theme_mode == "light" else THEME_DARK
    is_light = theme_mode == "light"

    panel_shadow = "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)" if is_light else "0 2px 4px rgba(0,0,0,0.25)"
    metric_shadow = "0 1px 3px rgba(0,0,0,0.05)" if is_light else "none"

    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400..700;1,9..40,400..700&family=Manrope:wght@500;600;700;800&display=swap');

:root {{
    --bg: {T['bg']};
    --panel: {T['panel']};
    --sidebar: {T['sidebar']};
    --text: {T['text']};
    --heading: {T['heading']};
    --muted: {T['muted']};
    --secondary: {T['secondary']};
    --line: {T['line']};
    --green: {T['green']};
    --green-soft: {T['green_soft']};
    --red: {T['red']};
    --red-soft: {T['red_soft']};
    --amber: {T['amber']};
    --amber-soft: {T['amber_soft']};
    --blue: {T['blue']};
    --blue-soft: {T['blue_soft']};
    --hover: {T['hover']};
    --input: {T['input']};
    --border: {T['line']};
    --card-bg: {T['panel']};
    --text-secondary: {T['secondary']};
    --bg-hover: {T['hover']};
}}

/* Completely hide Streamlit's default top header bar, deploy button, toolbar, and decorations */
header,
[data-testid="stHeader"],
[data-testid="stAppHeader"],
.stAppHeader,
div[data-testid="stDecoration"],
div[data-testid="stToolbar"],
.stDeployButton,
#MainMenu,
footer,
div[class*="stAppHeader"],
div[class*="stDecoration"] {{
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    width: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
    top: -9999px !important;
}}

/* Root layout & scroll hierarchy: Streamlit 1.62 */
html, body {{
    height: 100% !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
}}

.stApp {{
    height: 100% !important;
    overflow: hidden !important;
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    font-size: 15px !important;
}}

[data-testid="stAppViewContainer"] {{
    height: 100% !important;
    overflow: hidden !important;
}}

[data-testid="stMain"],
.stMain,
section.main {{
    height: 100dvh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    scroll-behavior: smooth !important;
    -webkit-overflow-scrolling: touch !important;
}}

/* Sleek custom industrial scrollbar */
[data-testid="stMain"]::-webkit-scrollbar,
.stMain::-webkit-scrollbar,
section.main::-webkit-scrollbar,
aside[data-testid="stSidebar"]::-webkit-scrollbar {{
    width: 6px !important;
    height: 6px !important;
}}

[data-testid="stMain"]::-webkit-scrollbar-track,
.stMain::-webkit-scrollbar-track,
section.main::-webkit-scrollbar-track,
aside[data-testid="stSidebar"]::-webkit-scrollbar-track {{
    background: transparent !important;
}}

[data-testid="stMain"]::-webkit-scrollbar-thumb,
.stMain::-webkit-scrollbar-thumb,
section.main::-webkit-scrollbar-thumb,
aside[data-testid="stSidebar"]::-webkit-scrollbar-thumb {{
    background: #cbd5e1 !important;
    border-radius: 4px !important;
}}

[data-testid="stMain"]::-webkit-scrollbar-thumb:hover,
.stMain::-webkit-scrollbar-thumb:hover,
section.main::-webkit-scrollbar-thumb:hover,
aside[data-testid="stSidebar"]::-webkit-scrollbar-thumb:hover {{
    background: var(--green) !important;
}}

.block-container {{
    padding-top: 1.2rem !important;
    padding-bottom: 3rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1640px !important;
}}

h1, h2, h3, h4 {{
    color: var(--heading) !important;
    font-family: 'Manrope', 'DM Sans', sans-serif !important;
    font-weight: 750 !important;
    letter-spacing: -0.5px !important;
}}

h1 {{ font-size: 28px !important; }}
h2 {{ font-size: 22px !important; }}
h3 {{ font-size: 18px !important; }}
h4 {{ font-size: 15px !important; }}

/* Top Brand & Workspace Bar */
.safesight-topbar {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 14px 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 22px;
    box-shadow: {panel_shadow};
}}

.safesight-brand {{
    display: flex;
    align-items: center;
    gap: 14px;
}}

.safesight-brand-logo {{
    background: var(--green-soft);
    color: var(--green);
    width: 44px;
    height: 44px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 23px;
    font-weight: 800;
}}

.safesight-brand-title strong {{
    font-size: 19px;
    letter-spacing: -0.5px;
    font-weight: 800;
    color: var(--heading);
}}

.safesight-brand-title strong span {{
    color: var(--green);
}}

.safesight-brand-title small {{
    display: block;
    font-size: 10px;
    letter-spacing: 1.6px;
    color: var(--muted);
    font-weight: 700;
    margin-top: 2px;
}}

.workspace-pill {{
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 8px 16px;
}}

.workspace-pill strong {{
    display: block;
    font-size: 13.5px;
    color: var(--heading);
}}

.workspace-pill small {{
    font-size: 11px;
    color: var(--muted);
}}

/* Status Dot Indicator with Pulse */
@keyframes pulse-dot {{
    0% {{ box-shadow: 0 0 0 0 rgba(8, 137, 108, 0.5); }}
    70% {{ box-shadow: 0 0 0 6px rgba(8, 137, 108, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(8, 137, 108, 0); }}
}}

@keyframes pulse-dot-red {{
    0% {{ box-shadow: 0 0 0 0 rgba(217, 101, 101, 0.6); }}
    70% {{ box-shadow: 0 0 0 6px rgba(217, 101, 101, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(217, 101, 101, 0); }}
}}

.status-dot {{
    width: 7px;
    height: 7px;
    display: inline-block;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 0 2px var(--green-soft);
    animation: pulse-dot 2.2s infinite ease-in-out;
}}

.status-dot.red {{
    background: var(--red);
    box-shadow: 0 0 0 2px var(--red-soft);
    animation: pulse-dot-red 1.8s infinite ease-in-out;
}}

.status-dot.amber {{
    background: var(--amber);
    box-shadow: 0 0 0 2px var(--amber-soft);
}}

/* Card Hover Micro-interactions */
.metric-card {{
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}}
.metric-card:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px rgba(8, 137, 108, 0.09) !important;
}}

.panel {{
    transition: box-shadow 0.2s ease, border-color 0.2s ease !important;
}}
.panel:hover {{
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06) !important;
}}

/* SAFE SIGHT Panels */
.panel {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 9px;
    box-shadow: {panel_shadow};
    overflow: hidden;
    margin-bottom: 20px;
}}

.panel-heading {{
    padding: 14px 20px;
    border-bottom: 1px solid var(--line);
    display: flex;
    align-items: center;
    justify-content: space-between;
}}

.panel-heading h3 {{
    font-size: 17px !important;
    font-weight: 700 !important;
    color: var(--heading) !important;
    margin: 0 !important;
}}

.panel-heading p {{
    font-size: 12px !important;
    color: var(--muted) !important;
    margin: 3px 0 0 0 !important;
}}

.panel-body {{
    padding: 20px 22px;
}}

/* SAFE SIGHT Metric Cards */
.metrics-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 20px;
}}

.metric-card {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 18px 20px 14px;
    position: relative;
    box-shadow: {metric_shadow};
}}

.metric-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 13px;
    color: var(--secondary);
    font-weight: 600;
}}

.metric-icon {{
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 17px;
}}

.metric-icon.green {{ background: var(--green-soft); color: var(--green); }}
.metric-icon.red {{ background: var(--red-soft); color: var(--red); }}
.metric-icon.amber {{ background: var(--amber-soft); color: var(--amber); }}
.metric-icon.blue {{ background: var(--blue-soft); color: var(--blue); }}

.metric-main {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-top: 8px;
}}

.metric-main strong {{
    font-family: 'Manrope', sans-serif;
    font-size: 38px;
    font-weight: 750;
    color: var(--heading);
    letter-spacing: -1px;
}}

.metric-main small {{
    font-size: 22px;
    font-weight: 600;
    color: var(--muted);
}}

.metric-foot {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    color: var(--muted);
    margin-top: 12px;
    border-top: 1px solid var(--line);
    padding-top: 10px;
}}

.metric-change {{
    font-weight: 600;
    font-size: 11.5px;
}}

.metric-change.green {{ color: var(--green); }}
.metric-change.red {{ color: var(--red); }}

/* Badges */
.badge {{
    font-size: 11px;
    line-height: 18px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 5px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    text-transform: uppercase;
}}

.badge-green {{ background: var(--green-soft); color: var(--green); }}
.badge-red {{ background: var(--red-soft); color: var(--red); }}
.badge-amber {{ background: var(--amber-soft); color: var(--amber); }}
.badge-blue {{ background: var(--blue-soft); color: var(--blue); }}
.badge-slate {{ background: var(--hover); color: var(--muted); }}

/* Progress Tracks */
.progress-track {{
    height: 5px;
    background: var(--bg);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 6px;
    border: 1px solid var(--line);
}}

.progress-track > div {{
    height: 100%;
    border-radius: 4px;
    background: var(--green);
    transition: width 0.3s ease;
}}

.progress-track.red > div {{ background: var(--red); }}
.progress-track.amber > div {{ background: var(--amber); }}

/* PPE Icon Badge Container */
.ppe-icon-badge {{
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: var(--bg);
    border: 1px solid var(--line);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    flex-shrink: 0;
    transition: transform 0.15s ease;
}}
.ppe-row:hover .ppe-icon-badge {{
    transform: scale(1.06);
    border-color: var(--green);
}}

/* Worker Card Grid */
.workers-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    margin-top: 16px;
}}

.worker-card {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 9px;
    padding: 16px;
    box-shadow: {panel_shadow};
    transition: transform 0.15s ease, border-color 0.15s ease;
}}

.worker-card:hover {{
    transform: translateY(-2px);
    border-color: var(--green);
}}

.worker-card-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}}

.worker-card-ppe {{
    display: flex;
    gap: 12px;
    margin: 14px 0;
    font-size: 11px;
}}

.worker-card-foot {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11px;
    color: var(--muted);
    border-top: 1px solid var(--line);
    padding-top: 10px;
}}

/* Zone Cards Grid */
.zone-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
    gap: 16px;
}}

.zone-card {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 9px;
    padding: 16px;
    box-shadow: {panel_shadow};
}}

/* Alerts Grid */
.alert-card {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-top: 3px solid var(--amber);
    border-radius: 9px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: {panel_shadow};
}}

.alert-card.high {{ border-top-color: var(--red); }}
.alert-card.low {{ border-top-color: var(--muted); }}

/* Sidebar Shell & Industrial Nav Styling */
[data-testid="stSidebar"],
section[data-testid="stSidebar"],
aside[data-testid="stSidebar"] {{
    background: var(--sidebar) !important;
    background-color: var(--sidebar) !important;
    border-right: 1px solid var(--line) !important;
    box-shadow: none !important;
    min-width: 320px !important;
    width: 320px !important;
    max-width: 340px !important;
}}

[data-testid="stSidebar"] > div:first-child,
section[data-testid="stSidebar"] > div:first-child {{
    background: transparent !important;
    border-right: none !important;
    padding-top: 0.6rem !important;
}}

[data-testid="stSidebar"] .stSidebarContent,
section[data-testid="stSidebar"] .stSidebarContent {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 16px 28px 16px !important;
    width: 100% !important;
    box-sizing: border-box !important;
}}

/* Clear any accidental emotion-cache borders or backgrounds */
[data-testid="stSidebar"] div[class*="st-emotion-cache"] {{
    border-right: none !important;
    box-shadow: none !important;
}}

/* Sidebar Radio Navigation */
[data-testid="stSidebar"] div[data-testid="stRadio"] {{
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    border: none !important;
    width: 100% !important;
    display: block !important;
}}

[data-testid="stSidebar"] div[data-testid="stRadio"] [data-testid="stWidgetLabel"] {{
    display: none !important;
}}

/* Radio Group: column flex spanning 100% full sidebar width */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] {{
    display: flex !important;
    flex-direction: column !important;
    gap: 6px !important;
    width: 100% !important;
    min-width: 100% !important;
    align-items: stretch !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    box-sizing: border-box !important;
}}

/* Transform each radio option label into a sleek, large enterprise nav button */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] [data-baseweb="radio"],
[data-testid="stSidebar"] [data-testid="stRadioOption"],
[data-testid="stSidebar"] div[data-testid="stRadio"] label {{
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-start !important;
    height: 52px !important;
    min-height: 52px !important;
    width: 100% !important;
    min-width: 100% !important;
    box-sizing: border-box !important;
    padding: 0 18px !important;
    border-radius: 10px !important;
    margin: 0 0 4px 0 !important;
    cursor: pointer !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    border-left: 4px solid transparent !important;
    box-shadow: none !important;
    visibility: visible !important;
    opacity: 1 !important;
}}

[data-testid="stSidebar"] [data-testid="stRadioGroup"] label:hover,
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {{
    background: var(--hover) !important;
    border-color: var(--line) !important;
    border-left: 4px solid var(--muted) !important;
    transform: translateX(3px) !important;
}}

/* Active Selected Nav Item */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label[data-selected="true"],
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"],
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) {{
    background: var(--green-soft) !important;
    border-color: rgba(8, 137, 108, 0.30) !important;
    border-left: 4px solid var(--green) !important;
    box-shadow: 0 2px 8px rgba(8, 137, 108, 0.08) !important;
}}

/* Completely hide the circular radio bullet input across Streamlit and BaseWeb */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] input[type="radio"],
[data-testid="stSidebar"] [data-testid="stRadioOption"] input[type="radio"] {{
    display: none !important;
    opacity: 0 !important;
    width: 0 !important;
    height: 0 !important;
    position: absolute !important;
    pointer-events: none !important;
}}

[data-testid="stSidebar"] [data-testid="stRadioGroup"] label > div:first-child:not(:has([data-testid="stMarkdownContainer"])),
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label input[type="radio"] + div,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label div[class*="RadioMark"],
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label svg,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label span:has(input),
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label > div:not(:has([data-testid="stMarkdownContainer"])),
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div > div:first-child:not([data-testid="stMarkdownContainer"]) {{
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
}}

/* Ensure inner wrappers fill the button width */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label > div,
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div {{
    flex: 1 1 100% !important;
    width: 100% !important;
    min-width: 0 !important;
    display: flex !important;
    align-items: center !important;
    background: transparent !important;
    visibility: visible !important;
    opacity: 1 !important;
}}

/* Streamlit Markdown Container */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] {{
    flex: 1 1 auto !important;
    width: 100% !important;
    min-width: 0 !important;
    display: flex !important;
    align-items: center !important;
    visibility: visible !important;
    opacity: 1 !important;
    overflow: visible !important;
    background: transparent !important;
}}

/* Nav label typography */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label p,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label span:not(:has(input)),
[data-testid="stSidebar"] [data-testid="stRadioOption"] p,
[data-testid="stSidebar"] [data-testid="stRadioOption"] span:not(:has(input)) {{
    font-size: 15.5px !important;
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    font-weight: 550 !important;
    color: #475569 !important;
    visibility: visible !important;
    opacity: 1 !important;
    line-height: 1.3 !important;
    margin: 0 !important;
    padding: 0 !important;
    display: block !important;
    white-space: nowrap !important;
    overflow: visible !important;
    letter-spacing: -0.2px !important;
}}

[data-testid="stSidebar"] [data-testid="stRadioGroup"] label:hover p,
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover p {{
    color: var(--heading) !important;
}}

[data-testid="stSidebar"] [data-testid="stRadioGroup"] label:has(input:checked) p,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label:has(input:checked) span,
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p,
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) p {{
    color: var(--green) !important;
    font-weight: 750 !important;
}}

/* Sidebar section header */
.nav-section-label {{
    font-size: 11px;
    letter-spacing: 1.6px;
    font-weight: 750;
    color: var(--muted);
    padding-left: 8px;
    margin-top: 18px;
    margin-bottom: 8px;
    text-transform: uppercase;
}}

/* Sidebar System Status Card */
.sidebar-system-card {{
    padding: 14px 16px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 9px;
    margin: 20px 0 12px 0;
}}

.sidebar-system-card-top {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--heading);
    font-weight: 650;
}}

.sidebar-system-card-sub {{
    font-size: 11.5px;
    color: var(--muted);
    margin: 5px 0 10px 16px;
}}

.sidebar-system-mini {{
    display: flex;
    justify-content: space-between;
    border-top: 1px solid var(--line);
    padding-top: 8px;
    color: var(--muted);
    font-size: 11px;
}}

/* Sidebar User Profile Card */
.sidebar-profile {{
    display: flex;
    align-items: center;
    gap: 10px;
    border-top: 1px solid var(--line);
    padding: 14px 4px 6px;
    width: 100%;
}}

.sidebar-avatar {{
    width: 32px;
    height: 32px;
    background: var(--green-soft);
    color: var(--green);
    border: 1px solid var(--line);
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-family: 'Manrope', sans-serif;
    font-weight: 700;
    font-size: 11px;
    position: relative;
    flex-shrink: 0;
}}

.sidebar-avatar > span {{
    position: absolute;
    background: var(--green);
    bottom: 0;
    right: 0;
    border: 2px solid var(--panel);
    width: 8px;
    height: 8px;
    border-radius: 50%;
}}

.sidebar-profile-info strong {{
    font-size: 11px;
    display: block;
    color: var(--heading);
    font-weight: 600;
}}

.sidebar-profile-info small {{
    font-size: 11px;
    color: var(--muted);
    display: block;
}}

/* Compliance Donut & Bars matching Reference Platform */
.compliance-content {{
    padding: 0 12px;
}}

.donut-wrap {{
    width: 140px;
    height: 140px;
    position: relative;
    margin: 0 auto 14px auto;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.donut-wrap > svg {{
    width: 140px;
    height: 140px;
    transform: rotate(-90deg);
    display: block;
}}

.donut-label {{
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    pointer-events: none;
}}

.donut-label strong {{
    font-family: 'Manrope', sans-serif;
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -1px;
    color: var(--heading);
    line-height: 1.2;
}}

.donut-label small {{
    font-size: 18px;
    color: var(--green);
}}

.donut-label span {{
    font-size: 11px;
    color: var(--muted);
    margin-top: 2px;
}}

.ppe-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 10px;
}}

.ppe-row {{
    display: flex;
    gap: 10px;
    align-items: center;
    width: 100%;
    box-sizing: border-box;
}}

.ppe-info {{
    flex: 1 1 auto;
    min-width: 0;
}}

.ppe-label {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    color: var(--secondary);
    margin-bottom: 4px;
}}

.ppe-label strong {{
    font-size: 11px;
    font-weight: 700;
    color: var(--heading);
}}

/* Custom Video Container */
div[data-testid="stVideo"] video, .element-container video {{
    border-radius: 6px !important;
    border: 1px solid var(--line) !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1) !important;
}}
/* SIMULATION MODE banner */
.demo-banner {{
    background: linear-gradient(90deg, var(--amber-soft), #fff8e1);
    border: 1px solid var(--amber);
    border-radius: 6px;
    padding: 8px 16px;
    text-align: center;
    font-size: 11px;
    font-weight: 700;
    color: var(--amber);
    letter-spacing: 0.5px;
    margin: 8px 0;
}}

/* Responsive: metric cards on narrow viewports */
@media (max-width: 768px) {{
    .metrics-grid {{
        grid-template-columns: repeat(2, 1fr) !important;
    }}
    .workers-grid {{
        grid-template-columns: 1fr !important;
    }}
}}

/* Form control styling */
div[data-testid="stSelectbox"] > div,
div[data-testid="stTextInput"] > div > input {{
    border-radius: 6px !important;
    border-color: var(--line) !important;
    font-family: 'DM Sans', sans-serif !important;
}}

/* Luxury entrance animations & hover micro-interactions */
@keyframes cardEntrance {{
    from {{
        opacity: 0;
        transform: translateY(6px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

.metric-card, .panel, .alert-card, .worker-card, .zone-card {{
    animation: cardEntrance 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}}
</style>
"""


def render_motion_bridge() -> None:
    """Retained for backwards-compatibility; animations are natively handled via GPU-accelerated CSS."""

