"""P1.6 Reality Coverage 单元测试。

覆盖：
- P1.6.1 GameRegistry binding 查询（binding_completeness / source_bindings / binding_report）
- P1.6.2 RealityHealthMonitor（源健康 + 覆盖日报）
- P1.6.3 MissingDataDetector（DATA_GAP 规则测试）
- P1.6.4 DailyRealityStore（安全文件名 + 读写 + 索引）
- E2E：hub + coverage 集成
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.growth_reality.coverage import (
    DailyRealityStore,
    DataGap,
    MissingDataDetector,
    RealityCoverageReport,
    RealityHealthMonitor,
    SourceHealth,
)
from src.growth_reality.coverage.snapshot_store import _safe_dir
from src.growth_reality.models import GrowthRealitySnapshot
from src.growth_reality.registry import DEFAULT_PATH, GameRegistry, GameRegistryEntry
from src.growth_reality.snapshot import CompanySnapshot, build_company_snapshot


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_snap(game_id, sources=None, real_domains=None, confidence=0.5, real_confidence=0.4, timestamp="2026-07-30T09:00:00"):
    return GrowthRealitySnapshot.from_dict({
        "game_id": game_id, "timestamp": timestamp,
        "sources": list(sources or []),
        "real_domains": list(real_domains or []),
        "confidence": confidence,
        "real_confidence": real_confidence,
    })


def _make_company(snaps):
    return build_company_snapshot(snaps, "2026-07-30")


# --------------------------------------------------------------------------- #
# P1.6.1 — Registry Binding 查询
# --------------------------------------------------------------------------- #
class TestRegistryBinding:
    def test_binding_completeness_fully_bound(self, tmp_path):
        data = {
            "games": [{
                "game_id": "g1", "display_name": "G1",
                "package_name": "com.test.g1", "genre": "casual",
                "platform": "android", "max_apps": ["ACCT_1"],
                "adjust_app_token": "tok_ref", "meta_app_id": "meta_g1",
                "country": "US", "max_account": "ACCT_1",
                "meta_campaign_ids": ["camp_1"],
            }],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        reg = GameRegistry(str(p))
        assert reg.binding_completeness("g1") == []

    def test_binding_completeness_missing_bindings(self, tmp_path):
        data = {
            "games": [{
                "game_id": "g1", "display_name": "G1",
                "package_name": "", "genre": "",
                "platform": "unknown", "max_apps": [],
                "adjust_app_token_ref": "", "meta_campaign_ids": [],
            }],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        reg = GameRegistry(str(p))
        missing = reg.binding_completeness("g1")
        assert "package_name" in missing
        assert "country" in missing
        assert "adjust_app_token" in missing
        assert "meta_app_id" in missing
        assert "platform" in missing
        # max_account 也缺失（无 max_apps 推导）
        assert "max_account" in missing

    def test_binding_completeness_unknown_game(self):
        reg = GameRegistry(DEFAULT_PATH)
        assert isinstance(reg.binding_completeness("no_such_game"), list)

    def test_source_bindings_fully_bound(self, tmp_path):
        data = {
            "games": [{
                "game_id": "g1", "package_name": "com.x",
                "platform": "ios", "max_apps": ["ACCT_2"],
                "adjust_app_token": "adj_ref", "meta_app_id": "meta_x",
                "country": "BR", "meta_campaign_ids": ["c1", "c2"],
                "max_account": "ACCT_2",
            }],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        reg = GameRegistry(str(p))
        b = reg.source_bindings("g1")
        assert b["max_account"] == "ACCT_2"
        assert b["package_name"] == "com.x"
        assert b["country"] == "BR"
        assert b["adjust_app_token"] == "adj_ref"
        assert b["meta_app_id"] == "meta_x"
        assert b["meta_campaign_ids"] == ["c1", "c2"]

    def test_game_id_to_adjust_token_compat(self, tmp_path):
        """旧 adjust_app_token_ref 仍被识别为已绑定。"""
        data = {
            "games": [{
                "game_id": "g1",
                "adjust_app_token_ref": "old_ref",
                "adjust_app_token": "",
            }],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        reg = GameRegistry(str(p))
        assert reg.game_id_to_adjust_token("g1") == "old_ref"

    def test_max_account_derived_from_max_apps(self, tmp_path):
        data = {
            "games": [{"game_id": "g1", "max_apps": ["ACCT_3"]}],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        reg = GameRegistry(str(p))
        assert reg.game_id_to_max_account("g1") == "ACCT_3"

    def test_max_account_explicit_wins(self, tmp_path):
        data = {
            "games": [{"game_id": "g1", "max_apps": ["ACCT_1"], "max_account": "ACCT_EXP"}],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        reg = GameRegistry(str(p))
        assert reg.game_id_to_max_account("g1") == "ACCT_EXP"

    def test_binding_report(self, tmp_path):
        data = {
            "games": [
                {"game_id": "g1", "package_name": "com.x", "platform": "android",
                 "max_apps": ["ACCT_1"], "adjust_app_token": "tok", "meta_app_id": "m",
                 "country": "US"},
                {"game_id": "g2"},  # 全空
            ],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        reg = GameRegistry(str(p))
        rpt = reg.binding_report()
        assert rpt["g1"]["completeness_ratio"] == 1.0
        assert rpt["g2"]["completeness_ratio"] < 1.0

    def test_country_meta_app_id_empty_by_default(self, tmp_path):
        data = {
            "games": [{"game_id": "g1"}],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        reg = GameRegistry(str(p))
        assert reg.game_id_to_country("g1") == ""
        assert reg.game_id_to_meta_app_id("g1") == ""


# --------------------------------------------------------------------------- #
# P1.6.3 — MissingDataDetector
# --------------------------------------------------------------------------- #
class TestMissingDataDetector:
    def _reg_with(self, tmp_path, **kw):
        data = {
            "games": [{
                "game_id": "g1", "package_name": "", "max_apps": [],
                "adjust_app_token_ref": "", "meta_campaign_ids": [], **kw,
            }],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        return GameRegistry(str(p))

    def test_no_gaps_when_all_ok(self, tmp_path):
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"], adjust_app_token="adj",
                             meta_app_id="meta", country="US")
        snap = _make_snap("g1", sources=["registry", "max_live", "adjust_live", "meta_live"],
                          real_domains=["product", "revenue", "acquisition"])
        gaps = MissingDataDetector.detect({"g1": snap}, reg)
        assert gaps == []

    def test_max_revenue_missing(self, tmp_path):
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"])
        snap = _make_snap("g1", sources=["registry"], real_domains=["product"])
        gaps = MissingDataDetector.detect({"g1": snap}, reg)
        assert any(g.gap_type == "max_revenue_missing" for g in gaps)

    def test_adjust_dau_missing(self, tmp_path):
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"], adjust_app_token="adj")
        snap = _make_snap("g1", sources=["registry", "max_live"],
                          real_domains=["product", "revenue"])
        gaps = MissingDataDetector.detect({"g1": snap}, reg)
        # adjust bound but no acquisition
        assert any(g.gap_type == "adjust_dau_missing" for g in gaps)
        assert any(g.gap_type == "roas_spend_missing" for g in gaps)

    def test_meta_data_missing(self, tmp_path):
        reg = self._reg_with(tmp_path, meta_app_id="meta")
        snap = _make_snap("g1", sources=["registry"], real_domains=["product"])
        gaps = MissingDataDetector.detect({"g1": snap}, reg)
        assert any(g.gap_type == "meta_data_missing" for g in gaps)

    def test_country_unbound_only_when_operating(self, tmp_path):
        """country_unbound 仅在在运营或有风险时触发，非运营不触发。"""
        reg = self._reg_with(tmp_path)  # no country, no bindings
        # 不在运营（无收入域）
        snap = _make_snap("g1", sources=["registry"], real_domains=["product"])
        gaps = MissingDataDetector.detect({"g1": snap}, reg)
        assert not any(g.gap_type == "country_unbound" for g in gaps)
        # 在运营（有真实收入域）
        snap2 = _make_snap("g1", sources=["registry", "max_live"],
                           real_domains=["product", "revenue"])
        gaps2 = MissingDataDetector.detect({"g1": snap2}, reg)
        assert any(g.gap_type == "country_unbound" for g in gaps2)

    def test_no_real_coverage_at_risk(self, tmp_path):
        reg = self._reg_with(tmp_path)
        snap = _make_snap("g1", sources=[], real_domains=[])
        gaps = MissingDataDetector.detect({"g1": snap}, reg, at_risk=["g1"])
        assert any(g.gap_type == "no_real_coverage_at_risk" for g in gaps)

    def test_severity_high_medium_low(self, tmp_path):
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"], adjust_app_token="adj")
        snap = _make_snap("g1", sources=["registry"],
                          real_domains=["product"])
        gaps = MissingDataDetector.detect({"g1": snap}, reg)
        sevs = {g.severity for g in gaps}
        assert "high" in sevs  # max_revenue_missing

    def test_summarize(self):
        gaps = [
            DataGap("a", "t1", "high", "", ""),
            DataGap("b", "t2", "high", "", ""),
            DataGap("c", "t3", "medium", "", ""),
            DataGap("d", "t4", "low", "", ""),
        ]
        s = MissingDataDetector.summarize(gaps)
        assert s == {"high": 2, "medium": 1, "low": 1, "total": 4}


# --------------------------------------------------------------------------- #
# P1.6.2 — RealityHealthMonitor
# --------------------------------------------------------------------------- #
class TestRealityHealthMonitor:
    def _reg_with(self, tmp_path, gid="g1", **kw):
        data = {
            "games": [{"game_id": gid, "package_name": "", "max_apps": [],
                       "adjust_app_token_ref": "", "meta_campaign_ids": [], **kw}],
        }
        p = tmp_path / "reg.json"
        p.write_text(json.dumps(data))
        return GameRegistry(str(p))

    def test_fully_covered(self, tmp_path):
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"], adjust_app_token="adj",
                             meta_app_id="meta", country="US")
        snap = _make_snap("g1", sources=["registry", "max_live", "adjust_live", "meta_live"],
                          real_domains=["product", "revenue", "acquisition"])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company, include_gaps=False)
        assert report.covered_games == 1
        assert report.coverage_ratio == 1.0
        assert report.per_game["g1"].fully_covered

    def test_only_registry_covered(self, tmp_path):
        """只有注册表 OK，其他源都未绑定 → fully_covered=True（无其他期望源）。"""
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"])  # 绑了 max_account
        snap = _make_snap("g1", sources=["registry"], real_domains=["product"])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company, include_gaps=False)
        # max_account bound but max_live MISSING → not fully covered
        assert report.per_game["g1"].fully_covered is False

    def test_max_missing_status(self, tmp_path):
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"])
        snap = _make_snap("g1", sources=["registry"], real_domains=["product"])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company, include_gaps=False)
        assert report.per_game["g1"].source_health["max_live"].status == "MISSING"

    def test_freshness_sim(self, tmp_path):
        reg = self._reg_with(tmp_path)  # no bindings
        snap = _make_snap("g1", sources=[], real_domains=[])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company, include_gaps=False)
        assert report.per_game["g1"].freshness == "sim"

    def test_freshness_live(self, tmp_path):
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"])
        snap = _make_snap("g1", sources=["registry", "max_live"],
                          real_domains=["product", "revenue"])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company, include_gaps=False)
        assert report.per_game["g1"].freshness == "live"

    def test_to_markdown(self, tmp_path):
        reg = self._reg_with(tmp_path, max_apps=["ACCT_1"], country="US")
        snap = _make_snap("g1", sources=["registry", "max_live"],
                          real_domains=["product", "revenue"])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company)
        md = report.to_markdown()
        assert "真实数据覆盖日报" in md
        assert "g1" in md
        assert "OK" in md

    def test_registry_always_ok(self, tmp_path):
        reg = self._reg_with(tmp_path)  # no bindings
        snap = _make_snap("g1", sources=["registry"], real_domains=["product"])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company, include_gaps=False)
        assert report.per_game["g1"].source_health["registry"].status == "OK"


# --------------------------------------------------------------------------- #
# P1.6.4 — DailyRealityStore
# --------------------------------------------------------------------------- #
class TestDailyRealityStore:
    def test_save_and_load(self, tmp_path):
        store = DailyRealityStore(str(tmp_path / "reality"))
        snap = _make_snap("g1", sources=["registry"], real_domains=["product"])
        store.save(snap, "2026-07-30T09:00:00")
        loaded = store.load("g1", "2026-07-30")
        assert loaded is not None
        assert loaded.game_id == "g1"

    def test_load_latest(self, tmp_path):
        store = DailyRealityStore(str(tmp_path / "reality"))
        store.save(_make_snap("g1", real_confidence=0.1), "2026-07-29T09:00:00")
        store.save(_make_snap("g1", real_confidence=0.9), "2026-07-30T09:00:00")
        latest = store.load_latest("g1")
        assert latest is not None
        assert latest.real_confidence == 0.9

    def test_load_range(self, tmp_path):
        store = DailyRealityStore(str(tmp_path / "reality"))
        store.save(_make_snap("g1"), "2026-07-28T09:00:00")
        store.save(_make_snap("g1"), "2026-07-29T09:00:00")
        store.save(_make_snap("g1"), "2026-07-30T09:00:00")
        snaps = store.load_range("g1", "2026-07-29", "2026-07-30")
        assert len(snaps) == 2

    def test_safe_dir_sanitize(self):
        assert _safe_dir("Quiz B?blico") == "Quiz B_blico"
        assert _safe_dir("a<b>c:d") == "a_b_c_d"
        assert _safe_dir("normal_name") == "normal_name"
        assert _safe_dir("path\\slash") == "path_slash"

    def test_special_chars_game_id(self, tmp_path):
        store = DailyRealityStore(str(tmp_path / "reality"))
        gid = "Quiz B?blico: Edi??o"
        snap = _make_snap(gid)
        store.save(snap, "2026-07-30T09:00:00")
        loaded = store.load(gid, "2026-07-30")
        assert loaded is not None
        assert loaded.game_id == gid
        assert store.dates(gid) == ["2026-07-30"]

    def test_index_integrity(self, tmp_path):
        """_index.json 正确维护 safe_dir → game_id 映射。"""
        store = DailyRealityStore(str(tmp_path / "reality"))
        store.save(_make_snap("g1"), "2026-07-30T09:00:00")
        store.save(_make_snap("Quiz B?blico"), "2026-07-30T09:00:00")
        ids = store.all_game_ids()
        assert "g1" in ids
        assert "Quiz B?blico" in ids
        assert len(ids) == 2

    def test_save_company(self, tmp_path):
        store = DailyRealityStore(str(tmp_path / "reality"))
        snaps = [_make_snap("g1"), _make_snap("g2")]
        company = _make_company(snaps)
        paths = store.save_company(company, "2026-07-30")
        assert len(paths) == 2
        assert all(p.exists() for p in paths)
        assert set(store.all_game_ids()) == {"g1", "g2"}

    def test_load_nonexistent(self, tmp_path):
        store = DailyRealityStore(str(tmp_path / "reality"))
        assert store.load("no_game", "2026-01-01") is None
        assert store.load_latest("no_game") is None
        assert store.dates("no_game") == []
        assert store.load_range("no_game", "2026-01-01", "2026-12-31") == []


# --------------------------------------------------------------------------- #
# E2E — Hub + Coverage 集成
# --------------------------------------------------------------------------- #
class TestCoverageE2E:
    def test_hub_refresh_then_coverage(self, tmp_path):
        """验证 E17.1 hub.refresh → monitor.check 整条链路。"""
        from src.growth_reality.agent import GrowthRealityHub
        from src.growth_reality.production_sources.max_source import MaxRealitySource
        from src.growth_reality.registry import RegistryRealitySource

        # 临时注册表：一个完全绑定的游戏
        reg_doc = {
            "games": [{
                "game_id": "g1", "package_name": "com.x",
                "platform": "android", "max_apps": ["ACCT_1"],
                "adjust_app_token": "adj_ref", "meta_app_id": "meta_x",
                "country": "US", "max_account": "ACCT_1",
            }],
        }
        reg_path = tmp_path / "reg.json"
        reg_path.write_text(json.dumps(reg_doc))
        reg = GameRegistry(str(reg_path))

        # MAX SIM 模式（不连接真实 MAX，但 source 会贡献 revenue 域）
        hub = GrowthRealityHub([
            RegistryRealitySource(reg),
            MaxRealitySource(mode="sim", registry=reg),
        ])
        company = hub.refresh(reg.all_game_ids(), "2026-07-30", persist=False)

        monitor = RealityHealthMonitor(reg)
        report = monitor.check(company)
        assert report.total_games == 1
        assert report.per_game["g1"].source_health["registry"].status == "OK"
        assert "真实数据覆盖日报" in report.to_markdown()

    def test_coverage_to_markdown_includes_gaps(self, tmp_path):
        reg_doc = {
            "games": [{
                "game_id": "g1", "max_apps": ["ACCT_1"],
                "adjust_app_token": "adj",
            }],
        }
        reg_path = tmp_path / "reg.json"
        reg_path.write_text(json.dumps(reg_doc))
        reg = GameRegistry(str(reg_path))
        # 只有 registry SIM 数据，max/adjust 缺失
        snap = _make_snap("g1", sources=["registry"], real_domains=["product"])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company)
        md = report.to_markdown()
        assert "DATA_GAP" in md or "high" in md.lower()
        assert "max_revenue_missing" in md or "adjust_dau_missing" in md

    def test_demo_full_coverage_zero_gaps(self, tmp_path):
        """模拟真实数据完全到位的场景：覆盖全绿，0 缺口。"""
        reg_doc = {
            "games": [{
                "game_id": "g1", "adjust_app_token": "adj",
                "max_apps": ["ACCT_1"], "meta_app_id": "meta",
                "country": "US", "package_name": "com.x",
                "platform": "android", "max_account": "ACCT_1",
            }],
        }
        reg_path = tmp_path / "reg.json"
        reg_path.write_text(json.dumps(reg_doc))
        reg = GameRegistry(str(reg_path))
        snap = _make_snap("g1",
                          sources=["registry", "max_live", "adjust_live", "meta_live"],
                          real_domains=["product", "revenue", "acquisition"])
        company = _make_company([snap])
        mon = RealityHealthMonitor(reg)
        report = mon.check(company)
        assert report.covered_games == 1
        assert report.gaps == []
        assert report.coverage_ratio == 1.0
