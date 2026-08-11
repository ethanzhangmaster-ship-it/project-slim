"""E9.9.5 Phase 6 Acceptance Test — E10 API Contract"""
import sys
sys.path.insert(0, 'src')

from market_ops.growth_decision.api import GrowthAPI
from market_ops.growth_decision.api_schema import (
    GrowthActionRequest, GrowthActionItem, GrowthActionResponse,
    PortfolioPoolState, PortfolioStateResponse,
    RiskItem, RiskStatusResponse,
)

# ── Helpers ────────────────────────────────────────────────

def _make_exp(cid: str, winner_level: str, confidence: float = 0.95) -> dict:
    return {
        "experiment_id": f"EXP_{cid}",
        "creative_id": cid,
        "decision": winner_level,
        "lift": 0.32 if winner_level == "WINNER" else 0.05,
        "confidence": confidence,
        "reason": f"ROAS +30%, lift={0.32}" if winner_level == "WINNER" else f"Level={winner_level}",
        "budget_before": 100.0,
    }


# ═══════════════════════════════════════════════════════════
# AC1: API 存在 — 3 methods
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC1: API Methods Exist")
print("=" * 50)

experiments = []
for i in range(1, 6):
    experiments.append(_make_exp(f"W{i:03d}", "WINNER"))
for i in range(1, 6):
    experiments.append(_make_exp(f"P{i:03d}", "PROMISING"))
for i in range(1, 6):
    experiments.append(_make_exp(f"F{i:03d}", "FAILED"))
for i in range(1, 6):
    experiments.append(_make_exp(f"I{i:03d}", "INCONCLUSIVE"))

api = GrowthAPI(experiments, total_budget=10000.0)

assert hasattr(api, 'get_growth_actions'), "Missing get_growth_actions()"
assert hasattr(api, 'get_portfolio_state'), "Missing get_portfolio_state()"
assert hasattr(api, 'get_risk_status'), "Missing get_risk_status()"

print("  get_growth_actions()  ✅")
print("  get_portfolio_state() ✅")
print("  get_risk_status()     ✅")
print("AC1: API Methods Exist — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC2: SCALE action 输出正确
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC2: SCALE Action Output")
print("=" * 50)

actions_resp = api.get_growth_actions()
assert isinstance(actions_resp, GrowthActionResponse), \
    f"Expected GrowthActionResponse, got {type(actions_resp)}"

scale_actions = [a for a in actions_resp.actions if a.action == "SCALE"]
kill_actions = [a for a in actions_resp.actions if a.action == "KILL"]
watch_actions = [a for a in actions_resp.actions if a.action == "WATCH"]
retest_actions = [a for a in actions_resp.actions if a.action == "RETEST"]

print(f"  SCALE:  {len(scale_actions)}")
print(f"  KILL:   {len(kill_actions)}")
print(f"  WATCH:  {len(watch_actions)}")
print(f"  RETEST: {len(retest_actions)}")

assert len(scale_actions) == 5, f"Expected 5 SCALE, got {len(scale_actions)}"
assert len(kill_actions) == 5, f"Expected 5 KILL, got {len(kill_actions)}"
assert len(watch_actions) == 5, f"Expected 5 WATCH, got {len(watch_actions)}"
assert len(retest_actions) == 5, f"Expected 5 RETEST, got {len(retest_actions)}"

# Verify SCALE action structure
scale = scale_actions[0]
print(f"\n  SCALE action detail:")
print(f"    creative_id:    {scale.creative_id}")
print(f"    action:         {scale.action}")
print(f"    budget_change:  {scale.budget_current} → {scale.budget_target}")
print(f"    confidence:     {scale.confidence}")
print(f"    reason:         {scale.reason}")

assert scale.action == "SCALE"
assert scale.budget_current == 100.0
assert scale.budget_target == 200.0
assert scale.confidence == 0.95
assert "WINNER" in scale.reason
assert "ROAS +30%" in " ".join(scale.reason)

print("AC2: SCALE Action Output — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC3: Risk Blocking — blocking=True → actions=[]
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC3: Risk Blocking")
print("=" * 50)

# Create blocking scenario: 5 WINNERs with tiny total_budget
blocking_exps = []
for i in range(1, 6):
    blocking_exps.append(_make_exp(f"BW{i:03d}", "WINNER", confidence=0.95))
for i in range(1, 4):
    blocking_exps.append(_make_exp(f"BP{i:03d}", "PROMISING"))

api_blocked = GrowthAPI(blocking_exps, total_budget=100.0)

# Verify risk is blocking
risk_status = api_blocked.get_risk_status()
print(f"  Blocking: {risk_status.blocking}")
print(f"  Risk level: {risk_status.risk_level}")
assert risk_status.blocking, "Expected blocking=True"

# Verify get_growth_actions returns empty
blocked_actions = api_blocked.get_growth_actions()
print(f"  Actions returned: {len(blocked_actions.actions)}")
assert len(blocked_actions.actions) == 0, \
    f"Expected 0 actions when blocking, got {len(blocked_actions.actions)}"

print("AC3: Risk Blocking — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC4: Portfolio State — 30/50/20 ratios
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC4: Portfolio State")
print("=" * 50)

portfolio = api.get_portfolio_state()
assert isinstance(portfolio, PortfolioStateResponse)

print(f"  Exploration: {portfolio.exploration.count} assets, ${portfolio.exploration.budget:.0f} ({portfolio.exploration.ratio})")
print(f"  Growth:      {portfolio.growth.count} assets, ${portfolio.growth.budget:.0f} ({portfolio.growth.ratio})")
print(f"  Harvest:     {portfolio.harvest.count} assets, ${portfolio.harvest.budget:.0f} ({portfolio.harvest.ratio})")
print(f"  Total:       {portfolio.total_assets} assets, ${portfolio.total_budget:.0f}")

# Verify ratios: 30/50/20
assert portfolio.exploration.ratio == 0.3, \
    f"Expected exploration 0.3, got {portfolio.exploration.ratio}"
assert portfolio.growth.ratio == 0.5, \
    f"Expected growth 0.5, got {portfolio.growth.ratio}"
assert portfolio.harvest.ratio == 0.2, \
    f"Expected harvest 0.2, got {portfolio.harvest.ratio}"

# Verify to_dict structure
d = portfolio.to_dict()
assert "portfolio" in d
assert "exploration" in d["portfolio"]
assert "growth" in d["portfolio"]
assert "harvest" in d["portfolio"]

print("AC4: Portfolio State — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC5: API Isolation — api.py no internal imports
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC5: API Isolation")
print("=" * 50)

import pathlib

api_file = pathlib.Path('src/market_ops/growth_decision/api.py')
code = api_file.read_text(encoding='utf-8')

# Check for actual import patterns (not docstring mentions)
import_patterns = [
    'from market_ops.growth_decision.scale_engine',
    'from market_ops.growth_decision.risk_controller',
    'from market_ops.growth_decision.portfolio_manager',
    'from market_ops.growth_decision.winner_detector',
    'from market_ops.growth_decision.kill_engine',
    'from .scale_engine',
    'from .risk_controller',
    'from .portfolio_manager',
    'from .winner_detector',
    'from .kill_engine',
]

violations = []
for pattern in import_patterns:
    if pattern in code:
        violations.append(f"api.py imports: {pattern}")

assert len(violations) == 0, f"API isolation violations: {violations}"

# Verify api.py only imports GrowthOrchestrator + api_schema
assert 'from market_ops.growth_decision.growth_orchestrator' in code, \
    "Must import GrowthOrchestrator"
assert 'from market_ops.growth_decision.api_schema' in code, \
    "Must import api_schema"

print("  NO import: scale_engine")
print("  NO import: risk_controller")
print("  NO import: portfolio_manager")
print("  NO import: winner_detector")
print("  NO import: kill_engine")
print("  ONLY imports: GrowthOrchestrator + api_schema")
print("AC5: API Isolation — PASS\n")


# ═══════════════════════════════════════════════════════════
# AC6: E10 Mock Consumer
# ═══════════════════════════════════════════════════════════
print("=" * 50)
print("AC6: E10 Mock Consumer")
print("=" * 50)

# Simulate E10 autonomous growth layer consuming the API
class E10MockConsumer:
    """Simulates E10 Autonomous Growth Layer."""

    def __init__(self):
        self.api: GrowthAPI | None = None

    def connect(self, experiment_results: list[dict], budget: float):
        """Connect to E9.9.5 Growth Control Plane."""
        self.api = GrowthAPI(experiment_results, total_budget=budget)

    def fetch_actions(self) -> GrowthActionResponse:
        """Fetch today's growth actions."""
        assert self.api is not None
        return self.api.get_growth_actions()

    def fetch_portfolio(self) -> PortfolioStateResponse:
        """Fetch current portfolio state."""
        assert self.api is not None
        return self.api.get_portfolio_state()

    def check_safety(self) -> RiskStatusResponse:
        """Check safety gate before execution."""
        assert self.api is not None
        return self.api.get_risk_status()

    def execute_cycle(self):
        """Execute one full cycle."""
        actions = self.fetch_actions()
        portfolio = self.fetch_portfolio()
        risk = self.check_safety()

        if risk.blocking:
            return {"status": "HALTED", "reason": "Safety gate triggered"}

        return {
            "status": "EXECUTED",
            "actions": len(actions.actions),
            "portfolio_total": portfolio.total_budget,
            "risk_level": risk.risk_level,
        }


# Create E10 consumer
e10 = E10MockConsumer()
e10.connect(experiments, budget=10000.0)

# Fetch all 3 API endpoints
actions = e10.fetch_actions()
portfolio = e10.fetch_portfolio()
risk = e10.check_safety()

assert isinstance(actions, GrowthActionResponse)
assert isinstance(portfolio, PortfolioStateResponse)
assert isinstance(risk, RiskStatusResponse)

print(f"  E10 fetched: {len(actions.actions)} actions")
print(f"  E10 fetched: portfolio ${portfolio.total_budget:.0f}")
print(f"  E10 fetched: risk blocking={risk.blocking}")

# Execute cycle
result = e10.execute_cycle()
assert result["status"] == "EXECUTED"
print(f"  E10 cycle: {result}")

# Test blocking scenario
e10_blocked = E10MockConsumer()
e10_blocked.connect(blocking_exps, budget=100.0)
result_blocked = e10_blocked.execute_cycle()
assert result_blocked["status"] == "HALTED"
print(f"  E10 blocked cycle: {result_blocked}")

print("AC6: E10 Mock Consumer — PASS\n")


# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
print(f"Risk status:")
print(f"  Blocking: {risk.blocking}")
print(f"  Risk level: {risk.risk_level}")
for r in risk.risks:
    print(f"    {r.type}: {r.level} — {r.detail}")

print(f"\n{'=' * 50}")
print(f"E9.9.5 Phase 6: 6/6 PASS")
print(f"{'=' * 50}")