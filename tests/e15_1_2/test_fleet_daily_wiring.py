"""E15.1.2 / E15.2.7 — Fleet verdict -> daily Feishu automation wiring.

Covers the three pieces added so the per-app IAA verdict (SCALE/KEEP/FIX/
KILL) reaches the operator's morning Feishu card with zero manual steps:

  * FeishuNotifier.send_markdown_card builds a valid interactive card.
  * daily_briefing._run_fleet builds verdicts, persists the .md, and pushes.
  * MonetizationIntelligenceAgent.run(cache_rows=True) persists the raw
    windowed rows to data/<ACCT>_report.json so fleet_bridge reads the
    SAME fresh window the morning card was built from.
"""
import json
import os

import pytest

from operation.factory_brain.fleet_bridge import (
    FleetGame, FleetVerdictReport, GameDecision,
)
from operation.optimizer.intelligence_agent import MonetizationIntelligenceAgent
from operation.optimizer.notify.feishu import FeishuNotifier


# --------------------------------------------------------------------- #
# Feishu generic markdown card
# --------------------------------------------------------------------- #
class TestFeishuMarkdownCard:
    def test_builds_interactive_card(self, monkeypatch):
        captured = {}

        def fake_post(self, payload):
            captured["p"] = payload
            return {"code": 0, "msg": "success"}

        monkeypatch.setattr(FeishuNotifier, "_post", fake_post)
        notifier = FeishuNotifier("https://example.com/hook")
        res = notifier.send_markdown_card(
            "🚢 真实舰队每日判决", "**Winner Game** SCALE", color="orange")
        assert res["code"] == 0
        p = captured["p"]
        assert p["msg_type"] == "interactive"
        assert p["card"]["header"]["template"] == "orange"
        assert p["card"]["header"]["title"]["content"] == "🚢 真实舰队每日判决"
        assert p["card"]["elements"][0]["tag"] == "markdown"
        assert p["card"]["elements"][0]["content"] == "**Winner Game** SCALE"

    def test_rate_limit_path_uses_post(self, monkeypatch):
        # _post is the single funnel; confirming send_markdown_card routes
        # through it keeps the rate-limit backoff behaviour intact.
        called = {}

        def fake_post(self, payload):
            called["c"] = payload
            return {"code": 0}

        monkeypatch.setattr(FeishuNotifier, "_post", fake_post)
        FeishuNotifier("https://x").send_markdown_card("t", "b")
        assert called["c"]["msg_type"] == "interactive"


# --------------------------------------------------------------------- #
# daily_briefing._run_fleet
# --------------------------------------------------------------------- #
class _FakeBridge:
    """Stands in for RealFleetBridge — returns one SCALE verdict."""

    def __init__(self, *a, **k):
        pass

    def build_all(self, accounts):
        g = FleetGame(app="Winner Game", revenue=280.0, impressions=4000,
                      attempts=110000, responses=75000, days=10, share=0.99,
                      ecpm=79.3, ecpm_ratio=1.39, attempts_per_day=11000,
                      show_rate=1.0)
        v = GameDecision(game_id="Winner Game", verdict="scale",
                         reason="replicate pattern",
                         metric_snapshot={"revenue": 280.0})
        rep = FleetVerdictReport(account="ACCT_TEST", total_revenue=282.0,
                                 blended_ecpm=56.0, games=[g], verdicts=[v])
        return [rep]

    def render_markdown(self, reports):
        return "# verdict\n| SCALE 赢家 | Winner Game | replicate pattern |"


class _FakeNotifier:
    captured = []

    def __init__(self, webhook=None):
        self.webhook = webhook

    def send_markdown_card(self, title, md, color="blue"):
        _FakeNotifier.captured.append((title, md, color))
        return {"code": 0}


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    _FakeNotifier.captured = []
    monkeypatch.setattr(
        "operation.factory_brain.fleet_bridge.RealFleetBridge", _FakeBridge)
    monkeypatch.setattr(
        "operation.optimizer.notify.feishu.FeishuNotifier", _FakeNotifier)


class TestRunFleet:
    def test_builds_and_pushes(self, tmp_path, monkeypatch):
        from operation.optimizer import daily_briefing as db
        monkeypatch.setattr(db, "OUT_DIR", str(tmp_path / "briefing"))
        out = db._run_fleet(["ACCT_TEST"], notify=True)
        assert out["status"] == "OK"
        assert out["verdicts"] == 1
        assert out["notified"] is True
        assert len(_FakeNotifier.captured) == 1
        title, md, color = _FakeNotifier.captured[0]
        assert "真实舰队" in title
        assert "SCALE" in md
        # verdict markdown persisted to disk
        assert os.path.exists(out["path"])
        # cleanup the daily artifact
        if os.path.exists(out["path"]):
            os.remove(out["path"])

    def test_no_notify_skips_push(self, monkeypatch):
        from operation.optimizer import daily_briefing as db
        out = db._run_fleet(["ACCT_TEST"], notify=False)
        assert out["status"] == "OK"
        assert out["notified"] is False
        assert _FakeNotifier.captured == []

    def test_no_data_when_bridge_empty(self, monkeypatch):
        from operation.optimizer import daily_briefing as db

        class _Empty:
            def __init__(self, *a, **k):
                pass

            def build_all(self, accounts):
                return []

            def render_markdown(self, reports):
                return ""

        monkeypatch.setattr(
            "operation.factory_brain.fleet_bridge.RealFleetBridge", _Empty)
        out = db._run_fleet(["ACCT_TEST"], notify=True)
        assert out["status"] == "NO_DATA"

    def test_failure_isolated(self, monkeypatch):
        from operation.optimizer import daily_briefing as db

        class _Boom:
            def __init__(self, *a, **k):
                pass

            def build_all(self, accounts):
                raise RuntimeError("boom")

            def render_markdown(self, reports):
                return ""

        monkeypatch.setattr(
            "operation.factory_brain.fleet_bridge.RealFleetBridge", _Boom)
        out = db._run_fleet(["ACCT_TEST"], notify=True)
        assert out["status"] == "FAIL"
        assert "boom" in out["error"]


# --------------------------------------------------------------------- #
# live pull persists cache (offline via injected rows)
# --------------------------------------------------------------------- #
def _rows():
    out = []
    for i in range(10):
        d = f"2026-07-{14 + i:02d}"
        for app, rev, imps, att, resp in (
            ("GameA", "10.0", "400", "11000", "7500"),
            ("GameB", "1.0", "50", "500", "100"),
        ):
            out.append({"day": d, "application": app, "ad_format": "REWARD",
                        "country": "us", "network": "MINTEGRAL_BIDDING",
                        "impressions": imps, "attempts": att,
                        "responses": resp, "ecpm": "0",
                        "estimated_revenue": rev})
    return out


def test_run_persists_cache(tmp_path):
    agent = MonetizationIntelligenceAgent()
    rows = _rows()
    agent.run(
        "TESTCACHE", "2026-07-14", "2026-07-23", rows=rows,
        save=True, cache_rows=True,
        out_dir=str(tmp_path / "reports"),
        experiments_dir=str(tmp_path / "exp"),
        config_dir=str(tmp_path / "cfg"),
        enable_ecpm_prediction=False,
    )
    cache = os.path.join("data", "TESTCACHE_report.json")
    try:
        assert os.path.exists(cache), "cache_rows should write data/<ACCT>_report.json"
        blob = json.load(open(cache, encoding="utf-8"))
        assert blob["account"] == "TESTCACHE"
        assert blob["start"] == "2026-07-14"
        assert blob["end"] == "2026-07-23"
        assert isinstance(blob["rows"], list)
        assert len(blob["rows"]) == len(rows)
    finally:
        if os.path.exists(cache):
            os.remove(cache)


def test_run_no_cache_when_disabled(tmp_path):
    agent = MonetizationIntelligenceAgent()
    agent.run(
        "TESTCACHE2", "2026-07-14", "2026-07-23", rows=_rows(),
        save=True, cache_rows=False,
        out_dir=str(tmp_path / "reports"),
        experiments_dir=str(tmp_path / "exp"),
        config_dir=str(tmp_path / "cfg"),
        enable_ecpm_prediction=False,
    )
    cache = os.path.join("data", "TESTCACHE2_report.json")
    try:
        assert not os.path.exists(cache)
    finally:
        if os.path.exists(cache):
            os.remove(cache)
