"""P1.7 — 真实校验审计层（Reality Validation Audit）。

在 E17.1 Reality Hub → E17.3 Decision Engine 之间插入信任门：
- reconciliation.py : 收入交叉对账（Adjust IAP + MAX Ad vs Total）
- freshness.py      : 数据新鲜度监控（GREEN/YELLOW/RED）
- confidence.py     : RealityScore = Coverage × Freshness × Consistency
- gate.py           : 决策守卫（RealityScore < 0.5 → 禁止 EXECUTE）
- auditor.py        : 审计编排器（一站式 produce AuditReport）
"""
from __future__ import annotations

from .auditor import RealityAuditor
from .confidence import ConfidenceScorer
from .freshness import DataFreshnessMonitor
from .gate import RealityGate, apply_level, decide_level
from .models import (
    AuditReport,
    FreshnessCheck,
    GameAuditEntry,
    GameFreshness,
    RealityScore,
    RevenueReconciliation,
)
from .reconciliation import RevenueReconciler

__all__ = [
    "RealityAuditor",
    "ConfidenceScorer",
    "DataFreshnessMonitor",
    "RealityGate",
    "apply_level",
    "decide_level",
    "AuditReport",
    "FreshnessCheck",
    "GameAuditEntry",
    "GameFreshness",
    "RealityScore",
    "RevenueReconciliation",
    "RevenueReconciler",
]
