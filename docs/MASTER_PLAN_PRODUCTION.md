# SAFE SIGHT AI — Production-Grade Master Plan (v1.0)

> Status: **implemented as Phase 5** on top of Phases 0–4 (see `docs/IMPROVEMENT_PLAN.md`).
> Goal: on-prem, evidence-first PPE operations at industrial reliability.

## 1. Where the project stood

Mature already: Streamlit + PySide6 desktop, YOLO 11-class PPE, worker association +
tracking, SQLite WAL audit trail, DB-backed snapshot index, atomic evidence writes,
retention caps, non-root Docker, lockfile, basic CI, 100+ tests, ruff clean.

## 2. Production gaps closed in this pass

| # | Gap | Fix (this session) |
|---|-----|--------------------|
| P0 | `ALLOW_EXTERNAL_MODEL_PATH=True` / `MODEL_UPLOAD_ENABLED=True` hardcoded, contradicting the trusted-checkpoint policy | `src/config/settings.py` now env-driven, default `false`; `src/config/runtime.py` validates and warns |
| P1 | Scattered env handling, no validated runtime surface | `src/config/runtime.py::load_runtime_config()` — one typed surface, secure defaults, `validated()` warnings |
| P2 | No structured logging / version / health payload | `src/observability/logging_setup.py`, `src/observability/health.py`, `src/__version__.py` (`1.0.0`) |
| P3 | No operator gate / RBAC for shared deployments | `src/security/auth.py` — optional SHA-256 password gate + `operator/supervisor/admin` permissions |
| P4 | No outbound alerting (Slack/webhook) | `src/alerts/webhooks.py` — stdlib POST, allowlist, `build_violation_payload()` |
| P5 | No privacy blur for evidence hand-off | `src/privacy/blur.py` — OpenCV Gaussian blur on copies; sealed DB keeps originals |
| P6 | Single USB camera only | `src/video/camera_registry.py` — `usb:/rtsp:/http:/demo` registry, redacted diagnostics, `PPE_CAMERA_SOURCES` |
| P7 | No backup / retention job | `src/storage/backup.py` + `scripts/backup_evidence.py` — SQLite online backup, retention purge mirrored to index |
| P8 | No prod compose / TLS / k8s / metrics example | `config/prod/docker-compose.prod.yml`, `nginx.example.conf`, `prometheus.example.yml`, `k8s-deployment.example.yaml` |
| P9 | CI without supply-chain signal | `ci.yml` adds offline readiness gate, Trivy scan (report), SBOM (best-effort) |
| P10 | No repeatable operator gates | `Makefile`, `scripts/prod_readiness_check.py` (exit 0/2), expanded `.env.example` |

## 3. What remains intentionally out of scope

- Full multi-camera live grid + RTSP reconnection supervisor (registry + parsing done; UI multiplexing is next).
- Hosted REST API / VMS integration (webhook payload schema is the contract; FastAPI service is Phase 6).
- Postgres migration path (SQLite WAL + backup covers single-site; multi-site needs a migration + tenancy design).
- Model registry / drift dashboard / ONNX-TensorRT export (weights stay in `models/`, versioned by release tag).
- SSO/OIDC (password gate covers small crews; enterprise SSO needs an identity provider decision).

## 4. Deployment path (happy path)

1. Copy a reviewed checkpoint to `models/best.pt`; `cp .env.example .env` and set domain secrets.
2. `make prod-check` → exit 0. `docker build -t safesight-ai:1.0.0 .`.
3. `cd config/prod && IMAGE_TAG=1.0.0 docker compose -f docker-compose.prod.yml up -d`.
4. Terminate TLS at the Nginx example; restrict ingress; schedule `scripts/backup_evidence.py` daily.
5. Validate per-camera precision/recall, define human review + retention policy, monitor drift.

## 5. Validation

- `ruff check .` clean; `pytest tests/ -q` green (incl. new `tests/test_production_hardening.py`, 30 tests).
- `python scripts/prod_readiness_check.py` exit 0 on a clean checkout.
- Headless `streamlit run app.py` → HTTP 200 on `/` and `/_stcore/health`.
- Commercial reminder: Ultralytics YOLO is AGPL — obtain a commercial license before proprietary sale.
