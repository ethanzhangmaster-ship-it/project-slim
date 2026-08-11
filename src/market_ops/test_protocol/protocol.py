"""E11 Phase 2.5 — Test Protocol 数据模型。

定义一次创意测试的完整规则：
  - 测试目标（AEO_IAP vs AEO_ROAS）
  - 测试预算和周期
  - 通过标准和处置规则
  - 素材成熟度分类
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TestObjective(str, Enum):
    """测试目标类型。

    AEO_IAP:  优化 App Install（测素材用，积累数据）
    AEO_ROAS: 优化 ROAS（放量用，优化收入）
    """
    AEO_IAP = "AEO_IAP"
    AEO_ROAS = "AEO_ROAS"


class TestResult(str, Enum):
    """测试结果判定。

    PASSED:            通过，可放量
    FAILED:            失败，应关闭
    BORDERLINE:        边缘，需延长观察
    INSUFFICIENT_DATA: 数据不足，无法判定
    """
    PASSED = "PASSED"
    FAILED = "FAILED"
    BORDERLINE = "BORDERLINE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TestDecision(str, Enum):
    """测试后的处置决策。

    SCALE:  放量（扩大预算 / 新建 Campaign）
    KILL:   关闭（暂停广告）
    EXTEND: 延长测试（再观察 3-5 天）
    REDUCE: 缩减预算（降低 50%）
    KEEP:   保持现状（继续观察）
    """
    SCALE = "SCALE"
    KILL = "KILL"
    EXTEND = "EXTEND"
    REDUCE = "REDUCE"
    KEEP = "KEEP"


class CreativeMaturity(str, Enum):
    """素材成熟度。

    NEW:      全新方向（从未测试过的概念）
    VARIANT:  Winner 变体（基于已验证方向的微调）
    LEGACY:   历史素材（已在跑的老素材）
    """
    NEW = "NEW"
    VARIANT = "VARIANT"
    LEGACY = "LEGACY"


@dataclass
class TestProtocol:
    """定义一次创意测试的完整规则。

    根据素材类型（图片/视频）和成熟度（NEW/VARIANT），
    使用不同的测试标准。

    Usage:
        proto = build_protocol(creative_type="image", maturity=CreativeMaturity.NEW)
        assert proto.test_duration_days == 5
        assert proto.test_budget == 50.0
    """

    # ── 测试配置 ────────────────────────────────────────
    test_objective: TestObjective = TestObjective.AEO_IAP
    test_budget: float = 50.0               # 每日预算（USD）
    test_duration_days: int = 5             # 测试周期（天）
    min_installs: int = 30                  # 最少安装数（低于此值不判定）
    min_spend: float = 100.0                # 最少花费（低于此值不判定）

    # ── 通过标准 ────────────────────────────────────────
    pass_roas_d7_min: float = 0.8           # D7 ROAS >= 此值算通过
    pass_cpi_max: float = 5.0               # CPI <= 此值算通过
    borderline_roas_min: float = 0.4        # D7 ROAS >= 此值算边缘

    # ── 处置规则 ────────────────────────────────────────
    winner_action: TestDecision = TestDecision.SCALE
    winner_budget_multiplier: float = 2.0   # 通过后预算倍数
    winner_max_budget: float = 500.0        # 单素材最大日预算
    loser_action: TestDecision = TestDecision.KILL
    borderline_action: TestDecision = TestDecision.EXTEND
    borderline_extend_days: int = 3         # 边缘素材延长天数
    reduce_ratio: float = 0.5               # 缩减预算比例

    # ── 素材类型 ────────────────────────────────────────
    creative_type: str = "image"            # "image" | "video"
    maturity: CreativeMaturity = CreativeMaturity.NEW

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_objective": self.test_objective.value,
            "test_budget": self.test_budget,
            "test_duration_days": self.test_duration_days,
            "min_installs": self.min_installs,
            "min_spend": self.min_spend,
            "pass_roas_d7_min": self.pass_roas_d7_min,
            "pass_cpi_max": self.pass_cpi_max,
            "borderline_roas_min": self.borderline_roas_min,
            "winner_action": self.winner_action.value,
            "winner_budget_multiplier": self.winner_budget_multiplier,
            "winner_max_budget": self.winner_max_budget,
            "loser_action": self.loser_action.value,
            "borderline_action": self.borderline_action.value,
            "borderline_extend_days": self.borderline_extend_days,
            "reduce_ratio": self.reduce_ratio,
            "creative_type": self.creative_type,
            "maturity": self.maturity.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestProtocol:
        return cls(
            test_objective=TestObjective(data.get("test_objective", "AEO_IAP")),
            test_budget=float(data.get("test_budget", 50.0)),
            test_duration_days=int(data.get("test_duration_days", 5)),
            min_installs=int(data.get("min_installs", 30)),
            min_spend=float(data.get("min_spend", 100.0)),
            pass_roas_d7_min=float(data.get("pass_roas_d7_min", 0.8)),
            pass_cpi_max=float(data.get("pass_cpi_max", 5.0)),
            borderline_roas_min=float(data.get("borderline_roas_min", 0.4)),
            winner_action=TestDecision(data.get("winner_action", "SCALE")),
            winner_budget_multiplier=float(data.get("winner_budget_multiplier", 2.0)),
            winner_max_budget=float(data.get("winner_max_budget", 500.0)),
            loser_action=TestDecision(data.get("loser_action", "KILL")),
            borderline_action=TestDecision(data.get("borderline_action", "EXTEND")),
            borderline_extend_days=int(data.get("borderline_extend_days", 3)),
            reduce_ratio=float(data.get("reduce_ratio", 0.5)),
            creative_type=str(data.get("creative_type", "image")),
            maturity=CreativeMaturity(data.get("maturity", "NEW")),
        )


@dataclass
class TestRecord:
    """测试记录，追踪一次测试的运行状态。

    与 TestProtocol 配合使用，记录实际测试进度和结果。
    """

    record_id: str = ""
    creative_asset_id: str = ""
    protocol: TestProtocol = field(default_factory=TestProtocol)

    # ── 测试状态 ────────────────────────────────────────
    status: str = "CREATED"      # CREATED → RUNNING → JUDGING → PASSED/FAILED/BORDERLINE
    result: TestResult = TestResult.INSUFFICIENT_DATA
    decision: TestDecision = TestDecision.KEEP

    # ── 时间追踪 ────────────────────────────────────────
    started_at: str = ""
    ended_at: str = ""
    judged_at: str = ""
    days_elapsed: int = 0

    # ── 实际数据 ────────────────────────────────────────
    actual_spend: float = 0.0
    actual_installs: int = 0
    actual_roas_d7: float = 0.0
    actual_cpi: float = 0.0

    # ── 扩展追踪 ────────────────────────────────────────
    extend_count: int = 0       # 延长次数
    max_extends: int = 2        # 最多延长次数

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "creative_asset_id": self.creative_asset_id,
            "protocol": self.protocol.to_dict(),
            "status": self.status,
            "result": self.result.value,
            "decision": self.decision.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "judged_at": self.judged_at,
            "days_elapsed": self.days_elapsed,
            "actual_spend": self.actual_spend,
            "actual_installs": self.actual_installs,
            "actual_roas_d7": self.actual_roas_d7,
            "actual_cpi": self.actual_cpi,
            "extend_count": self.extend_count,
            "max_extends": self.max_extends,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestRecord:
        return cls(
            record_id=data.get("record_id", ""),
            creative_asset_id=data.get("creative_asset_id", ""),
            protocol=TestProtocol.from_dict(data.get("protocol", {})),
            status=data.get("status", "CREATED"),
            result=TestResult(data.get("result", "INSUFFICIENT_DATA")),
            decision=TestDecision(data.get("decision", "KEEP")),
            started_at=data.get("started_at", ""),
            ended_at=data.get("ended_at", ""),
            judged_at=data.get("judged_at", ""),
            days_elapsed=int(data.get("days_elapsed", 0)),
            actual_spend=float(data.get("actual_spend", 0.0)),
            actual_installs=int(data.get("actual_installs", 0)),
            actual_roas_d7=float(data.get("actual_roas_d7", 0.0)),
            actual_cpi=float(data.get("actual_cpi", 0.0)),
            extend_count=int(data.get("extend_count", 0)),
            max_extends=int(data.get("max_extends", 2)),
        )


# ═══════════════════════════════════════════════════════════
# 预定义协议模板
# ═══════════════════════════════════════════════════════════

DEFAULT_PROTOCOLS: dict[str, TestProtocol] = {
    # 图片 - 新方向
    "image_new": TestProtocol(
        creative_type="image",
        maturity=CreativeMaturity.NEW,
        test_objective=TestObjective.AEO_IAP,
        test_budget=50.0,
        test_duration_days=5,
        min_installs=50,
        min_spend=100.0,
        pass_roas_d7_min=0.6,
        pass_cpi_max=5.0,
        borderline_roas_min=0.3,
        winner_budget_multiplier=2.0,
        winner_max_budget=300.0,
        borderline_extend_days=3,
    ),
    # 图片 - Winner 变体
    "image_variant": TestProtocol(
        creative_type="image",
        maturity=CreativeMaturity.VARIANT,
        test_objective=TestObjective.AEO_IAP,
        test_budget=50.0,
        test_duration_days=3,
        min_installs=30,
        min_spend=80.0,
        pass_roas_d7_min=0.8,
        pass_cpi_max=4.0,
        borderline_roas_min=0.5,
        winner_budget_multiplier=3.0,
        winner_max_budget=500.0,
        borderline_extend_days=3,
    ),
    # 视频 - 新方向
    "video_new": TestProtocol(
        creative_type="video",
        maturity=CreativeMaturity.NEW,
        test_objective=TestObjective.AEO_IAP,
        test_budget=80.0,
        test_duration_days=7,
        min_installs=70,
        min_spend=200.0,
        pass_roas_d7_min=0.6,
        pass_cpi_max=6.0,
        borderline_roas_min=0.3,
        winner_budget_multiplier=2.0,
        winner_max_budget=400.0,
        borderline_extend_days=5,
    ),
    # 视频 - Winner 变体
    "video_variant": TestProtocol(
        creative_type="video",
        maturity=CreativeMaturity.VARIANT,
        test_objective=TestObjective.AEO_IAP,
        test_budget=80.0,
        test_duration_days=5,
        min_installs=50,
        min_spend=150.0,
        pass_roas_d7_min=0.8,
        pass_cpi_max=5.0,
        borderline_roas_min=0.5,
        winner_budget_multiplier=3.0,
        winner_max_budget=600.0,
        borderline_extend_days=3,
    ),
    # 放量阶段 ROAS
    "scale_roas": TestProtocol(
        creative_type="image",
        maturity=CreativeMaturity.LEGACY,
        test_objective=TestObjective.AEO_ROAS,
        test_budget=200.0,
        test_duration_days=14,
        min_installs=100,
        min_spend=500.0,
        pass_roas_d7_min=1.0,
        pass_cpi_max=8.0,
        borderline_roas_min=0.7,
        winner_budget_multiplier=1.5,
        winner_max_budget=1000.0,
        borderline_extend_days=7,
    ),
}


def build_protocol(
    creative_type: str = "image",
    maturity: CreativeMaturity = CreativeMaturity.NEW,
) -> TestProtocol:
    """根据素材类型和成熟度构建 TestProtocol。

    Args:
        creative_type: "image" | "video"
        maturity: NEW | VARIANT | LEGACY

    Returns:
        对应的 TestProtocol 实例
    """
    # LEGACY 统一使用 scale_roas 协议
    if maturity == CreativeMaturity.LEGACY:
        return DEFAULT_PROTOCOLS["scale_roas"]

    key = f"{creative_type}_{maturity.value.lower()}"
    if key in DEFAULT_PROTOCOLS:
        return DEFAULT_PROTOCOLS[key]

    # 回退到默认
    return DEFAULT_PROTOCOLS["image_new"]