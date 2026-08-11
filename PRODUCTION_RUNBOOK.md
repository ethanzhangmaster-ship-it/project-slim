# Market Ops production runbook

## Safe default

Run the control plane and background services with the production override:

`docker compose -f docker-compose.yml -f docker-compose.production.yml up -d`

The override deliberately keeps `FACEBOOK_SANDBOX=true` and
`MARKET_OPS_ALLOW_PLATFORM_WRITES=0`. This allows reporting, source refresh,
recommendations and audit snapshots but prevents advertising-platform changes.

## Release gate

1. `market-ops-doctor --root . --write` must not report `blocked`.
2. The `data freshness` check must be within its configured limit.
3. Production CI must pass its contract suite.
4. `/readyz` must return HTTP 200 after deployment.
5. The control center must show no pending unreviewed approval.

## Enabling a real Meta write

Only after the account owner has verified every mapping in
`output/active/campaign_bindings.json`, set all of the following in the
deployment secret store:

- `FACEBOOK_SANDBOX=false`
- `MARKET_OPS_ALLOW_PLATFORM_WRITES=1`
- a valid Meta access token and ad-account ID

The approval artifact remains mandatory. A credential or an environment flag
does not by itself approve a budget, status or creative change.

## Incident response

Set `MARKET_OPS_ALLOW_PLATFORM_WRITES=0` first. The next readiness snapshot
will show publishing as approval-required while observation, reporting and the
audit ledger remain available. Preserve the cycle ID and task IDs from the
control API before investigating.
