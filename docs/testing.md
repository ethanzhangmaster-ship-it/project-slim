# Testing Guide

## Running Tests

```bash
# All tests
pytest tests/ -v

# By category
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v
pytest tests/security/ -v

# Legacy epic tests
pytest tests/e16_6*/ -v   # ASO intelligence
pytest tests/e16_1*/ -v   # Revenue intelligence
pytest tests/e15*/ -v     # Play runtime

# With coverage
pytest tests/ --cov=. --cov-report=html
```

## Test Structure

```
tests/
├── unit/          # Pure logic — no I/O, no network
├── integration/   # Cross-module or mocked external adapters
├── e2e/           # Full pipeline: Data → Agent → Decision → Memory
├── security/      # Secret scanner, env validator, permissions
├── e16_6*/        # ASO sub-agent tests (13 modules)
├── e16_1*/        # Revenue intelligence tests
├── e15*/          # Play runtime tests
└── conftest.py    # Shared fixtures
```

## Writing a Test

```python
# tests/unit/test_my_agent.py
from src.my_domain.models import MyModel

def test_model_roundtrip():
    m = MyModel(game_id="test", score=0.85)
    d = m.to_dict()
    restored = MyModel.from_dict(d)
    assert restored.score == pytest.approx(0.85, rel=1e-6)
```

## Test Matrix

| Layer | Mock I/O | Runtime | Purpose |
|-------|----------|---------|---------|
| Unit | No I/O | <1s | Verify logic |
| Integration | Mock external | <5s | Verify wiring |
| E2E | Real (sandbox) | <30s | Full pipeline |
| Security | No I/O | <1s | Hardcoded secrets scan |
