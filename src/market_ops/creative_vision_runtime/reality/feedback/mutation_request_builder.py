"""E12.4 Phase 2 — Mutation Request Builder。

将 RealityFeedbackSignal 转换为 Creative DNA Mutation Request。

流程:
  RealityFeedbackSignal
       │
       ▼
  SIGNAL_TO_INTENT 映射
       │
       ▼
  INTENT_DNA_CONSTRAINTS 填充
       │
       ▼
  INTENT_GENERATION_COUNT 配置
       │
       ▼
  MutationRequest（发送给 Creative DNA Engine）
"""

from __future__ import annotations

from .models import (
    INTENT_DNA_CONSTRAINTS,
    INTENT_GENERATION_COUNT,
    SIGNAL_TO_INTENT,
    MutationIntent,
    MutationRequest,
    RealityFeedbackSignal,
)


class MutationRequestBuilder:
    """突变请求构建器。

    将 RealityFeedbackSignal 转换为 Creative DNA Engine 可执行的
    MutationRequest，包含意图、DNA 约束、生成数量。

    Usage:
        >>> builder = MutationRequestBuilder()
        >>> signal = RealityFeedbackSignal(
        ...     creative_id="c001",
        ...     signal_type=FeedbackSignalType.FATIGUE_WARNING,
        ...     severity=0.85, confidence=0.91,
        ...     reason=["CTR -25%", "Frequency 5.2"],
        ... )
        >>> request = builder.build(signal)
        >>> print(request.intent, request.generation_count)
    """

    def __init__(self) -> None:
        self.total_requests_built: int = 0

    # ── Main API ───────────────────────────────────────────

    def build(self, signal: RealityFeedbackSignal) -> MutationRequest:
        """将单个反馈信号构建为突变请求。

        Args:
            signal: 反馈信号

        Returns:
            MutationRequest（含 DNA 约束和生成数量）
        """
        # 1. 映射 Signal → MutationIntent
        intent = self._resolve_intent(signal)

        # 2. 获取 DNA 约束
        constraints = self._resolve_constraints(intent, signal)

        # 3. 获取建议生成数量
        generation_count = INTENT_GENERATION_COUNT.get(intent, 10)

        # 4. 构建 MutationRequest
        request = MutationRequest(
            creative_id=signal.creative_id,
            intent=intent,
            signal_id=signal.signal_id,
            reason=list(signal.reason),
            confidence=signal.confidence,
            dna_constraints=constraints,
            generation_count=generation_count,
        )

        self.total_requests_built += 1
        return request

    def build_batch(
        self,
        signals: list[RealityFeedbackSignal],
    ) -> list[MutationRequest]:
        """批量构建突变请求。

        Args:
            signals: 反馈信号列表

        Returns:
            MutationRequest 列表（按置信度降序）
        """
        requests = [self.build(s) for s in signals]
        return sorted(requests, key=lambda r: r.confidence, reverse=True)

    def build_with_override(
        self,
        signal: RealityFeedbackSignal,
        intent: MutationIntent | None = None,
        generation_count: int | None = None,
        custom_constraints: dict[str, list[str]] | None = None,
    ) -> MutationRequest:
        """构建突变请求（允许覆盖默认值）。

        Args:
            signal:             反馈信号
            intent:             覆盖默认意图
            generation_count:   覆盖生成数量
            custom_constraints: 覆盖 DNA 约束

        Returns:
            MutationRequest
        """
        if intent is None:
            intent = self._resolve_intent(signal)

        if custom_constraints is not None:
            constraints = dict(custom_constraints)
        else:
            constraints = self._resolve_constraints(intent, signal)

        if generation_count is None:
            generation_count = INTENT_GENERATION_COUNT.get(intent, 10)

        request = MutationRequest(
            creative_id=signal.creative_id,
            intent=intent,
            signal_id=signal.signal_id,
            reason=list(signal.reason),
            confidence=signal.confidence,
            dna_constraints=constraints,
            generation_count=generation_count,
        )

        self.total_requests_built += 1
        return request

    # ── Private helpers ────────────────────────────────────

    @staticmethod
    def _resolve_intent(signal: RealityFeedbackSignal) -> MutationIntent:
        """解析信号对应的突变意图。"""
        return SIGNAL_TO_INTENT.get(
            signal.signal_type,
            MutationIntent.REFRESH_HOOK,
        )

    @staticmethod
    def _resolve_constraints(
        intent: MutationIntent,
        signal: RealityFeedbackSignal,
    ) -> dict[str, list[str]]:
        """解析 DNA 约束。

        将默认约束与信号中的额外信息合并。
        """
        default = INTENT_DNA_CONSTRAINTS.get(intent, {"keep": [], "change": []})
        constraints = {
            "keep": list(default.get("keep", [])),
            "change": list(default.get("change", [])),
        }

        # 从 signal metadata 中提取额外约束
        if signal.metadata:
            extra_keep = signal.metadata.get("dna_keep", [])
            extra_change = signal.metadata.get("dna_change", [])
            if extra_keep:
                constraints["keep"].extend(extra_keep)
            if extra_change:
                constraints["change"].extend(extra_change)

        # 去重
        constraints["keep"] = list(dict.fromkeys(constraints["keep"]))
        constraints["change"] = list(dict.fromkeys(constraints["change"]))

        return constraints

    def __repr__(self) -> str:
        return f"MutationRequestBuilder(built={self.total_requests_built})"