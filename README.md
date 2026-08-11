# Market Ops System

Runnable Python framework for a Feishu-based Market Ops loop:

- collect marketing data from Feishu Sheets, Feishu Bitable, or local CSV files
- generate weekly AI analysis for growth and creative review
- write draft action items into an action tracker
- run daily status sync with KPI callback and overdue detection

## Included

- `Ads Performance`, `Creative Library`, `Geo Performance` ingestion
- Adjust revenue ingestion through the existing dashboard config
- weekly report generation
- weekly digest generation and Feishu bot delivery
- action tracker writeback to local CSV or Feishu Sheets
- meeting reports writeback to Feishu Sheets
- daily task status sync
- daily sync summary output
- Feishu sheet normalization into internal standard CSV tables

## V2 Growth Roadmap

The next upgrade target is documented in `AI_MEDIA_BUYER_V2_ROADMAP.md`.
It defines the path from the current AI risk-control reporting system to an AI growth / media-buyer system, including creative DNA, creative clustering, fatigue detection, growth priority scoring, dynamic payback targets, user quality, and later approval-based action automation.

Phase 1 growth priority ranking is available as a standalone report:

```powershell
python -m market_ops.cli growth-priorities --report-date latest
```

It writes `growth_priorities_YYYYMMDD.md/json/csv` under `output/active/`. This command only generates recommendations; it does not send Feishu cards or change ad budgets.

## Project Layout

```text
.
|-- examples/
|-- input/
|-- output/
|   |-- active/
|   |-- archive/
|-- src/market_ops/
|   |-- clients/
|   |-- analyzers.py
|   |-- cli.py
|   |-- config.py
|   |-- pipeline.py
|   |-- reports.py
|   `-- task_sync.py
|-- .env.example
`-- README.md
```

## Creative Growth Loop V15 — Migration Notice

As of 2026-06, the original `src/market_ops/creative_loop/` has been superseded by **`src/market_ops/creative_growth_loop/`** (V15).

### Migration Map

| Old Module (`creative_loop/`) | V15 Module (`creative_growth_loop/`) | What's New in V15 |
|---|---|---|
| `pattern_engine.py` | `03_gene/gene_extractor.py` | 13-field CreativeGene + GeneLock |
| `mutation_engine.py` | `04_mutation/` | All 8 original mutation types + Hook+Overlay+Subject+Composition |
| `prompt_builder.py` | `05_prompt/prompt_builder.py` | Enhanced prompt builder |
| `image_generator.py` | `06_generation/image_generator.py` | lovart/gpt_image/flux/sdxl multi-engine fallback |
| `image_validator.py` | `07_validation/` | SimilarityFilter + DuplicateFilter + ImageQualityFilter |
| `scoring_engine.py` | `08_scoring/creative_score_engine.py` | 6-dimension scoring + diversity penalty |
| `library_manager.py` | `11_memory/` + `02_performance/` | WinnerMemory + LoserMemory + FamilyTree |
| `creative_loop.py` | `13_scheduler/daily_runner.py` | 10-step daily pipeline + auto_publish |

### New Capabilities (V15 Only)

| Module | Description |
|---|---|
| `01_collectors/` | Facebook Ads + AppsFlyer data-driven collection |
| `02_performance/` | WinnerEngine + LoserEngine performance ranking |
| `09_family/` | CreativeFamilyEngine family grouping |
| `10_explore/` | (已迁移至 `creative_intelligence/final_bandit.py`, Spec §13 封版) |
| `14_publish/` | FacebookPublisher end-to-end ad publishing |

### Deprecation Behavior

Importing any module from `market_ops.creative_loop` triggers a `DeprecationWarning` directing you to the V15 equivalent. Use:

```python
import warnings
warnings.filterwarnings("always", category=DeprecationWarning)
```

## Quick Start

1. Copy `.env.example` to `.env`
2. Fill Feishu and Adjust config values
3. Install and run:

```bash
python -m pip install -e .
python -m market_ops.cli sync-feishu-sources --print-summary
python -m market_ops.cli weekly-run --report-date latest --meeting-name "Weekly Market Ops Review"
python -m market_ops.cli weekly-pack --report-date latest --meeting-name "Weekly Market Ops Review" --send
python -m market_ops.cli weekly-digest --report-date latest --meeting-name "Weekly Market Ops Review" --send
python -m market_ops.cli creative-action-thresholds --report-date latest
python -m market_ops.cli report-audit --report-date latest
python -m market_ops.cli meeting-closeout --report-date latest --meeting-name "Weekly Market Ops Review"
python -m market_ops.cli daily-sync --as-of-date 2026-06-05
python -m market_ops.cli feishu-event-check --public-base-url https://your-domain.com
python -m market_ops.cli feishu-event-allowlist-suggest
python -m market_ops.cli feishu-event-allowlist-apply
python -m market_ops.cli feishu-event-server --host 0.0.0.0 --port 8080
python -m market_ops.cli feishu-event-simulate --report-date latest --text "@机器人 详细版"
```

Outputs are split by purpose:

- user-facing `.md` / `.json` reports and previews go to `output/active/`
- archived legacy outputs go to `output/archive/`
- raw `.csv` data exports and normalized tables stay under `output/`

## Weekly Market Group Send

Use this as the standard market-group send path. It syncs Feishu and Adjust source data first, then runs the self-check gate and report audit gate. If any gate fails, it does not send any webhook.

To preview everything without sending:

```powershell
.\preview_weekly_reports.ps1
```

This generates local previews, the self-check report, the report audit, the pre-send summary, and the weekly health check.
It also generates a single closure ledger so you can see, in one place, what is already ready, what is still pending, and what is blocked.

Current send gate behavior is fixed:

- if self-check fails: preview only, no webhook send
- if report audit fails: preview only, no webhook send
- if pre-send summary fails: preview only, no webhook send
- even when send passes, local preview files are still kept for traceability

```powershell
.\send_market_weekly_all.ps1
```

Equivalent manual CLI sequence:

```powershell
python -m market_ops.cli sync-feishu-sources --print-summary
python -m market_ops.cli card-preview --report-date latest
python -m market_ops.cli report-audit --report-date latest
python -m market_ops.cli market-send --report-date latest --all
```

This sends three cards to the market group:

- simple market summary
- detailed market report
- recovery report

The boss group is intentionally not included in this command.

The main files to inspect before or after a send are:

- `output/active/weekly_preview_overview_YYYYMMDD.md`
- `output/active/self_check_YYYYMMDD.md`
- `output/active/report_audit_YYYYMMDD.md`
- `output/active/pre_send_summary_YYYYMMDD.md`
- `output/active/weekly_health_check_YYYYMMDD.md`
- `output/active/closure_status_YYYYMMDD.md`

To install a Windows scheduled task for every Thursday at 15:00:

```powershell
.\install_weekly_market_send_task.ps1
```

To run the full local health check without sending:

```powershell
python -m market_ops.cli health-check --report-date latest
```

This will:

- regenerate previews
- rerun self-check and report audit
- rebuild the pre-send summary
- simulate the detailed-reply callback path
- write `weekly_health_check_YYYYMMDD.md`

If you only want the closure ledger:

```powershell
python -m market_ops.cli closure-status --report-date latest
```

To inspect the remaining manual gaps one by one:

```powershell
python -m market_ops.cli project-detail-coverage --report-date latest
python -m market_ops.cli p04-source-checklist --report-date latest
python -m market_ops.cli p04-verify-after-mapping --report-date latest
python -m market_ops.cli detail-reply-checklist --report-date latest
python -m market_ops.cli external-blockers --report-date latest
```

These commands answer:

- which projects really entered trusted project-level detail coverage
- why `P04` is still outside the trusted detail chain
- after filling `P04` links, whether `P04` has really become `trusted`
- whether the detailed in-group reply is already locked to a real Feishu chat
- one consolidated checklist for all remaining external blockers

For `P04`, the fastest path is:

1. Fill `output/active/p04_project_sheet_sources_template.env`
2. Copy the updated `FEISHU_PROJECT_SHEET_SOURCES_JSON` back into `.env`
3. Run:

```powershell
python -m market_ops.cli p04-verify-after-mapping --report-date latest
```

That command also writes:

- `output/active/p04_mapping_verify_YYYYMMDD.md`
- `output/active/p04_mapping_verify_YYYYMMDD.json`

## Manual Boss Group Send

Boss group sending is manual only. This script syncs Feishu and Adjust source data first, runs self-check and report audit, then sends the boss executive card and recovery card. It requires typing `SEND` before it sends anything.

```powershell
.\send_boss_manual.ps1
```

For a non-interactive confirmed run:

```powershell
.\send_boss_manual.ps1 -Force
```

## Local CSV Mode

These variables are already set in `.env.example`:

```env
ADS_PERFORMANCE_CSV=examples/ads_performance.sample.csv
CREATIVE_LIBRARY_CSV=examples/creative_library.sample.csv
GEO_PERFORMANCE_CSV=examples/geo_performance.sample.csv
ACTION_TRACKER_CSV=output/action_tracker.csv
MEETING_REPORTS_CSV=output/meeting_reports.csv
```

This mode is useful before real Feishu credentials are ready.

## Feishu Sheets Source Mode

When the team already works in Feishu Sheets rather than Bitable, configure:

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_DAILY_DATA_URL=https://.../sheets/...?...sheet=...
FEISHU_ROI_URL=https://.../wiki/...?...sheet=...
FEISHU_PROJECT_SHEET_SOURCES_JSON=[{"game":"P02 Mermaid","daily_url":"https://.../sheets/...?...sheet=...","roi_url":"https://.../wiki/...?...sheet=..."},{"game":"P07 Vampire","daily_url":"https://.../sheets/...?...sheet=...","roi_url":"https://.../wiki/...?...sheet=..."}]
FEISHU_ACTION_TRACKER_URL=https://.../sheets/...?...sheet=...
FEISHU_ACTION_TRACKER_SHEET_TITLE=Action Tracker
FEISHU_MEETING_REPORTS_URL=https://.../sheets/...?...sheet=...
FEISHU_MEETING_REPORTS_SHEET_TITLE=Meeting Reports
```

If you want creative analysis to come directly from Facebook instead of a Feishu creative sheet, configure:

```env
META_ACCESS_TOKEN=your_meta_system_user_or_long_lived_token
META_AD_ACCOUNT_ID=1234567890
META_API_VERSION=v22.0
```

When `META_ACCESS_TOKEN` and `META_AD_ACCOUNT_ID` are set, the sync flow will keep using Feishu for ads and Adjust for revenue, but it will source creatives from Facebook Ads instead of `FEISHU_CREATIVE_URL`.

If you also want Google Ads creatives included in the same analysis, configure:

```env
GOOGLE_ADS_DEVELOPER_TOKEN=your_google_ads_developer_token
GOOGLE_ADS_CLIENT_ID=your_oauth_client_id
GOOGLE_ADS_CLIENT_SECRET=your_oauth_client_secret
GOOGLE_ADS_REFRESH_TOKEN=your_oauth_refresh_token
GOOGLE_ADS_CUSTOMER_ID=1234567890
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
GOOGLE_ADS_CREATIVE_LOOKBACK_DAYS=7
```

When Google Ads credentials are present, the sync flow will merge Facebook creatives and Google Ads creatives into the same normalized creative table. If neither Facebook nor Google Ads is configured, the workflow falls back to the Feishu creative sheet.

You can also control when the system is allowed to auto-replace a `复制素材` action with a concrete `素材ID`:

```env
CREATIVE_ACTION_MIN_SPEND=50
CREATIVE_ACTION_MIN_ROI=1.0
```

Meaning:

- only creatives with spend at or above `CREATIVE_ACTION_MIN_SPEND`
- and total revenue ROI at or above `CREATIVE_ACTION_MIN_ROI`

are allowed to replace the manual creative label in weekly actions. If no candidate passes both thresholds, the system keeps the manual label and writes the reason into the preview and self-check report.

To see what each threshold setting would actually select on the current week, run:

```bash
python -m market_ops.cli creative-action-thresholds --report-date latest
```

This writes:

- `output/active/creative_action_thresholds_YYYYMMDD.md`
- `output/active/creative_action_thresholds_YYYYMMDD.json`

Then run:

```bash
python -m market_ops.cli sync-feishu-sources --print-summary
python -m market_ops.cli weekly-run --report-date latest --meeting-name "Weekly Market Ops Review"
```

`FEISHU_PROJECT_SHEET_SOURCES_JSON` is optional. Use it when different projects live in different Feishu books. Each item should include:

- `game`: the project name you want in the report, for example `P02 Mermaid`
- `daily_url`: the Feishu sheet or wiki URL that contains that project's daily data tabs
- `roi_url`: optional separate ROI book URL; if omitted, the workflow will look for ROI tabs in the same book as `daily_url`

The sync command normalizes the current Feishu sheets into:

- `output/normalized/ads_performance.csv`
- `output/normalized/creative_library.csv`
- `output/normalized/geo_performance.csv`

If the target writeback sheets do not exist yet, the workflow will create them automatically before writing rows.

## OpenAI Mode

```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=
```

## Feishu Bitable Mode

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_BITABLE_APP_TOKEN=bascnxxx
ADS_PERFORMANCE_TABLE_ID=tbl_ads
CREATIVE_LIBRARY_TABLE_ID=tbl_creative
GEO_PERFORMANCE_TABLE_ID=tbl_geo
ACTION_TRACKER_TABLE_ID=tbl_action
MEETING_REPORTS_TABLE_ID=tbl_reports
```

## Expected Fields

### Ads Performance

- `Date`
- `Channel`
- `Country`
- `Game`
- `Spend`
- `Impressions`
- `Clicks`
- `CPI`
- `ROAS`
- `Retention D1`
- `Retention D7`
- `Retention D30`

### Creative Library

- `Asset ID`
- `Video URL`
- `Hook Type`
- `Duration`
- `CTR`
- `CVR`
- `ROAS`
- `Status`

### Geo Performance

- `Country`
- `CPI Trend`
- `ROAS Trend`
- `Growth Stage`
- `Suggested Action`

### Action Tracker

- `Task ID`
- `Source Meeting`
- `Type`
- `Title`
- `Owner`
- `Status`
- `Acceptance Metric`
- `Due Date`
- `Description`
- `Latest Note`

### Meeting Reports

- `Meeting Name`
- `Report Date`
- `Growth Summary`
- `Creative Summary`
- `Strategy Summary`
- `Report Path`

## Commands

### Weekly Report

```bash
python -m market_ops.cli weekly-run --report-date latest --meeting-name "Weekly Market Ops Review"
```

### Weekly Pack

Use this when you want to generate and optionally send both the market-team report and the boss report in one run.

```bash
python -m market_ops.cli weekly-pack --report-date latest --meeting-name "Weekly Market Ops Review"
python -m market_ops.cli weekly-pack --report-date latest --meeting-name "Weekly Market Ops Review" --send
```

Weekly commands follow the meeting cadence automatically:

- if you run on Thursday, the reporting window is still last Thursday through this Wednesday
- `latest` and a Thursday meeting date both align to the same Wednesday cutoff

Creates:

- weekly markdown report
- draft action items
- report index record

### Daily Sync

```bash
python -m market_ops.cli daily-sync --as-of-date 2026-06-05
```

Creates:

- status updates for action tracker
- latest task notes
- overdue task list
- markdown sync summary

### Approve Meeting Actions

```bash
python -m market_ops.cli approve-meeting-actions --report-date latest --meeting-name "Weekly Market Ops Review"
```

Creates:

- batch transition from `待确认` to `执行中`
- meeting confirmation note for each approved action
- synced action status back to Feishu Sheets

### Weekly Group Digest

```bash
python -m market_ops.cli weekly-digest --report-date latest --meeting-name "Weekly Market Ops Review"
```

If you also configure `FEISHU_MARKET_WEBHOOK`, you can send it directly:

```bash
python -m market_ops.cli weekly-digest --report-date latest --meeting-name "Weekly Market Ops Review" --send
```

Optional inputs for the digest:

```env
FEISHU_MARKET_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
FEISHU_EVENT_VERIFICATION_TOKEN=your_callback_token
FEISHU_EVENT_PATH=/feishu/events
FEISHU_DETAIL_TRIGGER_KEYWORDS=详细,详细版,周报详细版,详版
COMPANY_OVERVIEW_URL=https://your-gemini-overview-page
COMPANY_OVERVIEW_MARKDOWN=input/company_overview.md
```

If `COMPANY_OVERVIEW_MARKDOWN` is still a placeholder, or `COMPANY_OVERVIEW_URL` is empty, the weekly digest will automatically generate the company overview from the latest ads and Adjust revenue data.

## Feishu @ Bot Detailed Reply

Use this when the group should receive the simple market card first, and only reply with the detailed version after someone mentions the bot and asks for details.

Required in Feishu:

- enable event subscription for `im.message.receive_v1`
- point the callback URL to `http(s)://your-host/feishu/events`
- keep callback encryption disabled for now

Recommended environment:

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_EVENT_VERIFICATION_TOKEN=your_callback_token
FEISHU_EVENT_PATH=/feishu/events
FEISHU_DETAIL_TRIGGER_KEYWORDS=详细,详细版,周报详细版,详版
FEISHU_DETAIL_ALLOWED_CHAT_IDS=
```

Run the callback service:

```bash
python -m market_ops.cli feishu-event-check --public-base-url https://your-domain.com
python -m market_ops.cli feishu-event-server --host 0.0.0.0 --port 8080
```

Simulate one local `@机器人` detailed request before going live:

```bash
python -m market_ops.cli feishu-event-simulate --report-date latest --text "@机器人 详细卡片"
```

Behavior:

- the normal scheduled send path still sends the simple market version by default
- if someone mentions the bot in a group and the message contains one of the detail keywords, the server runs the same send gate as the weekly send path
- only when self-check, report audit, and pre-send summary all pass will it reply in the same chat with the detailed market card and the recovery card
- if the gate fails, it only generates local preview and audit files, and does not send anything back to the group
- if `FEISHU_DETAIL_ALLOWED_CHAT_IDS` is empty, the server prints the incoming `chat_id` when a detail trigger matches, so you can lock it down to the market test group afterward
- the same trigger also writes recent chat observations into `output/active/feishu_detail_chat_observations.json`, so you can copy the real `chat_id` from that file
- you can also run `python -m market_ops.cli feishu-event-allowlist-suggest` to get a ready-to-paste `FEISHU_DETAIL_ALLOWED_CHAT_IDS=` value
- after you have a real observed `oc_...` group id, you can run `python -m market_ops.cli feishu-event-allowlist-apply` to write it back into `.env`
- if you already know the real group id, you can also run `python -m market_ops.cli feishu-event-allowlist-apply --chat-id oc_xxx`; the command will back up `.env` first

### Meeting Closeout

```bash
python -m market_ops.cli meeting-closeout --report-date latest --meeting-name "Weekly Market Ops Review"
```

If you want to update the task sheet without sending the closeout card to Feishu, use:

```bash
python -m market_ops.cli meeting-closeout --report-date latest --meeting-name "Weekly Market Ops Review" --no-send
```

Creates:

- batch transition from pending meeting actions into execution
- closeout summary markdown in `output/active/meeting_closeout_YYYYMMDD.md`
- optional Feishu group closeout card with approved owners and actions

Optional owner assignment rules:

```env
DEFAULT_TASK_OWNER=TBD
TASK_OWNER_RULES_JSON={"by_action_type":{"减量":"林凯","加码":"林凯","暂停":"林凯","复制素材":"牟耕"},"by_game":{"P04 Witch":"姜会伟"}}
```

Rule priority:

- explicit owner returned by AI
- `by_game`
- `by_action_type`
- `by_target_keyword`
- fallback owner

## Suggested Operating Rhythm

- weekly meeting time: every Thursday at 15:30
- automated market group send: every Thursday at 15:00
- pre-meeting automation runs self-check first, then sends simple market, detailed market, and recovery cards
- if self-check fails, automation only generates preview files and does not send webhook messages
- boss group remains manual/paused until explicitly enabled
- boss send requires both `ALLOW_BOSS_SEND=true` and `FEISHU_BOSS_WEBHOOK`
- `meeting-closeout` runs manually immediately after the weekly meeting
- manual decisions still happen during the meeting
- `daily-sync` runs once per day for KPI callback and risk detection
- optional Feishu workflow notification can reuse the daily sync summary
