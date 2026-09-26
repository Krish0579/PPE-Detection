# Deployment Checklist — SAFE SIGHT AI v1.0

- [ ] Reviewed `models/best.pt` in place; SHA-256 recorded; AGPL/commercial license cleared.
- [ ] `.env` created from `.env.example`; secrets set; file excluded from git (`git check-ignore .env`).
- [ ] `PPE_ENABLE_MODEL_UPLOAD=false`, `PPE_ALLOW_EXTERNAL_MODEL_PATH=false` in production.
- [ ] `make prod-check` exits 0; `ruff check .` clean; `pytest tests/ -q` green.
- [ ] `docker build -t safesight-ai:1.0.0 .` succeeds; image runs as UID 10001; `/app/data` persisted.
- [ ] TLS terminating proxy (see `config/prod/nginx.example.conf`); HSTS + hardened headers verified.
- [ ] Ingress restricted to operator network/VPN; Streamlit origins/hosts set to approved domains.
- [ ] Daily `scripts/backup_evidence.py` scheduled; restore drill completed.
- [ ] Retention (`PPE_EVIDENCE_RETENTION_DAYS`) + privacy impact assessment signed off.
- [ ] Per-camera validation + human incident-review process documented; drift monitoring assigned.
