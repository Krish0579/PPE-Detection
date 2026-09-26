# Security Policy — SAFE SIGHT AI

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.x (tagged releases) | Yes |
| < 1.0 / untagged builds | No — upgrade to a tagged release |

## Reporting a vulnerability

- Email the vendor security contact listed in your contract. Include: affected version/image
  digest, deployment topology, reproduction steps, logs (redact credentials), and impact.
- Do **not** open public issues for suspected vulnerabilities.
- Expect acknowledgment within **2 business days** and a triage plan within **5 business days**.

## Handling rules

- Customer evidence data is never requested for debugging. Share redacted logs and the
  readiness-gate output instead; use the privacy-blur workflow for any imagery.
- Secrets (`.env`, password hashes, webhook URLs, TLS keys) must never appear in reports,
  tickets, or chat. Rotate any exposed credential immediately.
- Security fixes ship as patch releases with a CHANGELOG entry; SEV handling per
  `docs/PRODUCTION_MASTER_PLAN.md` §6.

## Hardening baseline (verified per release)

Trusted-checkpoint policy (no browser uploads / external paths in production), non-root
container, TLS-terminating proxy, lockfile installs, SBOM + Trivy report, and a green
`scripts/prod_readiness_check.py` gate. See `docs/MASTER_PLAN_PRODUCTION.md` §2.
