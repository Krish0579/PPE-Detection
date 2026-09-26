# SAFE SIGHT AI — Company Production Master Plan (v1.0)

> Owner: Product / Delivery Manager. Status: **approved for build-out**.
> Engineering baseline: `docs/MASTER_PLAN_PRODUCTION.md` (Phase 5 delivered).
> Operations: `docs/PRODUCTION_RUNBOOK.md`. Go-live checks: `docs/DEPLOYMENT_CHECKLIST.md`.
> History: `docs/IMPROVEMENT_PLAN.md`, `CHANGELOG.md`. Security contact: `SECURITY.md`.
>
> **Assumptions (confirm at kickoff):** single-site on-prem deployment; supervisor-operated;
> Streamlit + PySide6 desktop; customer provides cameras/network/power; model weights customer-reviewed.
> Open decisions are marked **[DECISION]**.

## 1. Executive summary

SAFE SIGHT AI turns PPE detection into an operator review workflow with defensible evidence.
This plan makes it sellable, deployable, supportable, and legally shippable by closing every
non-code gap a customer, auditor, or insurer will ask about: scope, requirements, compliance,
risks, service levels, release discipline, training, and sign-off. Target: first paid pilot in
one site, then multi-site rollout.

## 2. Objectives and success criteria

| # | Objective | Measurable criterion |
|---|-----------|----------------------|
| O1 | Safe, honest operation | Zero unverified safety claims in UI/docs; every install has a signed validation record |
| O2 | Evidence that survives audit | 100% of exported incidents traceable to SQLite record + capture; restore drill passes |
| O3 | Reliable shifts | SLO: app healthy during 99.5% of scheduled monitoring hours per site/month |
| O4 | Shippable legally | AGPL cleared (commercial YOLO license **or** AGPL-compliant distribution), DPIA signed, retention policy signed |
| O5 | Supportable | Every customer has named support tier, runbook, backup proof, and trained operators |

## 3. Scope

**In:** live/video/image PPE monitoring, worker association, zones, evidence + certified exports,
hardening already delivered, deployment packaging, validation protocol, training, tier-1/2 support.
**Out (roadmap, not promised):** multi-camera live grid, RTSP auto-reconnect supervisor, hosted REST API,
Postgres multi-site, SSO/OIDC, ONNX/TensorRT edge builds, drift dashboard. Selling any of these as
"included" is a contract defect — track them in §12.

## 4. Stakeholders and RACI

| Role | Responsibility | R/A/C/I highlights |
|------|---------------|--------------------|
| Sponsor (customer exec) | Funds, accepts residual risk | **A**ccepts go-live, DPIA, retention |
| Safety manager | PPE policy, validation, incident review | **R**esponsible for validation record + review SOP |
| IT / facilities | Network, power, cameras, TLS, backups | **R**esponsible for infrastructure + restore drill |
| Vendor delivery lead (us) | Install, configure, train, hand over | **R**esponsible for deployment + docs |
| Vendor engineering | Defects, releases, model updates | **R**esponsible for fix SLAs |
| Operators | Daily monitoring, acknowledge/resolve | **R**esponsible for shift log |
| Legal/DPO | Licenses, DPIA, worker consultation | **A**pproves privacy + contract terms |

## 5. Requirements catalog (the whole picture)

### 5.1 Functional (what it must do)
- FR1–FR5: detect 5 PPE categories on live, video-file, and image inputs with per-class thresholds.
- FR6: associate PPE to workers, preserve identities across frames, debounce 1-frame dropouts.
- FR7: zones incl. restricted-zone violations and occupancy counts.
- FR8: atomic evidence capture, snapshot index with date/type filters, inspect lightbox, path-safe delete.
- FR9: certified exports (PDF/CSV/JSON/ZIP+manifest) with UTC timestamps; privacy-blurred hand-off copies.
- FR10: model trust boundary — reviewed `models/` weights only; uploads/external paths OFF in production.

### 5.2 Non-functional (how well it must behave)
- NFR-Performance: ≥15 FPS live inference on target hardware; image audit <5 s; startup <90 s.
- NFR-Reliability: SLO 99.5% of scheduled hours; auto-recover camera thread; no silent evidence loss.
- NFR-Scalability: 1 camera + 500 GB evidence per node baseline; retention enforced automatically.
- NFR-Maintainability: releases versioned (`src/__version__.py` + CHANGELOG), one-command readiness gate.
- NFR-Usability/Accessibility: keyboard operation, text+color status signals, WCAG AA contrast (locked by tests).
- NFR-Portability: Docker non-root image + native desktop; no cloud dependency at runtime.

### 5.3 Security
- Hardened defaults (validated by `scripts/prod_readiness_check.py`); secrets only via env, never in images.
- Optional operator gate + RBAC (`operator/supervisor/admin`); **[DECISION]** SSO if >20 users.
- Reverse-proxy TLS, same-origin Streamlit, 500 MB upload caps, path/traversal validation, SHA-256 model log.
- Supply chain: lockfile installs, SBOM per release, Trivy report, disclosure via `SECURITY.md`, patch SLA §7.

### 5.4 Safety, privacy, and legal (do not ship without these)
- **Efficacy honesty:** decision support only; UI/docs make no certification claims; safety-officer review SOP signed.
- **Site validation protocol (per camera):** precision/recall sampled across angles, lighting, shifts, PPE policy,
  and workforce groups (helmet/vest/boots/gloves/goggles); fairness check across groups; record signed by safety manager.
- **Privacy:** DPIA + worker consultation before recording; retention schedule signed (default 30 d);
  blur workflow for external hand-off; no face recognition, ever.
- **Licensing:** **[DECISION]** Ultralytics commercial license **or** AGPL-compliant distribution — cleared before
  any proprietary sale; model-weight and training-data rights documented; third-party notices shipped.
- **Regulatory watch:** EU AI Act assessment for workplace monitoring (likely high-risk obligations: risk
  management, logging, human oversight, transparency); OSHA/ISO 45001 record-keeping alignment; local
  labor/works-council rules per jurisdiction.

### 5.5 Operations
- Topology: on-prem node + TLS proxy (§`config/prod/`); health `/_stcore/health`; structured logs.
- Backup/DR: daily SQLite online backup + retention purge; RPO ≤ 24 h, RTO ≤ 4 h per single node; quarterly restore drill.
- Monitoring: health uptime, FPS/latency, evidence-disk growth, backup age, model version; webhook for violations.
- Change control: releases only via §8 process; model promotions logged with SHA-256 + approver.

### 5.6 Quality and acceptance
- Factory acceptance (FAT): full test suite green, gate exit 0, Docker build, smoke on reference clips.
- Site acceptance (SAT): per-camera validation record, backup/restore proof, operator training completion,
  runbook + retention + DPIA signatures. No SAT sign-off = no go-live.

## 6. Service levels and incident response

| Severity | Example | Response | Resolution target |
|----------|---------|----------|-------------------|
| SEV-1 | Monitoring blind during scheduled hours; evidence loss suspected | 1 business h | 4 h workaround, 5 d fix |
| SEV-2 | Degraded FPS, export failure, false-alarm storm | 4 business h | 10 d fix |
| SEV-3 | Cosmetic, docs, tuning advice | 2 business d | Next release |
| Security | Suspected breach/data exposure | 1 h triage per `SECURITY.md` | Case-by-case, customer notified |

Support hours **[DECISION]**: business-hours baseline; 24/7 only as a priced option with on-call rota.

## 7. Risks and mitigations (register)

| Risk | Impact | Mitigation | Owner |
|------|--------|------------|-------|
| Model misses PPE in site conditions | Safety incident + liability | Per-camera validation + human review SOP; never auto-actuate | Safety mgr |
| AGPL breach on sale | Legal/financial | License decision before first quote; notices + offer text in image | Legal |
| Worker-privacy dispute | Shutdown, fines | DPIA + consultation + retention + blur before go-live | DPO |
| Camera/network outage blinds shift | Undetected violations | Health monitoring, fallback SOP (foot patrol), RTO 4 h | IT |
| Evidence disk fills | Loss of audit trail | Retention automation + disk alerts + backup proof | IT |
| Scope creep (multi-cam/API/SSO) | Missed dates | §3 out-of-scope list enforced at contracting | Delivery lead |
| Key-person dependency | Support collapse | Runbook + cross-training + escrow of build docs | Delivery lead |

## 8. Release process (engineering must follow)

1. Bump version (`python scripts/release.py --bump minor --dry-run`, then for real).
2. `ruff check` on touched modules; full `pytest`; `scripts/prod_readiness_check.py` exit 0.
3. `docker build`; record image digest + model SHA-256 in CHANGELOG.
4. Trivy + SBOM attached to the release note.
5. Customer-facing changes need docs + migration notes; model changes need re-validation record.
6. Tag `vX.Y.Z`; only tagged builds ship to sites.

## 9. Commercial and training

- Commercial: priced per site (cameras + retention tier); support tiers priced separately; model re-validation
  visits billable; travel + hardware pass-through. Warranty: defects per §6, never safety outcomes.
- Contract must-haves: license grant, AGPL position, data ownership (customer owns evidence), retention schedule,
  liability cap + decision-support disclaimer, termination + data-return clause.
- Training (per site, recorded): operator shift workflow (4 h), supervisor review + exports (2 h),
  IT backup/restore + proxy (2 h). Completion certificates gate SAT.

## 10. Milestones to first paid pilot

| Milestone | Exit criteria | Typical owner |
|-----------|---------------|---------------|
| M1 Plan sign-off | This doc + open **[DECISION]**s closed | Sponsor |
| M2 FAT | Suite green, gate 0, image builds, SBOM/Trivy filed | Engineering |
| M3 Site ready | Infra + TLS + cameras + backup schedule live | IT |
| M4 Validation | Per-camera record signed; review SOP live | Safety mgr |
| M5 Training + DPIA | Certificates + DPIA/retention signatures | DPO / delivery |
| M6 Go-live | SAT signatures in §11; support tier active | Sponsor |

## 11. Go-live sign-off

| Gate | Evidence | Signed |
|------|----------|--------|
| Validation record per camera | precision/recall + fairness notes | Safety manager ___ date ___ |
| Privacy + retention | DPIA, consultation, schedule | DPO ___ date ___ |
| Backup/restore proof | drill log + RPO/RTO met | IT ___ date ___ |
| License clearance | YOLO + weights rights filed | Legal ___ date ___ |
| Training complete | certificates | Delivery lead ___ date ___ |
| Support active | tier, hours, contacts | Sponsor ___ date ___ |

## 12. Roadmap (explicitly not in v1.0)

Multi-camera grid, RTSP supervisor, REST/VMS API, Postgres multi-site, SSO/OIDC, ONNX/TensorRT edge,
drift dashboard, active-learning loop. Each needs its own mini-plan + price before promising dates.

## 13. Metrics the manager reviews monthly

SLO attainment, SEV counts vs §6, validation drift notes, disk/backup health, support tickets by tier,
training completion, license/contract status, top violation trends per site.
