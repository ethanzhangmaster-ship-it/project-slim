"""Meta Ads 数据拉取器 — 为 Workspace GrowthLoop 触发提供真实数据.

复用 scripts/run_growth_loop.py 和 scripts/run_feedback_bridge.py 中的现有函数,
不重造轮子. 作为薄层包装, 将数据拉取 → 聚合 → signals 生成 封装为统一接口.

流程:
  1. 检查 META_ACCESS_TOKEN / META_AD_ACCOUNT_ID 环境变量
  2. 调用 load_meta_ads_data() 拉取当前周期 + 上一周期数据
  3. 调用 aggregate_by_creative() 聚合指标
  4. 调用 build_creative_to_adset_map() 和 estimate_current_budgets()
  5. 调用 generate_predictions() → FeedbackController → filter_actionable_signals()
  6. 返回 GrowthLoopInput (signals + metrics + maps)

使用方式:
    fetcher = MetaAdsDataFetcher()
    if fetcher.is_configured():
        data = fetcher.fetch(days=7)
        result = orchestrator.run_cycle(
            signals=data.signals,
            current_metrics=data.current_metrics,
            ...
        )
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 确保 scripts 目录在 path 中
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


@dataclass
class GrowthLoopInput:
    """GrowthLoop run_cycle 所需的完整输入数据."""

    signals: list[Any] = field(default_factory=list)
    current_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    previous_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    creative_to_adset_map: dict[str, str] = field(default_factory=dict)
    current_budgets: dict[str, float] = field(default_factory=dict)
    reality_scores: dict[str, Any] = field(default_factory=dict)
    game_id_resolver: Any = None
    # 元信息
    creative_count: int = 0
    prediction_count: int = 0
    fetch_error: str | None = None


class MetaAdsDataFetcher:
    """Meta Ads 真实数据拉取器.

    复用 run_growth_loop.py 中的函数, 封装为 Workspace 可调用的接口.
    需要环境变量: META_ACCESS_TOKEN, META_AD_ACCOUNT_ID
    """

    def __init__(
        self,
        access_token: str | None = None,
        ad_account_id: str | None = None,
        api_version: str | None = None,
        game_name: str | None = None,
    ) -> None:
        self.access_token = access_token or os.getenv("META_ACCESS_TOKEN", "")
        self.ad_account_id = ad_account_id or os.getenv("META_AD_ACCOUNT_ID", "")
        self.api_version = api_version or os.getenv("META_API_VERSION", "v22.0")
        self.game_name = game_name or os.getenv("DEFAULT_GAME_NAME", "P04")

    def is_configured(self) -> bool:
        """检查是否配置了 Meta Ads 凭据."""
        return bool(self.access_token and self.ad_account_id)

    def fetch(self, days: int = 7) -> GrowthLoopInput:
        """拉取 Meta Ads 数据并转换为 GrowthLoop 输入.

        Args:
            days: 数据拉取天数 (当前周期)

        Returns:
            GrowthLoopInput 包含 signals, metrics, maps 等
        """
        if not self.is_configured():
            return GrowthLoopInput(
                fetch_error="META_ACCESS_TOKEN 或 META_AD_ACCOUNT_ID 未配置"
            )

        try:
            return self._do_fetch(days)
        except Exception as exc:
            logger.exception("Meta Ads data fetch failed")
            return GrowthLoopInput(fetch_error=str(exc))

    def _do_fetch(self, days: int) -> GrowthLoopInput:
        """执行实际的数据拉取和转换."""
        # 延迟导入 (仅在真正需要时加载)
        from run_growth_loop import (
            build_creative_to_adset_map,
            estimate_current_budgets,
            filter_actionable_signals,
            load_meta_ads_data,
            make_game_id_resolver,
            run_reality_audit,
        )
        from run_feedback_bridge import (
            aggregate_by_creative,
            generate_predictions,
            MemoryEnricher,
        )
        from market_ops.creative_vision_runtime.reality.feedback import (
            FeedbackController,
        )
        from market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
            ExperienceStore,
        )

        logger.info("Fetching Meta Ads data (days=%d)...", days)

        # Step 1: 拉取 Meta Ads 数据
        current_rows, previous_rows = load_meta_ads_data(
            self.access_token,
            self.ad_account_id,
            self.api_version,
            self.game_name,
            days,
        )
        logger.info("Fetched %d current rows, %d previous rows",
                    len(current_rows), len(previous_rows))

        if not current_rows:
            return GrowthLoopInput(
                fetch_error="当前周期无数据 (Meta Ads 返回空)"
            )

        # Step 2: 聚合指标
        current_metrics = aggregate_by_creative(current_rows)
        previous_metrics = aggregate_by_creative(previous_rows)

        # Step 3: 构建映射
        creative_to_adset_map = build_creative_to_adset_map(current_rows)
        current_budgets = estimate_current_budgets(current_metrics, days)

        # Step 4: 生成预测 + FeedbackController
        store = ExperienceStore()
        enricher = MemoryEnricher(store)
        predictions = generate_predictions(
            current_metrics, previous_metrics, enricher=enricher
        )
        controller = FeedbackController()
        feedback = controller.evaluate(predictions)
        signals = filter_actionable_signals(feedback, current_metrics)

        logger.info("Generated %d predictions, %d signals",
                    len(predictions), len(signals))

        # Step 5: RealityGate 审计
        reality_scores: dict[str, Any] = {}
        game_id_resolver: Any = None
        try:
            reality_scores, creative_to_game = run_reality_audit(
                game_name=self.game_name,
                current_metrics=current_metrics,
                data_dir=str(_PROJECT_ROOT / "data"),
            )
            game_id_resolver = make_game_id_resolver(creative_to_game)
        except Exception as exc:
            logger.warning("RealityGate audit failed: %s", exc)

        return GrowthLoopInput(
            signals=signals,
            current_metrics=current_metrics,
            previous_metrics=previous_metrics,
            creative_to_adset_map=creative_to_adset_map,
            current_budgets=current_budgets,
            reality_scores=reality_scores,
            game_id_resolver=game_id_resolver,
            creative_count=len(current_metrics),
            prediction_count=len(predictions),
        )
