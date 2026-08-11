"""E11 Phase 4.1 — IAP Creative Intelligence Analysis Core Layer（IAP 版）。

分析素材的 Creative DNA，回答：
  > 为什么这个 Creative 能带来 IAP 用户？

不是分析 CTR，不是分析下载，而是：
  > 什么视觉、玩法展示、情绪、价值表达，让用户下载后愿意付费？

升级到 IAP 版：
  Creative DNA → Player Cohort → Payment → LTV 因果链

模块结构（创意分析层）：
  models.py                  — 4 维分析 + 8 个 IAP 价值层模型
  visual_analyzer.py         — 视觉分析（composition/color/emotion/quality）
  hook_analyzer.py           — Hook 分析（hook_type/strength/purchase_intent）
  gameplay_analyzer.py       — 玩法分析（progression/economy/retention）
  monetization_analyzer.py   — 变现分析（purchase_trigger/iap_visibility/value_perception/urgency）
  creative_dna_extractor.py  — CreativeDNA V2 提取（分析→生产规则）
  analysis_engine.py         — 统一分析引擎
  validator.py               — 分析质量验证

模块结构（IAP 价值层 — Phase 4.1 新增）：
  creative_performance_analyzer.py  — 广告层表现分析（CTR/CPI/ROAS）
  player_attribution_analyzer.py    — Creative → Player Cohort 归因
  archetype_analysis.py             — Creative → Player Archetype 预测+校正
  payment_behavior_analyzer.py      — Creative → Payment Pattern 付费触发
  ltv_correlation_engine.py         — DNA → LTV 相关性引擎
  iap_fitness_engine.py             — IAP 综合价值评分（替代 ROAS Winner）
  creative_dna_evolution.py         — 下一代 DNA 进化方向
  analysis_orchestrator.py          — 编排器 + 端到端测试

模块结构（因果智能层 — Phase 4.2 新增）：
  player_journey_analyzer.py        — Creative → Player Journey 完整行为轨迹
  dna_causal_discovery.py           — DNA → Player Behavior → Revenue 因果发现
  evolution_policy_generator.py     — 进化策略生成器（连接 V5 Mutation Engine）
  models.py (Phase 4.2)             — PlayerJourneyProfile, GeneImpact, MutationPolicy,
                                      CreativeHypothesis, PsychologyGene, AudienceGene,
                                      ContextGene, CreativeDNAV2
"""

# ── 创意分析层（现有）───────────────────────────────────────
from .models import (
    VisualFeatures,
    HookFeatures,
    GameplayFeatures,
    MonetizationFeatures,
    CreativeAnalysis,
    HookType,
    VisualSubject,
    ColorStyle,
    Composition,
    ColorProfile,
    EmotionProfile,
    QualityProfile,
    ProgressionProfile,
    EconomyProfile,
    RetentionSignal,
    PurchaseTrigger,
    # IAP 价值层
    PerformanceMetrics,
    PlayerAttributionProfile,
    ArchetypeProfile,
    PaymentProfile,
    LTVProfile,
    CreativeValueProfile,
    IAPFitnessResult,
    CreativeEvolutionDirection,
    # Phase 4.2 因果智能层
    PlayerJourneyProfile,
    GeneImpact,
    CausalDiscoveryResult,
    CreativeHypothesis,
    MutationPolicy,
    PsychologyGene,
    AudienceGene,
    ContextGene,
    CreativeDNAV2,
)
from .visual_analyzer import VisualAnalyzer
from .hook_analyzer import HookAnalyzer
from .gameplay_analyzer import GameplayAnalyzer
from .monetization_analyzer import MonetizationAnalyzer
from .creative_dna_extractor import CreativeDNAExtractor, CreativeDNA
from .analysis_engine import AnalysisEngine, AnalysisReport, ANALYSIS_WEIGHTS
from .validator import Validator, ValidationReport

# ── IAP 价值层（新增）───────────────────────────────────────
from .creative_performance_analyzer import CreativePerformanceAnalyzer
from .player_attribution_analyzer import PlayerAttributionAnalyzer
from .archetype_analysis import ArchetypeAnalyzer
from .payment_behavior_analyzer import PaymentBehaviorAnalyzer
from .ltv_correlation_engine import LTVCorelationEngine
from .iap_fitness_engine import IAPFitnessEngine
from .creative_dna_evolution import CreativeDNAEvolutionEngine
from .analysis_orchestrator import AnalysisOrchestrator, run_analysis

# ── 因果智能层（Phase 4.2 新增）──────────────────────────────
from .player_journey_analyzer import PlayerJourneyAnalyzer
from .dna_causal_discovery import DNACausalDiscoveryEngine
from .evolution_policy_generator import EvolutionPolicyGenerator

__all__ = [
    # ── 创意分析层 Models ──
    "VisualFeatures", "HookFeatures", "GameplayFeatures", "MonetizationFeatures",
    "CreativeAnalysis", "HookType", "VisualSubject", "ColorStyle",
    "Composition", "ColorProfile", "EmotionProfile", "QualityProfile",
    "ProgressionProfile", "EconomyProfile", "RetentionSignal", "PurchaseTrigger",
    # ── IAP 价值层 Models ──
    "PerformanceMetrics", "PlayerAttributionProfile", "ArchetypeProfile",
    "PaymentProfile", "LTVProfile", "CreativeValueProfile",
    "IAPFitnessResult", "CreativeEvolutionDirection",
    # ── 创意分析层 Analyzers ──
    "VisualAnalyzer", "HookAnalyzer", "GameplayAnalyzer", "MonetizationAnalyzer",
    "CreativeDNAExtractor", "CreativeDNA",
    "AnalysisEngine", "AnalysisReport", "ANALYSIS_WEIGHTS",
    "Validator", "ValidationReport",
    # ── IAP 价值层 Analyzers ──
    "CreativePerformanceAnalyzer", "PlayerAttributionAnalyzer",
    "ArchetypeAnalyzer", "PaymentBehaviorAnalyzer",
    "LTVCorelationEngine", "IAPFitnessEngine",
    "CreativeDNAEvolutionEngine", "AnalysisOrchestrator",
    "run_analysis",
    # ── 因果智能层（Phase 4.2）Models ──
    "PlayerJourneyProfile", "GeneImpact", "CausalDiscoveryResult",
    "CreativeHypothesis", "MutationPolicy", "PsychologyGene",
    "AudienceGene", "ContextGene", "CreativeDNAV2",
    # ── 因果智能层（Phase 4.2）Analyzers ──
    "PlayerJourneyAnalyzer", "DNACausalDiscoveryEngine",
    "EvolutionPolicyGenerator",
]