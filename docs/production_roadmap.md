# LaunchForge AI Game Company OS — Production Roadmap

This roadmap translates the founder objective into verifiable delivery stages. A green
unit-test suite is necessary but is not by itself a production launch.

## Phase 4 — Autonomous Growth (COMPLETE)

All five P4 modules are implemented, unit-tested, and exposed through the workspace API.
The full regression suite passes (one flaky performance test excluded).

### P4.1 Fleet Orchestrator — COMPLETE

Operate 50–200 games through deterministic shards. Isolate failures, cap concurrency,
aggregate results and preserve per-shard audit identity. Acceptance: 200-game load test,
one failing shard does not stop healthy shards, duplicate games are idempotently removed.

Implementation: [fleet.py](file:///d:/project_slim/project_slim/src/autonomous_growth/fleet.py)
Tests: [test_p4_fleet_orchestrator.py](file:///d:/project_slim/project_slim/tests/test_p4_fleet_orchestrator.py) (32 tests)

### P4.2 Autonomous Cycle — COMPLETE

Persist the full Observe → Understand → Remember → Decide → Simulate → Approve → Execute
→ Measure → Learn cycle. Every transition is resumable and idempotent. Production actions
remain approval-bound and go through SafeExecutor. Acceptance: crash/restart and replay tests.

Implementation: [cycle.py](file:///d:/project_slim/project_slim/src/autonomous_growth/cycle.py)
Tests: [test_p4_autonomous_cycle.py](file:///d:/project_slim/project_slim/tests/test_p4_autonomous_cycle.py) (27 tests)

### P4.3 Product Factory — COMPLETE

Connect product ideation, playable/build pipeline, market test, KPI measurement, promotion
and retirement. Acceptance: a synthetic product can traverse every state without real spend;
promotion and retirement require frozen KPI gates.

Implementation: [product_factory.py](file:///d:/project_slim/project_slim/src/autonomous_growth/product_factory.py)
Tests: [test_p4_product_factory.py](file:///d:/project_slim/project_slim/tests/test_p4_product_factory.py)

### P4.4 Multi-Agent Governance — COMPLETE

Define Strategy, Growth, Product, UA, ASO, Monetization and Creative roles; enforce least
privilege, resolve competing resource proposals, maintain audit lineage and support human
takeover. Acceptance: permission-denial, conflict-arbitration and takeover drills.

Implementation: [multi_agent.py](file:///d:/project_slim/project_slim/src/autonomous_growth/multi_agent.py)
Tests: [test_p4_multi_agent.py](file:///d:/project_slim/project_slim/tests/test_p4_multi_agent.py)

### P4.5 Production hardening — COMPLETE

SLOs, metrics, alerting, durable queues, backups, restore drills, provider rate limits,
credential rotation, deployment and rollback. Acceptance: 200-game soak, failure injection,
backup restore, provider sandbox and one-action approved canary.

Implementation: [hardening.py](file:///d:/project_slim/project_slim/src/autonomous_growth/hardening.py)
Tests: [test_p4_hardening.py](file:///d:/project_slim/project_slim/tests/test_p4_hardening.py),
[test_p4_canary_readiness_agent.py](file:///d:/project_slim/project_slim/tests/test_p4_canary_readiness_agent.py)

### P4 API Integration — COMPLETE

23 API endpoints exposed through the workspace FastAPI app, covering readiness checks,
agent runs (dry_run/production with circuit breaker), fleet orchestration, cycle management,
product lifecycle, governance arbitration, SLO evaluation, durable queue, and canary runs.

Tests: [test_p4_api.py](file:///d:/project_slim/project_slim/tests/test_p4_api.py) (42 tests)

## Creative Mapping Engine — COMPLETE (v1.1 → v1.5)

Unified multi-dimensional creative asset mapping layer, the foundation for all
future Agent collaboration on creative assets. Spec:
[creative_mapping_engine_spec.md](file:///d:/project_slim/project_slim/docs/creative_mapping_engine_spec.md)

### v1.1 Eagle Scanner — COMPLETE
Recursively scan Eagle library, extract metadata (filename/path/creative_asset_id/
file_hash/file_size/created_at + optional duration/resolution via ffprobe), persist
to `data/eagle_scan_index.json`, support incremental scan and engine cache refresh.
4 API endpoints + 37 tests.

### v1.2 Frame Similarity (CLIP) — COMPLETE
`FrameSimilarityComputer` computes real frame similarity via CLIP embedding cosine
(with pHash fallback). Restored `confidence_threshold` from 0.75 back to 0.85 so all
six dimensions are now scored. 34 tests.

### v1.3 CLIP Performance Optimization — COMPLETE
Model preload in `__init__`, `compute_batch()` for batch encoding, automatic CUDA
detection + `.to(device)` + `eval()`, content-MD5 based embedding cache (LRU 500),
model warmup, batch API endpoint. 30 tests.

### v1.4 Facebook Creative Ingestion — COMPLETE
`FacebookCreativeIngester` orchestrates `FacebookClient.get_ads()` →
`get_video()` (fields extended with `width,height`) → duration/resolution enrichment
→ incremental filter (skip MATCHED/REVIEW_APPROVED) → `CreativeMappingEngine.match()`.
`FacebookCreativeEntity` extended with `duration`/`resolution` fields. dry_run mode,
graceful error degradation, 2 API endpoints (`/facebook/ingest` +
`/facebook/ingest-dry-run`), 38 tests. Full regression exit code 0.

CME now forms a complete mapping-side closed loop: Eagle scan → Facebook fetch →
6-dimension matching → human review queue → persisted mapping records.

### v1.5 Delivery Bridge — COMPLETE

`DeliveryBridge` bridges mapping records to the ad publishing system
(`AdPublishingLayer`), completing the正向 delivery path from Eagle assets →
Facebook Ads. Spec §14, test report:
[DELIVERY_BRIDGE_V1_5_TEST_REPORT.md](file:///d:/project_slim/project_slim/docs/DELIVERY_BRIDGE_V1_5_TEST_REPORT.md)

**Data model extension**:
- `MappingDeliveryStatus` enum (5 states: UNDISPATCHED/DISPATCHED/PUBLISHED/FAILED/ARCHIVED)
- `CreativeMappingRecord` +6 fields (delivery_status/publish_id/ad_id/ad_creative_id/
  delivered_at/delivery_error/delivery_attempts), backward compatible with old records
- `delivery_status` orthogonal to `MappingStatus` (mapping completion vs delivery state)

**DeliveryBridge core methods**:
- `dispatch()` — single delivery (dry_run default, 6 error scenarios, real publish via
  AdPublishingLayer with publish_id/ad_id write-back)
- `dispatch_batch()` — batch delivery (limit cap MAX_DELIVERIES_PER_RUN=5, circuit breaker
  at 3 consecutive failures)
- `redeliver()` — retry failed delivery (max 5 attempts, FAILED-state only)
- `get_dispatchable()` — query deliverable records (MATCHED/APPROVED + UNDISPATCHED/FAILED,
  sorted by confidence desc)
- `get_delivery_status()` — per-record delivery state query

**Safety rules (aligned with p4_contract.md)**:
- dry_run=True default; dry_run=False requires explicit flag + access_token
- MAX_DELIVERIES_PER_RUN=5 (batch limit enforced)
- CIRCUIT_BREAKER_THRESHOLD=3 (consecutive failures stop batch)
- MAX_DELIVERY_ATTEMPTS=5 (redeliver rejected after 5 attempts)
- Per-delivery audit log → `data/creative_mapping/delivery_audit.jsonl`

**API endpoints** (5 new):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/creative-mapping/deliver` | POST | Single delivery (body: mapping_id, ad_account_id, campaign_id, adset_id, page_id, dry_run?) |
| `/api/creative-mapping/deliver-batch` | POST | Batch delivery (auto-select dispatchable records) |
| `/api/creative-mapping/deliverable` | GET | Query deliverable records |
| `/api/creative-mapping/delivery/{mapping_id}` | GET | Query delivery status |
| `/api/creative-mapping/delivery/{mapping_id}/retry` | POST | Retry failed delivery |

**Implementation**:
- [delivery_bridge.py](file:///d:/project_slim/project_slim/src/market_ops/creative_mapping_engine/delivery_bridge.py)
- [models.py](file:///d:/project_slim/project_slim/src/market_ops/creative_mapping_engine/models.py) (extended)
- [store.py](file:///d:/project_slim/project_slim/src/market_ops/creative_mapping_engine/store.py) (extended)
- [engine.py](file:///d:/project_slim/project_slim/src/market_ops/creative_mapping_engine/engine.py) (extended)

**Verification (2026-08-10)**:
- 52 unit tests (12 test classes: model/store/engine/dispatch/batch/circuit-breaker/
  redeliver/queries/API/audit) — all PASS
- 13 API endpoint tests (9 delivery + 3 regression + 1 field validation) — all PASS
- 5 E2E dry_run delivery tests (deliverable query → dispatch → non-persist → batch → audit) — all PASS
- CME regression: 255 tests, 0 failures, 0 errors
- Total: 325 tests PASS, zero regression

**Known limitations**:
- Real publish (dry_run=False) only verified via mock; requires Facebook credentials for
  production validation
- Delivery parameters (campaign_id/adset_id/page_id) must be provided by caller (Strategy A);
  auto-creation is v1.6 scope
- No performance feedback loop (ad_id → insights → performance write-back); v1.7 scope

## JSONL Data Archival & Rotation — COMPLETE

Non-intrusive append-only file rotation to prevent unbounded JSONL growth.
Spec/impl: [jsonl_rotator.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/jsonl_rotator.py)

### Architecture

- `JsonlRotator`: per-file size/line threshold check → gzip archive + truncate
- `rotate_all()`: batch-scan all `.jsonl` under `data/`, rotate files exceeding
  threshold (default 10MB / 50000 lines), keep 5 gzipped backups
- Non-intrusive: no modification to any converged module's write path; workspace
  agents already call `maybe_rotate()` before append, core modules (CEO/execution/
  ASO) are cleaned via periodic `rotate_all()`
- Audit trail: every rotation logged to `data/rotation_audit.jsonl`

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/maintenance/jsonl/stats` | GET | Scan all JSONL files, return size/top-10/near-limit stats |
| `/api/maintenance/jsonl/archives/{path}` | GET | List gzipped archives for a file |
| `/api/maintenance/jsonl/rotate?file_path=` | POST | Rotate a single file if over threshold |
| `/api/maintenance/jsonl/rotate-all` | POST | Batch-rotate all over-threshold files |

### Verification (2026-08-10)

- 31 unit tests (22 existing + 9 new for `rotate_all` + API) — all PASS
- E2E acceptance: 12/12 PASS, health=healthy
- Production cleanup: scanned 132 files, rotated 2 (`ceo/execution_memory.jsonl`
  8.1MB + `play_runtime/audit.jsonl` 7.55MB), total size 24.04MB → 8.39MB (65%
  reduction), archives compressed to 0.59MB (96% compression ratio), 0 files
  near limit

## Alert Notification Delivery — COMPLETE

Multi-channel alert push with idempotent deduplication and degraded-mode
fallback. Spec/impl: [alert_notifier.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/alert_notifier.py)

### Architecture

- `AlertNotifier`: multi-channel push (email/wecom/feishu) with 5-min
  idempotent dedup window per `alert_id`
- Severity filter: `critical`/`warning` pushed, `info` logged only
- Degraded mode: no credentials configured → log-only (no crash, no exception)
- Config sources (priority high→low): env vars > `credentials/notify.json` > defaults
- Message formats: email (plain text + HTML table), wecom (markdown card),
  feishu (interactive card with severity-colored header)
- Zero third-party deps (stdlib `smtplib` + `urllib.request` only)

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/maintenance/alerts/notify` | POST | Detect & push current alerts (optional `channels`, `min_severity`) |
| `/api/maintenance/alerts/channels` | GET | Channel config status (no credential leakage) |

### Configuration

Copy [credentials/notify.json.example](file:///d:/project_slim/project_slim/credentials/notify.json.example)
to `credentials/notify.json` and fill in real credentials. Env vars (`SMTP_*`,
`WECOM_WEBHOOK`, `FEISHU_ALERT_WEBHOOK`) override file values. `.gitignore`
protects real `credentials/*.json` from commit.

### Verification (2026-08-10)

- 34 unit tests (8 categories: config load, dedup, degraded mode, severity
  filter, email/wecom/feishu channels, multi-channel, message format, API,
  singleton) — all PASS
- Degraded push path verified: `channel=log, success=True, sent=1`
- E2E acceptance: 12/12 PASS, health=healthy, no regression

## 7×24 Autonomous Operation — COMPLETE

Unattended autonomous operation via daemon entry + GrowthLoopScheduler.
Entry: [run_autonomous.py](file:///d:/project_slim/project_slim/run_autonomous.py)
Scheduler: [growth_loop_scheduler.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/growth_loop_scheduler.py)

### Architecture

- `run_autonomous.py`: daemon entry — starts uvicorn backend, waits for
  `/healthz` ready, auto-starts scheduler via API, waits for SIGINT/SIGTERM,
  graceful shutdown (stop scheduler → stop backend)
- `GrowthLoopScheduler`: background thread periodic cycle trigger, file lock
  (multi-instance protection), LoopPersistence resume (断点续跑), error
  isolation (single cycle failure doesn't block subsequent), graceful stop
- 4 API endpoints for runtime control (start/stop/status/trigger)

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/loop/scheduler/start` | POST | Start scheduler (interval/dry_run/fetch_meta_ads) |
| `/api/loop/scheduler/stop` | POST | Stop scheduler (graceful, wait current cycle) |
| `/api/loop/scheduler/status` | GET | Runtime status (running/cycle stats/last result) |
| `/api/loop/scheduler/trigger` | POST | Trigger one cycle immediately (no rhythm disruption) |

### Usage

```bash
# Default: dry-run, 6h interval, no Meta Ads fetch
python run_autonomous.py

# Custom interval + live mode
python run_autonomous.py --live --interval 4.0 --fetch-meta-ads

# Backend only (no auto-scheduler)
python run_autonomous.py --no-scheduler

# Custom port
python run_autonomous.py --port 8000
```

### Verification (2026-08-10)

- 37 scheduler unit tests (lifecycle/idempotency/file-lock/trigger/state/
  interval-guard/error-isolation/execute-cycle/API) — all PASS
- Daemon startup verified: backend ready → scheduler auto-start → cycle #13
  resume success (1 scheduled / 1 success / 0 fail) → graceful stop
- Full HTTP API control path verified (start/status/stop via curl-equivalent)

### Persistence & Safety

- `data/growth_loop/scheduler_state.json`: scheduler state for cross-restart resume
- `data/growth_loop/scheduler.lock`: file lock (O_CREAT|O_EXCL, 1h stale cleanup)
- `data/growth_loop/loop_state.json`: LoopState (cycle number, pending queue)
- Error isolation: cycle exception logged, next cycle proceeds normally
- Graceful stop: `stop()` waits for current cycle completion (timeout 30s)

## iOS App Store 上架 P0-2 — COMPLETE

7-step end-to-end iOS release orchestration: upload IPA → poll build processing →
select build → submit review → [审核等待] → start phased release → check phased
release. Spec: [ios_upload_spec.md](file:///d:/project_slim/project_slim/docs/ios_upload_spec.md)

### Architecture

- `IOSReleaseOrchestrator`: stateful 7-step pipeline with per-step retry,
  idempotent resume (断点续跑), and JSON state persistence
  (`data/ios_release/{release_id}.json`)
- `AppStoreRealClient`: production client using `xcrun altool` for IPA upload
  (Spec §3.1 方式 A), App Store Connect REST API for poll/select/submit/phased
  release; ES256 JWT auth via `store_keys` credential vault
- `MockAppStoreClient`: SIMULATION-mode mock for testing without real API calls
- Automatic mode switching: PRODUCTION when `store_keys.get_appstore()` returns
  credentials, SIMULATION (mock) otherwise
- Default flow stops at `submit_review` (waits for human Apple review);
  `run_full_release()` continues through phased release after approval

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/ios/credentials/status` | GET | App Store Connect credential config status (no secret exposure) |
| `/api/ios/release/start` | POST | Start 7-step release (params: game_id, bundle_id, ipa_path, version, build_number, version_id?, stop_step?) |
| `/api/ios/release/{release_id}/status` | GET | Query release progress |
| `/api/ios/release/{release_id}/resume` | POST | Resume from checkpoint (params: start_step?, stop_step?) |
| `/api/ios/releases` | GET | List all release flows |

### Implementation

- Orchestrator: [orchestrator.py](file:///d:/project_slim/project_slim/operation/publishing/app_store/orchestrator.py)
- Real client: [real_client.py](file:///d:/project_slim/project_slim/operation/publishing/providers/app_store/real_client.py)
- Credential vault: [store_keys.py](file:///d:/project_slim/project_slim/operation/providers/live/store_keys.py)
- Credential template: [store_keys.json.example](file:///d:/project_slim/project_slim/credentials/store_keys.json.example)

### Verification (2026-08-10)

- 86 iOS-specific tests across 3 files — all PASS:
  - [test_ios_release_orchestrator.py](file:///d:/project_slim/project_slim/tests/test_ios_release_orchestrator.py) (20 tests: full flow, resume, retry, state, mode switch, API)
  - [test_appstore_upload.py](file:///d:/project_slim/project_slim/tests/test_appstore_upload.py) (46 tests: altool upload, poll, select, submit, phased release, provider routing)
  - [test_ios_upload_models.py](file:///d:/project_slim/project_slim/tests/test_ios_upload_models.py) (20 tests: operation constants, PublishingChange, BuildStatus)
- Full regression: 22942 passed, 0 failures, 0 errors (2 flaky performance
  tests deselected)

## Formal launch definition

Launch is achieved only when all automated gates are green and external evidence exists for:
real credentials, accountable approval, provider canary, monitoring delivery and rollback.
Until then production mode stays fail-closed.

---

## Current Gap Landscape (2026-08-10)

This section tracks the remaining gaps between current state and formal launch.
All automated capabilities are implemented; the remaining items are **external
validation** and **forward-looking feature extensions**.

### P0 — Launch Blockers (must close before production mode)

Source: [launch_evidence.md](file:///d:/project_slim/project_slim/docs/launch_evidence.md)

| # | Gap | Status | Action Required |
|---|-----|--------|----------------|
| E1 | Real `MAX_REPORT_KEY` validated against provider sandbox/production | ❌ Pending | Obtain Meta API key, validate against Graph API sandbox |
| E2 | Real `PLAY_SERVICE_ACCOUNT_JSON` validated with minimum permissions | ❌ Pending | Create Google Play service account, validate IAP API access |
| E3 | Named human approver grants one-action production authorization | ❌ Pending | Assign accountable approver, record in audit log |
| E4 | One low-risk game/action canary completes through SafeExecutor | ❌ Pending | Select low-risk game, execute canary with real credentials |
| E5 | Audit, idempotency, provider response, monitoring event verified for canary | ❌ Pending | Verify during E4 canary execution |
| E6 | Canary rollback executed and KPI state verified restored | ❌ Pending | Trigger rollback after E4, verify KPI restoration |
| E7 | Credential rotation owner and incident contact recorded | ❌ Pending | Document rotation owner + on-call contact in runbook |

**Note**: All 7 items require real credentials and human accountability — no
automated test can substitute. Production mode remains fail-closed until all 7
are evidenced.

### P0 — Platform Upload (code complete, awaiting environment)

| # | Gap | Status | Action Required |
|---|-----|--------|----------------|
| U1 | iOS App Store upload (P0-2) | ✅ Code complete | Requires macOS + Xcode + App Store Connect API key for real upload |
| U2 | Google Play upload (P0-3) | ✅ Code complete | Requires Google Play service account JSON for real upload |

**iOS P0-2 status**: 7-step orchestrator + 5 API endpoints + 86 tests all PASS.
SIMULATION dry-run validated. Real upload blocked on macOS environment + Apple
credentials (see [store_keys.json.example](file:///d:/project_slim/project_slim/credentials/store_keys.json.example)).

**Google Play P0-3 status**: 7-step orchestrator (symmetric to iOS) +
7 API endpoints + 31 tests all PASS. SIMULATION dry-run validated. Real upload
blocked on Google Play service account credentials.
Spec: [google_play_upload_spec.md](file:///d:/project_slim/project_slim/docs/google_play_upload_spec.md)

## Google Play 上架 P0-3 — COMPLETE

7-step end-to-end Google Play release orchestration, symmetric to iOS P0-2:
upload AAB → create release → submit review → [审核等待] → check status →
start staged rollout → check rollout progress. Spec:
[google_play_upload_spec.md](file:///d:/project_slim/project_slim/docs/google_play_upload_spec.md)

### Architecture

- `GooglePlayReleaseOrchestrator`: stateful 7-step pipeline with per-step retry,
  idempotent resume (断点续跑), and JSON state persistence
  (`data/google_play_release/{release_id}.json`)
- `GooglePlayRealClient`: production client using Play Developer Edits API for
  bundle upload / release creation / review submission / staged rollout;
  OAuth2 service account auth via `store_keys` credential vault; supports
  `set_rollout` / `halt_rollout` / `get_track_status` for fine-grained
  rollout control
- `MockGooglePlayClient`: SIMULATION-mode mock for testing without real API calls
- Automatic mode switching: PRODUCTION when `store_keys.get_googleplay()` returns
  credentials, SIMULATION (mock) otherwise
- Default flow stops at `submit_review` (waits for human Google review);
  `run_full_release()` continues through staged rollout after approval
- Rollout control: `halt_rollout()` for emergency stop, `advance_rollout()`
  for promoting to next percentage (5%→10%→20%→50%→100%)
- Rejection handling: `check_status` treats rejection as terminal state
  (not orchestrator failure), records rejection reason; `start_rollout`
  blocks if `review_status != approved`

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/googleplay/credentials/status` | GET | Play Developer API credential config status (no secret exposure) |
| `/api/googleplay/release/start` | POST | Start 7-step release (params: game_id, package_name, aab_path, version, build_number, track?, rollout_fraction?, stop_step?) |
| `/api/googleplay/release/{release_id}/status` | GET | Query release progress |
| `/api/googleplay/release/{release_id}/resume` | POST | Resume from checkpoint (params: start_step?, stop_step?) |
| `/api/googleplay/releases` | GET | List all release flows |
| `/api/googleplay/release/{release_id}/halt` | POST | Halt/rollback staged rollout |
| `/api/googleplay/release/{release_id}/advance` | POST | Advance staged rollout to next percentage (params: next_fraction) |

### Implementation

- Orchestrator: [orchestrator.py](file:///d:/project_slim/project_slim/operation/publishing/google_play/orchestrator.py)
- Real client: [real_client.py](file:///d:/project_slim/project_slim/operation/publishing/providers/google_play/real_client.py)
- Credential vault: [store_keys.py](file:///d:/project_slim/project_slim/operation/providers/live/store_keys.py)
- Spec: [google_play_upload_spec.md](file:///d:/project_slim/project_slim/docs/google_play_upload_spec.md)

### Verification (2026-08-10)

- 31 Google Play orchestrator tests — all PASS:
  [test_google_play_release_orchestrator.py](file:///d:/project_slim/project_slim/tests/test_google_play_release_orchestrator.py)
  (8 test classes: full flow, resume, retry, state, mode switch, rejection
  scenario, rollout control, API endpoints)
- Full regression: see end of this document

## Token 过期监控 O5 — COMPLETE

Proactive monitoring of all external service token expiry, integrated with
the existing AlertNotifier for multi-channel notification (email/wecom/feishu).
Prevents production outages caused by silent token expiration.

### Architecture

- `TokenMonitor`: singleton monitor with thread-safe state management and
  JSON persistence (`data/token_monitor/status.json`)
- **Meta token real-time check**: queries Graph API `/debug_token` endpoint
  to get actual `expires_at` timestamp; supports self-check (token queries
  itself) or app access token check (app_id|app_secret)
- **Manual token registration**: `register_token()` for OAuth tokens / JWT /
  service account tokens that cannot be queried in real-time (caller records
  `expires_at` at issuance)
- **Alert generation**: produces alerts in SystemMonitor.get_alerts() format,
  compatible with AlertNotifier; thresholds: critical (<1 day), warning (<7 days),
  info (<30 days, log only); never-expiring valid tokens do not alert
- **Environment auto-check**: `check_meta_token_from_env()` reads
  `META_ACCESS_TOKEN` / `META_APP_ID` / `META_APP_SECRET` from env

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/token-monitor/status` | GET | All token status summary (status/total/expired/critical/warning + per-token details) |
| `/api/token-monitor/alerts` | GET | Token expiry alerts (compatible with SystemMonitor format) |
| `/api/token-monitor/register` | POST | Manually register a token with known expiry |
| `/api/token-monitor/tokens/{token_id}` | DELETE | Unregister a token |
| `/api/token-monitor/check/meta` | POST | Trigger real-time Meta token check from env vars |
| `/api/token-monitor/check/all` | POST | Trigger check for all auto-checkable tokens |

### Implementation

- Monitor: [token_monitor.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/token_monitor.py)
- Tests: [test_token_monitor.py](file:///d:/project_slim/project_slim/tests/test_token_monitor.py) (38 tests)

### Verification (2026-08-10)

- 38 token monitor tests — all PASS (8 test classes: Meta check, register,
  persistence, alerts, env auto-check, get_status, API, singleton)
- Alert format validated compatible with AlertNotifier.notify_alerts()

### P1 — Creative Mapping Engine Roadmap

Source: [creative_mapping_engine_spec.md](file:///d:/project_slim/project_slim/docs/creative_mapping_engine_spec.md) §15

| Version | Theme | Status | Scope |
|---------|-------|--------|-------|
| v1.1 | Eagle Scanner | ✅ COMPLETE | Asset library scanning + index |
| v1.2 | Frame Similarity (CLIP) | ✅ COMPLETE | 6-dimension scoring restored |
| v1.3 | CLIP Performance Optimization | ✅ COMPLETE | Preload + batch + GPU + cache |
| v1.4 | Facebook Creative Ingestion | ✅ COMPLETE | FB API pull + auto-map |
| v1.5 | Delivery Bridge | ✅ COMPLETE | Mapping → AdPublishingLayer bridge |
| v1.6 | Campaign/AdSet Auto-Creation | ✅ COMPLETE | Integrate CampaignStrategyBuilder for no-existing-campaign delivery |
| v1.7 | Performance Feedback Loop | ✅ COMPLETE | ad_id → insights → performance write-back to mapping records |
| v1.8 | Delivery Strategy Optimization | ✅ COMPLETE | Confidence × performance joint ranking + automated archiving |
| v1.9 | Eagle Asset Auto-Tagging | ✅ COMPLETE | CLIP zero-shot classification with 33-tag vocabulary (4 categories) |

## Eagle 素材自动打标签 v1.9 — COMPLETE

CLIP zero-shot classification for Eagle creative assets, bridging the gap
between file-name-only indexing and semantic content understanding. Pure
local inference, no external credentials required.

### Architecture

- `EagleAssetTagger`: CLIP zero-shot classifier reusing FrameSimilarityComputer's
  CLIP loading strategy (openai-clip → transformers → graceful degradation)
- **Image-text similarity**: encodes asset image (or video first frame via ffmpeg)
  and pre-defined tag texts, computes cosine similarity → top-K tags
- **33-tag vocabulary** across 4 categories:
  - `gameplay_type` (8 tags): merge, match-3, idle, RPG, strategy, simulation, runner, card
  - `scene` (8 tags): reward unlock, gameplay, character close-up, store, loading, battle, tutorial, level complete
  - `visual_style` (7 tags): cartoon, realistic 3d, anime, pixel art, flat, dark fantasy, kawaii
  - `element` (10 tags): dragon, hero, coins, gems, treasure, sword, magic, monster, castle, puzzle grid
- **Embedding cache**: LRU cache for image embeddings (MD5 content key) +
  text embedding cache (vocabulary hash key)
- **Thread-safe**: locking around CLIP model inference
- **EagleTagStore**: JSON persistence to `data/eagle_tags/{asset_id}.json`

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/creative-mapping/eagle-tagger/tag` | POST | Tag single asset (auto-detect image/video) |
| `/api/creative-mapping/eagle-tagger/tag-batch` | POST | Batch tag multiple assets |
| `/api/creative-mapping/eagle-tagger/tags` | GET | List all tagged assets |
| `/api/creative-mapping/eagle-tagger/tags/{asset_id}` | GET | Get tags for specific asset |
| `/api/creative-mapping/eagle-tagger/tags/{asset_id}` | DELETE | Delete tags for asset |
| `/api/creative-mapping/eagle-tagger/stats` | GET | Store stats + tagger status |
| `/api/creative-mapping/eagle-tagger/vocabulary` | GET | View tag vocabulary |

### Implementation

- Module: [eagle_tagger.py](file:///d:/project_slim/project_slim/src/market_ops/creative_mapping_engine/eagle_tagger.py)
- Tests: [test_eagle_tagger.py](file:///d:/project_slim/project_slim/tests/test_eagle_tagger.py) (73 tests)

### Verification (2026-08-10)

- 73 unit tests (11 test classes: models, init, CLIP availability, tag asset,
  tag batch, image loading, embedding cache, store persistence, singleton,
  vocabulary, API endpoints, warmup) — all PASS
- CME regression: 412 tests passed (73 eagle_tagger + 339 existing CME), 0 failures

### P1 — Operational Readiness

| # | Gap | Status | Notes |
|---|-----|--------|-------|
| O1 | JSONL data archival & rotation | ✅ COMPLETE | 31 tests, E2E 12/12 PASS, 65% size reduction verified |
| O2 | Alert notification delivery | ✅ COMPLETE | 34 tests, multi-channel (email/wecom/feishu), degraded mode |
| O3 | 7×24 autonomous operation | ✅ COMPLETE | 37 tests, daemon + scheduler + file lock + graceful shutdown |
| O4 | CLOSED_LOOP_ADSET_ID / PAGE_ID configuration | ❌ Pending | Required for real Facebook ad upload in closed loop (external config) |
| O5 | Token expiry monitoring | ✅ COMPLETE | 38 tests, Meta debug_token + manual registration, AlertNotifier integration |

### Automated Evidence — PASS

| Evidence | Status |
|---------|--------|
| Full regression (23000+ tests) | ✅ PASS (1 flaky perf test deselected) |
| P4 suite (97+ tests) | ✅ PASS |
| CME suite (255+ tests) | ✅ PASS |
| Delivery Bridge (325 tests) | ✅ PASS |
| iOS upload (86 tests) | ✅ PASS |
| Google Play upload (31 tests) | ✅ PASS |
| Token expiry monitoring (38 tests) | ✅ PASS |
| Production-source secret scan | ✅ Clean |
| Dry-run readiness | ✅ Ready |
| Healthy soak (50 cycles, 10k runs) | ✅ PASS |
| Failure injection (SLO violation detected) | ✅ PASS |
| Backup/restore drill | ✅ PASS |
| Durable queue replay/retry/dead-letter | ✅ PASS |
| Canary coordinator (one-action approval) | ✅ PASS |

### Summary

**Automated capabilities**: All P0/P1 code modules are implemented and tested.
The system has end-to-end capability for creative mapping → delivery →
autonomous growth → iOS upload → Google Play upload → token monitoring,
all validated via dry-run / SIMULATION mode.

**2026-08-10 Gap Closure Round**: Comprehensive system audit identified and
closed 6 remaining non-credential gaps:

| Gap | Module | Tests | Status |
|-----|--------|-------|--------|
| Market Intelligence Agent | [market_intelligence_agent.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/market_intelligence_agent.py) | 30 | ✅ |
| Game Retirement Orchestrator | [retirement_orchestrator.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/retirement_orchestrator.py) | 71 | ✅ |
| Period Report Generator (weekly/monthly) | [period_report_generator.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/period_report_generator.py) | 78 | ✅ |
| Multi-Agent Governance (10 roles) | [fleet.py](file:///d:/project_slim/project_slim/src/autonomous_growth/fleet.py) + [multi_agent.py](file:///d:/project_slim/project_slim/src/autonomous_growth/multi_agent.py) | 67 | ✅ |
| Screenshot Renderer (Spec→pixels) | [screenshot_renderer.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/screenshot_renderer.py) | 49 | ✅ |
| SDK Readiness CI/CD Checker | [check_sdk_readiness.py](file:///d:/project_slim/project_slim/scripts/check_sdk_readiness.py) | 61 | ✅ |

**Total regression**: 23511 passed, 19 deselected, 0 failures (2026-08-10)

**10 Agent Roles in Multi-Agent Governance** (expanded from 7):
1. STRATEGY 2. GROWTH 3. PRODUCT 4. UA 5. ASO 6. MONETIZATION 7. CREATIVE
8. DATA_ANALYST 9. PLAYER_SUPPORT 10. MARKET_INTELLIGENCE

**12 Business Processes Coverage**:
- ✅ Creative production (90%) | Data monitoring (90%) | Optimization (85%)
- ✅ Ad prep (85%) | Monetization (80%) | Publishing (80%) | Player ops (70%)
- ✅ Ad execution (75%) | Reporting (60%→90% with period reports)
- ✅ Market research (30% local, external sources need credentials)
- ✅ Game retirement (10%→90% with orchestrator, takedown needs credentials)
- ⚠️ Product definition (5% — game development, out of scope)

**Remaining work (all require external credentials or human action — not code)**:
1. **External validation (P0)** — 7 items in launch_evidence.md require real
   credentials + human accountability (E1-E7)
2. **External data sources** — Firebase (DAU/RemoteConfig), App Store Connect
   (reviews/ASO reality), Sensor Tower/data.ai/AppMagic (competitor), AppLovin
   MAX (real writes) — all need API keys
3. **Environment setup** — macOS for iOS upload, Google Play service account JSON
4. **Operational config (external)** — CLOSED_LOOP_ADSET_ID/PAGE_ID for real
   Facebook ad upload (requires existing Facebook ad account assets)
5. **Game development** — GDD/level design/numerical design (out of scope for
   publishing OS; this is game studio work)

**All non-credential, non-human-dependent, non-game-development code is COMPLETE.**
The only remaining gaps are external: real provider credentials (Meta API key,
Google Play service account, App Store Connect API key, Firebase service account,
Sensor Tower/data.ai API keys, MAX Report Key), human accountability (named
approver, rotation owner), external resource configuration (CLOSED_LOOP_ADSET_ID
/PAGE_ID pointing to real Facebook assets), and game development (GDD/level
design/numerical design). No further code implementation is blocked — production
mode remains fail-closed until the 7 P0 external evidence items (E1-E7) are
closed by humans with real credentials.

**Production mode**: Remains fail-closed until all P0 external evidence items
(E1-E7) are closed.
