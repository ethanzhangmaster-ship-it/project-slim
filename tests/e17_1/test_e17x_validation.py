"""P1.7 Reality Validation Audit — 完整测试套件。

用户验收五场景：
  Test1: 收入一致（Adjust=100, MAX=20 → Expected=120）
  Test2: 收入异常（Adjust=100, MAX=20, reported=300 → RED）
  Test3: 数据过期（48h → BLOCK）
  Test4: Reality Gate（score=0.3, EXECUTE → OBSERVE）
  Test5: 完整链（MAX+Adjust+Meta → Hub → Audit → Decision Engine）
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.growth_reality.validation import (
    AuditReport,
    ConfidenceScorer,
    DataFreshnessMonitor,
    RealityAuditor,
    RealityGate,
    RevenueReconciler,
)
from src.growth_reality.validation.models import (
    FreshnessCheck,
    GameAuditEntry,
    GameFreshness,
    RealityScore,
    RevenueReconciliation,
)
from src.growth_reality.models import GrowthRealitySnapshot
from src.growth_reality.snapshot import CompanySnapshot, build_company_snapshot


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _snap(gid="g1", revenue=0.0, real_confidence=0.4, sources=None, real_domains=None):
    return GrowthRealitySnapshot.from_dict({
        "game_id": gid, "timestamp": "2026-07-30T09:00:00",
        "sources": list(sources or []),
        "real_domains": list(real_domains or []),
        "confidence": 0.5, "real_confidence": real_confidence,
        "revenue": {"daily_revenue": revenue} if revenue else None,
    })


def _company(*snaps):
    return build_company_snapshot(list(snaps), "2026-07-30")


# --------------------------------------------------------------------------- #
# Test1: 收入一致 → GREEN
# --------------------------------------------------------------------------- #
class Test1_RevenueReconciliationOk:
    def test_adjust_100_max_20_expected_120(self):
        snap = _snap(revenue=120.0)
        r = RevenueReconciler.reconcile_game("g1", snap, 100.0, 20.0)
        assert r.expected_total == 120.0
        assert r.reported_total == 120.0
        assert r.variance == 0.0
        assert r.status == "GREEN"

    def test_small_variance_still_green(self):
        snap = _snap(revenue=119.0)
        r = RevenueReconciler.reconcile_game("g1", snap, 100.0, 20.0)
        # variance = |120-119|/120 = 0.0083
        assert r.variance < 0.01
        assert r.status == "GREEN"

    def test_variance_just_under_five_percent(self):
        snap = _snap(revenue=115.0)
        r = RevenueReconciler.reconcile_game("g1", snap, 100.0, 20.0)
        # |120-115|/120 = 0.0417
        assert r.variance < 0.05
        assert r.status == "GREEN"


# --------------------------------------------------------------------------- #
# Test2: 收入异常 → RED
# --------------------------------------------------------------------------- #
class Test2_RevenueReconciliationRed:
    def test_reported_300_vs_expected_120(self):
        snap = _snap(revenue=300.0)
        r = RevenueReconciler.reconcile_game("g1", snap, 100.0, 20.0)
        assert r.expected_total == 120.0
        assert r.reported_total == 300.0
        assert r.variance > 0.20  # |120-300|/120 = 1.5
        assert r.status == "RED"

    def test_no_iap_missing_ad(self):
        snap = _snap(revenue=10.0)
        r = RevenueReconciler.reconcile_game("g1", snap, 100.0, None)
        assert r.expected_total == 100.0
        assert r.status == "RED"  # reported=10, expected=100 → big gap

    def test_both_zero_trivially_green(self):
        snap = _snap(revenue=0.0)
        r = RevenueReconciler.reconcile_game("g0", snap, 0.0, 0.0)
        assert r.status == "GREEN"

    def test_insufficient_no_data(self):
        r = RevenueReconciler.reconcile_game("g1", None, None, None)
        assert r.status == "INSUFFICIENT"


# --------------------------------------------------------------------------- #
# Test3: 数据过期 → BLOCK
# --------------------------------------------------------------------------- #
class Test3_FreshnessMonitor:
    def test_freshness_green_less_than_6h(self):
        ts = datetime.now(timezone.utc) - timedelta(hours=3)
        fc = FreshnessCheck(source="max", last_sync=ts,
                            age_minutes=180, detail="")
        from src.growth_reality.validation.freshness import _status_by_age
        assert _status_by_age(180) == "GREEN"

    def test_freshness_yellow_6_to_24h(self):
        from src.growth_reality.validation.freshness import _status_by_age
        assert _status_by_age(12 * 60) == "YELLOW"

    def test_freshness_red_over_24h(self):
        from src.growth_reality.validation.freshness import _status_by_age
        assert _status_by_age(48 * 60) == "RED"

    def test_game_freshness_aggregates(self, tmp_path):
        # 模拟：使用 tmp_path 作为 data_dir
        mon = DataFreshnessMonitor(str(tmp_path))
        sf = {
            "max": FreshnessCheck(source="max", last_sync=datetime.now(timezone.utc),
                                  age_minutes=60, status="GREEN", detail=""),
            "adjust": FreshnessCheck(source="adjust", last_sync=datetime.now(timezone.utc),
                                     age_minutes=60, status="GREEN", detail=""),
        }
        gf = mon.game_freshness("g1", sf, {"max_live", "adjust_live"})
        assert gf.overall == "GREEN"
        assert gf.freshness_score == 1.0

    def test_game_freshness_mixed(self, tmp_path):
        mon = DataFreshnessMonitor(str(tmp_path))
        sf = {
            "max": FreshnessCheck(source="max", last_sync=datetime.now(timezone.utc),
                                  age_minutes=60, status="GREEN", detail=""),
            "adjust": FreshnessCheck(source="adjust", last_sync=None,
                                     age_minutes=0, status="UNKNOWN", detail=""),
        }
        gf = mon.game_freshness("g1", sf, {"max_live", "adjust_live"})
        # adjust UNKNOWN → scored=0.5 (excluded since status=UNKNOWN), max is GREEN=1.0
        # min(GREEN=1.0) = 1.0 → overall GREEN
        assert gf.freshness_score == 1.0

    def test_48h_old_data_red(self, tmp_path):
        mon = DataFreshnessMonitor(str(tmp_path))
        old_ts = datetime.now(timezone.utc) - timedelta(hours=48)
        sf = {
            "max": FreshnessCheck(source="max", last_sync=old_ts,
                                  age_minutes=48*60, status="RED", detail=""),
        }
        gf = mon.game_freshness("g1", sf, {"max_live"})
        assert gf.overall == "RED"
        assert gf.freshness_score == 0.0


# --------------------------------------------------------------------------- #
# Test4: Reality Gate
# --------------------------------------------------------------------------- #
class Test4_RealityGate:
    def test_score_03_blocks_execute(self):
        gt, reason = RealityGate.apply("EXECUTE", "g1", 0.3)
        assert gt == "OBSERVE"
        assert "禁止自动执行" in reason

    def test_score_065_allows_approve(self):
        gt, reason = RealityGate.apply("EXECUTE", "g1", 0.65)
        assert gt == "APPROVE"
        assert "需人工审批" in reason

    def test_score_09_allows_execute(self):
        gt, reason = RealityGate.apply("EXECUTE", "g1", 0.9)
        assert gt == "EXECUTE"
        assert "允许自动执行" in reason

    def test_approve_at_065_unchanged(self):
        gt, reason = RealityGate.apply("APPROVE", "g1", 0.65)
        assert gt == "APPROVE"

    def test_reject_not_gated(self):
        gt, reason = RealityGate.apply("REJECT", "g1", 0.1)
        assert gt == "REJECT"

    def test_observe_not_gated(self):
        gt, reason = RealityGate.apply("OBSERVE", "g1", 0.1)
        assert gt == "OBSERVE"

    def test_gate_decisions_batch(self):
        decisions = [
            {"game_id": "g1", "decision_type": "EXECUTE"},
            {"game_id": "g2", "decision_type": "EXECUTE"},
            {"game_id": "g3", "decision_type": "APPROVE"},
        ]
        scores = {
            "g1": RealityScore.compute("g1", 0.9, 1.0, 1.0),   # 0.9 → EXECUTE
            "g2": RealityScore.compute("g2", 0.2, 1.0, 1.0),   # 0.2 → BLOCKED
            "g3": RealityScore.compute("g3", 0.6, 1.0, 1.0),   # 0.6 → APPROVE
        }
        gated = RealityGate.gate_decisions(decisions, scores)
        assert gated[0]["gated_type"] == "EXECUTE"
        assert gated[1]["gated_type"] == "OBSERVE"
        assert gated[1]["gated"] is True
        assert gated[2]["gated_type"] == "APPROVE"

    def test_gate_edge_050_boundary(self):
        """score=0.5 exactly → APPROVE (not BLOCKED)"""
        assert RealityGate.apply("EXECUTE", "g1", 0.5) == \
            ("APPROVE", f"RealityScore=0.50 在 APPROVE 区间，需人工审批")

    def test_gate_edge_080_boundary(self):
        """score=0.8 exactly → EXECUTE"""
        gt, reason = RealityGate.apply("EXECUTE", "g1", 0.8)
        assert gt == "EXECUTE"


# --------------------------------------------------------------------------- #
# Test5: 完整审计链路
# --------------------------------------------------------------------------- #
class Test5_FullAuditChain:
    def test_auditor_full_chain(self, tmp_path):
        """MAX+Adjust+Meta → Hub → Audit → Decision 全链路。"""
        # mock 对账数据
        adjust_data = {"g1": 1000.0}
        max_data = {"g1": 300.0}

        # 模拟 E17.1 快照（reported = 1300 exactly matching）
        snap = _snap("g1", revenue=1300.0, real_confidence=0.6,
                     sources=["registry", "max_live", "adjust_live", "meta_live"],
                     real_domains=["product", "revenue", "acquisition"])
        company = _company(snap)

        auditor = RealityAuditor(str(tmp_path))
        report = auditor.audit(
            company, adjust_data, max_data,
            active_sources_by_game={"g1": {"max_live", "adjust_live", "meta_live"}},
        )

        assert report.total_games == 1
        assert report.green == 1
        assert report.red == 0
        entry = report.entries[0]
        assert entry.recon is not None
        assert entry.recon.status == "GREEN"
        assert entry.recon.variance == 0.0
        assert entry.score is not None
        # coverage=0.6, freshness_score depends on local data, consistency=1.0(GREEN)
        assert entry.score.composite > 0  # at minimum coverage*1*1
        assert entry.decision_ready
        assert report.decision_ready == 1

    def test_audit_report_markdown(self, tmp_path):
        adjust_data = {"g1": 1000.0}
        max_data = {"g1": 300.0}
        snap = _snap("g1", revenue=1300.0, real_confidence=0.6,
                     sources=["registry", "max_live", "adjust_live"],
                     real_domains=["product", "revenue", "acquisition"])
        company = _company(snap)

        auditor = RealityAuditor(str(tmp_path))
        report = auditor.audit(company, adjust_data, max_data,
                               active_sources_by_game={"g1": {"max_live", "adjust_live"}})
        md = report.to_markdown()
        assert "Reality Audit Report" in md
        assert "g1" in md
        assert "GREEN" in md or "green" in md.lower()

    def test_audit_with_multiple_games(self, tmp_path):
        snap1 = _snap("g1", revenue=1300.0, real_confidence=0.8,
                      sources=["registry", "max_live", "adjust_live"],
                      real_domains=["product", "revenue", "acquisition"])
        snap2 = _snap("g2", revenue=300.0, real_confidence=0.2,
                      sources=["registry", "max_live"],
                      real_domains=["product", "revenue"])
        company = _company(snap1, snap2)

        auditor = RealityAuditor(str(tmp_path))
        report = auditor.audit(
            company,
            {"g1": 1000.0, "g2": None},
            {"g1": 300.0, "g2": 30.0},
            active_sources_by_game={
                "g1": {"max_live", "adjust_live"},
                "g2": {"max_live"},
            },
        )

        assert report.total_games == 2
        md = report.to_markdown()
        assert "g1" in md
        assert "g2" in md

    def test_audit_with_no_data_insufficient(self, tmp_path):
        snap = _snap("g1", real_confidence=0.0, sources=["registry"],
                     real_domains=["product"])
        company = _company(snap)

        auditor = RealityAuditor(str(tmp_path))
        report = auditor.audit(company, {}, {},
                               active_sources_by_game={"g1": set()})

        assert report.total_games == 1
        entry = report.entries[0]
        assert entry.recon is not None
        assert entry.recon.status == "INSUFFICIENT"
        assert report.decision_ready == 0

    def test_consistency_score_mapping(self):
        """验证 variance→consistency 映射。"""
        from src.growth_reality.validation.reconciliation import RevenueReconciler as RC
        assert RC.consistency_score(
            RevenueReconciliation("g", status="GREEN")) == 1.0
        assert RC.consistency_score(
            RevenueReconciliation("g", status="YELLOW")) == 0.6
        assert RC.consistency_score(
            RevenueReconciliation("g", status="RED")) == 0.3
        assert RC.consistency_score(
            RevenueReconciliation("g", status="INSUFFICIENT")) == 1.0

    def test_e2e_with_gate_integration(self, tmp_path):
        """E2E: Audit → Score → Gate → Downgrade. 全链打通。"""
        snap = _snap("g1", revenue=1300.0, real_confidence=0.9,
                     sources=["registry", "max_live", "adjust_live"],
                     real_domains=["product", "revenue", "acquisition"])
        company = _company(snap)

        auditor = RealityAuditor(str(tmp_path))
        report = auditor.audit(
            company, {"g1": 1000.0}, {"g1": 300.0},
            active_sources_by_game={"g1": {"max_live", "adjust_live"}},
        )

        entry = report.entries[0]
        score = entry.score
        assert score is not None
        # 模拟 E17.3 决策：给 g1 出 EXECUTE，经 RealityGate 过滤
        decisions = [{"game_id": "g1", "decision_type": "EXECUTE"}]
        scores_dict = {"g1": score}
        gated = RealityGate.gate_decisions(decisions, scores_dict)
        assert gated[0]["gated_type"] == "EXECUTE"  # score high enough

    def test_e2e_low_score_blocks(self):
        """E2E: low coverage → low score → decision blocked。"""
        snap = _snap("g1", real_confidence=0.0, sources=[],
                     real_domains=[])
        company = _company(snap)

        auditor = RealityAuditor()
        report = auditor.audit(
            company, {}, {},
            active_sources_by_game={"g1": set()},
        )

        entry = report.entries[0]
        assert entry.score is not None
        assert entry.score.composite < 0.5
        assert entry.score.decision_level == "BLOCKED"

        decisions = [{"game_id": "g1", "decision_type": "EXECUTE"}]
        gated = RealityGate.gate_decisions(decisions, {"g1": entry.score})
        assert gated[0]["gated_type"] == "OBSERVE"
