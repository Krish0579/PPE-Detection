# Changelog — SAFE SIGHT AI

All notable changes are recorded here. Version source of truth: `src/__version__.py`.
Release discipline: `docs/PRODUCTION_MASTER_PLAN.md` §8.

## [Unreleased]

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
- Coverage ratchet: `pytest-cov` wired into CI with `fail_under = 68` (measured baseline
  69% on `src/`); `make coverage` locally.
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
