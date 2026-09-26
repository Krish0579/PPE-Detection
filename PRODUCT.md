# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are industrial safety supervisors and operations managers who
monitor active work areas, investigate PPE incidents, and retain defensible
evidence. Operators use the system during live shifts as well as when reviewing
recorded clips or inspection images.

## Product Purpose

SAFE SIGHT AI applies a reviewed PPE-detection model to live cameras, video
files, and still images; it associates safety equipment with workers, presents
actionable violations, and maintains an incident-evidence record.

## Positioning

An on-premise, evidence-first safety operations workspace that turns visual PPE
detection into an operator review workflow rather than a stream of raw model
boxes.

## Operating Context

The current implementation is a Streamlit application with OpenCV camera
capture, Ultralytics YOLO inference, local SQLite evidence storage, and
downloadable reports. It is intended for controlled local or private-network
deployments.

## Capabilities and Constraints

- Live camera monitoring, video inspection, static-image inspection, evidence
  review, model settings, PPE-policy settings, worker tracking, and zones.
- Model results are decision support and require site-specific validation and
  human safety review.
- Browser model uploads are disabled by default; production checkpoints are
  reviewed and stored in the trusted `models/` directory.
- This product record is inferred from the existing implementation and the
  user's request for a complete operational redesign because the structured
  interview tool was unavailable.

## Brand Commitments

The existing product name is SAFE SIGHT AI. Its voice should be direct,
reassuring, accountable, and operationally precise; it must not make unverified
safety or certification claims.

## Evidence on Hand

The repository contains a functional Streamlit implementation, a locally
available PPE checkpoint at `models/best.pt`, automated tests, and locally
generated evidence artifacts. There are no approved customer logos,
testimonials, certification records, or benchmark claims to present.

## Product Principles

- Surface urgent work before configuration and decoration.
- Keep detection, uncertainty, and human action legible.
- Preserve evidence and operational context together.
- Make the safe/default deployment path the easiest path.
- Maintain accessible, calm, high-density controls for shift use.

## Accessibility & Inclusion

The interface should support keyboard operation, visible focus states, semantic
status messaging, non-color-only safety signals, and responsive use on
supervisor laptops and tablets.
