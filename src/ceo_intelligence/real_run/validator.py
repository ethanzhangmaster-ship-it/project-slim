"""P1.5 — First Real CEO Run 验收闸门（RealRunValidator）。

三道验收门（用户验收标准，硬指标）：
    Gate 1 数据真实性  — hub.real_api_called=True；Adjust/MAX/Meta 三源均真打；
                         快照 sources 禁止出现 SIM 源（demo_sim / catalog）。
    Gate 2 Reality 完整性 — 目标游戏 Revenue + Spend + DAU + ROAS + 渠道 全齐。
    Gate 3 决策有效性  — ≥1 个 EXECUTE 或 APPROVE，且并非全部 OBSERVE。

附加硬断言：reality_confidence > 0.8。
    定义：真实源覆盖的「核心经营域」占比 = |real_domains ∩ {revenue,
    acquisition, product}| / 3。aso/creative 目前无真实源（E16.6 ASO 属独立
    体系，P2 接入），若按全 5 域算上限只有 0.6，永远无法达标——因此以
    CEO 经营决策实际依赖的三个核心域为分母，口径透明可审计。

纪律：纯确定性检查，无 LLM、无网络；失败信息全中文、可直接进报告。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:  # pragma: no cover - 仅类型提示，避免运行时环
    from .runner import RealRunResult

# 核心经营域：CEO 决策直接依赖的三个域（真实源当前可覆盖的全集）
CORE_DOMAINS = ("revenue", "acquisition", "product")
# SIM / 假数据源黑名单（生产报告禁止出现）
FORBIDDEN_SOURCE_IDS = ("demo_sim", "catalog")
# 三个必须真打的生产源标识
REQUIRED_REAL_FLAGS = ("adjust", "max", "meta")
MIN_REALITY_CONFIDENCE = 0.8


class RealityGateError(AssertionError):
    """任一验收门失败时抛出（含全部失败明细）。"""


@dataclass
class GateResult:
    name: str
    passed: bool
    details: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "details": list(self.details)}


@dataclass
class ValidationResult:
    gates: List[GateResult] = field(default_factory=list)
    reality_confidence: float = 0.0

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def failures(self) -> List[str]:
        out: List[str] = []
        for g in self.gates:
            if not g.passed:
                out.extend(f"[{g.name}] {d}" for d in g.details)
        return out

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reality_confidence": self.reality_confidence,
            "gates": [g.to_dict() for g in self.gates],
        }


def compute_reality_confidence(real_domains: List[str]) -> float:
    """核心经营域真实覆盖度 = |real_domains ∩ CORE_DOMAINS| / 3。"""
    hit = len(set(real_domains) & set(CORE_DOMAINS))
    return round(hit / len(CORE_DOMAINS), 4)


class RealRunValidator:
    """P1.5 验收闸门：对 RealRunResult 跑三道门 + 置信度硬断言。"""

    def __init__(self, min_reality_confidence: float = MIN_REALITY_CONFIDENCE):
        self.min_reality_confidence = min_reality_confidence

    # ------------------------------------------------------------------ #
    def validate(self, result: "RealRunResult") -> ValidationResult:
        gates = [
            self._gate1_authenticity(result),
            self._gate2_completeness(result),
            self._gate3_decision(result),
            self._gate4_confidence(result),
        ]
        return ValidationResult(
            gates=gates, reality_confidence=result.reality_confidence
        )

    def assert_valid(self, result: "RealRunResult") -> ValidationResult:
        vr = self.validate(result)
        if not vr.passed:
            raise RealityGateError("；".join(vr.failures))
        return vr

    # ------------------------------------------------------------------ #
    def _gate1_authenticity(self, result: "RealRunResult") -> GateResult:
        details: List[str] = []
        if not result.hub_real_api_called:
            details.append("hub.last_real_api_called=False：全链路未发生真实 API 调用")
        for key in REQUIRED_REAL_FLAGS:
            if not result.source_flags.get(key, False):
                details.append(f"生产源 {key} 未真打（real_api_called=False）")
        snap = result.snapshot
        if snap is not None:
            bad = [s for s in snap.sources if s in FORBIDDEN_SOURCE_IDS]
            if bad:
                details.append(f"快照混入 SIM/假数据源：{', '.join(bad)}")
        else:
            details.append("目标游戏无快照，无法核验来源")
        return GateResult("Gate1 数据真实性", passed=not details, details=details)

    def _gate2_completeness(self, result: "RealRunResult") -> GateResult:
        details: List[str] = []
        snap = result.snapshot
        if snap is None:
            return GateResult(
                "Gate2 Reality完整性", False, ["目标游戏无快照"])
        if not (snap.revenue and snap.revenue.daily_revenue > 0):
            details.append("缺 Revenue（daily_revenue<=0 或缺失）")
        if not (snap.acquisition and snap.acquisition.spend > 0):
            details.append("缺 UA Spend（spend<=0 或缺失）")
        if not (snap.product and snap.product.dau > 0):
            details.append("缺 DAU（dau<=0 或缺失）")
        if not (snap.acquisition and snap.acquisition.roas > 0):
            details.append("缺 ROAS（未形成真实收入×花费配对，或为 0）")
        has_channel = bool(
            (snap.revenue and snap.revenue.network_distribution)
            or ("meta_live" in snap.sources)
        )
        if not has_channel:
            details.append("缺 渠道信息（无 MAX 网络分布，也无 Meta 渠道源）")
        return GateResult("Gate2 Reality完整性", passed=not details, details=details)

    def _gate3_decision(self, result: "RealRunResult") -> GateResult:
        details: List[str] = []
        report = result.decision_report
        decisions = list(report.decisions) if report else []
        if not decisions:
            details.append("决策数为 0（E17.2 未产出任何机会 → E17.3 无决策）")
        else:
            types = [d.decision_type.value for d in decisions]
            actionable = [t for t in types if t in ("execute", "approve")]
            if not actionable:
                details.append(
                    f"无 EXECUTE/APPROVE 决策（实际分布：{types}）")
            if types and all(t == "observe" for t in types):
                details.append("全部决策为 OBSERVE，CEO Brain 未产生可执行结论")
        return GateResult("Gate3 决策有效性", passed=not details, details=details)

    def _gate4_confidence(self, result: "RealRunResult") -> GateResult:
        details: List[str] = []
        rc = result.reality_confidence
        if not rc > self.min_reality_confidence:
            details.append(
                f"reality_confidence={rc:.2f} 未超过 {self.min_reality_confidence:.2f}"
                f"（核心域真实覆盖：{sorted(set(result.snapshot.real_domains) & set(CORE_DOMAINS)) if result.snapshot else []}）"
            )
        return GateResult("Gate4 真实置信度>0.8", passed=not details, details=details)


__all__ = [
    "CORE_DOMAINS",
    "FORBIDDEN_SOURCE_IDS",
    "GateResult",
    "MIN_REALITY_CONFIDENCE",
    "RealityGateError",
    "RealRunValidator",
    "ValidationResult",
    "compute_reality_confidence",
]
