# E10 Autonomous Growth Layer — PRD v1.0

**Status**: FROZEN — Architecture Design Contract  
**Date**: 2026-07-20  
**Depends on**: E9.9.5 Growth Control Plane (PRODUCTION READY)  
**Next**: E10.1 Execution Runtime Implementation

---

# 1. System Positioning

## 1.1 Role in Growth OS

```
E9.9.5 Growth Control Plane
         │
         │  GrowthAction[]
         │  "What should we do?"
         ↓
E10 Autonomous Growth Layer
         │
         │  ExecutionTask[]
         │  "How do we execute it?"
         ↓
  UA Platforms (Meta / Google / TikTok)
```

E9.9.5 answers: **"What growth actions should we take?"**  
E10 answers: **"How do we execute those actions autonomously?"**

E10 is the **Execution Plane**, not the Decision Plane. It must not add new decision logic, creative strategy, or risk evaluation. Those belong to E9.9.5.

## 1.2 Core Principle

> E10 executes decisions. It does not make them.

All intelligence lives in E9.9.5. E10 is a reliable, safe, auditable execution layer.

---

# 2. Module Boundary

## 2.1 E10 Sub-module Split

```
E10 Autonomous Growth
│
├── E10.1 Execution Runtime        ← Phase 1 (this PRD)
├── E10.2 UA Automation
├── E10.3 Budget Executor
├── E10.4 Creative Deployment
├── E10.5 Market Feedback Loop
├── E10.6 Autonomous Controller
```

### 2.1.1 E10.1 Execution Runtime (Phase 1 Scope)

- Task creation from E9.9.5 GrowthAction
- Execution state machine
- Approval gating
- Result collection
- Feedback loop back to E9.9.5

### 2.1.2 E10.2 UA Automation (Future)

- Meta Ads API integration
- Google Ads API integration
- TikTok Ads API integration
- Campaign CRUD operations

### 2.1.3 E10.3 Budget Executor (Future)

- Budget change execution
- Daily spend cap enforcement
- Multi-platform budget sync

### 2.1.4 E10.4 Creative Deployment (Future)

- Creative asset upload
- Ad creative lifecycle management
- Platform-specific creative validation

### 2.1.5 E10.5 Market Feedback Loop (Future)

- Real-time performance data ingestion
- Attribution data integration
- Feedback signal generation

### 2.1.6 E10.6 Autonomous Controller (Future)

- Full autonomous mode
- Self-healing execution
- Multi-platform orchestration

## 2.2 E10.1 Package Structure

```
src/market_ops/autonomous_growth/
│
├── __init__.py
├── schemas.py              # ExecutionTask, ExecutionResult, ApprovalRequest
├── execution_engine.py     # Core execution runtime
├── approval_gate.py        # Human-in-the-loop safety layer
├── result_collector.py     # Execution result aggregation
├── feedback_loop.py        # E9.9.5 feedback signal generation
├── api.py                  # Internal E10 API (consumed by E10.2-E10.6)
└── export.py               # Execution logs and audit trail
```

---

# 3. Execution Schema

## 3.1 ExecutionTask

```python
@dataclass
class ExecutionTask:
    task_id: str                    # UUID
    correlation_id: str             # From E9.9.5 GrowthOrchestrator

    # Source
    action: str                     # SCALE / KILL / WATCH / RETEST
    creative_id: str
    growth_decision_id: str         # Reference to E9.9.5 GrowthDecision

    # Budget
    budget_before: float
    budget_after: float

    # Target
    channel: str                    # facebook / google / tiktok

    # Status
    status: str                     # ExecutionStatus enum
    approval_required: bool
    approver: str                   # Who approved (empty if auto)

    # Risk
    risk_level: str                 # from E9.9.5 RiskReport

    # Timing
    created_at: str
    approved_at: str
    executed_at: str
    verified_at: str
    completed_at: str

    # Result
    result: ExecutionResult | None
```

## 3.2 ExecutionResult

```python
@dataclass
class ExecutionResult:
    task_id: str
    success: bool
    platform_response: dict         # Raw API response
    actual_budget_applied: float
    error_message: str
    retry_count: int
    verified_at: str
```

## 3.3 ExecutionStatus Enum

```python
class ExecutionStatus(str, Enum):
    CREATED = "CREATED"           # Task created, not yet processed
    PENDING_APPROVAL = "PENDING_APPROVAL"  # Waiting for human review
    APPROVED = "APPROVED"         # Approved, ready to execute
    REJECTED = "REJECTED"         # Human rejected
    EXECUTING = "EXECUTING"       # API call in progress
    VERIFYING = "VERIFYING"       # Verifying execution result
    COMPLETED = "COMPLETED"       # Successfully executed and verified
    FAILED = "FAILED"             # Execution failed
    ROLLING_BACK = "ROLLING_BACK" # Reverting the change
    ROLLED_BACK = "ROLLED_BACK"   # Successfully reverted
```

## 3.4 ApprovalRequest

```python
@dataclass
class ApprovalRequest:
    request_id: str
    task_id: str
    action: str
    creative_id: str
    budget_change: dict           # {before, after}
    risk_level: str
    reason: str                   # Why this needs human approval
    created_at: str
    status: str                   # PENDING / APPROVED / REJECTED
```

---

# 4. Execution State Machine

## 4.1 Happy Path

```
CREATED
    │
    │  risk_level == SAFE
    ↓
APPROVED (auto)
    │
    │  risk_level == WARNING
    ↓
PENDING_APPROVAL (human)
    │
    │  human approves
    ↓
APPROVED
    │
    ↓
EXECUTING
    │
    │  API call succeeds
    ↓
VERIFYING
    │
    │  verification passes
    ↓
COMPLETED
```

## 4.2 Failure Path

```
EXECUTING
    │
    │  API call fails
    ↓
FAILED
    │
    │  retry < max_retries
    ↓
EXECUTING (retry)
    │
    │  retry exhausted
    ↓
ROLLING_BACK
    │
    │  rollback succeeds
    ↓
ROLLED_BACK
```

## 4.3 Rejection Path

```
PENDING_APPROVAL
    │
    │  human rejects
    ↓
REJECTED
```

## 4.4 Transition Rules

| From | To | Condition |
|------|----|-----------|
| CREATED | APPROVED | risk_level == SAFE |
| CREATED | PENDING_APPROVAL | risk_level in (WARNING, CRITICAL) |
| PENDING_APPROVAL | APPROVED | human approves |
| PENDING_APPROVAL | REJECTED | human rejects |
| APPROVED | EXECUTING | auto |
| EXECUTING | VERIFYING | API success |
| EXECUTING | FAILED | API error |
| FAILED | EXECUTING | retry_count < max_retries |
| FAILED | ROLLING_BACK | retry_count >= max_retries |
| ROLLING_BACK | ROLLED_BACK | rollback success |
| VERIFYING | COMPLETED | verification passes |
| VERIFYING | FAILED | verification fails |

---

# 5. Approval Policy

## 5.1 Tiered Approval

| Risk Level | Approval Mode | Max Budget Change | Auto Execute |
|-----------|---------------|-------------------|-------------|
| SAFE | AUTO | ≤ $200/day | Yes |
| WARNING | HUMAN | ≤ $500/day | No |
| CRITICAL | HUMAN + MANAGER | Any | No |

## 5.2 Auto-Approval Criteria

All must be true:
1. `risk_level == SAFE`
2. `budget_after - budget_before <= 200`
3. `scale_step <= 2` (100→200 or 200→500)
4. `action != KILL` (kill always needs human)

## 5.3 Human Approval Required

- `risk_level == WARNING` or `CRITICAL`
- Budget change > $200/day
- Scale step > 2 (500→1000+)
- KILL action (always)
- New channel campaign creation

## 5.4 Manager Approval Required

- `risk_level == CRITICAL`
- Budget change > $1000/day
- Scale step == 5 (2000→5000)

---

# 6. Safety Strategy

## 6.1 Execution Guardrails

### 6.1.1 Pre-Execution Checks

Before ANY execution:
1. Verify E9.9.5 risk status is not blocking
2. Verify creative still exists in platform
3. Verify budget change within platform limits
4. Verify no duplicate execution (idempotency check)

### 6.1.2 Execution Timeout

- Max execution time: 30 seconds per task
- Timeout → FAILED → retry

### 6.1.3 Rate Limiting

- Max 10 executions per minute
- Max 100 executions per hour
- Prevents platform API throttling

### 6.1.4 Rollback Capability

Every SCALE action must support rollback:
- Record `budget_before` before execution
- Rollback API call: restore to `budget_before`
- KILL actions: NOT rollback-able (destructive)

## 6.2 Circuit Breaker

```
If failure_rate > 30% within 5 minutes:
    → PAUSE all executions
    → Alert human operator
    → Auto-resume after 15 minutes
```

## 6.3 Audit Trail

Every execution produces:
- `execution_log.jsonl` — append-only log
- `approval_log.jsonl` — human approval records
- `rollback_log.jsonl` — rollback operations

---

# 7. E10.1 API Contract

## 7.1 Input: E9.9.5 → E10

```python
from growth_decision.api import GrowthAPI

api = GrowthAPI(experiment_results, total_budget=10000)
actions = api.get_growth_actions()      # GrowthActionResponse
portfolio = api.get_portfolio_state()   # PortfolioStateResponse
risk = api.get_risk_status()            # RiskStatusResponse
```

## 7.2 E10.1 Internal API (for E10.2-E10.6)

```python
class ExecutionRuntime:
    def create_tasks(actions: GrowthActionResponse) -> list[ExecutionTask]
    def execute_task(task: ExecutionTask) -> ExecutionTask
    def execute_all() -> list[ExecutionTask]
    def rollback_task(task_id: str) -> ExecutionTask
    def get_task_status(task_id: str) -> ExecutionTask
    def get_pending_approvals() -> list[ApprovalRequest]
    def approve(request_id: str, approver: str) -> ExecutionTask
    def reject(request_id: str, approver: str, reason: str) -> ExecutionTask
```

## 7.3 Output: E10 → E9.9.5 Feedback

```
output/autonomous_growth/
├── execution_results.json       # All execution results
├── feedback_signals.json        # Signals for E9.9.5
├── execution_log.jsonl          # Audit trail
├── approval_log.jsonl           # Approval records
├── rollback_log.jsonl           # Rollback records
└── daily_execution_report.json  # Daily summary
```

---

# 8. E10.1 Implementation Scope

## 8.1 Phase 1 Inclusions

| Module | File | Responsibility |
|--------|------|---------------|
| schemas | `schemas.py` | ExecutionTask, ExecutionResult, ApprovalRequest |
| execution_engine | `execution_engine.py` | Task creation, state machine, mock execution |
| approval_gate | `approval_gate.py` | Tiered approval, auto/manual routing |
| result_collector | `result_collector.py` | Execution result aggregation |
| feedback_loop | `feedback_loop.py` | E9.9.5 feedback signal generation |
| api | `api.py` | Internal E10.1 API |
| export | `export.py` | Execution logs and audit trail |

## 8.2 Phase 1 Exclusions (Future Phases)

| Feature | Phase | Reason |
|---------|-------|--------|
| Meta Ads API integration | E10.2 | Requires OAuth, account setup |
| Google Ads API integration | E10.2 | Requires OAuth, account setup |
| Auto create ad accounts | E10.2 | High risk, needs human setup |
| Auto creative generation | E10.4 | Already in E9.8 scope |
| Auto store updates | E10.4 | Platform-specific, high risk |
| Auto product changes | E10.4 | Product-level, needs PM approval |
| Real-time budget sync | E10.3 | Requires multi-platform state |
| Full autonomous mode | E10.6 | Needs all sub-modules complete |

## 8.3 Mock Execution Strategy

E10.1 uses mock platform adapters:

```python
class MockPlatformAdapter:
    """Simulates UA platform API for development."""
    def execute_scale(creative_id, budget) -> dict:
        return {"status": "success", "budget_applied": budget}
    def execute_kill(creative_id) -> dict:
        return {"status": "success"}
    def rollback(creative_id, budget) -> dict:
        return {"status": "success", "budget_restored": budget}
```

Real API integration deferred to E10.2.

---

# 9. E10.1 Acceptance Criteria

## AC1: Task Creation

Input: 20 GrowthAction from E9.9.5  
Output: 20 ExecutionTask with correct status  
- 5 SCALE → CREATED, risk SAFE → APPROVED
- 5 KILL → CREATED → PENDING_APPROVAL
- 5 WATCH → CREATED (no execution needed)
- 5 RETEST → CREATED (no execution needed)

## AC2: Execution State Machine

Verify full happy path:
```
CREATED → APPROVED → EXECUTING → VERIFYING → COMPLETED
```

Verify failure → rollback:
```
EXECUTING → FAILED → ROLLING_BACK → ROLLED_BACK
```

## AC3: Approval Policy

- SAFE + budget ≤ 200 → AUTO APPROVED
- WARNING → PENDING_APPROVAL
- CRITICAL → PENDING_APPROVAL
- KILL action → always PENDING_APPROVAL

## AC4: Safety Guardrails

- Pre-execution: verify E9.9.5 risk not blocking
- Idempotency: duplicate task_id → skipped
- Timeout: execution > 30s → FAILED
- Rollback: SCALE rollback restores budget_before

## AC5: Feedback Loop

After execution:
- Generate feedback_signals.json
- Contains: task_id, action, success, platform_response
- Compatible with E9.9.5 GrowthDecision input format

## AC6: Audit Trail

- execution_log.jsonl: one line per execution
- approval_log.jsonl: one line per approval
- All logs JSON-serializable with timestamps

## AC7: Architecture

- NO import from E9.9.5 internal modules (only GrowthAPI)
- NO import from E9.9 (experiment_intelligence)
- NO import from E9.8 (creative_evolution)
- ONLY imports: growth_decision.api.GrowthAPI

## AC8: Performance

- 20 tasks → execution < 2 seconds
- 1000 tasks → execution < 10 seconds

---

# 10. Architecture Freeze Declaration

```
E10.1 Execution Runtime

STATUS: SPECIFICATION FROZEN
INPUT:  E9.9.5 GrowthAPI (3 endpoints)
OUTPUT: execution_results.json, feedback_signals.json
BOUNDARY: Execution Plane — no decision logic
NEXT: Implementation Phase
```

## Implementation Order

```
E10.1
  Phase 1: schemas.py              ← ExecutionTask, ExecutionResult, ApprovalRequest
  Phase 2: execution_engine.py     ← State machine + mock execution
  Phase 3: approval_gate.py        ← Tiered approval policy
  Phase 4: result_collector.py     ← Execution result aggregation
  Phase 5: feedback_loop.py        ← E9.9.5 feedback signals
  Phase 6: api.py + export.py      ← Internal API + audit trail
  Phase 7: Release Gate            ← 8 ACs
```

---

**PRD v1.0 Frozen. Ready for E10.1 Phase 1 Implementation.**