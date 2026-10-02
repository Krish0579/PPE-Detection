# SAFE SIGHT AI — Production Readiness & UI/UX Enhancement Plan

**Date:** 2026-04-22  
**Project:** Safe Sight AI — On-premise PPE-compliance computer vision monitoring  
**Architecture:** Streamlit web app + PySide6 desktop client + YOLO inference engine  

---

## 1. Executive Summary

Safe Sight AI is a **functional, well-architected** PPE detection platform with strong UI theming,
real-time video pipelines, and comprehensive compliance tracking. This plan addresses the
remaining gaps that prevent it from being **deployment-ready in regulated industrial environments**.

Priorities are labelled **P0** (blocker for production deployment), **P1** (high value, next release),
and **P2 (nice to have, future iteration).**

---

## 2. Priority Action Items

### 2.1 Authentication & Authorization (P0)

| Item | Effort | Current | Target |
|------|--------|---------|--------|
| Role-based access control | 3 days | `is_authenticated` binary flag | `admin`, `supervisor`, `operator`, `auditor` roles |
| Session expiry & idle timeout | 1 day | None | 15-min idle → lock screen |
| Audit trail for user actions | 2 days | None | Every settings change, alert resolution, model swap logged |
| Integration with LDAP/OIDC/SSO | 3–5 days | Static password SHA256 | Enterprise IdP support via `python-social-auth` |
| Multi-factor authentication | 2 days | None | TOTP via `pyotp` for admin accounts |

**Implementation:** Extend `src/security/auth.py` with a user store (SQLite), role decorators on pages, and session timestamps.

---

### 2.2 Security Hardening (P0)

| Item | Effort | Current | Target |
|------|--------|---------|--------|
| Secrets management | 1 day | Env vars + `.env` | Encrypted config file or HashiCorp Vault integration |
| Input sanitization | 2 days | Basic `escape()` on HTML | OWASP-recommended sanitization on all user inputs |
| Rate limiting on auth endpoints | 1 day | None | 5 attempts/min → 30s lockout |
| HTTPS redirect in Docker | 0.5 day | Plain HTTP | Auto-redirect, HSTS headers |
| CVE scanning in CI | 1 day | Manual `pip-audit` | Pre-commit hook + CI gate |

---

### 2.3 Monitoring & Observability (P0)

| Item | Effort | Current | Target |
|------|--------|---------|--------|
| Structured JSON logging | 2 days | Plain Python `logging` | JSON logs with correlation IDs for log aggregators (Loki, ELK) |
| Prometheus metrics endpoint | 2 days | None on web | Expose `/metrics` with inference latency, violation rate, uptime |
| Health check page | 1 day | Docker HEALTHCHECK only | Full dependency health: model loaded, camera accessible, disk space, DB |
| Sentry/error tracking integration | 1 day | None | Breadcrumb trail on production errors |
| Alertmanager integration | 1 day | None | Webhook on sustained violation rate > threshold |

**Implementation:** Add `src/observability/metrics.py` — Prometheus client counters + structured logging adapter.

---

### 2.4 Testing & Quality Gates (P0)

| Item | Effort | Current | Target |
|------|--------|---------|--------|
| Raise coverage floor | 3 days | 65% | 80% branch coverage |
| Integration tests with real model | 2 days | Unit tests only | Docker Compose test suite with mock camera feeds |
| Performance regression benchmarks | 2 days | None | CI-enforced FPS floor (≥15 FPS on reference hardware) |
| API contract tests | 1 day | None | Verify all page renders don't raise exceptions |
| Data integrity tests | 1 day | None | Evidence storage round-trip, DB migration forward/backward |

---

### 2.5 UI/UX — Polish & Industry‑Readiness (P1)

#### 2.5.1 Mobile & Responsive Design

| Item | Effort | Target |
|------|--------|--------|
| Responsive metric grid | 1 day | 4-col → 2-col → 1-col breakpoints (768px, 480px) |
| Touch-friendly navigation | 1 day | Larger tap targets, swipe gestures on tablets |
| Viewport meta for mobile browsers | 0.5 day | Proper `viewport` + `touch-action` |
| Sidebar collapses on small screens | 1 day | Hamburger toggle, auto-collapse < 900px |

The existing theme (`src/ui/theme.py`) already includes partial responsive rules
(`@media (max-width: 1280px)`, `768px`). Extend to cover all page components.

#### 2.5.2 Accessibility (WCAG 2.1 AA)

| Item | Effort | Target |
|------|--------|--------|
| Colour contrast audit | 1 day | All text/background combos ≥ 4.5:1 |
| ARIA labels on custom components | 2 days | Keyboard navigation, screen reader support |
| Focus indicators | 1 day | Visible focus ring on all interactive elements |
| `prefers-reduced-motion` compliance | 0.5 day | Already partial — audit and complete (X7 item) |
| Alt text on camera frames | 1 day | Descriptive alt text for `st.image` outputs |

#### 2.5.3 Performance UX

| Item | Effort | Target |
|------|--------|--------|
| Skeleton loading states everywhere | 2 days | `render_skeleton_block()` already exists — wire into all data-dependent panels |
| Optimistic UI updates | 3 days | Show "Acknowledged" states before server confirms |
| WebSocket-based real-time updates | 3 days | Replace 0.5s polling fragment with push via `st_connection` or SSE bridge |
| Lazy-load non-critical panels | 1 day | Defer rendering of trend charts and zone map until visible |
| Infinite scroll on event log | 1 day | Virtualised list via `st.dataframe` pagination |

#### 2.5.4 Visual & UX Enhancements

| Item | Effort | Target |
|------|--------|--------|
| Multi-language i18n support | 5 days | `gettext`-based `.po` files; English + Spanish + French initial |
| Onboarding wizard / first-run tour | 2 days | Step-by-step guide for new operators |
| Customizable dashboard layout | 3 days | Drag-and-drop panel reordering (St. fragments) |
| Notification centre | 2 days | In-app bell icon with unread count for alerts |
| Dark mode session persistence | 1 day | Store preference in `localStorage`, not just session_state |
| Export dashboard as PDF snapshot | 2 days | Full-page PDF with all visible panels |

#### 2.5.5 Error Handling & Resilience

| Item | Effort | Target |
|------|--------|--------|
| Page-level error boundaries | 1 day | Each page catches exceptions → friendly fallback, not Streamlit traceback |
| Graceful camera failure recovery | 1 day | Auto-retry camera open with exponential backoff |
| Offline/ degraded mode banner | 1 day | Detect missing model → clear banner + demo mode fallback |
| Connection status indicator | 1 day | WebSocket ping/pong with visual indicator |

---

### 2.6 Data Layer & Persistence (P1)

| Item | Effort | Current | Target |
|------|--------|---------|--------|
| Database migration system | 2 days | SQLite direct | Alembic-managed migrations |
| Scheduled evidence pruning | 1 day | Manual button | Background scheduler (APScheduler) |
| Backup automation | 2 days | Manual `scripts/backup_evidence.py` | Cron-based or systemd timer, S3/cloud compatible |
| Read replica support | 3 days | None | Separate read-only DB for dashboard queries |
| Data retention policy UI | 1 day | None | Configurable retention in Settings page |

---

### 2.7 Deployment & DevOps (P1)

| Item | Effort | Current | Target |
|------|--------|---------|--------|
| CI/CD pipeline (GitHub Actions) | 2 days | None | Lint → test → build → deploy per branch |
| Docker Compose with dependencies | 1 day | Single Dockerfile | + Redis cache, Postgres optional, nginx reverse proxy |
| Kubernetes manifests | 2 days | `k8s-deployment.example.yaml` | Production-ready Helm chart |
| Terraform infrastructure | 3 days | None | AWS/Azure/GCP module for VM + networking |
| Automatic model update from registry | 2 days | Manual file copy | Pull from Hugging Face or S3 on restart |
| Health-check-driven rolling update | 1 day | None | K8s readiness + liveness probes |

---

### 2.8 Desktop App Hardening (P2)

| Item | Effort | Current | Target |
|------|--------|---------|--------|
| Auto-update mechanism | 3 days | None | Electron-style updater for PyInstaller builds |
| Application signing & notarization | 2 days | None | macOS `.app` notarization, Windows Authenticode |
| Offline mode | 1 day | None | Full local SQLite sync with cloud on reconnect |
| Native system tray | 1 day | None | Minimise to tray with status icon |
| Hardware acceleration detection | 1 day | None | GPU/CPU selector in preferences |

---

## 3. Implementation Phases

### Phase 1: Production Minimum (Weeks 1–2)
1. Auth & RBAC overhaul
2. Secrets management + env-based config
3. Structured logging + Prometheus metrics
4. Raise test coverage to 80%
5. WCAG colour contrast + focus indicators

### Phase 2: Operational Excellence (Weeks 3–4)
1. Database migrations (Alembic)
2. CI/CD pipeline (lint → test → build → deploy)
3. Docker Compose with Redis + nginx
4. Sentry/error tracking
5. Session timeout + idle lock

### Phase 3: UI/UX Transformation (Weeks 5–7)
1. Responsive design overhaul (mobile + tablet)
2. Skeleton loading states (all panels)
3. WebSocket real-time updates
4. Onboarding tour / first-run wizard
5. Notification centre
6. i18n (English + Spanish)
7. Dark mode localStorage persistence

### Phase 4: Enterprise Scale (Weeks 8–10)
1. K8s/Helm deployment manifests
2. Auto-backup + scheduled pruning
3. SSO/LDAP integration
4. Performance regression CI gate
5. Customizable dashboard layout
6. Desktop app auto-update + signing

---

## 4. Measurement & KPIs

| Metric | Current | Target |
|--------|---------|--------|
| Test coverage (branch) | 65% | ≥80% |
| Page load time | ~2.0s | ≤800ms |
| Inference FPS (balanced mode) | ~25 | ≥30 |
| Accessibility score (Lighthouse) | Unknown | ≥90 |
| Mobile usability | Poor | Full responsive |
| Operator error rate | Unknown | <1% (targeting zero) |
| Time to first meaningful render | ~3s | ≤1.5s |
| Crash-free session rate | Unknown | ≥99.9% |

---

## 5. Immediate Next Steps (Do This Now)

1. **Create a `config/prod/secrets.env.example`** with placeholders for every secret
2. **Set up GitHub Actions** workflow that runs `ruff check`, `pytest --cov`, and `pip-audit`
3. **Add RBAC decorators** to `src/security/auth.py` — three lines per page
4. **Wire skeleton states** into `live_feed.py` — `render_skeleton_block()` exists but isn't shown during camera init in all branches
5. **Run the production hardening test suite** (`tests/test_production_hardening.py`) and fix its failures

---

## 6. Architecture Diagram (Proposed Addition)

```
┌──────────────────────────────────────────────────┐
│                   Load Balancer                    │
├──────────────────────┬───────────────────────────┤
│   Streamlit Web UI   │   PySide6 Desktop Client   │
│   (:8501)            │   (PyInstaller bundle)     │
├──────────┬───────────┴──┬────────────────────────┤
│ Auth     │  Inference   │  Observability          │
│ (RBAC)   │  (YOLOv8)    │  (Prometheus + Loki)    │
├──────────┴──────────────┴────────────────────────┤
│              Data Layer                            │
│  SQLite/Postgres   │   Redis Cache   │   S3/FS    │
│  (Events + Users)  │   (Session)     │ (Evidence) │
└───────────────────────────────────────────────────┘
```