# SAFE SIGHT AI — Production Readiness Roadmap

**Audit date:** 2026-10-05
**Status:** Current implementation review and execution plan
**Primary release target assumed:** A single-site, on-premise browser workspace. Keep the PySide6 desktop client as a separate supported surface only if it has a committed operator need.

This replaces the older current-state audit in this file. Use this roadmap as the execution source of truth; older production plans and hardening notes remain reference material until they are reconciled.

## Executive assessment

SAFE SIGHT AI has a substantial working foundation: Python, Streamlit and PySide6 clients, YOLO inference, camera and video review, an operator-focused browser shell, SQLite evidence storage, retention and integrity checks, deployment examples, and CI quality gates.

It is **not ready for a shared industrial pilot yet**. The largest blockers are not missing dashboard features. They are the trust and operations gaps underneath them: authentication is optional by default, role checks are not enforced at the incident action boundary, live detections do not create records in the incident repository, camera recovery and notification queues are not connected to the runtime, and the current benchmark prints fixed sample numbers.

The strongest next step is to make one complete safety workflow trustworthy: a confirmed detection becomes a durable incident with linked evidence; the correct signed-in person can acknowledge and resolve it; operators can see camera and model health; and the record can be recovered and audited after a restart.

## Audit basis and limits

- The repository is a Python project. The pasted project summary describes TypeScript, but the checked-in README and pyproject identify Python, Streamlit, PySide6, OpenCV, Ultralytics YOLO, and SQLite.
- The working tree already contained more than 100 changed or untracked entries before this document was edited. Findings describe that in-progress tree; they do not attribute those changes to this review. Preserve and reconcile them before producing a release build.
- The offline readiness check completed with **0 blocking findings and 0 warnings**. It confirms a small set of files, imports, secure model-path flags, and a temporary evidence-store round trip. It does not verify the end-to-end incident flow, configured authentication, role enforcement, external health endpoints, alert persistence, field accuracy, or backup restoration.
- I reviewed source and deployment configuration. I did not run the test suite, build a container, or inspect a live browser/camera session. The local Docker command could not validate Compose configuration because the Compose subcommand is unavailable.
- The Ruflo security CLI was not cached and network access was restricted, so this review used source inspection and the repository readiness check rather than that scanner.

## Current-state scorecard

| Area | Assessment | Evidence and consequence |
|---|---|---|
| Product and detection | Strong prototype foundation; field performance unproven | A local checkpoint and image, video, and camera paths exist. There is no source-bound benchmark or site-specific per-class accuracy report. |
| Browser UI | Strong design foundation; operator workflow is incomplete | Command Center, Live Feed, Incidents, Reports, Evidence, Review, Settings, and Health routes exist with dark/light styling and shared components. The Camera Wall module is not in the active navigation. |
| Incident lifecycle | Critical integration gap | The incident repository and state machine exist, but source review found no production call that sends detector events to IncidentManager.ingest. The Incidents and Reports pages read a separate SQLite incident store, so they can remain empty while the live detector reports violations. |
| Access control | Production blocker for shared deployments | Authentication defaults off. Password verification in the active auth module uses unsalted SHA-256. Permission matrices exist, but page actions do not call them; incident transitions receive hard-coded actor roles, and the page constructs the manager without an authorizer. |
| Camera resilience | Partial, not operationally integrated | A reconnect state machine and camera registry exist, but they are not wired into the active capture lifecycle. The active OpenCV manager starts one device index; per-camera RTSP health and recovery need an end-to-end implementation. |
| Alerts | Useful components, no durable delivery guarantee | Dispatchers have retries, but their queues are in memory. A process restart loses queued work; a full queue can drop a notification. |
| Evidence and recovery | Good primitives; release workflow still needs proof | Evidence hashes, an event chain, retention, backup helpers, and a restore script exist. A versioned migration path and a rehearsed, safe restore procedure are not established. A separate audit-log module is not connected to all consequential actions. |
| Health and metrics | Visible in the UI; not a service contract | Health payload and metrics modules exist, but there is no application route exposing readiness or Prometheus metrics. The container check uses Streamlit's generic health URL, which does not prove model, camera, or evidence-store readiness. |
| Deployment | Good artifacts; Compose paths corrected, runtime validation pending | The image is non-root and CI builds it. This review corrected the production Compose build context, root .env path, and root models/ mount. The Compose subcommand is unavailable here, so config validation and an actual Compose build remain release gates. The current CI Trivy scan is non-blocking and SBOM generation is best-effort. |
| Performance evidence | Not trustworthy yet | scripts/benchmark.py assigns fixed FPS, latency, and queue values instead of measuring inference. Do not use its output for sizing or customer claims. |
| Claims and reporting | Copy needs correction | The Reports page calls downloads “certified” although the product record says no certification is held. Report period and author defaults should come from the operator's selected period and authenticated identity, not fixed example values. |
| Documentation | Duplicated plans have drifted | Several production plans overlap, and older ones describe gaps that now have code or omit newer integration risks. This file is the current execution plan. |

## Release scope

Start with one supported deployment: the browser application on a private site network behind a configured reverse proxy. Decide and document the supported camera count, stream types, hardware profile, retention window, and expected operating hours before claiming site readiness.

The desktop client can remain available for local evaluation, but it should not be treated as production-equivalent until identity, permissions, incident actions, evidence exports, and recovery behavior match the browser client. Defer multi-tenant hosting, cross-camera identity tracking, a public inference API, and accelerator conversions until a measured pilot justifies them.

## Implementation phases

### Phase 0 — Stabilize the release baseline

1. Review the existing local changes as a single integration effort. Record the exact source revision and model digest used for validation; do not discard or overwrite in-progress files.
2. Confirm the first supported deployment profile and which client is in scope.
3. The production Compose paths now target the repository-root Dockerfile, .env, and models/. Add a configuration-only check and an actual Compose build to release validation; neither was runnable in this review environment.
4. Replace the placeholder benchmark with measurements from the real capture and inference pipeline. Record hardware, model digest, input size, warm-up, frame loss, p50/p95 latency, throughput, CPU, memory, and queue depth.
5. Establish an initial site validation set and have the safety owner set per-class recall, precision, and false-alert limits before any pilot. Do not invent generic accuracy claims.

**Exit gate:** The intended deployment can be configured from documented files, its image can be built from a clean source snapshot, and the benchmark reports measured values tied to that snapshot.

### Phase 1 — Make incidents and permissions trustworthy

1. Define one event contract from confirmed detection through incident, evidence, audit, notification, and report. Ingest events only after the existing debounce/confirmation policy; deduplicate repeated frames into the same open incident.
2. Connect the video pipeline to the persistent incident manager. Store the model/checkpoint digest, camera, zone, timestamps, class, confidence, evidence references, and review status with each incident.
3. Enforce authorization inside the service that changes incident state, evidence, policy, model, and exports. UI hiding is only a usability layer. Bind every action to the authenticated user and actual role; remove hard-coded operator and safety_officer actors.
4. For any shared or network deployment, require authentication at startup. Use the existing modern password-hashing support or an approved identity provider; do not use unsalted SHA-256 for stored passwords. Keep a documented single-station mode only for a physically controlled workstation.
5. Escape every database- or user-derived value before rendering custom HTML. Remove unsupported “certified” wording and describe reports as operational records unless certification is independently obtained.

**Exit gate:** A detector event appears in the persistent incident list, survives restart, links to verifiable evidence, and can only be acknowledged, resolved, or dismissed by an authorized role with a recorded reason and real actor identity.

### Phase 2 — Keep cameras and alerts alive through failures

1. Connect camera registry and reconnect state to actual camera workers. Show per-camera connected, delayed, reconnecting, failed, and simulated states with the last-frame time.
2. Make stale video unmistakable. Stop presenting the last good image as live when frames stop arriving; show the failure and recovery action on both the Camera Wall and incident context.
3. Use a bounded durable alert outbox with idempotency, retry schedule, delivery state, failure visibility, and operator replay. Track queue-full drops and do not report an alert as delivered before its destination confirms receipt.
4. Keep the real camera count, stream types, and hardware limits within measured operating capacity. A demo stream must remain explicitly marked as simulated in every page and export.

**Exit gate:** Simulated camera loss is visible within the configured stale threshold, recovery follows a bounded retry policy, queued alerts survive an application restart, and no page presents stale or simulated imagery as live.

### Phase 3 — Make evidence recoverable and privacy-governed

1. Add ordered, versioned database migrations for both evidence and incident data. Test fresh databases and upgrades from each supported schema version.
2. Link incident transitions, evidence deletion/export, policy changes, and model changes to the tamper-evident audit trail. Anchor integrity outside the writable event database when the deployment needs stronger evidence against a local administrator.
3. Run scheduled backups for the database and referenced evidence files. Restore into a staging location, verify database integrity and file hashes, then promote through an atomic, documented procedure.
4. Define retention and access rules with the site. Verify deletion covers files, indexes, exports, backups, and temporary uploads; document face blurring and its limits. Restrict support bundles to approved fields and redact credentials and worker imagery by default.

**Exit gate:** A restore drill reproduces a known incident and its evidence on a clean target; integrity verification detects altered or missing files; retention and export behavior match the signed site policy.

### Phase 4 — Make production state observable and releasable

1. Provide separate liveness and readiness signals. Readiness must report model load, evidence database, and required camera/notification dependencies; it must fail clearly when a required dependency is unavailable.
2. Expose metrics only on the private operations interface: camera freshness and reconnects, inference latency and throughput, incident counts, alert queue depth/drops, database health, disk usage, and model version.
3. Extend the readiness gate so it rejects unsafe deployment configuration, missing authentication on shared deployments, invalid paths, unverified restore state, and absent model provenance. Keep warning-only local workstation settings explicit.
4. Make high/critical container scanning a blocking CI gate, with documented per-vulnerability exceptions. Require an SBOM and build the deployment image from the same locked dependency set used by release validation.
5. Publish an operator runbook for startup, camera loss, model rollback, failed alerts, restore, privacy requests, and incident escalation. Keep Kubernetes examples informational until they are actually validated.

**Exit gate:** A release candidate has a green clean-checkout CI run, a valid Compose configuration and image, an SBOM, passing readiness signals, and a rehearsed rollback and restore procedure.

### Phase 5 — Finish the operator experience around real work

Keep the existing SAFE SIGHT visual identity and dark/light token system. Shape the browser interface for a supervisor who must decide quickly whether to act, review, or investigate:

- **Command Center:** lead with open urgent incidents, current site/shift, measured camera health, and the next action. Keep “unmeasured” distinct from zero and never show a green workspace state without fresh input.
- **Camera Wall:** add the existing page to navigation. Each tile should show source, zone, last-frame age, model state, incident count, and whether the feed is simulated. Support focus mode and a readable single-camera review layout.
- **Incident workbench:** provide a severity-sorted queue and a detail panel with timeline, annotated evidence, camera/zone, model version, confidence, prior actions, and role-appropriate actions. Require a reason for false-positive and resolution decisions.
- **Evidence review:** connect incident actions to frame or clip review, timestamp navigation, integrity state, and a traceable export. Do not label an export certified.
- **Reports and settings:** use actual site timezone, selected date range, and authenticated actor; label all assumptions. Organize configuration into policy, camera, model, privacy, and integrations, with changes restricted by permission.
- **Navigation and interaction:** render the existing Monitor, Review, and Configure groups instead of a flat list of nine routes. Preserve keyboard shortcuts, add visible focus and helpful empty/error states, and make primary actions usable on a supervisor tablet.
- **Accessibility and clarity:** target WCAG 2.1 AA contrast and keyboard operation; never rely on color alone for severity or stream state; honor reduced motion; label camera imagery and announce status changes. Verify at desktop and tablet widths with real screenshots before release.

**Exit gate:** A new operator can identify an urgent incident, open its evidence, record an authorized action, and return to monitoring without losing context. A stale camera, missing model, empty incident store, and failed export each have clear recovery guidance.

### Phase 6 — Validate a site pilot and approve release

1. Validate per-class performance by camera, distance, lighting, occlusion, and PPE type against a site-approved labeled set. Report false negatives and false alerts per camera-hour, not only overall mAP.
2. Run a soak at the target camera count and resolution. Measure latency, frame loss, memory growth, reconnect time, disk growth, notification delivery, and operator-visible degradation.
3. Have the site safety owner review sample detections, retention, privacy notices, incident workflow, and the operational limits. Model output remains decision support and cannot be presented as an automatic safety determination.
4. Record the source revision, dependency lock, model digest and rights, benchmark report, migration version, security exceptions, and rollback target in the release record.

**Go-live gate:** Every required limit is approved before the pilot, the measured pilot meets those limits, the recovery drill passes, and unresolved safety or privacy risks have an accountable owner.

## Immediate work order

1. Preserve and review the existing working-tree changes; decide the supported deployment profile.
2. Validate the corrected Compose paths, then replace the fixed-value benchmark with a real capture/inference benchmark.
3. Wire confirmed detections into persistent incidents and enforce real identity and permissions at service boundaries.
4. Connect camera recovery and a durable alert outbox to the runtime.
5. Complete migrations, recovery, readiness/metrics endpoints, and privacy controls.
6. Build the advanced operator surfaces on top of that reliable event and camera state, then run site validation.

No release should be called production-ready solely because the current offline readiness script passes.
