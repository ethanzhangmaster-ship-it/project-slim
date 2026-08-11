"""E15.1.2 — Real Fleet Bridge + IAA decision mode tests.

Synthetic rows shaped exactly like the cached MAX report
(data/<ACCT>_report.json). Thresholds mirror the real-fleet calibration
documented in decision_engine.py.
"""
import json
import os

import pytest

from operation.factory_brain import (
    GameDecisionEngine, NORTH_STAR_RPD, RealFleetBridge, Verdict,
)


# --------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------- #
def row(app, day="2026-07-14", rev="0", imps="0", att="0", resp="0",
        network="MINTEGRAL_BIDDING"):
    return {"day": day, "application": app, "ad_format": "REWARD",
            "country": "us", "network": network,
            "impressions": str(imps), "attempts": str(att),
            "responses": str(resp), "ecpm": "0",
            "estimated_revenue": str(rev)}


def winner_rows(days=10):
    """99%-share, high-eCPM app: rev $28/d over 400 imps/d."""
    out = []
    for i in range(days):
        d = f"2026-07-{14 + i:02d}"
        out.append(row("Winner Game", d, rev=28.0, imps=400,
                       att=11000, resp=7500))
    return out


def zombie_rows(days=10):
    """Heavy traffic, negligible money: eCPM ~$1, tiny share."""
    return [row("Zombie Game", f"2026-07-{14 + i:02d}", rev=0.011,
                imps=10, att=1000, resp=400) for i in range(days)]


def fix_rows(days=10):
    """Fills but never shows."""
    return [row("Broken Game", f"2026-07-{14 + i:02d}", rev=0,
                imps=0, att=1300, resp=380) for i in range(days)]


def dead_rows(days=10):
    return [row("Dead Game", f"2026-07-{14 + i:02d}", rev=0,
                imps=0, att=3, resp=0) for i in range(days)]


def keep_rows(days=10):
    """Meaningful share but eCPM below blend."""
    return [row("Keep Game", f"2026-07-{14 + i:02d}", rev=2.0,
                imps=110, att=3600, resp=2000) for i in range(days)]


@pytest.fixture()
def bridge_env(tmp_path):
    data = tmp_path / "data"
    metrics = tmp_path / "metrics"
    data.mkdir()
    metrics.mkdir()
    return data, metrics, RealFleetBridge(
        data_dir=str(data), metrics_dir=str(metrics))


def write_report(data_dir, account, rows, start="2026-07-14",
                 end="2026-07-23"):
    payload = {"account": account, "start": start, "end": end, "rows": rows}
    p = os.path.join(str(data_dir), f"{account}_report.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return p


# --------------------------------------------------------------------- #
# IAA decision engine
# --------------------------------------------------------------------- #
class TestIaaVerdicts:
    def setup_method(self):
        self.eng = GameDecisionEngine()

    def test_winner_scales(self):
        d = self.eng.evaluate_iaa({
            "app": "w", "revenue": 282.0, "share": 0.99, "ecpm": 79.3,
            "ecpm_ratio": 1.39, "impressions": 3560, "attempts": 111000,
            "responses": 75000, "attempts_per_day": 11100, "days": 10})
        assert d.verdict == Verdict.SCALE.value
        assert "replicate pattern" in d.reason

    def test_winner_needs_both_share_and_ecpm(self):
        # premium eCPM but tiny share -> not a winner
        d = self.eng.evaluate_iaa({
            "app": "n", "revenue": 3.0, "share": 0.01, "ecpm": 90.0,
            "ecpm_ratio": 1.6, "impressions": 30, "attempts": 900,
            "responses": 500, "attempts_per_day": 90, "days": 10})
        assert d.verdict != Verdict.SCALE.value

    def test_broken_show_path_is_fix_not_kill(self):
        d = self.eng.evaluate_iaa({
            "app": "b", "revenue": 0.0, "share": 0.0, "ecpm": 0.0,
            "ecpm_ratio": 0.0, "impressions": 0, "attempts": 13010,
            "responses": 3785, "attempts_per_day": 1301, "days": 10})
        assert d.verdict == Verdict.FIX.value
        assert "never show" in d.reason

    def test_dead_traffic_kills(self):
        d = self.eng.evaluate_iaa({
            "app": "d", "revenue": 0.0, "share": 0.0, "ecpm": 0.0,
            "ecpm_ratio": 0.0, "impressions": 0, "attempts": 40,
            "responses": 0, "attempts_per_day": 4, "days": 10})
        assert d.verdict == Verdict.KILL.value
        assert "dead traffic" in d.reason

    def test_dead_beats_fix_at_tiny_volume(self):
        # 15 req/day with a few fills is dead, not an engineering ticket
        d = self.eng.evaluate_iaa({
            "app": "s", "revenue": 0.0, "share": 0.0, "ecpm": 0.0,
            "ecpm_ratio": 0.0, "impressions": 0, "attempts": 30,
            "responses": 28, "attempts_per_day": 15, "days": 2})
        assert d.verdict == Verdict.KILL.value

    def test_zombie_kills(self):
        d = self.eng.evaluate_iaa({
            "app": "z", "revenue": 1.11, "share": 0.004, "ecpm": 1.13,
            "ecpm_ratio": 0.02, "impressions": 978, "attempts": 10741,
            "responses": 3814, "attempts_per_day": 1074, "days": 10})
        assert d.verdict == Verdict.KILL.value
        assert "zombie" in d.reason

    def test_meaningful_share_low_ecpm_keeps(self):
        d = self.eng.evaluate_iaa({
            "app": "k", "revenue": 21.7, "share": 0.372, "ecpm": 19.0,
            "ecpm_ratio": 0.49, "impressions": 1139, "attempts": 35970,
            "responses": 19515, "attempts_per_day": 3597, "days": 10})
        assert d.verdict == Verdict.KEEP.value
        assert "optimise" in d.reason

    def test_no_signal_returns_none(self):
        assert self.eng.evaluate_iaa({"app": "x"}) is None

    def test_iaa_mode_and_manual_apply(self):
        d = self.eng.evaluate_iaa({
            "app": "w", "revenue": 10.0, "share": 0.5, "ecpm": 80.0,
            "ecpm_ratio": 1.5, "impressions": 100, "attempts": 5000,
            "responses": 3000, "attempts_per_day": 500, "days": 10})
        assert d.mode == "iaa"
        assert d.requires_manual_apply is True
        assert d.budget_delta_pct == 0.0

    def test_trend_appears_in_winner_reason(self):
        d = self.eng.evaluate_iaa({
            "app": "w", "revenue": 100.0, "share": 0.9, "ecpm": 80.0,
            "ecpm_ratio": 1.4, "impressions": 1000, "attempts": 9000,
            "responses": 6000, "attempts_per_day": 900, "days": 10,
            "trend_pct": 0.44})
        assert "+44%" in d.reason

    def test_fleet_filters_none(self):
        out = self.eng.evaluate_iaa_fleet([
            {"app": "empty"},
            {"app": "d", "revenue": 0.0, "share": 0.0, "ecpm": 0.0,
             "ecpm_ratio": 0.0, "impressions": 0, "attempts": 10,
             "responses": 0, "attempts_per_day": 1, "days": 10},
        ])
        assert len(out) == 1


# --------------------------------------------------------------------- #
# bridge: loading + per-app economics
# --------------------------------------------------------------------- #
class TestBridgeLoading:
    def test_missing_report_none(self, bridge_env):
        _, _, br = bridge_env
        assert br.load_report("NOPE") is None

    def test_malformed_report_none(self, bridge_env):
        data, _, br = bridge_env
        p = os.path.join(str(data), "BAD_report.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write("{not json")
        assert br.load_report("BAD") is None

    def test_bare_list_accepted(self, bridge_env):
        data, _, br = bridge_env
        p = os.path.join(str(data), "L_report.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(winner_rows(), f)
        rep = br.load_report("L")
        assert rep is not None and len(rep["rows"]) == 10

    def test_empty_rows_none(self, bridge_env):
        data, _, br = bridge_env
        write_report(data, "E", [])
        assert br.load_report("E") is None

    def test_user_metrics_absent_empty(self, bridge_env):
        _, _, br = bridge_env
        assert br.load_user_metrics("NOPE") == {}

    def test_user_metrics_parsed(self, bridge_env):
        _, metrics, br = bridge_env
        with open(os.path.join(str(metrics), "A.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"account": "A", "dau": 5511,
                       "arpdau_history": [
                           {"date": "2026-07-26", "dau": 5483,
                            "arpdau": 0.13, "revenue": 712.81}]}, f)
        um = br.load_user_metrics("A")
        assert um["dau"] == 5511
        assert um["arpdau"] == pytest.approx(0.13)


class TestBridgeEconomics:
    def test_share_ecpm_ratio_computed(self, bridge_env):
        data, _, br = bridge_env
        write_report(data, "A", winner_rows() + zombie_rows())
        rep = br.build("A")
        w = next(g for g in rep.games if g.app == "Winner Game")
        z = next(g for g in rep.games if g.app == "Zombie Game")
        assert w.share > 0.99
        assert w.ecpm_ratio > 1.0 > z.ecpm_ratio
        assert w.attempts_per_day == pytest.approx(11000)

    def test_trend_positive_when_second_half_higher(self, bridge_env):
        data, _, br = bridge_env
        rows = [row("T", f"2026-07-{14 + i:02d}",
                    rev=(1.0 if i < 5 else 2.0), imps=100,
                    att=1000, resp=600) for i in range(10)]
        write_report(data, "A", rows)
        rep = br.build("A")
        g = rep.games[0]
        assert g.trend_pct == pytest.approx(1.0)   # +100%

    def test_trend_none_for_short_window(self, bridge_env):
        data, _, br = bridge_env
        rows = [row("T", f"2026-07-{14 + i:02d}", rev=1.0, imps=10,
                    att=100, resp=60) for i in range(2)]
        write_report(data, "A", rows)
        rep = br.build("A")
        assert rep.games[0].trend_pct is None


# --------------------------------------------------------------------- #
# bridge: verdict card
# --------------------------------------------------------------------- #
class TestVerdictCard:
    def _full_fleet(self, data):
        return write_report(
            data, "A",
            winner_rows() + zombie_rows() + fix_rows()
            + dead_rows() + keep_rows())

    def test_full_fleet_verdicts(self, bridge_env):
        data, _, br = bridge_env
        self._full_fleet(data)
        rep = br.build("A")
        by_app = {v.game_id: v.verdict for v in rep.verdicts}
        assert by_app["Winner Game"] == "scale"
        assert by_app["Zombie Game"] == "kill"
        assert by_app["Broken Game"] == "fix"
        assert by_app["Dead Game"] == "kill"
        assert by_app["Keep Game"] == "keep"

    def test_verdicts_sorted_scale_first(self, bridge_env):
        data, _, br = bridge_env
        self._full_fleet(data)
        rep = br.build("A")
        assert rep.verdicts[0].verdict == "scale"
        assert rep.verdicts[-1].verdict == "kill"

    def test_north_star_context(self, bridge_env):
        data, metrics, br = bridge_env
        self._full_fleet(data)
        with open(os.path.join(str(metrics), "A.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"dau": 5000, "arpdau_history": [
                {"date": "2026-07-26", "dau": 5000, "arpdau": 0.13,
                 "revenue": 650.0}]}, f)
        rep = br.build("A")
        assert rep.dau == 5000
        assert rep.north_star == NORTH_STAR_RPD
        assert rep.north_star_met is True

    def test_north_star_unknown_without_dau(self, bridge_env):
        data, _, br = bridge_env
        self._full_fleet(data)
        rep = br.build("A")
        assert rep.arpdau is None
        assert rep.north_star_met is None

    def test_real_api_locked_false(self, bridge_env):
        data, _, br = bridge_env
        self._full_fleet(data)
        rep = br.build("A")
        assert rep.real_api_called is False
        assert all(v.requires_manual_apply for v in rep.verdicts)

    def test_build_all_skips_missing(self, bridge_env):
        data, _, br = bridge_env
        self._full_fleet(data)
        reports = br.build_all(["A", "MISSING"])
        assert len(reports) == 1

    def test_markdown_contains_all_sections(self, bridge_env):
        data, _, br = bridge_env
        self._full_fleet(data)
        md = br.render_markdown(br.build_all(["A"]))
        for token in ("SCALE 赢家", "KEEP 优化", "FIX 修链路", "KILL 放弃",
                      "requires_manual_apply", "北极星"):
            assert token in md

    def test_report_to_dict_roundtrip(self, bridge_env):
        data, _, br = bridge_env
        self._full_fleet(data)
        d = br.build("A").to_dict()
        assert d["real_api_called"] is False
        assert len(d["verdicts"]) == 5
        assert json.dumps(d)   # serialisable
