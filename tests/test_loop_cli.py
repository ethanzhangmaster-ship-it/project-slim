import json
from pathlib import Path

from market_ops.product import loop_cli


def test_cli_plans_cycle(tmp_path: Path, monkeypatch, capsys):
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps([{"experiment_id": "e1", "creative_id": "c1", "decision": "WINNER", "confidence": 0.9, "budget_before": 100}]), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["loop", "--database", str(tmp_path / "loop.db"), "plan", "--input", str(evidence), "--total-budget", "1000"])
    loop_cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["cycle_id"]
    assert payload["tasks"][0]["creative_id"] == "c1"
