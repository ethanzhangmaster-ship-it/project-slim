# P4 Autonomous Growth Agent Contract

## Production objective

P4 is the top-level safety envelope around the existing Memory Controller,
Daily Operator, approval workflow and SafeExecutor. It does not bypass or replace
their contracts. Production execution remains fail-closed.

## Frozen rules

1. Default mode is `dry_run`; production must be explicitly selected.
2. Production requires declared provider credentials and an approval gate.
3. Per-run limits: games, actions, daily budget and minimum confidence.
4. The same date/game-set/mode is idempotent.
5. Consecutive failures open a circuit breaker; reset requires authorization.
6. Simulation/dry-run never reports executed actions or authorized spend.
7. All provider execution continues through the existing SafeExecutor.
8. Startup readiness validates configuration, writable state/log paths and credentials.
9. No physical memory deletion and no governance bypass.
10. Formal go-live requires the checklist in `docs/production_runbook.md`.
