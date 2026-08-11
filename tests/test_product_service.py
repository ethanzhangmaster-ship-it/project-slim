from pathlib import Path

import pytest

from market_ops.product import service


def test_service_rejects_unsafe_short_interval(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.argv", ["service", "worker", "--root", str(tmp_path), "--interval-seconds", "1"])
    with pytest.raises(SystemExit, match="at least 10"):
        service.main()
