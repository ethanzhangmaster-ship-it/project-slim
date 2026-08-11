"""Growth Strategy Layer — DiagnosticEngine.

诊断引擎：从 FeedbackSignal + 指标快照推断根因。

数据流:
  RealityFeedbackSignal + 当前/历史指标 → DiagnosisResult

诊断决策树基于可用指标构建：
  - 可用: ctr, cpi, roas, spend, clicks, impressions(推导), installs(推导), revenue(推导)
  - 推导: cpm = spend / impressions * 1000, frequency = impressions / installs (近似)
  - 不可用: 直接 frequency（AdsPerformanceRow 无此字段）

当指标不足以确定根因时，降级为 "undiagnosed" 并保留所有候选。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 枚举
# ──────────────────────────────────────────────


class RootCause(str, Enum):
    """诊断根因类型。"""

    CREATIVE_FATIGUE = "creative_fatigue"
    AUDIENCE_SATURATION = "audience_saturation"
    HOOK_DECAY = "hook_decay"
    AUDIENCE_QUALITY_DROP = "audience_quality_drop"
    MONETIZATION_ISSUE = "monetization_issue"
    SCALING_TOO_FAST = "scaling_too_fast"
    CLICKBAIT_MISMATCH = "clickbait_mismatch"
    UNDIAGNOSED = "undiagnosed"


class StrategyType(str, Enum):
    """增长策略类型（与 V2 架构一致）。"""

    SCALE = "scale"
    SUPPRESS = "suppress"
    REFRESH = "refresh"
    PAUSE = "pause"
    MAINTAIN = "maintain"
    EXPLORE = "explore"


# 根因 → 推荐策略
ROOT_CAUSE_TO_STRATEGY: dict[RootCause, StrategyType] = {
    RootCause.CREATIVE_FATIGUE: StrategyType.SUPPRESS,
    RootCause.AUDIENCE_SATURATION: StrategyType.SUPPRESS,
    RootCause.HOOK_DECAY: StrategyType.REFRESH,
    RootCause.AUDIENCE_QUALITY_DROP: StrategyType.SUPPRESS,
    RootCause.MONETIZATION_ISSUE: StrategyType.SUPPRESS,
    RootCause.SCALING_TOO_FAST: StrategyType.SUPPRESS,
    RootCause.CLICKBAIT_MISMATCH: StrategyType.PAUSE,
    RootCause.UNDIAGNOSED: StrategyType.MAINTAIN,
}


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────


@dataclass
class DiagnosisCandidate:
    """鉴别诊断候选。"""

    root_cause: RootCause = RootCause.UNDIAGNOSED
    probability: float = 0.0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause": self.root_cause.value,
            "probability": round(self.probability, 4),
            "evidence": self.evidence,
        }


@dataclass
class DiagnosisResult:
    """诊断结果。"""

    diagnosis_id: str = ""
    signal_id: str = ""
    creative_id: str = ""
    signal_type: str = ""
    root_cause: RootCause = RootCause.UNDIAGNOSED
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    differential: list[DiagnosisCandidate] = field(default_factory=list)
    recommended_strategy_type: StrategyType = StrategyType.MAINTAIN
    metrics_snapshot: dict[str, float] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.diagnosis_id:
            self.diagnosis_id = f"diag_{uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.recommended_strategy_type or self.recommended_strategy_type == StrategyType.MAINTAIN:
            self.recommended_strategy_type = ROOT_CAUSE_TO_STRATEGY.get(
                self.root_cause, StrategyType.MAINTAIN
            )

    @property
    def is_confident(self) -> bool:
        """诊断置信度是否足够高。"""
        return self.confidence >= 0.6

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "signal_id": self.signal_id,
            "creative_id": self.creative_id,
            "signal_type": self.signal_type,
            "root_cause": self.root_cause.value,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "differential": [c.to_dict() for c in self.differential],
            "recommended_strategy_type": self.recommended_strategy_type.value,
            "metrics_snapshot": self.metrics_snapshot,
            "created_at": self.created_at,
        }


# ──────────────────────────────────────────────
# 指标工具
# ──────────────────────────────────────────────


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """安全除法。"""
    if denominator == 0:
        return default
    return numerator / denominator


def _pct_change(old: float, new: float) -> float:
    """计算百分比变化（-1.0 ~ +inf）。"""
    if old == 0:
        return 0.0
    return (new - old) / old


def derive_cpm(spend: float, impressions: float) -> float:
    """推导 CPM = 花费 / 展示 * 1000。"""
    return _safe_div(spend, impressions, 0.0) * 1000


def derive_frequency(impressions: float, installs: float) -> float:
    """推导频次 = 展示 / 安装（近似值，真实频次需要 reach 数据）。"""
    return _safe_div(impressions, installs, 0.0)


# ──────────────────────────────────────────────
# 诊断决策树
# ──────────────────────────────────────────────


class DiagnosticEngine:
    """诊断引擎 — 从信号 + 指标推断根因。

    诊断决策树:

    ROAS下降 / 疲劳信号
      ├── CTR 也下降?
      │   ├── 频次高 (推导 installs 低)?
      │   │   → creative_fatigue (素材疲劳)
      │   ├── CPM 上升 > 20%?
      │   │   → audience_saturation (受众饱和)
      │   └── CPM 稳定?
      │       → hook_decay (钩子衰退)
      ├── CTR 稳定?
      │   ├── CPI 上升 > 20%?
      │   │   → audience_quality_drop (受众质量下降)
      │   ├── 花费增加 > 50%?
      │   │   → scaling_too_fast (扩展过快)
      │   └── 花费稳定 + ROAS 下降
      │       → monetization_issue (商业化问题)
      └── CTR 上升 + ROAS 下降?
          → clickbait_mismatch (标题党不匹配)

    SCALE_OPPORTUNITY 信号:
      → 直接诊断为 "healthy_growth"（不需要根因分析）
      → recommended_strategy = SCALE

    数据不足时:
      → root_cause = "undiagnosed"
      → 保留所有候选鉴别诊断
    """

    # ── 阈值常量 ──
    CTR_DROP_SIGNIFICANT = 0.15       # CTR 下降 15% 为显著
    CTR_DROP_SEVERE = 0.30            # CTR 下降 30% 为严重
    ROAS_DROP_SIGNIFICANT = 0.20      # ROAS 下降 20% 为显著
    CPM_INCREASE_SIGNIFICANT = 0.20   # CPM 上升 20% 为显著
    CPI_INCREASE_SIGNIFICANT = 0.20   # CPI 上升 20% 为显著
    SPEND_INCREASE_SIGNIFICANT = 0.50 # 花费增加 50% 为显著
    FREQUENCY_HIGH = 3.0              # 推导频次 > 3 为高频
    FREQUENCY_SEVERE = 5.0            # 推导频次 > 5 为严重

    def diagnose(
        self,
        signal: Any,
        current_metrics: dict[str, float],
        previous_metrics: dict[str, float] | None = None,
    ) -> DiagnosisResult:
        """对单个反馈信号执行诊断。

        Args:
            signal: RealityFeedbackSignal 或包含 signal_type/creative_id/severity 的对象
            current_metrics: 当前周期指标 (aggregate_by_creative 输出)
            previous_metrics: 上一周期指标 (用于趋势对比)

        Returns:
            DiagnosisResult: 诊断结果
        """
        previous_metrics = previous_metrics or {}
        signal_type = self._get_signal_type(signal)
        creative_id = self._get_creative_id(signal)
        signal_id = self._get_signal_id(signal)

        # 构建指标快照（含推导指标）
        snapshot = self._build_snapshot(current_metrics, previous_metrics)

        result = DiagnosisResult(
            signal_id=signal_id,
            creative_id=creative_id,
            signal_type=signal_type,
            metrics_snapshot=snapshot,
        )

        # 指标为空时直接降级为 undiagnosed
        if snapshot.get("spend", 0) == 0 and snapshot.get("ctr", 0) == 0:
            self._diagnose_unknown(result, snapshot)
            return result

        # 按信号类型路由到不同诊断逻辑
        if signal_type == "scale_opportunity":
            self._diagnose_scale(result, snapshot)
        elif signal_type in ("roas_decline", "creative_replacement"):
            self._diagnose_decline(result, signal, snapshot)
        elif signal_type == "fatigue_warning":
            self._diagnose_fatigue(result, signal, snapshot)
        else:
            # data_collection 或未知信号
            self._diagnose_unknown(result, snapshot)

        # 子方法可能只设了 root_cause 没设 strategy，同步一次
        # (_diagnose_scale 会显式设 SCALE，不会被覆盖)
        if result.recommended_strategy_type == StrategyType.MAINTAIN:
            result.recommended_strategy_type = ROOT_CAUSE_TO_STRATEGY.get(
                result.root_cause, StrategyType.MAINTAIN
            )

        return result

    # ── 主诊断方法 ──

    def _diagnose_scale(
        self,
        result: DiagnosisResult,
        snapshot: dict[str, float],
    ) -> None:
        """诊断放量机会信号 — 不需要根因分析。"""
        result.root_cause = RootCause.UNDIAGNOSED  # 不是问题，是机会
        result.recommended_strategy_type = StrategyType.SCALE
        result.confidence = 0.80
        result.evidence = [
            "ROAS 健康，指标稳定",
            f"当前 ROAS {snapshot.get('roas', 0):.2f}",
            f"CTR {snapshot.get('ctr', 0):.4f}",
        ]

    def _diagnose_decline(
        self,
        result: DiagnosisResult,
        signal: Any,
        snapshot: dict[str, float],
    ) -> None:
        """诊断 ROAS 下降 / 需替换信号 — 完整决策树。"""
        ctr_change = snapshot.get("ctr_change", 0.0)
        cpm_change = snapshot.get("cpm_change", 0.0)
        cpi_change = snapshot.get("cpi_change", 0.0)
        spend_change = snapshot.get("spend_change", 0.0)
        frequency = snapshot.get("frequency", 0.0)
        prev_ctr = snapshot.get("prev_ctr", 0.0)
        curr_ctr = snapshot.get("ctr", 0.0)
        prev_cpm = snapshot.get("prev_cpm", 0.0)
        curr_cpm = snapshot.get("cpm", 0.0)
        prev_cpi = snapshot.get("prev_cpi", 0.0)
        curr_cpi = snapshot.get("cpi", 0.0)
        prev_spend = snapshot.get("prev_spend", 0.0)
        curr_spend = snapshot.get("spend", 0.0)
        curr_roas = snapshot.get("roas", 0.0)

        candidates: list[DiagnosisCandidate] = []

        # ── 分支 1: CTR 也在下降 ──
        if ctr_change < -self.CTR_DROP_SIGNIFICANT:
            # 子分支 1a: 频次高 → 素材疲劳
            if frequency >= self.FREQUENCY_SEVERE:
                result.root_cause = RootCause.CREATIVE_FATIGUE
                result.confidence = 0.90
                result.evidence = [
                    f"频次 {frequency:.1f}（严重 > {self.FREQUENCY_SEVERE}）",
                    f"CTR {prev_ctr:.4f}→{curr_ctr:.4f}（{ctr_change:+.1%}）",
                    f"CPM {prev_cpm:.2f}→{curr_cpm:.2f}（{cpm_change:+.1%}）",
                ]
                candidates.append(self._candidate(
                    RootCause.AUDIENCE_SATURATION,
                    0.20,
                    [f"CPM 变化 {cpm_change:+.1%}"],
                ))
                candidates.append(self._candidate(
                    RootCause.HOOK_DECAY,
                    0.10,
                    ["CPM 未显著上升，可能仅钩子衰退"],
                ))

            # 子分支 1b: CPM 上升 → 受众饱和
            elif cpm_change > self.CPM_INCREASE_SIGNIFICANT:
                result.root_cause = RootCause.AUDIENCE_SATURATION
                result.confidence = 0.85
                result.evidence = [
                    f"CPM {prev_cpm:.2f}→{curr_cpm:.2f}（{cpm_change:+.1%}）",
                    f"CTR {prev_ctr:.4f}→{curr_ctr:.4f}（{ctr_change:+.1%}）",
                    "竞价升高 + 点击率下降 = 受众饱和",
                ]
                candidates.append(self._candidate(
                    RootCause.CREATIVE_FATIGUE,
                    0.15,
                    [f"频次 {frequency:.1f}"],
                ))

            # 子分支 1c: CPM 稳定 → 钩子衰退
            else:
                result.root_cause = RootCause.HOOK_DECAY
                result.confidence = 0.80
                result.evidence = [
                    f"CTR {prev_ctr:.4f}→{curr_ctr:.4f}（{ctr_change:+.1%}）",
                    f"CPM {prev_cpm:.2f}→{curr_cpm:.2f}（{cpm_change:+.1%}，稳定）",
                    "CTR 下降但 CPM 稳定，素材吸引力衰退",
                ]
                candidates.append(self._candidate(
                    RootCause.CREATIVE_FATIGUE,
                    0.15,
                    [f"频次 {frequency:.1f}"],
                ))

        # ── 分支 2: CTR 稳定 ──
        elif abs(ctr_change) <= self.CTR_DROP_SIGNIFICANT:
            # 子分支 2a: CPI 上升 → 受众质量下降
            if cpi_change > self.CPI_INCREASE_SIGNIFICANT:
                result.root_cause = RootCause.AUDIENCE_QUALITY_DROP
                result.confidence = 0.82
                result.evidence = [
                    f"CPI ${prev_cpi:.2f}→${curr_cpi:.2f}（{cpi_change:+.1%}）",
                    f"CTR 稳定（{ctr_change:+.1%}），点击质量未变",
                    "安装成本上升 = 用户质量下降",
                ]
                candidates.append(self._candidate(
                    RootCause.AUDIENCE_SATURATION,
                    0.10,
                    ["CPM 可能也在上升"],
                ))

            # 子分支 2b: 花费大幅增加 → 扩展过快
            elif spend_change > self.SPEND_INCREASE_SIGNIFICANT:
                result.root_cause = RootCause.SCALING_TOO_FAST
                result.confidence = 0.80
                result.evidence = [
                    f"花费 ${prev_spend:.0f}→${curr_spend:.0f}（{spend_change:+.1%}）",
                    f"CTR 稳定，CPI {cpi_change:+.1%}",
                    f"ROAS {curr_roas:.2f}，规模扩展过快导致效率下降",
                ]

            # 子分支 2c: CTR/CPI/花费都稳定但 ROAS 下降 → 商业化问题
            else:
                result.root_cause = RootCause.MONETIZATION_ISSUE
                result.confidence = 0.65
                result.evidence = [
                    f"ROAS {curr_roas:.2f}（下降）",
                    f"CTR 稳定（{ctr_change:+.1%}），CPI 稳定（{cpi_change:+.1%}）",
                    "获客指标平稳但 ROAS 下降，问题出在商业化端",
                ]
                candidates.append(self._candidate(
                    RootCause.AUDIENCE_QUALITY_DROP,
                    0.20,
                    ["可能是用户质量微变，指标未捕获"],
                ))
                candidates.append(self._candidate(
                    RootCause.SCALING_TOO_FAST,
                    0.15,
                    [f"花费变化 {spend_change:+.1%}"],
                ))

        # ── 分支 3: CTR 上升 + ROAS 下降 → 标题党不匹配 ──
        elif ctr_change > self.CTR_DROP_SIGNIFICANT:
            result.root_cause = RootCause.CLICKBAIT_MISMATCH
            result.confidence = 0.78
            result.evidence = [
                f"CTR {prev_ctr:.4f}→{curr_ctr:.4f}（{ctr_change:+.1%}，上升）",
                f"ROAS {curr_roas:.2f}（下降）",
                "点击率上升但 ROAS 下降 = 点击与转化不匹配",
            ]
            candidates.append(self._candidate(
                RootCause.HOOK_DECAY,
                0.15,
                ["可能是钩子误导导致点击但未转化"],
            ))

        # ── 分支 4: 数据不足 ──
        else:
            self._diagnose_unknown(result, snapshot)
            return

        result.differential = candidates

    def _diagnose_fatigue(
        self,
        result: DiagnosisResult,
        signal: Any,
        snapshot: dict[str, float],
    ) -> None:
        """诊断疲劳信号 — 频次 + CTR 双指标判断。"""
        frequency = snapshot.get("frequency", 0.0)
        ctr_change = snapshot.get("ctr_change", 0.0)
        prev_ctr = snapshot.get("prev_ctr", 0.0)
        curr_ctr = snapshot.get("ctr", 0.0)
        cpm_change = snapshot.get("cpm_change", 0.0)

        if frequency >= self.FREQUENCY_SEVERE and ctr_change < -self.CTR_DROP_SIGNIFICANT:
            # 高频次 + CTR 下降 = 确认素材疲劳
            result.root_cause = RootCause.CREATIVE_FATIGUE
            result.confidence = 0.90
            result.evidence = [
                f"频次 {frequency:.1f}（严重 > {self.FREQUENCY_SEVERE}）",
                f"CTR {prev_ctr:.4f}→{curr_ctr:.4f}（{ctr_change:+.1%}）",
            ]
            result.differential = [
                self._candidate(
                    RootCause.AUDIENCE_SATURATION,
                    0.15,
                    [f"CPM 变化 {cpm_change:+.1%}"],
                ),
            ]

        elif frequency >= self.FREQUENCY_HIGH and ctr_change < -self.CTR_DROP_SIGNIFICANT:
            # 中等频次 + CTR 下降 = 可能疲劳
            result.root_cause = RootCause.CREATIVE_FATIGUE
            result.confidence = 0.70
            result.evidence = [
                f"频次 {frequency:.1f}（偏高 > {self.FREQUENCY_HIGH}）",
                f"CTR {prev_ctr:.4f}→{curr_ctr:.4f}（{ctr_change:+.1%}）",
            ]
            result.differential = [
                self._candidate(
                    RootCause.HOOK_DECAY,
                    0.25,
                    ["频次不高，可能是钩子衰退"],
                ),
                self._candidate(
                    RootCause.AUDIENCE_SATURATION,
                    0.15,
                    [f"CPM 变化 {cpm_change:+.1%}"],
                ),
            ]

        elif ctr_change < -self.CTR_DROP_SEVERE:
            # 频次不高但 CTR 严重下降 = 钩子衰退
            result.root_cause = RootCause.HOOK_DECAY
            result.confidence = 0.75
            result.evidence = [
                f"CTR {prev_ctr:.4f}→{curr_ctr:.4f}（{ctr_change:+.1%}，严重下降）",
                f"频次 {frequency:.1f}（不高）",
                "频次低但 CTR 严重下降，钩子吸引力衰退",
            ]

        else:
            # 数据不明确
            result.root_cause = RootCause.UNDIAGNOSED
            result.confidence = 0.35
            result.evidence = [
                f"频次 {frequency:.1f}",
                f"CTR 变化 {ctr_change:+.1%}",
                "指标不足以确认疲劳根因",
            ]
            result.differential = [
                self._candidate(
                    RootCause.CREATIVE_FATIGUE,
                    0.30,
                    ["疲劳信号触发但证据不足"],
                ),
                self._candidate(
                    RootCause.HOOK_DECAY,
                    0.25,
                    ["可能是钩子衰退"],
                ),
            ]

    def _diagnose_unknown(
        self,
        result: DiagnosisResult,
        snapshot: dict[str, float],
    ) -> None:
        """数据不足时的降级诊断。"""
        result.root_cause = RootCause.UNDIAGNOSED
        result.confidence = 0.20
        result.evidence = [
            "信号类型未知或数据不足",
            f"可用指标: {', '.join(snapshot.keys())}",
        ]
        result.differential = []

    # ── 辅助方法 ──

    def _build_snapshot(
        self,
        current: dict[str, float],
        previous: dict[str, float],
    ) -> dict[str, float]:
        """构建指标快照，含推导指标和变化率。"""
        # 原始指标
        curr_spend = current.get("spend", 0.0)
        curr_clicks = current.get("clicks", 0.0)
        curr_ctr = current.get("ctr", 0.0)
        curr_cpi = current.get("cpi", 0.0)
        curr_roas = current.get("roas", 0.0)
        curr_impressions = current.get("impressions", 0.0)
        curr_installs = current.get("installs", 0.0)
        curr_revenue = current.get("revenue", 0.0)

        prev_spend = previous.get("spend", 0.0)
        prev_ctr = previous.get("ctr", 0.0)
        prev_cpi = previous.get("cpi", 0.0)
        prev_roas = previous.get("roas", 0.0)
        prev_impressions = previous.get("impressions", 0.0)
        prev_installs = previous.get("installs", 0.0)

        # 推导指标
        curr_cpm = derive_cpm(curr_spend, curr_impressions)
        prev_cpm = derive_cpm(prev_spend, prev_impressions)
        curr_frequency = derive_frequency(curr_impressions, curr_installs)

        # 变化率
        ctr_change = _pct_change(prev_ctr, curr_ctr) if prev_ctr > 0 else 0.0
        cpm_change = _pct_change(prev_cpm, curr_cpm) if prev_cpm > 0 else 0.0
        cpi_change = _pct_change(prev_cpi, curr_cpi) if prev_cpi > 0 else 0.0
        spend_change = _pct_change(prev_spend, curr_spend) if prev_spend > 0 else 0.0
        roas_change = _pct_change(prev_roas, curr_roas) if prev_roas > 0 else 0.0

        return {
            # 当前指标
            "spend": curr_spend,
            "clicks": curr_clicks,
            "ctr": curr_ctr,
            "cpi": curr_cpi,
            "roas": curr_roas,
            "impressions": curr_impressions,
            "installs": curr_installs,
            "revenue": curr_revenue,
            "cpm": curr_cpm,
            "frequency": curr_frequency,
            # 上一周期指标
            "prev_spend": prev_spend,
            "prev_ctr": prev_ctr,
            "prev_cpi": prev_cpi,
            "prev_roas": prev_roas,
            "prev_cpm": prev_cpm,
            "prev_impressions": prev_impressions,
            "prev_installs": prev_installs,
            # 变化率
            "ctr_change": ctr_change,
            "cpm_change": cpm_change,
            "cpi_change": cpi_change,
            "spend_change": spend_change,
            "roas_change": roas_change,
        }

    def _candidate(
        self,
        root_cause: RootCause,
        probability: float,
        evidence: list[str],
    ) -> DiagnosisCandidate:
        """创建鉴别诊断候选。"""
        return DiagnosisCandidate(
            root_cause=root_cause,
            probability=probability,
            evidence=evidence,
        )

    def _get_signal_type(self, signal: Any) -> str:
        """从信号对象提取 signal_type 字符串。"""
        if hasattr(signal, "signal_type"):
            st = signal.signal_type
            return st.value if hasattr(st, "value") else str(st)
        if isinstance(signal, dict):
            st = signal.get("signal_type", "")
            return st.value if hasattr(st, "value") else str(st)
        return ""

    def _get_creative_id(self, signal: Any) -> str:
        """从信号对象提取 creative_id。"""
        if hasattr(signal, "creative_id"):
            return signal.creative_id
        if isinstance(signal, dict):
            return signal.get("creative_id", "")
        return ""

    def _get_signal_id(self, signal: Any) -> str:
        """从信号对象提取 signal_id。"""
        if hasattr(signal, "signal_id"):
            return signal.signal_id
        if isinstance(signal, dict):
            return signal.get("signal_id", "")
        return ""


# ──────────────────────────────────────────────
# 批量诊断
# ──────────────────────────────────────────────


def diagnose_signals(
    signals: list[Any],
    current_metrics: dict[str, dict[str, float]],
    previous_metrics: dict[str, dict[str, float]] | None = None,
) -> list[DiagnosisResult]:
    """批量诊断多个信号。

    Args:
        signals: RealityFeedbackSignal 列表
        current_metrics: {creative_id: metrics_dict}
        previous_metrics: {creative_id: metrics_dict}

    Returns:
        list[DiagnosisResult]
    """
    previous_metrics = previous_metrics or {}
    engine = DiagnosticEngine()
    results: list[DiagnosisResult] = []

    for signal in signals:
        creative_id = engine._get_creative_id(signal)
        curr = current_metrics.get(creative_id, {})
        prev = previous_metrics.get(creative_id, {})

        if not curr:
            logger.warning(
                "DiagnosticEngine: no current metrics for creative_id=%s, skipping",
                creative_id,
            )
            continue

        result = engine.diagnose(signal, curr, prev)
        results.append(result)

    return results
