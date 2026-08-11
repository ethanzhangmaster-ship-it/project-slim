"""E15.1.2/P2 — Unified single morning card.

run_all() must NOT push a per-account card, and must fold revenue
diagnosis + fleet verdicts + growth opportunities into ONE Feishu card
(zero clicks). No duplicate / separate fleet or growth card.
"""
import pytest

from operation.optimizer.intelligence_agent import MonetizationIntelligenceAgent
from operation.optimizer.notify.feishu import FeishuNotifier


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


class _FakeNotifier:
    cards = []
    texts = []

    def __init__(self, webhook=None):
        self.webhook = webhook

    def send_markdown_card(self, title, md, color="blue"):
        _FakeNotifier.cards.append((title, md, color))
        return {"code": 0}

    def send_text(self, text):
        _FakeNotifier.texts.append(text)
        return {"code": 0}

    def _post(self, payload):
        return {"code": 0}


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    _FakeNotifier.cards = []
    _FakeNotifier.texts = []
    monkeypatch.setattr(
        "operation.optimizer.notify.feishu.FeishuNotifier", _FakeNotifier)
    # No live MAX pull and no real DAU source during the test.
    monkeypatch.setattr(
        MonetizationIntelligenceAgent, "pull_rows",
        lambda self, *a, **k: _rows())
    import operation.optimizer.daily_briefing as db
    monkeypatch.setattr(db, "_fetch_user_metrics", lambda *a, **k: None)


class _FakeBridge:
    def __init__(self, *a, **k):
        pass

    def build_all(self, accounts):
        from operation.factory_brain.fleet_bridge import (
            FleetGame, FleetVerdictReport, GameDecision,
        )
        g = FleetGame(app="Winner Game", revenue=280.0, impressions=4000,
                      attempts=110000, responses=75000, days=10, share=0.99,
                      ecpm=79.3, ecpm_ratio=1.39, attempts_per_day=11000,
                      show_rate=1.0)
        # per-app Rev/DAU must flow through to the card: attach a real value.
        g.dau = 1421.0
        g.rev_per_dau = 280.0 / (1421.0 * 10)
        v = GameDecision(game_id="Winner Game", verdict="scale",
                         reason="replicate pattern",
                         metric_snapshot={"revenue": 280.0,
                                         "rev_per_dau": g.rev_per_dau})
        return [FleetVerdictReport(account="ACCT_TEST", total_revenue=282.0,
                                   blended_ecpm=56.0, games=[g], verdicts=[v],
                                   north_star=0.03)]

    def render_markdown(self, reports):
        # Mirror the real renderer's per-app column so the unified card wires
        # through the same content a human actually reads each morning.
        lines = ["# 真实舰队每日判决", ""]
        for r in reports:
            lines.append(f"## {r.account}")
            lines.append("")
            lines.append("| 判决 | 游戏 | 单游戏 Rev/DAU | 理由 |")
            lines.append("|---|---|---|---|")
            for v in r.verdicts:
                cell = ("✅$%.4f" % v.metric_snapshot.get("rev_per_dau", 0.0))
                lines.append(f"| {v.verdict.upper()} | {v.game_id} | {cell} | {v.reason} |")
        return "\n".join(lines)


def test_single_unified_card(monkeypatch):
    import operation.factory_brain.fleet_bridge as fb
    monkeypatch.setattr(fb, "RealFleetBridge", _FakeBridge)
    from operation.optimizer import daily_briefing as db
    summary = db.run_all(["ACCT_TEST"], notify=True)
    # Exactly ONE card pushed — no per-account, no separate fleet/growth card.
    assert len(_FakeNotifier.cards) == 1, _FakeNotifier.cards
    title, md, color = _FakeNotifier.cards[0]
    assert "全量晨报" in title
    # All five sections present in the single card.
    assert "1️⃣" in md and "营收诊断" in md
    assert "2️⃣" in md and "舰队" in md
    assert "3️⃣" in md and "新游机会" in md
    assert "4️⃣" in md and "上架状态" in md
    assert "5️⃣" in md and "待产状态" in md
    # Revenue table + fleet verdict marker + growth opportunity marker.
    assert "ACCT_TEST" in md
    assert "SCALE" in md
    assert "MOCK" in md  # growth mock source marker folded in
    # ---- per-app Rev/DAU must reach the operator's morning card ----
    # Section 2 is the fleet verdict; assert the per-game column + a real
    # dollar value landed there (not just a placeholder). This locks the
    # A-upgrade wiring so a future refactor can't silently drop it.
    assert "单游戏 Rev/DAU" in md, "fleet verdict card missing per-app column"
    assert "Winner Game" in md
    # rev_per_dau = 280/(1421*10) = 0.0197 -> rendered "$0.0197"
    assert "0.0197" in md, "per-app Rev/DAU value not on card"
    # digest bookkeeping + growth ran OK
    assert summary["digest"]["notified"] is True
    assert summary["growth"]["status"] == "OK"
    assert "markdown" in summary["digest"]


def test_no_card_when_no_notify(monkeypatch):
    import operation.factory_brain.fleet_bridge as fb
    monkeypatch.setattr(fb, "RealFleetBridge", _FakeBridge)
    from operation.optimizer import daily_briefing as db
    db.run_all(["ACCT_TEST"], notify=False)
    assert _FakeNotifier.cards == []


def test_digest_content_has_three_sections(monkeypatch):
    import operation.factory_brain.fleet_bridge as fb
    monkeypatch.setattr(fb, "RealFleetBridge", _FakeBridge)
    from operation.optimizer import daily_briefing as db
    summary = db.run_all(["ACCT_TEST"], notify=False)
    md = summary["digest"]["markdown"]
    # No leaked standalone H1s from folded sub-reports (they are stripped).
    assert md.count("# 🌅") == 1
    for marker in ("营收诊断", "真实舰队判决", "新游机会", "上架状态",
                   "待产状态"):
        assert marker in md


def test_store_status_section_safe_dry_run(monkeypatch):
    """Store-status section must appear, and the default dry-run mode must
    make ZERO network calls (real_api_called stays False) even with a catalog
    full of games."""
    import operation.factory_brain.fleet_bridge as fb
    monkeypatch.setattr(fb, "RealFleetBridge", _FakeBridge)

    import operation.publishing_factory.catalog.game_registry as gr
    import operation.publishing_factory.catalog.product_profile as pp

    class _FakeReg:
        def __init__(self, *a, **k):
            pass

        def load(self):
            return self

        def list_all(self):
            g = pp.GameProduct(
                game_id="merge_monster",
                package_name="com.foo.mergemonster",
                platforms=["app_store", "google_play"],
                status="published")
            return [g]

    monkeypatch.setattr(gr, "GameRegistry", _FakeReg)
    # Ensure the opt-in gate is OFF for this test (default safe).
    monkeypatch.delenv("LAUNCHFORGE_STORE_LIVE", raising=False)
    import operation.optimizer.daily_briefing as db_mod
    monkeypatch.setattr(db_mod, "_store_status_live", lambda: False)

    from operation.optimizer import daily_briefing as db
    summary = db.run_all(["ACCT_TEST"], notify=False)
    md = summary["digest"]["markdown"]
    assert "4️⃣" in md and "上架状态" in md
    # fake game shows up in the store table (two platform rows)
    assert md.count("merge_monster") >= 2
    # dry-run: never touched the real stores
    assert summary["store"]["real_api_called"] is False
    assert summary["store"]["games"] == 2
    # still a single folded card, store folded in (not pushed separately)
    assert len(_FakeNotifier.cards) == 0


def test_production_readiness_section_safe_no_config(monkeypatch):
    """Section 5 (Production Readiness · 14-day closed-testing clock) must
    appear even when the tester community is not configured yet, and
    must remain a pure read (no writes)."""
    import operation.factory_brain.fleet_bridge as fb
    monkeypatch.setattr(fb, "RealFleetBridge", _FakeBridge)

    # Isolate tester_progress / tester_community / tester_pool to a tmp dir
    # so the test doesn't read production credentials OR the real pool file.
    import os
    import tempfile
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("LAUNCHFORGE_TESTER_PROGRESS",
                        os.path.join(tmp, "tester_progress.json"))
    monkeypatch.setenv("LAUNCHFORGE_TESTER_COMMUNITY",
                        os.path.join(tmp, "tester_community.json"))
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_POOL",
                        os.path.join(tmp, "tester_pool.json"))
    # Remove any leaked-in tmp_path data so the section reports "no apps
    # tracked yet" rather than something from another test run.
    monkeypatch.setenv("LAUNCHFORGE_DAILY_BRIEFING_RESET", "1")

    from operation.optimizer import daily_briefing as db
    summary = db.run_all(["ACCT_TEST"], notify=False)
    md = summary["digest"]["markdown"]
    # Section 5 header must be present
    assert "5️⃣" in md and "待产状态" in md
    # No apps tracked yet — default safe guidance shown
    assert "no apps tracked" in md or "暂无待产 App" in md
    # production_readiness status is OK (zero writes — purely a render)
    assert summary["production"]["status"] == "OK"
    # safe defaults: community configured is False (no creds supplied)
    assert summary["production"]["community_configured"] is False
    assert summary["production"]["tracked_packages"] == 0
    # still exactly zero pushes
    assert len(_FakeNotifier.cards) == 0


def test_play_runtime_section_present(monkeypatch):
    """Section 6 (E13.5 Play Runtime · 24h audit) must appear in the unified
    card and read only the local JSONL audit log (zero network / writes)."""
    import operation.factory_brain.fleet_bridge as fb
    monkeypatch.setattr(fb, "RealFleetBridge", _FakeBridge)

    import json
    import os
    import tempfile
    from datetime import datetime, timedelta, timezone
    tmp = tempfile.mkdtemp()
    audit_file = os.path.join(tmp, "audit.jsonl")
    # one fake audit record WITHIN the last-24h window so the section renders a
    # row (not the EMPTY placeholder). Use a relative timestamp — a hardcoded
    # past date would silently fall outside last_24h() and flake the test.
    recent_at = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    rec = {"op": "update_listing", "package_name": "com.foo.x",
           "radius": "metadata", "stage": "execute", "real_api_called": True,
           "ok": True, "at": recent_at}
    with open(audit_file, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    monkeypatch.setenv("LAUNCHFORGE_PLAY_AUDIT", audit_file)

    from operation.optimizer import daily_briefing as db
    summary = db.run_all(["ACCT_TEST"], notify=False)
    md = summary["digest"]["markdown"]
    assert "6️⃣" in md and "Play Runtime" in md
    assert summary["play_runtime"]["status"] == "OK"
    assert summary["play_runtime"]["count"] == 1
    # zero pushes (folded, not sent separately)
    assert len(_FakeNotifier.cards) == 0
