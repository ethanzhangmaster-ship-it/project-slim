"""P1 — per-app Rev/DAU upgrade (account -> single-game granularity).

Covers the full seam: Adjust `dimensions=app` parse -> UserMetrics.app_dau
-> ManualDropIn `apps` block -> fleet_bridge per-game Rev/DAU join +
north-star check + markdown rendering.
"""
import json
import os

from operation.factory_brain import NORTH_STAR_RPD, RealFleetBridge
from operation.factory_brain.fleet_bridge import FleetGame
from operation.providers.live.adjust.kpi_client import _parse_dau_csv_by_app
from operation.optimizer.user_metrics import (
    AdjustProvider, ManualDropInProvider, UserMetrics, UserMetricsService,
    save_dropin_dau_apps,
)


# --------------------------------------------------------------------- #
# kpi_client: dimensions=app CSV parsing
# --------------------------------------------------------------------- #
class TestParseDauByApp:
    def test_basic(self):
        csv = "app,daus\ntok_a,1200\ntok_b,400\n"
        assert _parse_dau_csv_by_app(csv) == {"tok_a": 1200.0, "tok_b": 400.0}

    def test_averages_repeated_tokens(self):
        csv = "app,daus\ntok_a,100\ntok_a,200\ntok_b,50\n"
        out = _parse_dau_csv_by_app(csv)
        assert out == {"tok_a": 150.0, "tok_b": 50.0}

    def test_empty(self):
        assert _parse_dau_csv_by_app("") == {}
        assert _parse_dau_csv_by_app("app,daus\n") == {}


# --------------------------------------------------------------------- #
# providers fill app_dau
# --------------------------------------------------------------------- #
class _MockPerAppClient:
    def fetch_avg_dau_by_app(self, token, app_tokens, start, end):
        return {"tok_a": 1200.0, "tok_b": 400.0}

    def fetch_avg_dau(self, token, app_tokens, start, end):
        return 1600.0


class _MockEmptyPerAppClient:
    def fetch_avg_dau_by_app(self, token, app_tokens, start, end):
        return {}

    def fetch_avg_dau(self, token, app_tokens, start, end):
        return 900.0


class TestAdjustPerApp:
    def test_per_app_with_remap(self):
        prov = AdjustProvider(
            api_token="t", account_apps={"ACCT": ["tok_a", "tok_b"]},
            client=_MockPerAppClient(),
            token_to_app={"tok_a": "Game A", "tok_b": "Game B"})
        um = prov.fetch("ACCT", "2026-07-14", "2026-07-23")
        assert um is not None
        assert um.app_dau == {"Game A": 1200.0, "Game B": 400.0}
        assert um.dau == 1600
        assert um.source == "adjust"

    def test_fallback_when_per_app_empty(self):
        prov = AdjustProvider(
            api_token="t", account_apps={"ACCT": ["tok_a"]},
            client=_MockEmptyPerAppClient())
        um = prov.fetch("ACCT", "2026-07-14", "2026-07-23")
        assert um is not None
        assert um.app_dau == {}
        assert um.dau == 900


class TestManualDropInApps:
    def test_reads_apps_block(self, tmp_path):
        p = tmp_path / "A.json"
        p.write_text(json.dumps({
            "account": "A", "dau": 5000,
            "apps": {"Game A": {"dau": 1000}, "Game B": 500}}),
            encoding="utf-8")
        prov = ManualDropInProvider()
        prov.DIR = str(tmp_path)
        um = prov.fetch("A", "2026-07-14", "2026-07-23")
        assert um is not None
        assert um.dau == 5000
        assert um.app_dau == {"Game A": 1000.0, "Game B": 500.0}

    def test_accepts_flat_apps(self, tmp_path):
        p = tmp_path / "A.json"
        p.write_text(json.dumps({"account": "A", "dau": 10,
                                 "apps": {"Game A": 7}}), encoding="utf-8")
        prov = ManualDropInProvider()
        prov.DIR = str(tmp_path)
        um = prov.fetch("A", "2026-07-14", "2026-07-23")
        assert um.app_dau == {"Game A": 7.0}


class TestUserMetricsRoundtrip:
    def test_app_dau_survives_dict(self):
        m = UserMetrics(account="A", period_start="2026-07-14",
                        period_end="2026-07-23", dau=100, app_dau={"g": 5.0})
        m2 = UserMetrics.from_dict(m.to_dict())
        assert m2.app_dau == {"g": 5.0}
        assert m2.dau == 100


# --------------------------------------------------------------------- #
# fleet_bridge per-game Rev/DAU join
# --------------------------------------------------------------------- #
def _row(app, day, rev, imps, att, resp, network="MINTEGRAL_BIDDING"):
    return {"day": day, "application": app, "ad_format": "REWARD",
            "country": "us", "network": network,
            "impressions": str(imps), "attempts": str(att),
            "responses": str(resp), "ecpm": "0",
            "estimated_revenue": str(rev)}


def _winner_rows(days=10):
    return [_row("Winner Game", f"2026-07-{14 + i:02d}", rev=28.0, imps=400,
                 att=11000, resp=7500) for i in range(days)]


def _write_report(data_dir, account, rows):
    payload = {"account": account, "start": "2026-07-14",
               "end": "2026-07-23", "rows": rows}
    p = os.path.join(str(data_dir), f"{account}_report.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return p


class TestFleetPerAppDau:
    def test_per_app_rev_per_dau_joins(self, tmp_path):
        data = tmp_path / "data"
        metrics = tmp_path / "metrics"
        data.mkdir()
        metrics.mkdir()
        _write_report(data, "A", _winner_rows())
        # Winner Game: $28/day * 10 = $280 window; per-app DAU 100 ->
        # rev_per_dau = 280 / (100 * 10) = 0.28 (>= north star 0.03)
        with open(os.path.join(str(metrics), "A.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"account": "A", "dau": 5000,
                       "apps": {"Winner Game": {"dau": 100}}}, f)
        br = RealFleetBridge(data_dir=str(data), metrics_dir=str(metrics))
        rep = br.build("A")
        g = next(x for x in rep.games if x.app == "Winner Game")
        assert g.dau == 100
        assert g.rev_per_dau == 0.28
        # per-game north-star marker present in markdown
        md = br.render_markdown([rep])
        assert "✅$0.2800" in md
        assert "单游戏 Rev/DAU" in md

    def test_no_app_dau_falls_back_to_none(self, tmp_path):
        data = tmp_path / "data"
        metrics = tmp_path / "metrics"
        data.mkdir()
        metrics.mkdir()
        _write_report(data, "A", _winner_rows())
        with open(os.path.join(str(metrics), "A.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"account": "A", "dau": 5000}, f)
        br = RealFleetBridge(data_dir=str(data), metrics_dir=str(metrics))
        rep = br.build("A")
        for g in rep.games:
            assert g.dau is None
            assert g.rev_per_dau is None
        md = br.render_markdown([rep])
        # no per-game marker when absent
        assert "—" in md

    def test_service_persists_app_dau_to_dropin(self, tmp_path, monkeypatch):
        """When the Adjust provider wins WITH per-app data, the service must
        cache app_dau into outputs/user_metrics/<ACCT>.json — that file is
        what fleet_bridge joins on, so without this write the daily verdict
        card silently loses per-game Rev/DAU."""
        monkeypatch.chdir(tmp_path)  # ManualDropInProvider.DIR is CWD-relative
        prov = AdjustProvider(
            api_token="t", account_apps={"ACCT": ["tok_a", "tok_b"]},
            client=_MockPerAppClient(),
            token_to_app={"tok_a": "Game A", "tok_b": "Game B"})
        svc = UserMetricsService(providers=[prov])
        m = svc.fetch("ACCT", "2026-07-14", "2026-07-23")
        assert m.app_dau == {"Game A": 1200.0, "Game B": 400.0}
        p = os.path.join("outputs", "user_metrics", "ACCT.json")
        assert os.path.exists(p)
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        assert d["dau"] == 1600
        assert d["apps"] == {"Game A": {"dau": 1200.0},
                             "Game B": {"dau": 400.0}}
        # fleet_bridge reads the same file shape via load_user_metrics
        br = RealFleetBridge(metrics_dir=os.path.join(
            "outputs", "user_metrics"))
        um = br.load_user_metrics("ACCT")
        assert um["app_dau"] == {"Game A": 1200.0, "Game B": 400.0}

    def test_save_dropin_dau_apps_merge(self, tmp_path):
        p = save_dropin_dau_apps("A", {"Game A": 100, "Game B": 50},
                                 "2026-07-27", dir=str(tmp_path))
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        assert d["apps"] == {"Game A": {"dau": 100.0},
                             "Game B": {"dau": 50.0}}
        # second call merges without dropping existing
        save_dropin_dau_apps("A", {"Game C": 9}, "2026-07-27",
                             dir=str(tmp_path))
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        assert set(d["apps"].keys()) == {"Game A", "Game B", "Game C"}
