# Market Ops — Ultimate Product Target

The product turns performance signals into safe, measurable creative-growth
actions through one observable loop:

`collect → normalize → understand → decide → produce → approve → execute → measure → learn`

## Non-negotiable boundaries

1. Observation and recommendation may run automatically.
2. Creative generation may run automatically inside configured cost limits.
3. Platform writes require an explicit approval artifact.
4. Every write is idempotent, audited, rate-limited and reversible.
5. A failed dependency, stale source or quality gate blocks downstream execution.
6. Experimental engines never become production dependencies without a stable contract.

## Production surfaces

- `market-ops`: business workflows and reports.
- `market-ops-control`: health and readiness control center.
- `market-ops-doctor`: machine-readable deployment diagnosis.
- `/healthz`, `/readyz`, `/api/status`: stable operational contracts.

## Definition of done

- A clean environment installs from `pyproject.toml`.
- The control center starts without external credentials.
- Local sample mode builds reports without network access.
- Connected mode identifies missing credentials and data sources.
- Recommendation paths remain usable without generation or publishing systems.
- Execution paths cannot bypass approval and safety gates.
- CI tests the control-plane contract and core report/decision paths.
- Containers start real processes and expose health checks.
