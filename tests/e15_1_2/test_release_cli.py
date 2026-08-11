"""Smoke tests for the Release Agent CLI (argparse routing + gate)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from operation.publishing_factory.play_runtime import release_cli
from operation.publishing_factory.play_runtime.release_agent import (
    ReleaseAgent, ReleasePolicy,
)
from operation.publishing_factory.play_runtime.connector import PlayConnector
from monetization.providers.models import SandboxMode


class FakeClient:
    def __init__(self):
        self.calls = []
        self.tracks = {}
        self.owned = True

    def check_status(self, pkg):
        return {"success": self.owned, "status": "published"}

    def get_track_status(self, pkg, track="production"):
        t = self.tracks.get(pkg)
        if t is None:
            return {"success": True, "track": track, "status": "empty",
                    "releases": [], "user_fraction": 0.0}
        return {"success": True, "track": track, "status": t["status"],
                "releases": [{"status": t["status"],
                              "userFraction": t["user_fraction"]}],
                "user_fraction": t["user_fraction"]}

    def set_rollout(self, pkg, track="production", user_fraction=0.05, **kw):
        self.calls.append(("set_rollout", pkg, user_fraction))
        self.tracks[pkg] = {"status": "inProgress",
                            "user_fraction": float(user_fraction)}
        return {"success": True, "detail": "ok"}

    def halt_rollout(self, pkg, track="production"):
        self.calls.append(("halt", pkg))
        return {"success": True, "detail": "halted"}


def _patch(monkeypatch, fc):
    monkeypatch.setattr(
        "operation.publishing_factory.play_runtime.release_cli.PlayConnector",
        lambda *a, **k: PlayConnector(client=fc, sandbox=SandboxMode.PRODUCTION))


def test_cli_evaluate_dry_run(monkeypatch, capsys):
    fc = FakeClient()
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    _patch(monkeypatch, fc)
    rc = release_cli.main(["evaluate", "com.x.5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "advance" in out or "hold" in out


def test_cli_advance_without_apply_refused(monkeypatch, capsys):
    fc = FakeClient()
    fc.tracks["com.x.5"] = {"status": "inProgress", "user_fraction": 0.05}
    _patch(monkeypatch, fc)
    rc = release_cli.main(["advance", "com.x.5"])  # no --apply
    assert rc == 0
    # without --apply the connector is not unlocked -> no real write
    assert fc.calls == []
