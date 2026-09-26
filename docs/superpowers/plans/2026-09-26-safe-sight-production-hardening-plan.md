# SAFE SIGHT AI Production Hardening & Architectural Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate `app.py` into a thin shell delegating to `src/ui/pages/*`, fix all security boundaries (S1–S8), eliminate dead code and duplicate weights, make SQLite storage portable, resolve all 415 ruff linter errors, and establish a green CI and Git baseline.

**Architecture:** The Streamlit runner `app.py` acts as a thin routing layer that delegates to `src/ui/pages/*`, `src/ui/app_context.py`, `src/ui/shell.py`, and `src/security/auth.py`. Storage paths in SQLite are relative and resolved dynamically. Validation routines in `src/core/validation.py` are strictly enforced at all entry points.

**Tech Stack:** Python 3.11, Streamlit, PySide6, PyTorch / Ultralytics YOLOv8, OpenCV, SQLite, Ruff, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-safe-sight-production-hardening-design.md`

## Global Constraints
- Files must adhere to modular responsibilities and remain under 500 lines where practical.
- Security-by-default: Model uploads disabled unless explicitly configured; paths restricted to trusted directories.
- Zero ruff errors across the repository (`ruff check .` exit code 0).
- 100% passing tests on pytest suite.

---

### Task 1: Repository Setup, Packaging Sync & Dead Code Elimination

**Files:**
- Create: `.gitignore`, `LICENSE`, `CONTRIBUTING.md`
- Modify: `pyproject.toml`, `requirements-dev.txt`
- Delete: `scripts/ppe_agent.py`, `runs/detect/train5/weights/best.pt`

**Interfaces:**
- Consumes: Environment configuration and project structure.
- Produces: Clean Git repository root, synchronized packaging files, removed dead weight.

- [ ] **Step 1: Initialize Git and update .gitignore**
  Configure `.gitignore` to exclude `.venv/`, `.ruff_cache/`, `.pytest_cache/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `data/`, `runs/`, `.agents/`, `awesome-freellm-apis/`, `.streamlit/credentials.toml`, `.vscode/`.
- [ ] **Step 2: Sync pyproject.toml & requirements-dev.txt**
  Set `version = "1.0.0"`, add `pypdf>=5.0`, `PySide6>=6.6`, `pytest-qt>=4.4` to dependencies.
- [ ] **Step 3: Create LICENSE and CONTRIBUTING.md**
  Add standard MIT/Proprietary license notice and contributor guidance.
- [ ] **Step 4: Remove dead files**
  Delete unreferenced `scripts/ppe_agent.py` and duplicate weight `runs/detect/train5/weights/best.pt`.
- [ ] **Step 5: Verify git status and packaging**
  Run: `git status` to verify clean tracking.

---

### Task 2: Storage Portability & Desktop Security Validation

**Files:**
- Modify: `src/storage/evidence.py`, `src/desktop/views/settings_view.py`
- Test: `tests/test_snapshot_index.py`, `tests/test_security_hardening.py`

**Interfaces:**
- Consumes: `src/core/validation.py:validate_model_path`, `PROJECT_ROOT`
- Produces: Relative snapshot paths in SQLite records, trusted model validation in Desktop GUI.

- [ ] **Step 1: Update snapshot persistence in src/storage/evidence.py**
  Ensure stored snapshot paths are normalized to relative paths (`data/evidence/filename.jpg`) or resolved safely against `PROJECT_ROOT`.
- [ ] **Step 2: Update model validation in desktop settings**
  In `src/desktop/views/settings_view.py`, wrap model path input with `validate_model_path(...)`.
- [ ] **Step 3: Run storage and security tests**
  Run: `.venv/bin/pytest tests/test_snapshot_index.py tests/test_security_hardening.py -v`
  Expected: PASS

---

### Task 3: Thin Shell `app.py` & Authentication Gate

**Files:**
- Modify: `app.py`, `src/ui/app_context.py`
- Test: `tests/test_app_smoke.py`, `tests/test_production_hardening.py`

**Interfaces:**
- Consumes: `src.ui.pages.{live_feed, video_file, image_analysis, evidence_log, system_settings}`, `src.security.auth.{is_auth_configured, verify_password}`, `src.observability.logging_setup.configure_logging`
- Produces: Streamlit web interface with modular routing and authentication.

- [ ] **Step 1: Implement authentication & logging bootstrap in app.py**
  Configure logging, check `SAFE_SIGHT_AUTH_REQUIRED` / runtime auth status, render login screen if unauthenticated.
- [ ] **Step 2: Implement thin page router in app.py**
  Replace monolithic 1,438-line `app.py` with dynamic dispatch delegating to `src/ui/pages/` using `build_context()`.
- [ ] **Step 3: Verify all 5 pages render via smoke test**
  Run: `.venv/bin/pytest tests/test_app_smoke.py -v`
  Expected: PASS

---

### Task 4: Ruff Linter & Code Quality Remediation (415 Errors -> 0)

**Files:**
- Modify: Codebase files across `src/`, `app.py`, `tests/`, `scripts/`, `desktop.py`
- Test: Ruff check command

**Interfaces:**
- Consumes: Python AST / Ruff ruleset
- Produces: 0 lint errors, clean imports, resolved loop variable capture and redefinition bugs.

- [ ] **Step 1: Run automated safe fixes**
  Run: `.venv/bin/ruff check --fix .`
- [ ] **Step 2: Fix loop variable captures (B023) and redefinitions (F811)**
  Ensure all default parameter captures in lambda callbacks in `components.py` and unique definitions in `renderer.py` are fixed.
- [ ] **Step 3: Fix manual lint violations**
  Clean up remaining unfixable errors (e.g. DTZ005, S110, PLW1508).
- [ ] **Step 4: Verify zero linter errors**
  Run: `.venv/bin/ruff check .`
  Expected: `All checks passed!`

---

### Task 5: End-to-End Verification & Production Readiness Check

**Files:**
- Test: All files in `tests/`, `scripts/prod_readiness_check.py`

**Interfaces:**
- Consumes: Entire application test suite and readiness verification script.
- Produces: Full green test suite and production verification receipt.

- [ ] **Step 1: Run full pytest suite**
  Run: `.venv/bin/pytest tests/ -v`
  Expected: 127+ passed.
- [ ] **Step 2: Run production readiness check script**
  Run: `.venv/bin/python scripts/prod_readiness_check.py`
  Expected: 18/18 checks PASS.
- [ ] **Step 3: Git commit baseline**
  Stage all files and commit clean production-hardened baseline.
