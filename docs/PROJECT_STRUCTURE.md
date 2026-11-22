# Project structure

SAFE SIGHT AI keeps the launchers at the repository root because Streamlit and
PySide6 tooling expect a simple entry point. Application code is grouped by
responsibility under `src/`; operational material stays under `docs/`,
`scripts/`, `config/`, and `tests/`.

```text
.
├── app.py                       # Browser workspace launcher (Streamlit)
├── desktop.py                   # Desktop workspace launcher (PySide6)
├── src/
│   ├── alerts/                  # Webhook delivery and alert payloads
│   ├── compliance/              # Compliance and regulatory rules
│   ├── config/                  # Validated environment and app settings
│   ├── core/                    # Core logic and models
│   │   ├── models.py            # Core domain models
│   │   ├── events.py            # Event system
│   │   ├── rules.py             # Business rules
│   │   ├── incident_manager.py  # Incident management
│   │   └── shifts.py            # Shift management
│   ├── desktop/                 # Desktop window, views, widgets, and workers
│   ├── integrations/            # External integrations
│   ├── observability/           # Logging, health, and metrics
│   │   ├── metrics.py           # Application metrics
│   │   └── system_health.py     # System health and checks
│   ├── privacy/                 # Privacy-preserving evidence transforms
│   ├── reporting/               # Report generation
│   ├── security/                # Authentication, sessions, and permissions
│   │   ├── rbac.py              # Role-based access control
│   │   ├── passwords.py         # Password management
│   │   ├── rate_limit.py        # Rate limiting logic
│   │   └── sessions.py          # Session management
│   ├── storage/                 # Data storage and retention
│   │   ├── repositories.py      # Data access repositories
│   │   ├── audit_log.py         # Audit logging
│   │   └── retention.py         # Data retention policies
│   ├── ui/
│   │   ├── components/          # Reusable browser UI primitives and panels
│   │   ├── pages/               # Browser routes, split by user workflow
│   │   ├── navigation.py        # Route metadata and sidebar sections
│   │   ├── app_context.py       # Session state and runtime dependencies
│   │   ├── status.py            # Measured workspace status vocabulary
│   │   └── theme*.py            # Browser design tokens and CSS
│   ├── video/                   # Video ingestion and processing
│   │   ├── ring_buffer.py       # Frame ring buffer
│   │   └── connection.py        # Stream connection logic
│   └── vision/                  # Computer vision pipelines
├── config/prod/                 # Example deployment configurations
├── data/                        # Local runtime evidence (not source-controlled)
├── deployment/                  # Docker and deployment configurations
├── docs/                        # Plans, runbooks, deployment, and this guide
├── models/                      # Trusted local checkpoints (ignored by git)
├── scripts/                     # Backup, install, release, and readiness tools
│   ├── benchmark.py             # Blueprint §17 benchmark script
│   └── restore.py               # Blueprint §14 restore script
└── tests/                       # Unit, domain, security, UI, and smoke tests
```

## Naming rules

- Use `snake_case.py` for Python modules and `test_<area>.py` for tests.
- Name browser routes after the operator task (`evidence_log.py`,
  `image_analysis.py`) rather than the implementation detail.
- Keep reusable browser UI in `src/ui/components/`; keep route-specific logic in
  `src/ui/pages/`.
- Put deployment examples in `config/` and procedural guidance in `docs/`.
- Do not commit runtime databases, uploads, caches, model weights, or secrets.
- Preserve `app.py` and `desktop.py` as stable launch commands; they are thin
  entry points, not a place for feature logic.

## Common commands

```bash
.venv/bin/python -m streamlit run app.py
.venv/bin/python desktop.py
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
make prod-check
```
