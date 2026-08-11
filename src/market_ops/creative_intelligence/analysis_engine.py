"""E11 Phase 4.1 — Analysis Engine（IAP 版）。

统一分析入口，串联整个分析管线：

    CreativeEntity
          │
          ├── VisualAnalyzer          → VisualFeatures
          ├── HookAnalyzer            → HookFeatures
          ├── GameplayAnalyzer        → GameplayFeatures
          ├── MonetizationAnalyzer    → MonetizationFeatures
          └── CreativeDNAExtractor    → CreativeDNA
          │
          ▼
    CreativeAnalysis

同时计算 Performance Correlation：
  连接 Phase 2.5 的 Test Protocol 数据，
  判断分析维度与 ROAS 的关联度。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import (
    CreativeAnalysis,
    VisualFeatures,
    HookFeatures,
    GameplayFeatures,
    MonetizationFeatures,
)
from .visual_analyzer import VisualAnalyzer
from .hook_analyzer import HookAnalyzer
from .gameplay_analyzer import GameplayAnalyzer
from .monetization_analyzer import MonetizationAnalyzer
from .creative_dna_extractor import CreativeDNAExtractor, CreativeDNA


# 综合评分权重
ANALYSIS_WEIGHTS: dict[str, float] = {
    "monetization": 0.35,    # 变现展示（最重要）
    "hook": 0.25,            # Hook 质量
    "gameplay": 0.20,        # 玩法展示
    "visual": 0.20,          # 视觉
}


@dataclass
class AnalysisReport:
    """批量分析报告。"""
    total_analyzed: int = 0
    winner_count: int = 0
    iap_quality_count: int = 0
    clickbait_count: int = 0
    winner_rate: float = 0.0
    avg_analysis_score: float = 0.0
    analyses: list[CreativeAnalysis] = field(default_factory=list)
    dna_list: list[CreativeDNA] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_analyzed": self.total_analyzed,
            "winner_count": self.winner_count,
            "iap_quality_count": self.iap_quality_count,
            "clickbait_count": self.clickbait_count,
            "winner_rate": self.winner_rate,
            "avg_analysis_score": self.avg_analysis_score,
            "analyses": [a.to_dict() for a in self.analyses],
            "dna_list": [d.to_dict() for d in self.dna_list],
            "errors": self.errors,
        }

    def to_summary(self) -> str:
        lines = [
            "=" * 60,
            "  Creative Analysis Report",
            "=" * 60,
            f"  Total Analyzed:     {self.total_analyzed}",
            f"  Winners:            {self.winner_count}",
            f"  IAP Quality:        {self.iap_quality_count}",
            f"  Clickbait Detected: {self.clickbait_count}",
            f"  Winner Rate:        {self.winner_rate:.1%}",
            f"  Avg Analysis Score: {self.avg_analysis_score:.1f}",
            "=" * 60,
        ]
        return "\n".join(lines)


class AnalysisEngine:
    """创意分析引擎。

    统一入口，串联所有分析器，输出 CreativeAnalysis + CreativeDNA。
    """

    def __init__(self):
        self.visual_analyzer = VisualAnalyzer()
        self.hook_analyzer = HookAnalyzer()
        self.gameplay_analyzer = GameplayAnalyzer()
        self.monetization_analyzer = MonetizationAnalyzer()
        self.dna_extractor = CreativeDNAExtractor()

    def analyze(self, entity) -> CreativeAnalysis:
        """分析单个 CreativeEntity。

        Args:
            entity: CreativeEntity 实例

        Returns:
            CreativeAnalysis: 分析结果
        """
        creative_id = getattr(entity, "creative_asset_id", "UNKNOWN")

        # Step 1: 视觉分析
        visual = self.visual_analyzer.analyze(entity)

        # Step 2: Hook 分析
        hook = self.hook_analyzer.analyze(entity)

        # Step 3: 玩法分析
        gameplay = self.gameplay_analyzer.analyze(entity)

        # Step 4: 变现分析
        monetization = self.monetization_analyzer.analyze(entity, hook_features=hook)

        # Step 5: 综合评分
        analysis_score = self._compute_score(visual, hook, gameplay, monetization)

        # Step 6: AI 洞察
        insight = self._generate_insight(visual, hook, gameplay, monetization)

        return CreativeAnalysis(
            creative_id=creative_id,
            visual_features=visual,
            hook_features=hook,
            gameplay_features=gameplay,
            monetization_features=monetization,
            analysis_score=analysis_score,
            insight=insight,
        )

    def analyze_batch(self, entities: list) -> AnalysisReport:
        """批量分析。"""
        analyses: list[CreativeAnalysis] = []
        dna_list: list[CreativeDNA] = []
        errors: list[dict] = []

        for entity in entities:
            try:
                analysis = self.analyze(entity)
                analyses.append(analysis)

                # 提取 DNA（带 ROAS 数据）
                roas = self._get_roas(entity)
                dna = self.dna_extractor.extract(analysis, roas_d30=roas)
                dna_list.append(dna)
            except Exception as e:
                cid = getattr(entity, "creative_asset_id", "UNKNOWN")
                errors.append({"creative_id": cid, "error": str(e)})

        total = len(analyses)
        winner_count = sum(1 for a in analyses if a.is_winner)
        iap_quality_count = sum(1 for a in analyses if a.is_iap_quality)
        clickbait_count = sum(1 for a in analyses if a.hook_features.is_clickbait)
        avg_score = sum(a.analysis_score for a in analyses) / max(total, 1)

        return AnalysisReport(
            total_analyzed=total,
            winner_count=winner_count,
            iap_quality_count=iap_quality_count,
            clickbait_count=clickbait_count,
            winner_rate=winner_count / max(total, 1),
            avg_analysis_score=round(avg_score, 1),
            analyses=analyses,
            dna_list=dna_list,
            errors=errors,
        )

    # ── 综合评分 ──────────────────────────────────────────

    def _compute_score(
        self, v: VisualFeatures, h: HookFeatures,
        g: GameplayFeatures, m: MonetizationFeatures,
    ) -> float:
        """计算综合分析评分 (0-100)。

        权重：monetization(0.35) + hook(0.25) + gameplay(0.20) + visual(0.20)
        """
        return round(
            m.monetization_score * ANALYSIS_WEIGHTS["monetization"]
            + h.hook_score * ANALYSIS_WEIGHTS["hook"]
            + g.gameplay_score * ANALYSIS_WEIGHTS["gameplay"]
            + v.visual_score * ANALYSIS_WEIGHTS["visual"],
            1,
        )

    # ── ROAS ─────────────────────────────────────────────

    def _get_roas(self, entity) -> float | None:
        performance = getattr(entity, "performance", None)
        if not performance:
            return None
        revenue = getattr(performance, "revenue", None)
        acquisition = getattr(performance, "acquisition", None)
        if not revenue or not acquisition:
            return None
        spend = getattr(acquisition, "spend", 0) or 0
        iap_d30 = getattr(revenue, "iap_d30", 0) or 0
        if spend <= 0:
            return None
        return iap_d30 / spend

    # ── AI 洞察 ──────────────────────────────────────────

    def _generate_insight(
        self, v: VisualFeatures, h: HookFeatures,
        g: GameplayFeatures, m: MonetizationFeatures,
    ) -> str:
        """生成 AI 洞察。"""
        parts: list[str] = []

        # Hook 洞察
        if h.is_clickbait:
            parts.append("Clickbait hook detected: high curiosity but low purchase intent")
        elif h.is_iap_quality:
            parts.append(f"Quality IAP hook: {h.hook_type.value} with strong purchase intent")

        # 变现洞察
        if m.is_high_monetization:
            trigger = m.purchase_trigger.dominant_trigger
            parts.append(f"High monetization: {trigger}-driven purchase trigger")

        # 玩法洞察
        if g.gameplay_score >= 60:
            parts.append("Strong gameplay showcase with clear progression and economy")

        # 视觉洞察
        if v.emotion.desire >= 70:
            parts.append(f"High desire emotion: {v.emotion.dominant_emotion}-driven")

        # 综合
        if not parts:
            parts.append("Moderate creative performance with limited IAP signals")

        return " | ".join(parts)