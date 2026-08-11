# LaunchForge Production Runbook

## Automated gates

- Full test suite green.
- P4 readiness gate green for the exact production configuration.
- Required provider environment variables present.
- Approval workflow and SafeExecutor enabled.
- `data/`, `logs/`, audit and backup destinations writable.
- Dry-run canary completes with `real_api_called=false`.
- SLO: success rate >=99%, failed shards=0, average cycle latency <=300s,
  durable queue depth <=1000.
- 200-game healthy soak and failure-injection run recorded in `launch_evidence.md`.

## Controlled rollout

1. Run one game in dry-run for 24 hours.
2. Enable production for one low-risk, explicitly approved action.
3. Verify provider result, audit event, idempotency record and rollback snapshot.
4. Hold for one monitoring interval; rollback on KPI or health breach.
5. Increase game/action limits gradually. Never bypass the P4 limits.

## Emergency stop

- Remove/expire production approval.
- Open the circuit breaker or stop the worker.
- Execute the recorded rollback plan through SafeExecutor.
- Preserve audit and memory files; do not delete history.

## External launch evidence

Formal launch sign-off must record credential validation, provider sandbox/canary
results, monitoring destination, backup restore evidence and an accountable approver.
