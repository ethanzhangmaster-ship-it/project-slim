# Agent Development Guide

## How to Create a New Agent

Every agent follows the same pattern:

```
models.py   →  Data structures (dataclasses with to_dict/from_dict)
engine.py   →  Core logic (pure functions, no side effects)
agent.py    →  Orchestrator (build() factory + run() pipeline)
```

### Example: Minimal Agent

```python
# models.py
from dataclasses import dataclass, field

@dataclass
class MyInsight:
    game_id: str
    score: float

    def to_dict(self): return {"game_id": self.game_id, "score": self.score}

# engine.py
class MyEngine:
    def analyze(self, data: dict) -> MyInsight:
        score = data.get("metric", 0) * 1.5
        return MyInsight(game_id=data.get("game_id", ""), score=score)

# agent.py
class MyAgent:
    @staticmethod
    def build() -> "MyAgent":
        return MyAgent(engine=MyEngine())

    def __init__(self, engine: MyEngine):
        self.engine = engine

    def run(self, data: dict) -> dict:
        insight = self.engine.analyze(data)
        return {"insight": insight.to_dict()}
```

## Rules

1. **No direct API calls** in engine modules. Route through `security.secrets.SecretManager`.
2. **Use structured logging**: `from observability.logger import get_logger`
3. **Audit all decisions**: `from audit.trail import AuditTrail, DecisionRecord`
4. **Memory via JSONL**: append-only files in `data/` directories
5. **Tests**: one test file per module under `tests/`

## Naming Conventions

- Agent modules: `src/<domain>_intelligence/` or `src/<domain>/`
- Agent entry point: `agent.py` with `build()` factory
- Tests: `tests/<epic_id>/test_<module>.py`

## Existing Agents

| Agent | Location | Description |
|-------|----------|-------------|
| ASO Intelligence | `src/aso_intelligence/` | App Store Optimization (13 sub-agents) |
| Revenue Intelligence | `src/revenue_intelligence/` | Revenue analysis & CFO tools |
| Economy Intelligence | `src/economy_intelligence/` | In-game economy optimization |
| Monetization Agent | `monetization/agent/` | Ad monetization decision engine |
| Publishing Agent | `operation/publishing/` | Google Play / App Store release |
