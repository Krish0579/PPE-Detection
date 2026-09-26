# Production Runbook — SAFE SIGHT AI

## Daily
- Confirm `/_stcore/health` is 200 and `model_loaded=true`.
- Review Evidence Log → Incident Management; acknowledge/resolve with a second pair of eyes for CRITICAL.
- Check disk: Evidence dir growth, oldest capture age, backup job timestamp.

## Weekly
- Run `make prod-check`; review `validated()` warnings (external paths / uploads must stay OFF on exposed hosts).
- Spot-check 20 captures against live conditions (angle, lighting, PPE policy); log precision/recall notes.
- Rotate operator password (`SAFE_SIGHT_OPERATOR_PASSWORD_SHA256`); verify webhook delivery with one test event.

## Monthly
- Full backup restore drill: `backup_sqlite` → fresh host → `query_events` count matches.
- Retention audit: confirm files older than `PPE_EVIDENCE_RETENTION_DAYS` are purged from disk + index.
- Model review: only promote reviewed `.pt` weights into `models/`; record SHA-256 + approver in the release notes.

## Incidents
- Evidence export: use Certified Audit Export; enable `PPE_PRIVACY_BLUR_FACES=true` workflow (blur copies) before external hand-off.
- Webhook outage: events remain sealed in SQLite; replay from `query_events()` — webhooks are notifications, never the record.
- Camera denial (macOS TCC): grant Terminal/Streamlit camera access, or use Direct Browser Camera / WebRTC (browser holds permission).

## Never do
- Never enable `PPE_ENABLE_MODEL_UPLOAD` / `PPE_ALLOW_EXTERNAL_MODEL_PATH` on an internet-exposed instance.
- Never copy `.env` with real secrets into images, tickets, or chat.
- Never treat model output as a replacement for an on-site safety officer.
