"""E11 Phase 2.5 — Test Protocol Decision Engine。

核心决策引擎，负责：
  1. AEO vs ROAS 决策：根据素材成熟度和数据量选择测试目标
  2. 测试结果判定：根据 ROAS/CPI/安装量判断 PASSED/FAILED/BORDERLINE
  3. 处置决策矩阵：根据结果和成本决定 SCALE/KILL/EXTEND/REDUCE/KEEP

决策原则：
  - AEO 用来"测素材"（积累安装数据）
  - ROAS 用来"放量"（优化收入效率）
  - 测试阶段用 AEO，通过后切换到 ROAS 放量
  - Winner 不放原 Campaign 预算（避免打乱学习），而是新建 ROAS Campaign
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .protocol import (
    TestObjective,
    TestResult,
    TestDecision,
    TestProtocol,
    CreativeMaturity,
)

if TYPE_CHECKING:
    from market_ops.creative_repository import CreativeEntity


@dataclass
class ObjectiveDecision:
    """AEO/ROAS 决策结果。"""

    objective: TestObjective = TestObjective.AEO_IAP
    reason: str = ""
    confidence: float = 0.0     # 0.0 - 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective.value,
            "reason": self.reason,
            "confidence": self.confidence,
        }


@dataclass
class JudgementResult:
    """测试结果判定。"""

    result: TestResult = TestResult.INSUFFICIENT_DATA
    roas_d7: float = 0.0
    cpi: float = 0.0
    installs: int = 0
    spend: float = 0.0
    reason: str = ""
    details: dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "roas_d7": self.roas_d7,
            "cpi": self.cpi,
            "installs": self.installs,
            "spend": self.spend,
            "reason": self.reason,
            "details": self.details,
        }


@dataclass
class DispositionDecision:
    """处置决策。"""

    decision: TestDecision = TestDecision.KEEP
    action: str = ""                 # 具体操作描述
    new_budget: float = 0.0          # 新预算
    new_objective: TestObjective | None = None  # 新测试目标
    should_create_new_campaign: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "action": self.action,
            "new_budget": self.new_budget,
            "new_objective": self.new_objective.value if self.new_objective else None,
            "should_create_new_campaign": self.should_create_new_campaign,
            "reason": self.reason,
        }


class TestProtocolEngine:
    """测试协议决策引擎。

    核心职责：
      1. decide_objective(): 根据素材状态选择 AEO 还是 ROAS
      2. judge():            根据实际数据判断测试结果
      3. decide_disposition(): 根据测试结果给出处置方案

    Usage:
        engine = TestProtocolEngine()
        objective = engine.decide_objective(entity)
        judgement = engine.judge(entity, protocol)
        disposition = engine.decide_disposition(judgement, protocol)
    """

    # ── AEO vs ROAS 决策 ────────────────────────────────

    def decide_objective(
        self,
        entity: CreativeEntity | None = None,
        maturity: CreativeMaturity = CreativeMaturity.NEW,
        has_historical_data: bool = False,
        historical_roas_d7: float = 0.0,
    ) -> ObjectiveDecision:
        """决定使用 AEO_IAP 还是 AEO_ROAS 作为测试目标。

        决策树：
          LEGACY + 有历史数据 + ROAS >= 1.0 → AEO_ROAS（放量）
          VARIANT + 有历史数据 + ROAS >= 0.8 → AEO_ROAS
          其他 → AEO_IAP（测素材）

        Args:
            entity:       CreativeEntity（可选，从 performance 读取数据）
            maturity:     素材成熟度
            has_historical_data: 是否有历史数据
            historical_roas_d7:  历史 D7 ROAS

        Returns:
            ObjectiveDecision
        """
        # 从 entity 读取数据
        if entity is not None and entity.has_performance:
            if entity.has_revenue:
                has_historical_data = True
                historical_roas_d7 = entity.performance.roas_d7

        # LEGACY + 已验证 ROAS → ROAS 放量
        if maturity == CreativeMaturity.LEGACY and has_historical_data:
            if historical_roas_d7 >= 1.0:
                return ObjectiveDecision(
                    objective=TestObjective.AEO_ROAS,
                    reason=f"Legacy creative with ROAS D7={historical_roas_d7:.2f} >= 1.0, ready for ROAS scaling",
                    confidence=0.9,
                )
            elif historical_roas_d7 >= 0.7:
                return ObjectiveDecision(
                    objective=TestObjective.AEO_ROAS,
                    reason=f"Legacy creative with borderline ROAS D7={historical_roas_d7:.2f}, try ROAS cautiously",
                    confidence=0.6,
                )

        # VARIANT + 已验证 ROAS → ROAS
        if maturity == CreativeMaturity.VARIANT and has_historical_data:
            if historical_roas_d7 >= 0.8:
                return ObjectiveDecision(
                    objective=TestObjective.AEO_ROAS,
                    reason=f"Winner variant with ROAS D7={historical_roas_d7:.2f} >= 0.8, switch to ROAS",
                    confidence=0.85,
                )
            elif historical_roas_d7 >= 0.6:
                return ObjectiveDecision(
                    objective=TestObjective.AEO_ROAS,
                    reason=f"Variant with moderate ROAS D7={historical_roas_d7:.2f}, test ROAS",
                    confidence=0.55,
                )

        # 默认：AEO_IAP 测素材
        return ObjectiveDecision(
            objective=TestObjective.AEO_IAP,
            reason=f"New or unverified creative, use AEO_IAP to accumulate install data (maturity={maturity.value})",
            confidence=0.95,
        )

    # ── 测试结果判定 ─────────────────────────────────────

    def judge(
        self,
        entity: CreativeEntity | None = None,
        protocol: TestProtocol | None = None,
        *,
        roas_d7: float | None = None,
        cpi: float | None = None,
        installs: int | None = None,
        spend: float | None = None,
        days_elapsed: int | None = None,
    ) -> JudgementResult:
        """根据实际数据判断测试结果。

        判定逻辑：
          1. 数据不足 (installs < min_installs 或 spend < min_spend) → INSUFFICIENT_DATA
          2. ROAS >= pass_roas_d7 且 CPI <= pass_cpi_max → PASSED
          3. ROAS < borderline_roas_min → FAILED
          4. 其他 → BORDERLINE

        Args:
            entity:   CreativeEntity（从 performance 读取数据）
            protocol: TestProtocol（判定标准）
            roas_d7:  手动指定 D7 ROAS（覆盖 entity）
            cpi:      手动指定 CPI
            installs: 手动指定安装数
            spend:    手动指定花费
            days_elapsed: 已测试天数

        Returns:
            JudgementResult
        """
        if protocol is None:
            protocol = TestProtocol()

        # 从 entity 读取数据
        if entity is not None:
            if roas_d7 is None:
                roas_d7 = entity.performance.roas_d7
            if cpi is None:
                cpi = entity.performance.cpi
            if installs is None:
                installs = entity.performance.acquisition.installs
            if spend is None:
                spend = entity.performance.acquisition.spend

        roas_d7 = roas_d7 or 0.0
        cpi = cpi or 0.0
        installs = installs or 0
        spend = spend or 0.0

        # 1. 数据不足检查
        if installs < protocol.min_installs:
            return JudgementResult(
                result=TestResult.INSUFFICIENT_DATA,
                roas_d7=roas_d7,
                cpi=cpi,
                installs=installs,
                spend=spend,
                reason=f"Installs ({installs}) < minimum ({protocol.min_installs}), need more data",
                details={"deficit": protocol.min_installs - installs},
            )

        if spend < protocol.min_spend:
            return JudgementResult(
                result=TestResult.INSUFFICIENT_DATA,
                roas_d7=roas_d7,
                cpi=cpi,
                installs=installs,
                spend=spend,
                reason=f"Spend (${spend:.0f}) < minimum (${protocol.min_spend:.0f}), need more data",
                details={"deficit": round(protocol.min_spend - spend, 2)},
            )

        # 2. 通过判定
        if roas_d7 >= protocol.pass_roas_d7_min and cpi <= protocol.pass_cpi_max:
            return JudgementResult(
                result=TestResult.PASSED,
                roas_d7=roas_d7,
                cpi=cpi,
                installs=installs,
                spend=spend,
                reason=f"ROAS D7={roas_d7:.2f} >= {protocol.pass_roas_d7_min} AND CPI=${cpi:.2f} <= ${protocol.pass_cpi_max}",
                details={"roas_margin": round(roas_d7 - protocol.pass_roas_d7_min, 4)},
            )

        # 3. ROAS 达标但 CPI 不达标 → BORDERLINE
        if roas_d7 >= protocol.pass_roas_d7_min and cpi > protocol.pass_cpi_max:
            return JudgementResult(
                result=TestResult.BORDERLINE,
                roas_d7=roas_d7,
                cpi=cpi,
                installs=installs,
                spend=spend,
                reason=f"ROAS OK ({roas_d7:.2f}) but CPI too high (${cpi:.2f} > ${protocol.pass_cpi_max})",
                details={"cpi_excess": round(cpi - protocol.pass_cpi_max, 2)},
            )

        # 4. 失败判定
        if roas_d7 < protocol.borderline_roas_min:
            return JudgementResult(
                result=TestResult.FAILED,
                roas_d7=roas_d7,
                cpi=cpi,
                installs=installs,
                spend=spend,
                reason=f"ROAS D7={roas_d7:.2f} < borderline ({protocol.borderline_roas_min})",
                details={"roas_deficit": round(protocol.borderline_roas_min - roas_d7, 4)},
            )

        # 5. 边缘判定
        return JudgementResult(
            result=TestResult.BORDERLINE,
            roas_d7=roas_d7,
            cpi=cpi,
            installs=installs,
            spend=spend,
            reason=f"ROAS D7={roas_d7:.2f} between borderline ({protocol.borderline_roas_min}) and pass ({protocol.pass_roas_d7_min})",
            details={"roas_gap": round(protocol.pass_roas_d7_min - roas_d7, 4)},
        )

    # ── 处置决策矩阵 ─────────────────────────────────────

    def decide_disposition(
        self,
        judgement: JudgementResult,
        protocol: TestProtocol,
        *,
        extend_count: int = 0,
        max_extends: int = 2,
    ) -> DispositionDecision:
        """根据测试结果给出处置方案。

        处置矩阵：
          PASSED:
            - ROAS >= 1.2 且 CPI <= $3  → SCALE (3x)
            - ROAS 0.8-1.2 或 CPI $3-5 → SCALE (1.5x-2x)
            - 其他（理论上不会到这里）      → SCALE (1.5x)
          FAILED:
            - CPI > $8 或 ROAS < 0.2    → KILL
            - 其他                        → REDUCE
          BORDERLINE:
            - extend_count < max_extends → EXTEND
            - 否则                        → REDUCE
          INSUFFICIENT_DATA:
            - 未到测试周期                 → KEEP
            - 已到测试周期                 → EXTEND (继续观察)

        Args:
            judgement:     测试结果判定
            protocol:      测试协议
            extend_count:  已延长次数
            max_extends:   最多延长次数

        Returns:
            DispositionDecision
        """
        result = judgement.result

        # ── PASSED → SCALE ──
        if result == TestResult.PASSED:
            return self._disposition_passed(judgement, protocol)

        # ── FAILED → KILL / REDUCE ──
        if result == TestResult.FAILED:
            return self._disposition_failed(judgement, protocol)

        # ── BORDERLINE → EXTEND / REDUCE ──
        if result == TestResult.BORDERLINE:
            return self._disposition_borderline(judgement, protocol, extend_count, max_extends)

        # ── INSUFFICIENT_DATA → KEEP / EXTEND ──
        return self._disposition_insufficient(judgement, protocol)

    def _disposition_passed(
        self,
        judgement: JudgementResult,
        protocol: TestProtocol,
    ) -> DispositionDecision:
        """通过 → 放量。"""
        roas = judgement.roas_d7
        cpi = judgement.cpi

        # 强 Winner：ROAS >= 1.2 且 CPI <= $3 → 3x
        if roas >= 1.2 and cpi <= 3.0:
            multiplier = 3.0
            new_budget = min(protocol.test_budget * multiplier, protocol.winner_max_budget)
            return DispositionDecision(
                decision=TestDecision.SCALE,
                action=f"Strong winner: ROAS={roas:.2f}, CPI=${cpi:.2f}. Scale to ${new_budget:.0f}/day",
                new_budget=new_budget,
                new_objective=TestObjective.AEO_ROAS,
                should_create_new_campaign=True,
                reason="High ROAS + low CPI → create new ROAS campaign at 3x budget",
            )

        # 中等 Winner：ROAS >= 0.8 或 CPI <= $5 → 2x
        multiplier = protocol.winner_budget_multiplier
        new_budget = min(protocol.test_budget * multiplier, protocol.winner_max_budget)
        return DispositionDecision(
            decision=TestDecision.SCALE,
            action=f"Winner: ROAS={roas:.2f}, CPI=${cpi:.2f}. Scale to ${new_budget:.0f}/day",
            new_budget=new_budget,
            new_objective=TestObjective.AEO_ROAS,
            should_create_new_campaign=True,
            reason="Passed test → create new ROAS campaign at standard multiplier",
        )

    def _disposition_failed(
        self,
        judgement: JudgementResult,
        protocol: TestProtocol,
    ) -> DispositionDecision:
        """失败 → 关闭或缩减。"""
        roas = judgement.roas_d7
        cpi = judgement.cpi

        # 明确失败：CPI > $8 或 ROAS < 0.2 → KILL
        if cpi > 8.0 or roas < 0.2:
            return DispositionDecision(
                decision=TestDecision.KILL,
                action=f"Kill: ROAS={roas:.2f}, CPI=${cpi:.2f}. Pause ad immediately",
                new_budget=0.0,
                reason="Clear failure: ROAS too low or CPI too high",
            )

        # 可疑失败 → REDUCE 50%
        new_budget = protocol.test_budget * protocol.reduce_ratio
        return DispositionDecision(
            decision=TestDecision.REDUCE,
            action=f"Reduce budget to ${new_budget:.0f}/day and observe",
            new_budget=new_budget,
            reason=f"Borderline failure: ROAS={roas:.2f}, CPI=${cpi:.2f}. Reduce to see if improves",
        )

    def _disposition_borderline(
        self,
        judgement: JudgementResult,
        protocol: TestProtocol,
        extend_count: int,
        max_extends: int,
    ) -> DispositionDecision:
        """边缘 → 延长或缩减。"""
        if extend_count < max_extends:
            return DispositionDecision(
                decision=TestDecision.EXTEND,
                action=f"Extend test by {protocol.borderline_extend_days} days (extend #{extend_count + 1}/{max_extends})",
                new_budget=protocol.test_budget,
                reason=f"Borderline ROAS={judgement.roas_d7:.2f}, need more data to decide",
            )

        # 已延长多次 → 缩减
        new_budget = protocol.test_budget * protocol.reduce_ratio
        return DispositionDecision(
            decision=TestDecision.REDUCE,
            action=f"Max extends reached ({extend_count}/{max_extends}), reduce budget to ${new_budget:.0f}/day",
            new_budget=new_budget,
            reason=f"Borderline after {extend_count} extensions, reducing budget",
        )

    def _disposition_insufficient(
        self,
        judgement: JudgementResult,
        protocol: TestProtocol,
    ) -> DispositionDecision:
        """数据不足 → 保持或延长。"""
        return DispositionDecision(
            decision=TestDecision.KEEP,
            action=f"Keep observing: only {judgement.installs} installs / ${judgement.spend:.0f} spend",
            new_budget=protocol.test_budget,
            reason=f"Insufficient data: min installs={protocol.min_installs}, min spend=${protocol.min_spend:.0f}",
        )

    def __repr__(self) -> str:
        return "TestProtocolEngine()"