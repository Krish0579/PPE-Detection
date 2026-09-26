# Changelog — SAFE SIGHT AI

All notable changes are recorded here. Version source of truth: `src/__version__.py`.
Release discipline: `docs/PRODUCTION_MASTER_PLAN.md` §8.

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
