# SAFE SIGHT AI

SAFE SIGHT AI is a private-network PPE review workspace. It runs a reviewed
Ultralytics YOLO checkpoint against live cameras, recorded video, and still
images; associates required equipment with people; and retains incident
evidence in a local SQLite store.

## Included capabilities

- Validated image, video, and optional checkpoint uploads with size limits.
- Trusted-checkpoint policy: deployed instances disable browser model uploads
  and only load reviewed `.pt` weights from `models/` by default.
- Atomic evidence writes, SQLite WAL mode, bounded snapshot retention, and
  downloadable audit reports.
- Non-root Docker image, health check, secure Streamlit request protections,
  and a repeatable runtime/development dependency contract.

## Run locally

### 1. Native Desktop Application (PySide6)
Launch the desktop workspace with camera capture, timeline scrubbing, and evidence review:
```bash
python3 desktop.py
```

### 2. Browser Interface (Streamlit + WebRTC)
```bash
python3 -m streamlit run app.py
```

### Run Tests
```bash
python3 -m pytest tests/ -v
```

For a container deployment, copy a reviewed checkpoint to `models/best.pt`,
then run:

```bash
docker build -t safesight-ai .
docker run --rm -p 8501:8501 -v safesight-data:/app/data safesight-ai
```

For an internet-facing deployment, terminate TLS at a reverse proxy, set
Streamlit's `server.corsAllowedOrigins` and `server.allowedHosts` to your
approved domains, and restrict ingress to authenticated users. The application
is intentionally configured for same-origin browser access by default.

## Operating requirements

Treat model results as decision support, not a replacement for an on-site
safety officer. Before site rollout, validate precision and recall for each
camera angle, lighting condition, equipment policy, and workforce group; define
a human review process; set evidence-retention and access policies; and monitor
model drift.

The application defaults to a trusted model directory. To permit external
paths or browser checkpoint uploads during a controlled administration session,
set `PPE_ALLOW_EXTERNAL_MODEL_PATH=true` or `PPE_ENABLE_MODEL_UPLOAD=true`.
Never enable these settings for an internet-exposed operator instance.

## Commercial release checklist

You must obtain a commercial license for Ultralytics YOLO or otherwise comply
with its AGPL terms before selling a proprietary deployment. Also obtain rights
to the supplied model weights and training data, conduct a privacy impact
assessment for recorded worker imagery, and provide local legal review for the
jurisdictions where the product is deployed.
