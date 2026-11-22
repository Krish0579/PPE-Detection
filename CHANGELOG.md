# Changelog — SAFE SIGHT AI

All notable changes are recorded here. Version source of truth: `src/__version__.py`.
Release discipline: `docs/PRODUCTION_MASTER_PLAN.md` §8.

## [Unreleased]

### Removed
- **Dark mode toggle.** The sidebar "Appearance" section, the `theme_mode` session
  key, and the theme-switch `st.rerun()` are gone; the workspace renders the light
  operations theme unconditionally. Dark-palette contrast tests in
  `test_theme_contrast.py` are retained so the guarantee survives if it returns.
- **Keyboard shortcuts.** The global keydown handler (`render_keyboard_shortcuts_script`),
  the eight hidden `__hk_nav_N` buttons, the `S` camera toggle, the `?` cheat-sheet
  dialog, the sidebar "Shortcuts" cheat-sheet, the `.ops-kbd` CSS, the unused
  `render_motion_bridge()` helper, and the `_pending_nav` session plumbing are all
  removed. Navigation is mouse-driven only.

### Fixed
- **One worker no longer appears as two people.** Operator report: the Evidence Log
  showed two personnel cards for a single worker. Detector NMS runs *per class*, so
  one human could survive as two boxes (full-body plus a tighter second-pass crop
  from multi-scale TTA / person-crop refinement, or under two person-like class
  names); each box became its own track and its own person card. New
  `suppress_duplicate_person_boxes()` in `src/core/worker_tracker.py` collapses such
  boxes before tracking, using IoU **and** containment (a box nested in a larger one
  has low IoU but near-total containment). Input order is preserved so track results
  stay index-aligned with the boxes passed in. Genuinely distinct people — including
  workers standing shoulder to shoulder — are never merged.
- **Identity-less violation labels are no longer misattributed.** In
  `consolidate_person_alerts`, a bare label such as `"no helmet"` was pinned to
  `Person 1` unconditionally, falsely incriminating the first individual in a
  multi-person scene. Such labels are now only attributed when exactly one person is
  in scope; otherwise nothing is invented.
- **Compliance panel no longer claims "Ready · 100%" when nobody is observed.** With
  zero workers every PPE row rendered a full green bar reading `Ready · 100%`. Rows
  now render neutral with `Not measured`.
- **Productivity metrics are measured, not assumed.** `render_productivity_view`
  hardcoded `Stationary / Idle` to `0` and labelled absent dwell data as
  `"Active Shift"`; idle count is now derived from dwell time and absent dwell
  reports `Not measured`.

### Added
- `tests/test_duplicate_person_suppression.py` (18 tests): duplicate-box collapsing,
  preservation of distinct people and of input order, tracker identity stability
  across a duplicate frame, and end-to-end Evidence Log card counts for one vs. two
  workers plus the misattribution guard.
- `tests/test_worker_status_table.py` (8 tests): the per-worker PPE checklist now
  distinguishes worn / confirmed-missing / not-observed, so an `UNKNOWN` status can no
  longer render as a red `❌ NO HELMET` for PPE the detector never saw.
- `TestRemovedChrome` asserts the dark-mode and shortcut removals actually took
  effect, so neither can creep back in via a stray import or leftover widget.

### Fixed (earlier this session)
- **Operator-facing status is now measured, never assumed.** Command Center, Camera
  Wall, and System Health previously printed hardcoded readouts — `Storage: OK`,
  `Uptime: LIVE`, `Webhooks: OK`, `Status: LIVE`, `FPS: 0.0` — regardless of real
  state, and none of the three pages were reachable from `app.py`. All three are
  now wired into navigation and derive every value from observed runtime state via
  the new `src/ui/status.py`.
- **An unmeasured subsystem can no longer be reported as healthy.** `Status.UNKNOWN`
  is a first-class outcome rendered with a neutral badge; `overall_status()` returns
  `UNKNOWN` when any subsystem is unmeasured (or nothing was measured at all) rather
  than collapsing to a reassuring green verdict. A camera that has never run reads
  "Offline — no camera running", not a healthy tile.
- **Safety score no longer scores an empty population.** Pages computed
  `100.0 if total == 0 else ...`, so an idle workspace claimed *perfect* safety while
  observing nobody; the Command Center additionally rendered `0.0%`, which reads as
  total non-compliance. Both now render an em dash and "Not measured". This applies
  to `live_feed.py`, `video_file.py`, `image_analysis.py`, and both metric and
  compliance-donut renderers.
- **Camera Wall streaming tile no longer reports `ATTENTION` when healthy.** An
  error-free stream now reports `OK`; a stream carrying a capture error reports
  `ATTENTION`.
- `src/ui/styles.py` was never imported, so the entire `ops-*` CSS layer it defined
  (including `.sr-only`) silently fell back to browser defaults — status-table
  captions rendered as visible body text. Those rules now live in `theme.py`, which
  `app.py` actually loads.
- Camera Wall no longer prints raw HTML entities at the operator: tile detail text is
  HTML-escaped, so `&mdash;` surfaced literally. Plain em dashes are used instead.

### Added
- `src/ui/status.py`: pure, testable subsystem-status layer (`Status`, `ComponentStatus`,
  `DiskStatus`, `overall_status`, per-subsystem builders). Unmeasurable signals return
  `UNKNOWN` rather than a healthy default.
- Navigation now exposes eight pages — Command Center, Live Feed, Video File, Image
  Analysis, Camera Wall, Evidence Log, System Settings, System Health — with the app
  defaulting to Command Center so operators land on the situation overview. Keyboard
  hotkeys follow the page count (1–8) and the handler is driven by the nav map.
- `tests/test_ui_status.py` (37 tests): locks in the unknown-is-not-healthy contract,
  disk measurement thresholds, webhook-allowlist posture, XSS escaping of rendered
  detail text, the empty-population score rules, and regression guards asserting the
  hardcoded `Storage: OK` / `Uptime: LIVE` / `Webhooks: OK` literals cannot return.
- `tests/test_safety_domain.py` (18 tests): worker-tracking temporal debounce (a
  one-frame detector miss must not flip compliance status) and feature-similarity
  bounds.

### Removed
- **Five orphaned duplicate modules** (~740 statements of unreachable code, all at 0%
  coverage and all verified to duplicate live implementations before deletion):
  `src/video/telemetry.py` (method-for-method copy of `pipeline.TelemetryState`),
  `src/storage/evidence_snapshots.py` (all 16 methods already on `EvidenceManager`),
  `src/video/renderer_mixins.py` (both methods already on `OverlayRenderer`),
  `src/storage/pdf_builder.py` (duplicate of `pdf_report.generate_audit_pdf`), and the
  never-imported `src/ui/styles.py`. Deleting these removes the divergence risk of a
  copy silently drifting from the code actually used at runtime.

### Changed
- `src/ui/components.py` (1697 lines, 3.4x the project's 500-line rule) is now a
  package split by concern: `base`, `dashboard`, `workers`, `alerts`, `analytics`,
  `reports`, `audio`. `src.ui.components` remains a stable import facade, so no caller
  changed. Also deleted the fully orphaned `src/ui/shell.py` and the dead
  `render_safesight_topbar` / `render_floor_map` top-level exports.

### Security
- **Critical:** bumped locked `torch` 2.2.2 → 2.14.0 and `torchvision` 0.17.2 → 0.29.0,
  remediating 20+ disclosed CVEs (PYSEC-2024-259, PYSEC-2025-41, PYSEC-2025-189..209,
  PYSEC-2026-1970, PYSEC-2026-2286). Floor enforced via `requirements.txt`,
  `pyproject.toml`, and a new blocking `pip-audit` CI job (`dep-audit`).
- Webhook egress: allowlist matching is now host-aware (exact host, scheme-equality,
  path-prefix segments) instead of raw string prefix; domain-suffix attacks and
  credential-embedding URLs are rejected. Regression-locked by
  `test_webhook_allowlist_host_hardening`.

### Fixed
- **Live Stream & Camera Snapshot Capture Pipeline Remediations:**
  - Resolved port 8501 collision by terminating stale foreign background process bound to `*:8501`.
  - Fixed in-place array mutation in Direct Browser Camera capture (`src/ui/pages/live_feed.py`): passed clean frame copy to renderer avoiding duplicated/smeared overlays.
  - Replaced 95MB 8K canvas payload with optimized 1080p target canvas mode (`src/video/renderer.py`, `src/ui/pages/live_feed.py`, `src/ui/pages/image_analysis.py`), eliminating WebSocket serialization lag and browser disconnects.
  - Enabled continuous 0.5s telemetry refresh for WebRTC video feed (`@st.fragment(run_every=0.5)`), resolving frozen 0-detection HUD on live browser streams.
  - Hardened inference engine (`src/core/detector.py`): eliminated PyTorch CPU fp16 half-precision errors and broadened exception handling to automatically fall back to resilient prediction.
  - Added standalone detection fallback in camera capture worker (`src/video/camera.py`) when worker tracking list is empty.

### Added
- **Phase 5 Theme Advancement & UI Polish:**
  - Tokenized theme stylesheet (`src/ui/theme.py`): eliminated hardcoded light-only colors for nav labels (`var(--secondary)`), scrollbars (`var(--scrollbar-thumb)`), demo banners (`var(--amber)` / `var(--amber-soft)`), and active-nav indicators.
  - BaseWeb popover theming: dropdown menus, listboxes, and options strictly follow the active theme (`var(--panel)`, `var(--text)`, `var(--hover)`).
  - Accessibility: `prefers-reduced-motion` media query disables animations, transitions, and pulse dots for operators who request reduced motion.
  - Responsive layout: responsive sidebar media queries relax pinned 320px width to 272px (≤1280px) and 232px (≤900px), with 2-column metric cards and single-column worker grids on narrow viewports.
  - Keyboard shortcuts handler (`src/ui/components.py:render_keyboard_shortcuts_script`): global keydown listener bound to parent document for keys 1-5 (navigation), S (camera start/stop), and ? (help dialog); input-safe and modifier-key guards.
  - Two-stage pending navigation pattern (`app.py`): hidden hotkey buttons set `_pending_nav` consumed before radio widget instantiation to preserve session state without widget conflict.
  - Themed empty-state helper (`src/ui/components.py:render_empty_state`): action-led HTML empty state with icon, title, subtitle, and hint pill replacing flat cv2.putText placeholders.
  - Themed operator login card (`app.py`): branded authentication gate with password verification and clean layout.
  - Authentic footer: displays model information and trusted-checkpoint verification policy.
  - AI Precision & Accuracy Engine: test-time augmentation (TTA), hierarchical two-pass person crop refinement, and boosted performance profile (`src/core/detector.py`, `src/config/settings.py`).
  - Comprehensive theme regression suite (`tests/test_theme_advancement.py`): 17 unit and AppTest regression tests.
- `pip-audit` dependency gate in CI and `make audit`; `make format` / `make format-check`.
- Ruff format enforcement: `ruff format --check` added to CI; whole repo reformatted
  (71 files) to a single deterministic style.
- Rotating file logging (`src/observability/logging_setup.py`): native installs rotate
  `data/logs/safesight.log` (10 MiB x 5); containers keep stdout-only logs
  (`SAFE_SIGHT_CONTAINER=1` baked into the image; `SAFE_SIGHT_LOG_FILE=off|path`).
- Coverage ratchet: `pytest-cov` wired into CI with `fail_under = 65` (measured baseline
  66.53% on `src/`); `make coverage` locally.
- CI matrix across all supported runtimes (Python 3.10 / 3.11 / 3.12).
- `.pre-commit-config.yaml` (ruff lint + format) and `.github/dependabot.yml`
  (weekly pip + actions updates; torch/torchvision grouped as a strict pair).

## [1.0.0] — 2026-09-25

### Added
- Phase 5 production hardening: validated runtime config (`src/config/runtime.py`) with
  secure-by-default trust flags; structured logging, health/version payload.
- Operator security: optional SHA-256 password gate + operator/supervisor/admin RBAC.
- Integrations: best-effort violation webhooks with allowlist; multi-camera source registry
  (`usb:/rtsp:/http:/demo`); privacy face/person blur for evidence hand-off.
- Operations: SQLite online backup + retention enforcement (`scripts/backup_evidence.py`);
  prod compose, Nginx TLS example, Prometheus example, K8s manifest; Makefile;
  offline readiness gate (`scripts/prod_readiness_check.py`, exit 0/2).
- Governance: company production master plan, runbook, deployment checklist,
  security policy; expanded `.env.example`; CI with gate + Trivy + SBOM.

### Fixed
- **Critical:** `ALLOW_EXTERNAL_MODEL_PATH` / `MODEL_UPLOAD_ENABLED` were hardcoded `True`,
  contradicting the trusted-checkpoint policy. Now env-driven, default `false`.

### Compliance notes
- Ultralytics YOLO is AGPL: clear a commercial license or distribute AGPL-compliantly
  before any proprietary sale. Complete DPIA + per-camera validation before go-live.
