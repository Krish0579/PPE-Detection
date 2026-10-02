# SAFE SIGHT AI — Production & Industrial Readiness Plan (v2, refined)

> Refined 2026-09-27 from a deeper codebase audit at commit `23790a4`
> (156 tests green, ruff clean, coverage ~69%). Supersedes the v1 advancement
> plan in this file. Phases 0–5 (bugs, structure, UX, storage, hardening) are
> complete — see `docs/IMPROVEMENT_PLAN.md`.

---

## 1. Readiness Definitions

**Production ready** — secure by default, observable, recoverable, deployable,
monitored, documented, and regression-tested.

**Industrial ready** — runs 24/7 on a plant floor: multi-camera RTSP ingestion,
role-separated shift operations, evidence an operator can defend in an audit,
alerts that survive network blips, air-gapped install, known hardware sizing,
graceful degradation, and a maintenance mode.

### 1.1 Current-state scorecard (verified in this audit)

| Area | State | Evidence |
|------|-------|----------|
| CI/CD quality gates | ✅ strong | lint-test, dep-audit, docker-build, sbom+trivy jobs |
| Deployment artifacts | ✅ present | `config/prod/` compose, nginx, prometheus, k8s examples |
| Secure-by-default trust flags | ✅ done | `src/config/runtime.py` |
| Evidence retention & DB index | ✅ done | `evidence.py` prune/backfill |
| **RBAC enforcement** | ❌ dead code | `auth.py:30-38` `can()`/`ROLE_PERMISSIONS` never called |
| **Login hardening** | ❌ absent | no throttling, no session expiry/idle timeout |
| **Alert delivery reliability** | ❌ single-shot | `webhooks.py:105` — no retry/queue |
| **Health endpoint** | ❌ dead code | `health.py:12` `build_health_payload` never called |
| **Prometheus metrics** | ❌ absent | nothing to scrape; example config exists |
| **Evidence integrity** | ❌ absent | no SHA-256 per artifact/chain |
| **Camera resilience** | ❌ partial | error surfaced, no reconnect/watchdog |
| **DB migrations / restore drill** | ❌ absent | ad-hoc schema changes; restore unscripted |
| **Inference perf tooling** | ❌ absent | no benchmark, no ONNX, static frame-skip |
| **Multi-camera / RTSP UI** | ❌ unused | `camera_registry.py` parsed but not rendered |
| **Analytics surfaces** | ❌ unused | floor map / safety analytics / productivity built, never rendered |
| **Zones** | ❌ capacity-only | no intrusion/dwell alerts |

---

## 2. Workstreams

Each item: **verified gap → work → files → acceptance → tests**.

### W1 — Security, Access & Evidence Integrity *(production trust)*

| ID | Gap (verified) | Work | Files | Acceptance | Tests |
|----|----|------|-------|------------|-------|
| W1.1 | RBAC defined, never enforced; only `operator` exists; destructive ops ungated | Enforce `can()` at every consequential action (evidence delete, ZIP export, clear session, model upload/switch, settings write); admin role via separate `PPE_ADMIN_PASSWORD_SHA256`; supervisor read-only on evidence; UI hides/disables what the role cannot do | `src/security/auth.py`, `app.py`, `src/ui/pages/*` | operator cannot reach destructive actions; admin can; permissions table documented | unit: `can()` matrix; AppTest: role-gated button visibility |
| W1.2 | No throttling; sessions never expire | Login throttling (per-process exponential backoff after N failures) + session expiry (`PPE_SESSION_TTL_MIN`, default 480) + idle re-auth; constant-time compare already via `hmac.compare_digest` — verify | `src/security/auth.py`, `app.py` | lockout after 5 failures for backoff window; expired session forces re-login | unit: backoff table, expiry math; AppTest: gate re-locks |
| W1.3 | Evidence has no tamper evidence | SHA-256 per snapshot at write (column + filename manifest); event rows hash-linked (`sha256(prev_hash + payload)`) making silent edits detectable; `scripts/verify_evidence.py` verifies chain offline | `src/storage/evidence.py`, `scripts/verify_evidence.py` | chain verification passes on fresh DB; detects a tampered row/byte | unit: chain verify + tamper detection |
| W1.4 | No maintenance mode | `PPE_MAINTENANCE=1` → banner + inference paused + evidence sealed (no writes), UI still reachable for supervisors; readiness-gate check | `src/config/runtime.py`, `app.py` | mode engages without restart; no writes while sealed | unit: config parse + seal behavior |

### W2 — Reliability & Alerting *(industrial uptime)*

| ID | Gap | Work | Files | Acceptance | Tests |
|----|----|------|-------|------------|-------|
| W2.1 | Webhooks single-shot | Alert outbox: events enqueue to SQLite (`alert_outbox` table); worker thread posts with exponential backoff (3 tries), marks delivered/failed; failed rows visible + replayable in Settings; DLQ after final failure | `src/alerts/outbox.py` (new), `webhooks.py`, `evidence.py`, `src/ui/pages/system_settings.py` | transient failure → alert still delivered; replay works; no alert loss over 100-event burst | unit: enqueue/retry/replay; integration: fake urlopen failures |
| W2.2 | No camera watchdog / RTSP reconnect | Stream health watchdog: consecutive-failure detection, exponential reconnect backoff, per-camera status (OK/DEGRADED/DEAD) surfaced; auto-restart of capture worker; honest badges | `src/video/camera.py`, `camera_registry.py` | simulated stream death → auto-recovery ≤ 30 s; status correct in UI | unit: fake-clock backoff/reconnect state machine |
| W2.3 | No migration path | Versioned schema migrations (`PRAGMA user_version` + ordered migration scripts) applied on open; current ad-hoc `_init_db`/backfill folded in as migration 001 | `src/storage/evidence.py`, `src/storage/migrations.py` (new) | fresh + aged DB both open cleanly; migration idempotent, runs once | unit: fresh/aged/already-migrated DBs |
| W2.4 | Restore unvalidated | `scripts/restore_evidence.py` (restore into temp dir, verify DB opens + snapshot hashes match) + documented restore drill in runbook | `scripts/restore_evidence.py` (new), `docs/PRODUCTION_RUNBOOK.md` | drill script round-trips a backup end-to-end | unit: backup→restore→verify round-trip |

### W3 — Observability & Operability *(see the system)*

| ID | Gap | Work | Files | Acceptance | Tests |
|----|----|------|-------|------------|-------|
| W3.1 | Health payload dead code | Expose `/healthz` route: run lightweight Streamlit server-served health via `st.pages` static route or a tiny sidecar thread serving the payload (model, device, mode, uptime, db ok); k8s liveness/readiness wired to it | `src/observability/health.py`, `config/prod/k8s-deployment.example.yaml` | `GET /healthz` returns payload 200; k8s example uses it | integration: boot server, assert payload |
| W3.2 | No metrics | Prometheus text exporter: fps, inference ms, detections/person/violations counters, alert queue depth, camera states, snapshot count — scraped from telemetry state; port gated behind `PPE_ENABLE_METRICS` (default off, secure-by-default) | `src/observability/metrics.py` (new), `config/prod/prometheus.example.yml` | `curl /metrics` returns valid exposition; example scrape config matches | unit: exposition format; integration: endpoint up |
| W3.3 | No drift monitor | `scripts/drift_report.py`: weekly per-class confidence/count distributions from SQLite vs 30-day baseline; flags shifts; cron/launchd examples | `scripts/drift_report.py` (new) | flags synthetic drift in fixture DB; report human-readable | unit: drift detector on shifted vs stable fixtures |
| W3.4 | Coverage ratchet idle at 68 | Raise `fail_under` 68 → 74 after W1–W3 tests; 80 after W5 | `pyproject.toml` | CI green at new floor | CI itself |

### W4 — Inference Performance & Sizing *(measure → optimize)*

| ID | Gap | Work | Files | Acceptance | Tests |
|----|----|------|-------|------------|-------|
| W4.1 | No benchmark truth | `scripts/benchmark_inference.py`: cold start, warm FPS, p50/p95 latency × perf profile × backend; JSON to `data/benchmarks/`; `make benchmark` | `scripts/benchmark_inference.py` (new), `Makefile` | reproducible offline run with commit metadata | smoke: runs on synthetic frames |
| W4.2 | Torch-only inference | ONNX export + runtime path; `PPE_BACKEND=auto\|torch\|onnx` (auto = benchmark winner, persisted); parity guard | `src/core/detector.py`, `model_manager.py`, `requirements.txt` | box IoU ≥ 0.99 vs torch on evidence frames; speed delta recorded | unit: parity on fixtures |
| W4.3 | Static frame skip | Adaptive skip: skip only when measured inference ms exceeds capture budget; hysteresis to avoid flapping | `src/video/camera.py`, `settings.py` | target FPS held under load; no drops when idle | unit: fake-clock scheduler |
| W4.4 | Unbounded memory paths | Ring buffer (≤3 frames), explicit release after encode, single warmup, thread caps | `camera.py`, `pipeline.py` | flat RSS across 10-min simulated run | soak: RSS trend assert |
| W4.5 | No hardware sizing guidance | Benchmark-driven sizing table (CAMs × resolution → CPU/GPU profile) in docs; refreshed by benchmark output | `docs/SIZING.md` (new) | table cites measured numbers only | doc lint |

### W5 — Capability Advancement *(industrial features)*

| ID | Gap | Work | Files | Acceptance | Tests |
|----|----|------|-------|------------|-------|
| W5.1 | Registry unused in UI | Multi-camera grid (usb/rtsp/http/demo): per-camera tiles, status from W2.2, violation chips, focus mode; SIM honesty per tile | `src/ui/pages/live_feed.py`, `camera_registry.py` | 0/N cameras render; per-tile status; AppTest clean | AppTest + unit registry |
| W5.2 | Analytics never rendered | "Operations Dashboard" page: floor map, safety analytics, productivity view + persistent KPIs from SQLite; shift summary | `src/ui/pages/operations_dashboard.py` (new), `app.py`, desktop nav parity | renders with empty store; data from persisted trail | AppTest |
| W5.3 | Zones capacity-only | Restricted-zone entry alert (debounced once per entry), per-worker dwell time, explicit over-capacity events; distinct webhook payload | `ppe_associator.py`, `pipeline.py`, `webhooks.py` | entry fires once; dwell accumulates; capacity event logged | unit: entry/dwell/capacity |
| W5.4 | Webhook-only alerting | Optional SMTP digest channel (`PPE_SMTP_*`), off by default, evidence thumbnails, env-only secrets | `src/alerts/email.py` (new) | disabled unless configured; digest renders | unit: fake SMTP |
| W5.5 | No model A/B path | Image Analysis: two trusted checkpoints side-by-side (overlay diff + metric table) for validated upgrades | `image_analysis.py`, `model_manager.py` | graceful single-model fallback; diff correct | unit + AppTest |
| W5.6 | No headless API | Opt-in FastAPI (`PPE_ENABLE_API=true`): `/healthz`, `/version`, `/infer` (image→workers), `/events`; same validation + trust policy | `src/api/` (new), `Makefile`, `Dockerfile` | off by default; endpoints + rejection paths covered | API tests |

### W6 — Compliance & Release Gates *(ship it safely)*

| ID | Gap | Work | Files | Acceptance |
|----|----|------|-------|------------|
| W6.1 | Readiness gate partial | Extend `prod_readiness_check.py`: auth configured in prod, maintenance flag documented, backup freshness, evidence chain verifies, metrics opt-in documented | `scripts/prod_readiness_check.py` | exit 2 on missing prod-critical config |
| W6.2 | Upgrade/rollback undefined | Versioned release procedure doc: tag → benchmark → readiness gate → deploy → rollback (prior image + DB migration-safe check) | `docs/RELEASE_PROCEDURE.md` (new) | dry-run documented against compose |
| W6.3 | Desktop drift | Share theme tokens + nav parity with web; document deliberate gaps | `src/desktop/` | desktop boots; parity checklist in doc |
| W6.4 | Legal/privacy guardrails | Keep AGPL + DPIA gates visible in release checklist; no claims of certification | `docs/RELEASE_PROCEDURE.md` | checklist enforced at release |

---

## 3. Execution Milestones

| Milestone | Contents | Rationale | Est. effort |
|-----------|----------|-----------|-------------|
| **M1 — Trust** | W1.1–W1.4, W2.1 | Security + alert reliability first: nothing else matters if evidence/alerts can't be trusted | ~2 sessions |
| **M2 — Visibility** | W3.1–W3.3, W2.3–W2.4, W4.1 | Health, metrics, migrations, restore drill, and the benchmark baseline before optimizing | ~2 sessions |
| **M3 — Speed & Scale** | W4.2–W4.5, W2.2 | Optimize against W4.1 numbers; watchdog for 24/7 capture | ~2 sessions |
| **M4 — Capability** | W5.1–W5.6, W6.1–W6.4, W3.4 (ratchet→80) | Features on a trustworthy, measured foundation; release gates last | ~3 sessions |

Dependencies: W2.1 before W5.3/W5.4 (outbox carries new alert types) · W4.1 before W4.2/W4.5 · W2.2 before W5.1 (per-camera status) · W2.3 before any schema-adding item.

## 4. Definition of Done (every milestone)

- `python3 -m pytest tests -q` green; `ruff check .` + `ruff format --check` clean
- Coverage ratchet never lowered; every new surface renders with an empty evidence store
- Perf items include before/after `make benchmark` JSON; accuracy parity locked by tests
- No secrets in code; no unverified safety/certification claims; readiness gate passes

## 5. Risk Register

| Risk | Mitigation |
|------|------------|
| Inference changes regress accuracy (W4.2) | Box-output parity tests vs evidence snapshots gate every backend change |
| AGPL (Ultralytics) | Commercial license or AGPL compliance before proprietary sale — carried in release checklist (W6.4) |
| Worker imagery privacy | DPIA required before go-live; blur tooling exists; carried in release checklist |
| Scope creep | Each item independently shippable; explicit defer allowed without blocking a milestone |
| Migration breakage (W2.3) | Migrations additive + idempotent; restore drill (W2.4) is the rollback path |

## 6. Out of Scope (this plan)

Person re-identification across cameras, multi-tenant SaaS, cloud model serving, video archival/NVR storage beyond existing retention, mobile-native apps.
