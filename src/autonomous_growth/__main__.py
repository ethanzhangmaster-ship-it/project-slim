"""Production readiness command: python -m src.autonomous_growth [dry_run|production]."""
import json
import sys

from .models import AgentConfig
from .readiness import ProductionReadinessGate


mode = sys.argv[1] if len(sys.argv) > 1 else "dry_run"
required = (["MAX_REPORT_KEY", "PLAY_SERVICE_ACCOUNT_JSON"]
            if mode == "production" else [])
report = ProductionReadinessGate(".").check(AgentConfig(mode=mode, required_env=required))
print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
raise SystemExit(0 if report.ready else 2)
