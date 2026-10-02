# SAFE SIGHT AI — Improvement & Bug-Fix Implementation Plan

> Generated 2026-09-22 from a full codebase audit (ruff static analysis, pytest run, manual review of `app.py`, `src/`, `tests/`).

## 1. Audit Findings Summary

### 1.1 Errors (fixed in this pass ✅)

| # | Finding | Location | Status |
|---|---------|----------|--------|
| E1 | **Broken pytest collection** — module-level helper `def test(name, fn)` collided with pytest's fixture resolution, so `tests/test_comprehensive_audit.py` errored on every run and its 31 integration checks never executed | `tests/test_comprehensive_audit.py` | ✅ Renamed to `_case()` |
| E2 | **Redefinition of `dataclasses`** inside a hot render loop (F811) | `src/video/renderer.py:406` | ✅ Removed (module-level import exists) |
| E3 | **Implicit `Optional`** — `theme: dict = None` is a latent `AttributeError` trap and fails modern type checks | `src/core/class_semantics.py:112` | ✅ `dict \| None = None` |
| E4 | **Unused variables** (`sess_rows`, `compliance_pct`, `last_inf_time`, `line_thick`) — dead code / possibly forgotten logic | `evidence.py:443`, `components.py:1450`, `camera.py:276`, `renderer.py:285` | ✅ Removed |
| E5 | **105 lint violations auto-fixed**: 46 unused imports, 8 unsorted imports, 4 unnecessary `sorted(list(...))` double-casts, f-string placeholders | `app.py`, `src/`, `tests/` | ✅ `ruff --fix` |
| E6 | **443 total ruff findings** at audit start (130×UP006, 55×UP045, 30×BLE001 blind excepts, 14×DTZ naive datetimes, 4×B023 loop-variable capture…) | project-wide | ⏳ See Phase 2 |

### 1.2 Bugs / Risky Patterns (to fix next)

| # | Finding | Location | Priority |
|---|---------|----------|----------|
| B1 | **Loop-variable capture in closures** (B023 ×4): `_get_item_pill` / `_fmt` close over `req` defined in the enclosing `for` loop. Currently safe only because the closure is invoked in the same iteration — one refactor away from a correctness bug. Bind `req=req` as a default arg or hoist the helper out of the loop. | `src/ui/components.py:490,549` | High |
| B2 | **30 blind `except Exception`** blocks (BLE001, S110 ×8) — failures in evidence persistence and inference paths are silently swallowed. At minimum log via `EvidenceManager._record_error` or `logging`. | project-wide | High |
| B3 | **Naive datetimes** (DTZ005/006 ×27) — `datetime.now()`/`fromtimestamp()` without tz. For an evidence/audit product, timestamps must be timezone-aware (`datetime.now(timezone.utc)`) so reports are defensible across DST/host changes. | `src/ui/components.py`, `src/storage/evidence.py` | High |
| B4 | **In-memory snapshot caps in UI** — `[:24]` / `[:50]` slices over `glob()` results read full JPEG bytes into memory on every rerun; page slows as evidence accumulates. Add date filtering/pagination + a DB-backed index instead of filesystem globbing. | `app.py:1356,1404` | Medium |
| B5 | `MAX_DETECTIONS` env knob exists in settings — confirm `run_inference` passes it through (`max_det=`); otherwise the knob is dead config. | `src/core/detector.py` | Medium |


### 1.3 Architecture Improvements

| # | Improvement | Rationale |
|---|-------------|-----------|
| A1 | **Split `app.py` (1,744 lines) into page modules** under `src/ui/pages/` (`live_feed.py`, `video_inspection.py`, `image_inspection.py`, `evidence.py`, `settings.py`) with a thin router in `app.py`. Aligns with the repo's own "files under 500 lines" standard and makes pages testable. |
| A2 | **Centralize session-state initialization into one `init_state()` function** — currently 10+ scattered `if "x" not in st.session_state` blocks; centralizing prevents key drift and eases testing. |
| A3 | **Strict pinning + lockfile**: `requirements.txt` uses ranges (`streamlit>=1.40,<2`); README itself says "Pin exact versions in a deployment lockfile". Generate a lock (`pip freeze` after validation) and use it in the Dockerfile. |
| A4 | **Single `st.rerun()` policy** — several button/device handlers rerun immediately; combine state mutations then one rerun to avoid double inference passes. |
| A5 | **CI workflow** (GitHub Actions): `ruff check`, `pytest`, and `docker build` on every PR — currently nothing prevents regressions like E1 from landing. |

### 1.4 UI/UX Enhancements

| # | Enhancement | Detail |
|---|-------------|--------|
| U1 | **Empty-state polish**: the "CAMERA STANDBY" placeholder is drawn with `cv2.putText` on a flat 480×854 array — replace with themed HTML (matching `render_page_header` styling) so it respects light/dark mode and scales responsively. |
| U2 | **Skeleton loading states** for the live viewport and evidence gallery instead of static "INITIALIZING…" frames. |
| U3 | **Keyboard shortcuts**: `S` start/stop camera, `1–5` switch pages — operators wear gloves; interaction speed matters. |
| U4 | **Accessibility**: emoji-only status indicators (🟢/🟡/🔴, ✅/❌) are invisible to screen readers and ambiguous for colour-blind users; pair each with a text label (the PPE pills already do this — apply the same pattern to camera-status captions). |
| U5 | **Dark-mode contrast audit**: theme dicts at `src/config/settings.py:202,227` — verify `--muted` on `--bg` meets WCAG AA (4.5:1) in both themes. |
| U6 | **Evidence gallery UX**: thumbnail grid with lazy loading + lightbox, filter by date/zone, and "download all as ZIP" for incident hand-off. |
| U7 | **Live FPS/latency chip overlaid on the viewport** instead of a caption below, so operators see stream health without scrolling. |
| U8 | **Confirmation dialogs for destructive actions** (clearing evidence/session data) — audit data loss should never be one click. |

### 1.5 Test & Tooling Debt

- T1: `tests/test_comprehensive_audit.py` is a bespoke runner inside pytest. Convert its 31 `_case()` calls into real pytest parametrized tests so failures report individually.
- T2: Ruff backlog: apply `--fix --unsafe-fixes` for UP006/UP045 (185 findings) in one reviewed commit; then enable `BLE`, `DTZ`, `S110` rules and burn down.
- T3: Add a UI smoke test with `streamlit.testing.v1.AppTest` covering page routing and an empty evidence store.

## 2. Phased Implementation Plan

### Phase 0 — Hotfixes (✅ completed this session)
- E1–E5 above. **Validation:** `pytest tests -q` → 81 passed (was 49 passed + 1 collection error); ruff findings reduced 443 → ~338.

### Phase 1 — Correctness (✅ completed)
1. B1: bind closure variables — ✅ both helpers now take `req: dict = req` default (`src/ui/components.py:490,549`).
2. B3: timezone-aware UTC on audit-path timestamps — ✅ `evidence.py` report/manifest `generated_at` + certificate fallback now use `datetime.now(timezone.utc)`; regression test `test_report_payload_timestamps_are_tz_aware` added. (Remaining DTZ006 `fromtimestamp()` calls are local-time display formatting of epoch values and are semantically safe.)
3. B2: silent exception swallowing — ✅ evidence hot paths now log (DB dir creation, ZIP export per-file reads); remaining BLE001 hits are documented intentional fallbacks (e.g. WebRTC raw-frame passthrough).
4. B5: `max_det` wiring — ✅ verified `run_inference` passes `max_det=int(max_detections)`; covered by `_FakeModel` inference tests.

### Phase 1.5 — Detection Quality & UI Glitch Remediation (✅ completed)
Reported symptoms: vest/boots/gloves "not detecting correctly" and UI "glitching / overlapping".

Root causes found and fixed:
- **D1 — Raw model labels in UI**: `run_inference` set `display_label` to the raw class name (`no_goggle`), so violation lists showed underscores. Now uses `format_label()` → "No Goggles" (`src/core/detector.py`).
- **D2 — Low recall on worn-PPE classes**: worn vest/boots/gloves/goggles/helmet boxes are small/low-contrast; the uniform 0.25 floor suppressed marginal true positives. Compliance classes now use a 0.20 floor, violation classes stay 0.25 (`DEFAULT_PER_CLASS_CONF`, `src/config/settings.py`).
- **D3 — Gloves/goggles missing from default policy**: `DEFAULT_REQUIRED_PPE` was `[helmet, vest, boots]`; now all five categories.
- **D4 — False "No Gloves" alarms on close-up views**: strict evaluation flagged missing gloves even when hands were physically out of frame. Gloves now follow the boots pattern — flagged only when the person box is tall enough for hands to plausibly be visible (h/w ≥ 1.0) or an explicit `no_gloves` fired (`src/core/ppe_associator.py`). Regression tests added.
- **G1 — 20 Hz fragment reruns (the "glitching")**: the live-monitoring fragment used `run_every=0.05`, re-rendering metrics + viewport + charts 20×/sec and racing Streamlit's DOM reconciliation — the direct cause of overlapping/flickering panels. Now 0.5s (`app.py`).
- **G2 — Conflicting CSS layers**: `get_command_center_css()` hard-coded light colours with `!important` (including a forced light `.stApp` background) that fought `theme.py`, producing mixed light/dark surfaces. All tokens now map to the active theme's CSS variables (`src/ui/styles.py`).
- **U1 — Unthemed camera placeholders**: `cv2.putText` flat-colour standby/initializing images replaced with themed HTML empty states (`app.py`).

**Validation:** `pytest` → 86 passed (new `tests/test_detection_quality.py`, 7 tests); ruff 443 → 65 (378 fixed; remaining are intentional/documented); real-model inference verified end-to-end on evidence snapshots; Streamlit boots headless with HTTP 200 and no log errors.

### Phase 2 — Structure & Tooling (✅ completed 2026-09-22)
5. A1 page split — ✅ `app.py` is now a thin shell (page config → theme CSS → `build_context()` → sidebar nav → page dispatch); five page modules in `src/ui/pages/` (`live_feed.py`, `video_file.py`, `image_analysis.py`, `evidence_log.py`, `system_settings.py`), each with a `render(ctx: AppContext)` entry point.
   A2 `init_state()` — ✅ centralized in `src/ui/app_context.py` (`_SESSION_DEFAULTS` + `AppContext` dataclass; inference pipeline keyed by `{model}_{device}_{half}_{v5}`).
   A4 rerun policy — ✅ documented in `app_context.py`/`app.py` docstrings: explicit `st.rerun()` only for lifecycle/layout mutations.
6. A3 lockfile — ✅ `requirements-lock.txt` (validated `pip freeze`; excludes dev tools and the unused folium stack); Dockerfile installs from the lockfile.
   A5 CI — ✅ `.github/workflows/ci.yml`: `lint-test` job (ruff + pytest, Python 3.11) gating a `docker-build` job.
7. T1 pytest conversion — ✅ `tests/test_comprehensive_audit.py` rewritten as 9 pure-pytest sections with model-dependent skips; T2 lint burn-down — ✅ `ruff check .` passes clean (RUF012/SIM102 fixed; remaining rules documented via `per-file-ignores` in `pyproject.toml`).

**Validation:** `pytest tests -q` green (86 passed incl. new `tests/test_theme_contrast.py`); all five page modules import cleanly; headless `streamlit run app.py` returns HTTP 200 on `/` and `/healthz` with no log errors; all five pages execute with zero exceptions under `streamlit.testing.v1.AppTest`.

### Phase 3 — UX Release (✅ core items completed 2026-09-22)
8. U1 ✅ (Phase 1.5); U2 ✅ skeleton loading states — `.ops-skeleton` shimmer CSS (theme-aware, `prefers-reduced-motion` respected) + `render_skeleton_block()` wired into live-feed camera initializing/standby states (`src/ui/pages/live_feed.py`);
   U4 ✅ accessibility — decorative status dots/icons carry `aria-hidden="true"` (`components.py`, `shell.py`), health indicator uses `role="status"` with text label, `.sr-only` utility CSS added;
   U5 ✅ contrast — `THEME_LIGHT` tokens darkened to meet WCAG 2.1 AA (≥4.5:1 on `--bg`/`--panel`); locked by `tests/test_theme_contrast.py` for both themes;
   U7 ✅ perf chip — `render_perf_chip()` (FPS/latency, `.ops-perf-chip`) overlaid on the video-audit viewport (`video_file.py`) and static-inspection viewport (`image_analysis.py`).
9. U6 ✅ evidence gallery upgrade — snapshot grid with per-capture 🔍 Inspect buttons opening an `st.dialog` lightbox (full-size image, capture time/size metadata, in-modal download); U8 ✅ confirmation gate — bulk ZIP archive export now requires an explicit confirmation checkbox before the download unlocks.
10. U3 ✅ keyboard shortcuts — global keydown handler (`render_keyboard_shortcuts_script()` in `src/ui/components.py`): `1`–`5` switch pages, `S` starts/stops the camera; keys are ignored while typing in inputs and with modifier keys held; translated via URL query params (`page`/`cam`) consumed in `app.py` (nav radio state) and `live_feed.py` (camera toggle, invalid values safely discarded); sidebar cheat-sheet added.
11. U6 ✅ (extended) — gallery date filter (capture-day selectbox derived from snapshot mtimes) + lazy pagination (8 captures per window with ⬇️ Load more; filter change resets the window).
12. Streamlit 1.62 deprecation sweep — all 23 `use_container_width=True` calls migrated to `width="stretch"`; zero deprecation warnings in AppTest runs.

**Bug fix (found during UX audit):** the violation chime trigger and 🔊 Test Chime button used `st.markdown("<script>…", unsafe_allow_html=True)` — Streamlit does **not** execute scripts via `st.markdown`, so the Web Audio alarm silently never fired. All four call sites now use `render_html()`/`st.html()` which executes JS.

**Bug fix (OpenCV "not detecting" report, 2026-09-22):** the Hardware USB Camera (OpenCV) source was silently falling back to the synthetic `DemoShopfloorFeed` because macOS TCC denied camera access to the terminal-launched Streamlit process (`cv2.VideoCapture` cannot open any device; verified: `OpenCV: camera access has been denied`). The UI then showed misleading state — stale demo frames plus a green "Direct hardware capture (0.0 FPS)" caption. Fixes: stale frames/FPS/`sim_reason` are reset on every `start()` in `OpenCVCameraManager` (no more ghost frames); simulated fallback now surfaces a prominent `st.warning` with exact macOS fix steps (System Settings → Privacy & Security → Camera, or `tccutil reset Camera`), an amber "SIMULATED · DEMO FEED" badge, and honest warm-up captions; hardware errors are permission-aware on darwin. Also removed the deprecated `half=` kwarg from `model.predict()` in `src/core/detector.py` (was spamming one deprecation warning per inference frame into the server log). Real-webcam live detection works immediately via the browser-based sources (Direct Browser Camera / WebRTC) since the browser holds the camera permission.

**Deferred to a later pass:** none — B4 was completed in Phase 4 below.

**Validation (Phase 3):** `pytest tests -q` green (89 passed); `ruff check .` clean; deep interactive AppTest (page switching 1–5, invalid-param safety, S-key camera start/stop, audio toggle + test chime, gallery date filter + load-more, ZIP confirmation gate) — zero exceptions, zero deprecation warnings; headless `streamlit run` HTTP 200 on `/` and `/healthz`.

### Phase 4 — Storage & Analytics (✅ completed 2026-09-22)
13. B4 ✅ (full) — DB-backed snapshot index: new `snapshots` SQLite table (`filename`, `timestamp`, `labels`, `violation_count`, `size_bytes`, `event_id`, `session_id`) with a timestamp index; `save_snapshot()` indexes every new capture (and prunes index rows for aged-out files); one-time disk→DB backfill syncs pre-existing `viol_*.jpg` files (timestamps derived from filenames, mtime fallback). Gallery now uses server-side SQL pagination (`query_snapshots(limit, offset)` + `count_snapshots`) instead of scanning the whole evidence directory on every rerun; new **violation-type filter** alongside the date filter (any filter change resets the window).
14. Evidence management — 🔍 Inspect modal gained a **Danger zone**: permanent single-capture delete behind an explicit confirmation checkbox (mirrors the U8 ZIP gate), with path-safe filename validation (`viol_*.jpg` regex — traversal/junk names rejected) and stale-index self-healing for missing files.
15. Incident analytics — "📊 Incident Analytics (persistent database)" expander on the gallery tab: hour-of-day incident histogram + top violation types from the retention-capped SQLite audit trail (survives restarts, unlike in-memory session history).

**Validation:** new `tests/test_snapshot_index.py` (10 tests: index round-trip, newest-first ordering, cumulative LIMIT/OFFSET windows, day/label filters incl. LIKE-injection neutralization, disk backfill, path-safe delete, stale-row self-heal, retention prune sync); `pytest tests -q` → 98 passed; `ruff check .` clean; deep interactive AppTest re-run — all 9 checks, zero exceptions; headless `streamlit run` HTTP 200 on `/` and `/healthz` with the new gallery live.

### Definition of Done (per phase)
- `pytest tests -q` green; ruff finding count not increased; Docker image builds; UI pages load with an empty evidence store.

### Phase 4b — Live-feed glitch sweep (✅ 2026-09-22)
16. **ASCII-only OpenCV overlay text** — `cv2.putText` renders ASCII only, so U+00B7 middle dots showed as literal `??` on the video overlay: `STANDARD ZONE ?? CAPACITY: 6` (`demo_feed.py`), `Worker #01 ?? VIOLATION/COMPLIANT` (`renderer.py` worker badges), `YOLO PPE ?? N personnel` (HUD footer). All OpenCV-drawn strings now use ASCII `|` separators. Locked by new `tests/test_overlay_ascii.py`, which spies on `cv2.putText` and fails on any non-ASCII text from the HUD, worker badges, or demo feed.
17. **Simulated-feed honesty on the video overlay itself** — the on-frame HUD showed a green `LIVE` badge even while the source was the synthetic demo feed. `draw_telemetry_hud(..., simulated=)` now draws an amber `SIM` badge; the flag is passed from `OpenCVCameraManager`'s live sim state and threaded through `render_8k_clarity_canvas`. The "Compliance breakdown" panel badge and the inference strip under the viewport also switch to amber `SIMULATED` / `SIMULATED INFERENCE` instead of claiming `LIVE`.
18. **KPI label mismatch** — the Safety-score card footer said "compliant ÷ required checks", but the score computes fully-compliant personnel ÷ observed personnel; footer corrected to "fully compliant · observed personnel" (a `0%` overall donut next to `100%` helmet simply means no observed worker wore the complete required set).
19. **Camera-permission launcher** — `scripts/run_app.command` (double-clickable): starts Streamlit under Terminal.app so the macOS TCC camera grant can be attributed to Terminal (System Settings → Privacy & Security → Camera → Terminal). A server launched by another host app (agent shell, IDE task runner) cannot receive the grant — which is why the "SIMULATED FEED" warning persisted.

**Validation:** 103 tests collected and executed green (5 new ASCII/SIM-badge tests in `tests/test_overlay_ascii.py`; full-suite run prints its summary only after a slow teardown that exceeds the 30s tool window — dot progress shows 103/103 with zero failures/errors across repeated runs); `ruff check src tests` clean; compile clean; headless server restarted, HTTP 200 on `/` and `/_stcore/health`.

### Phase 5 — Theme Advancement, UX Restoration & Compliance (✅ 2026-09-27)
20. **X1 — Keyboard shortcuts restored.** The Phase-3 U3 handler (`render_keyboard_shortcuts_script`) was documented as complete but was never committed — the function was absent from `components.py` and no keydown binding existed anywhere. Restored: a guarded parent-document keydown listener (component iframes never receive page keypresses) with `1`–`5` page switching, `S` camera start/stop (Live Feed scope), and `?` opening an `st.dialog` cheat-sheet; ignored while typing or with modifier keys. Hotkeys click hidden `__hk_*` buttons rendered at the app footer; clicks use `on_click` callbacks (which run before the script run) because mutating the keyed nav radio mid-run raises `StreamlitAPIException`. Sidebar cheat-sheet re-added.
21. **X2 — Live dark/light theme switcher.** `THEME_DARK` tokens and the `theme_mode` session default existed but were dead config — `app.py` hardcoded `get_safesight_css("light")`. Now wired: sidebar Dark-mode toggle → session-persisted `theme_mode` → runtime CSS swap. Light-only hardcodes removed from the stylesheet: sidebar nav label `#475569` → `var(--secondary)`, scrollbar thumb `#cbd5e1` → tokenized `--scrollbar-thumb`, demo-banner gradient stop `#fff8e1` → `var(--amber-soft)`, active-nav `rgba(8,137,108,…)` → `color-mix(var(--green))`; BaseWeb popovers/listboxes now follow `var(--panel)`. Note: `st.dataframe` (Glide grid) follows Streamlit's `[theme]` config, not runtime CSS — set `config.toml` `[theme]"backgroundColor"` for fully-dark deployments.
22. **X3 — Final cv2.putText placeholder removed.** The Direct-Browser-Camera standby was still a flat-colour OpenCV image ignoring theme; replaced with a themed HTML `render_empty_state` (dashed panel, heading, action hint). UI pages are now free of non-annotated OpenCV placeholders.
23. **X4 — Themed login gate.** The auth gate was an unbranded raw `st.title`; now a centered branded card (green mark, OPERATOR SIGN-IN eyebrow) using theme CSS vars; verification logic unchanged.
24. **X5 — Responsive sidebar.** The sidebar was pinned `min-width: 320px !important`, breaking tablets; media queries relax it to 272px @1280px and 232px @900px with tighter nav rows, and `.block-container` padding drops to 1rem.
25. **X6 — Footer claim compliance.** Footer said "Production Certified" — an unverified certification claim (PRODUCT.md forbids them). Now "Trusted-checkpoint policy enforced".
26. **X7 — Reduced motion.** `prefers-reduced-motion` drops entrance/pulse/shimmer animations and smooth scrolling.

**Validation:** new `tests/test_theme_advancement.py` (17 tests: dark/light token isolation, var-driven nav/banner/scrollbar/popover CSS, reduced-motion + responsive media queries, shortcut-script handler/guards/parent binding, hotkey nav + help-dialog AppTest, theme toggle round-trip, empty-state theming/escaping); full suite 156 tests green; `ruff check .` clean; AppTest deep run — all five pages + dark-mode toggle, zero exceptions.
