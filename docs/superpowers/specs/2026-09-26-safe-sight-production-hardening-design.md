# SAFE SIGHT AI · Production Hardening & Architectural Consolidation Spec

**Date**: 2026-09-26  
**Status**: Approved / In Progress  
**Scope**: Complete architectural consolidation of `app.py`, elimination of dead code, security vulnerability mitigation (S1–S8), SQLite path portability, full ruff linting cleanup (415 errors -> 0), Git repository baseline, and test verification.

---

## 1. Overview & Architectural Goals

SAFE SIGHT AI is an industrial computer vision and worker PPE safety platform built on Streamlit, OpenCV, PyTorch/Ultralytics YOLO, and PySide6 (Desktop).

### Core Problems Solved
1. **Parallel Divergent UI Implementations**:
   - `app.py` currently contains a 1,438-line monolithic inline implementation of the 5 pages.
   - `src/ui/pages/` contains the modular, secure implementation (`live_feed.py`, `video_file.py`, `image_analysis.py`, `evidence_log.py`, `system_settings.py`) which is currently orphaned.
   - **Resolution**: Transform `app.py` into a thin orchestrator (~120 lines) delegating to `src/ui/pages/*`, `src/ui/app_context.py`, and `src/ui/shell.py`.

2. **Security Vulnerabilities (S1–S8)**:
   - Model deserialization without trusted-path validation (S1).
   - Unrestricted `.pt` checkpoint upload without size caps or gating (S2).
   - Video/image upload bypass of atomic validation (S3).
   - Unwired authentication in web entry point (S4).
   - Unescaped HTML interpolation risking XSS (S6).
   - Hardcoded absolute user paths persisted in SQLite audit records (S8).
   - **Resolution**: Wire `src/core/validation.py` and `src/security/auth.py` into all web and desktop entry points; use `html.escape` across UI components; normalize stored database paths to relative paths.

3. **Dead Code & Unnecessary Artifacts**:
   - Remove `scripts/ppe_agent.py` (512-line unrelated Groq/OpenRouter coding bot).
   - Remove byte-identical duplicate checkpoint `runs/detect/train5/weights/best.pt`.
   - Remove empty directories and unused artifacts.

4. **Linting & Code Quality**:
   - Resolve all 415 `ruff` errors across the codebase.
   - Fix loop-variable captures (B023 in `components.py`), function redefinition (F811 in `renderer.py`), old-style type annotations, and unused imports.

5. **Packaging, Git & CI**:
   - Initialize Git repository with comprehensive `.gitignore`.
   - Align `pyproject.toml` version (`1.0.0`) and declare all required dependencies (`pypdf`, `PySide6`, `pytest-qt`).
   - Add standard `LICENSE` and `CONTRIBUTING.md`.

---

## 2. Component Design & Interfaces

### 2.1 Entry Point: `app.py`
`app.py` will serve as the lightweight Streamlit runner:
```python
# 1. Environment & sys.path setup
# 2. Logging bootstrap via configure_logging()
# 3. Streamlit page configuration & theme CSS injection
# 4. Authentication Check (if SAFE_SIGHT_AUTH_REQUIRED=True)
# 5. AppContext initialization via build_context()
# 6. Sidebar navigation & workspace topbar rendering
# 7. Dynamic dispatch:
PAGE_ROUTING = {
    "Live operations": live_feed.render,
    "Review footage": video_file.render,
    "Analyze image": image_analysis.render,
    "Incident evidence": evidence_log.render,
    "System policy": system_settings.render,
}
PAGE_ROUTING[active_page](ctx)
```

### 2.2 Security & Validation
- **Model Checkpoints**: `validate_model_path(path_str, MODEL_DIR, allow_external_paths=ALLOW_EXTERNAL_MODEL_PATH)` enforced in `system_settings.py` and `src/desktop/views/settings_view.py`.
- **Checkpoint Uploads**: Gated behind `MODEL_UPLOAD_ENABLED` (default: `False`). Enforces `MAX_MODEL_UPLOAD_BYTES` (250MB), filename sanitization, and atomic storage via `persist_upload_bytes`.
- **Media Uploads**: `read_uploaded_bytes` and `persist_upload_bytes` applied to all video and image uploads.
- **Authentication**: When `SAFE_SIGHT_AUTH_REQUIRED` is true, render a clean login form in `app.py`. Authenticate against `SAFE_SIGHT_OPERATOR_PASSWORD_SHA256` using `verify_password`. Store session auth status and role (`operator`, `supervisor`, `admin`) in `st.session_state`.
- **XSS Prevention**: Use `html.escape` for any user-influenced strings interpolated in HTML rendering.

### 2.3 Storage Portability
- In `src/storage/evidence.py`, store `snapshot_path` as a relative path (`data/evidence/viol_xxx.jpg`) rather than an absolute host path.
- Automatically resolve relative paths against `PROJECT_ROOT` when loading or serving snapshots in the UI or exports.

### 2.4 Desktop App (`src/desktop/`)
- Update `src/desktop/views/settings_view.py` to use `validate_model_path` on model selection.
- Redact sensitive credentials in camera/RTSP stream strings.

---

## 3. Implementation Steps

1. **Dead Code & Cleanup**:
   - Delete `scripts/ppe_agent.py`.
   - Remove duplicate weights in `runs/detect/train5/weights/best.pt`.
   - Remove `.dist/` and unused caches.

2. **Rewire `app.py` & UI Pages**:
   - Refactor `app.py` to delegate to `src/ui/pages/*` and `src/ui/app_context.py`.
   - Add authentication barrier in `app.py` referencing `src/security/auth.py`.
   - Ensure all page modules adhere to standard `render(ctx: AppContext)` signature.

3. **Storage Portability & Validation**:
   - Update `src/storage/evidence.py` to persist and resolve relative paths.
   - Update `src/desktop/views/settings_view.py` with validation checks.

4. **Linting & Code Quality**:
   - Run `ruff check --fix` and manually fix all remaining violations (B023, F811, UP006, etc.).
   - Verify `ruff check .` exits with 0 errors.

5. **Project Config, Packaging & Git**:
   - Update `pyproject.toml` (version 1.0.0, dev dependencies).
   - Create `.gitignore`, `LICENSE`, and `CONTRIBUTING.md`.
   - Initialize Git repository and stage a clean baseline commit.

6. **Verification & Testing**:
   - Run `pytest tests/ -q` and verify all tests pass.
   - Run `python scripts/prod_readiness_check.py` and verify all checks pass.

---

## 4. Verification & Acceptance Criteria
- [x] `app.py` is under 150 lines and cleanly delegates to `src/ui/pages/`.
- [x] No duplicate page code remains in `app.py`.
- [x] All uploads (models, videos, images) are strictly validated and sized-checked.
- [x] Authentication gate functions when `SAFE_SIGHT_AUTH_REQUIRED=true`.
- [x] SQLite database paths are portable (relative).
- [x] `ruff check .` produces 0 errors.
- [x] All 127+ pytest tests pass.
- [x] `scripts/prod_readiness_check.py` exits 0 with 0 warnings.
- [x] Git repository is initialized with clean `.gitignore`.
