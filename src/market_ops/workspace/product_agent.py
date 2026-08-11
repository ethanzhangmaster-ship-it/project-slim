"""Product Manager Agent — 把商业机会变成产品方案.

从市场机会（品类/受众/地区）自动生成 PRD（产品需求文档）、GDD（游戏设计文档）、
Feature 优先级排序、Roadmap 规划和 KPI 目标设定，接入 workspace 组织架构。

设计原则（继承 LiveOps Agent 纪律红线）:
  - 复用 v9_company/product_division 和 v8_growth/product_agent 的数据模型，不新增算法层
  - 默认 dry_run：产品方案只生成不执行
  - 产品参数走配置（ProductTemplateConfig），禁止硬编码模板
  - 接入 MessageBus 广播产品事件
  - 执行结果回流 CEO Memory（domain="product"）

依赖注入:
  product_director / feature_strategy / roadmap_engine 可在 __init__ 注入（便于测试），
  默认懒加载 v9_company/product_division 的真实实例。当真实模块不可导入时
  （如纯 workspace 部署），优雅降级到内置模板。
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


@dataclass
class MarketOpportunity:
    """市场机会输入 — Product Agent 的起点."""

    opportunity_id: str = ""
    genre: str = ""                 # Merge / Match3 / Simulation / Casual / Puzzle
    target_audience: str = ""       # 女性30-45 / 男性18-25 / 全年龄
    target_market: str = ""         # US / JP / KR / Global
    platform: str = "mobile"        # mobile / PC / console
    budget_usd: float = 0.0         # 预期开发预算
    timeline_months: int = 6        # 预期开发周期
    competitor_analysis: str = ""   # 竞品分析摘要
    market_size: str = ""           # 市场规模描述

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KPIDefinition:
    """单个 KPI 目标定义."""

    metric: str            # retention_d1 / retention_d30 / roas_d60 / arpu / dau
    target: float          # 目标值
    benchmark: float       # 行业基准
    measurement: str       # 衡量方式描述

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductRequirementDoc:
    """PRD — 产品需求文档.

    把商业机会转化为可执行的产品方案。
    """

    prd_id: str
    title: str                      # 产品名称
    genre: str                      # 品类
    opportunity_id: str             # 关联的市场机会 ID
    vision: str                     # 产品愿景（一句话）
    target_audience: str            # 目标用户
    target_market: str              # 目标市场
    core_gameplay: str              # 核心玩法描述
    meta_loop: str                  # Meta 循环描述
    monetization_model: str         # 变现模式 (IAP / IAA / Hybrid)
    kpi_targets: list[KPIDefinition]  # KPI 目标列表
    key_features: list[str]         # 核心功能列表
    target_dau: int                 # 目标 DAU
    budget_usd: float               # 预算
    timeline_months: int            # 周期
    risk_assessment: str            # 风险评估
    go_no_go: str                   # GO / NO_GO / REVIEW
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prd_id": self.prd_id,
            "title": self.title,
            "genre": self.genre,
            "opportunity_id": self.opportunity_id,
            "vision": self.vision,
            "target_audience": self.target_audience,
            "target_market": self.target_market,
            "core_gameplay": self.core_gameplay,
            "meta_loop": self.meta_loop,
            "monetization_model": self.monetization_model,
            "kpi_targets": [k.to_dict() for k in self.kpi_targets],
            "key_features": self.key_features,
            "target_dau": self.target_dau,
            "budget_usd": round(self.budget_usd, 2),
            "timeline_months": self.timeline_months,
            "risk_assessment": self.risk_assessment,
            "go_no_go": self.go_no_go,
            "created_at": self.created_at,
        }


@dataclass
class GameDesignDocument:
    """GDD — 游戏设计文档.

    从 PRD 细化为可开发的设计方案。
    """

    gdd_id: str
    prd_id: str                     # 关联的 PRD
    game_name: str
    genre: str
    core_loop: list[str]            # 核心循环步骤
    meta_loop: list[str]            # Meta 循环步骤
    mechanics: list[dict[str, Any]] # 机制列表
    economy_system: dict[str, Any]  # 经济系统
    progression: list[str]          # 进阶系统
    art_style: str                  # 美术风格
    narrative: str                  # 叙事概述
    retention_features: list[str]   # 留存功能
    social_features: list[str]      # 社交功能
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gdd_id": self.gdd_id,
            "prd_id": self.prd_id,
            "game_name": self.game_name,
            "genre": self.genre,
            "core_loop": self.core_loop,
            "meta_loop": self.meta_loop,
            "mechanics": self.mechanics,
            "economy_system": self.economy_system,
            "progression": self.progression,
            "art_style": self.art_style,
            "narrative": self.narrative,
            "retention_features": self.retention_features,
            "social_features": self.social_features,
            "created_at": self.created_at,
        }


@dataclass
class FeatureItem:
    """单个 Feature 项."""

    feature_id: str
    title: str
    category: str                   # MONETIZATION / RETENTION / ACQUISITION / ENGAGEMENT / TECH
    description: str
    priority_score: float           # 0..100
    expected_impact: str            # 预期影响描述
    effort_days: int                # 预估工时
    sprint: int                     # 目标 Sprint 编号

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoadmapMilestone:
    """路线图里程碑."""

    milestone_id: str
    title: str
    target_date: str                # ISO 日期
    status: str                     # PLANNED / IN_PROGRESS / COMPLETED / DELAYED
    deliverables: list[str]         # 交付物列表
    sprint: int                     # Sprint 编号

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductRoadmap:
    """产品路线图."""

    roadmap_id: str
    prd_id: str
    game_name: str
    start_date: str
    end_date: str
    milestones: list[RoadmapMilestone]
    total_sprints: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "roadmap_id": self.roadmap_id,
            "prd_id": self.prd_id,
            "game_name": self.game_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "milestones": [m.to_dict() for m in self.milestones],
            "total_sprints": self.total_sprints,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 品类模板配置（禁止硬编码，参数走配置）
# ═══════════════════════════════════════════════════════════════


@dataclass
class GenreTemplate:
    """品类模板 — 由 genre 索引，控制 PRD/GDD 生成参数."""

    core_gameplay: str
    meta_loop: str
    monetization_model: str
    core_loop_steps: list[str]
    meta_loop_steps: list[str]
    mechanics: list[dict[str, Any]]
    economy_template: dict[str, Any]
    progression_template: list[str]
    art_style: str
    retention_features: list[str]
    social_features: list[str]
    default_kpi_targets: list[dict[str, Any]]
    key_features: list[str]
    risk_factors: list[str]


# 默认品类模板
_DEFAULT_GENRE_TEMPLATES: dict[str, GenreTemplate] = {
    "Merge": GenreTemplate(
        core_gameplay="合并相同物品生成更高阶物品，解锁新内容和区域",
        meta_loop="合并产出资源 → 资源用于装修/建造 → 装修解锁剧情 → 剧情驱动探索新区域",
        monetization_model="Hybrid",
        core_loop_steps=["收集资源", "合并物品", "解锁新物品", "完成任务"],
        meta_loop_steps=["合并产出装饰品", "装修房屋/花园", "解锁剧情章节", "探索新区域"],
        mechanics=[
            {"name": "Merge Board", "type": "core", "description": "拖拽合并棋盘", "complexity": "medium"},
            {"name": "Energy System", "type": "economy", "description": "能量限制合并次数", "complexity": "low"},
            {"name": "Decoration", "type": "meta", "description": "装饰系统驱动Meta进度", "complexity": "medium"},
            {"name": "Story Unlock", "type": "progression", "description": "剧情章节解锁", "complexity": "low"},
        ],
        economy_template={
            "hard_currency": "Gems",
            "soft_currency": "Coins",
            "energy": {"initial": 100, "max": 200, "regen_minutes": 2},
            "pay_points": ["Day 3", "Day 7", "Day 14"],
        },
        progression_template=["Level 1-50: 基础合并", "Level 51-100: 高级物品", "Level 101+: 装饰解锁"],
        art_style="Pastel / Cozy / Warm colors",
        retention_features=["Daily Login Bonus", "Merge Events", "Seasonal Decoration", "Collection Album"],
        social_features=["Guild Merge", "Gift Energy", "Leaderboard"],
        default_kpi_targets=[
            {"metric": "retention_d1", "target": 0.45, "benchmark": 0.40, "measurement": "次日留存率"},
            {"metric": "retention_d7", "target": 0.20, "benchmark": 0.15, "measurement": "7日留存率"},
            {"metric": "retention_d30", "target": 0.08, "benchmark": 0.05, "measurement": "30日留存率"},
            {"metric": "roas_d60", "target": 1.0, "benchmark": 0.80, "measurement": "60日ROAS"},
            {"metric": "arpu", "target": 0.15, "benchmark": 0.10, "measurement": "日均ARPU"},
        ],
        key_features=[
            "Merge Board 核心玩法",
            "装饰/装修 Meta 系统",
            "剧情驱动进度",
            "Energy 经济系统",
            "社交公会",
        ],
        risk_factors=["品类竞争激烈", "创意疲劳快", "需要持续内容更新"],
    ),
    "Match3": GenreTemplate(
        core_gameplay="三消匹配通关，获取奖励用于建设/装修",
        meta_loop="通关获取星星 → 星星用于建设 → 建设解锁新场景 → 新场景提供新关卡",
        monetization_model="Hybrid",
        core_loop_steps=["选择关卡", "三消匹配", "达成目标", "获取奖励"],
        meta_loop_steps=["星星用于建设", "解锁新场景", "新场景新关卡", "剧情推进"],
        mechanics=[
            {"name": "Match3 Board", "type": "core", "description": "三消棋盘", "complexity": "medium"},
            {"name": "Level Design", "type": "progression", "description": "关卡设计曲线", "complexity": "high"},
            {"name": "Building System", "type": "meta", "description": "建设Meta", "complexity": "medium"},
            {"name": "Boosters", "type": "monetization", "description": "道具系统", "complexity": "low"},
        ],
        economy_template={
            "hard_currency": "Gems",
            "soft_currency": "Coins",
            "lives": {"initial": 5, "max": 5, "regen_minutes": 30},
            "pay_points": ["Day 1", "Day 5", "Day 10"],
        },
        progression_template=["Level 1-100: 基础三消", "Level 101-300: 高级机制", "Level 301+: 特殊关卡"],
        art_style="Vibrant / Colorful / Cartoon",
        retention_features=["Daily Bonus", "Tournament", "New Levels Weekly", "Character Collection"],
        social_features=["Team", "Lives Gift", "Tournament Ranking"],
        default_kpi_targets=[
            {"metric": "retention_d1", "target": 0.50, "benchmark": 0.45, "measurement": "次日留存率"},
            {"metric": "retention_d7", "target": 0.22, "benchmark": 0.18, "measurement": "7日留存率"},
            {"metric": "retention_d30", "target": 0.10, "benchmark": 0.07, "measurement": "30日留存率"},
            {"metric": "roas_d60", "target": 1.2, "benchmark": 1.0, "measurement": "60日ROAS"},
            {"metric": "arpu", "target": 0.20, "benchmark": 0.15, "measurement": "日均ARPU"},
        ],
        key_features=[
            "三消核心玩法",
            "建设 Meta 系统",
            "500+ 关卡",
            "道具/Boosters",
            "锦标赛社交",
        ],
        risk_factors=["关卡设计成本高", "竞争白热化", "CPI 持续上涨"],
    ),
    "Simulation": GenreTemplate(
        core_gameplay="经营模拟，管理资源和发展虚拟世界",
        meta_loop="经营赚取收入 → 投资扩建 → 解锁新内容 → 吸引更多用户",
        monetization_model="IAP",
        core_loop_steps=["收集资源", "建造设施", "管理经营", "获取收入"],
        meta_loop_steps=["收入投资扩建", "解锁新区域", "招募角色", "故事推进"],
        mechanics=[
            {"name": "Resource Management", "type": "core", "description": "资源管理", "complexity": "high"},
            {"name": "Building System", "type": "meta", "description": "建造系统", "complexity": "medium"},
            {"name": "Character System", "type": "engagement", "description": "角色系统", "complexity": "medium"},
            {"name": "Quest System", "type": "progression", "description": "任务系统", "complexity": "low"},
        ],
        economy_template={
            "hard_currency": "Diamonds",
            "soft_currency": "Gold",
            "energy": {"initial": 50, "max": 100, "regen_minutes": 5},
            "pay_points": ["Day 5", "Day 14", "Day 30"],
        },
        progression_template=["Level 1-25: 基础经营", "Level 26-75: 扩展设施", "Level 76+: 高级内容"],
        art_style="Realistic / Detailed / Isometric",
        retention_features=["Daily Quests", "Seasonal Events", "Achievement System", "Character Stories"],
        social_features=["Visit Friends", "Trade Resources", "Co-op Events"],
        default_kpi_targets=[
            {"metric": "retention_d1", "target": 0.40, "benchmark": 0.35, "measurement": "次日留存率"},
            {"metric": "retention_d7", "target": 0.18, "benchmark": 0.14, "measurement": "7日留存率"},
            {"metric": "retention_d30", "target": 0.07, "benchmark": 0.05, "measurement": "30日留存率"},
            {"metric": "roas_d90", "target": 1.5, "benchmark": 1.2, "measurement": "90日ROAS"},
            {"metric": "arpu", "target": 0.30, "benchmark": 0.20, "measurement": "日均ARPU"},
        ],
        key_features=[
            "经营模拟核心",
            "建造/扩建系统",
            "角色招募",
            "任务/剧情",
            "社交访问",
        ],
        risk_factors=["开发周期长", "内容量大", "需要持续运营"],
    ),
}


@dataclass
class ProductTemplateConfig:
    """产品模板配置 — 控制 PRD/GDD 生成参数（禁止硬编码）."""

    genre_templates: dict[str, GenreTemplate] = field(
        default_factory=lambda: {k: v for k, v in _DEFAULT_GENRE_TEMPLATES.items()}
    )
    default_budget_usd: float = 300000.0
    default_timeline_months: int = 6
    default_target_dau: int = 100000
    sprint_weeks: int = 2            # 每个 Sprint 周数


# ═══════════════════════════════════════════════════════════════
# Product Manager Agent
# ═══════════════════════════════════════════════════════════════


class ProductManagerAgent:
    """Product Manager Agent — 把商业机会变成产品方案.

    用法:
        agent = ProductManagerAgent(data_dir="data")
        prd = agent.generate_prd(opportunity)
        gdd = agent.generate_gdd(prd.prd_id)
        features = agent.prioritize_features(prd.prd_id)
        roadmap = agent.create_roadmap(prd.prd_id)
    """

    def __init__(
        self,
        data_dir: str = "data",
        config: ProductTemplateConfig | None = None,
        product_director: Any = None,
        feature_strategy: Any = None,
        roadmap_engine: Any = None,
        message_bus: Any = None,
        agent_identity: Any = None,
    ) -> None:
        self.data_dir = data_dir
        self.config = config or ProductTemplateConfig()
        self._product_director = product_director
        self._feature_strategy = feature_strategy
        self._roadmap_engine = roadmap_engine
        self._message_bus = message_bus
        self._agent_identity = agent_identity

    # ── 懒加载依赖（复用 v9_company，不导入则降级）──────────────

    def _get_product_director(self) -> Any:
        if self._product_director is not None:
            return self._product_director
        try:
            from src.market_ops.game_company.v9_company.product_division import ProductDirector
            self._product_director = ProductDirector()
        except ImportError as exc:
            logger.warning("ProductDirector unavailable, using built-in templates: %s", exc)
            self._product_director = None
        return self._product_director

    def _get_feature_strategy(self) -> Any:
        if self._feature_strategy is not None:
            return self._feature_strategy
        try:
            from src.market_ops.game_company.v9_company.product_division import FeatureStrategy
            self._feature_strategy = FeatureStrategy()
        except ImportError as exc:
            logger.warning("FeatureStrategy unavailable, using built-in logic: %s", exc)
            self._feature_strategy = None
        return self._feature_strategy

    def _get_roadmap_engine(self) -> Any:
        if self._roadmap_engine is not None:
            return self._roadmap_engine
        try:
            from src.market_ops.game_company.v9_company.product_division import RoadmapEngine
            self._roadmap_engine = RoadmapEngine()
        except ImportError as exc:
            logger.warning("RoadmapEngine unavailable, using built-in logic: %s", exc)
            self._roadmap_engine = None
        return self._roadmap_engine

    # ── 核心方法 ─────────────────────────────────────────────

    def generate_prd(self, opportunity: MarketOpportunity) -> ProductRequirementDoc:
        """从市场机会生成 PRD.

        Args:
            opportunity: 市场机会输入

        Returns:
            ProductRequirementDoc 实例
        """
        genre = opportunity.genre or "Merge"
        template = self.config.genre_templates.get(genre, self.config.genre_templates["Merge"])

        prd_id = f"prd_{uuid.uuid4().hex[:12]}"
        now = _now_iso()

        # 构建 KPI 目标
        kpi_targets = [
            KPIDefinition(
                metric=k["metric"],
                target=k["target"],
                benchmark=k["benchmark"],
                measurement=k["measurement"],
            )
            for k in template.default_kpi_targets
        ]

        # 风险评估
        risk_factors = template.risk_factors
        if opportunity.budget_usd < self.config.default_budget_usd * 0.5:
            risk_factors.append("预算偏低，可能影响内容质量")
        if opportunity.timeline_months < self.config.default_timeline_months * 0.6:
            risk_factors.append("周期偏短，开发风险高")
        risk_assessment = "; ".join(risk_factors) if risk_factors else "风险可控"

        # Go/No-Go 决策
        go_no_go = self._assess_go_no_go(opportunity, template, risk_factors)

        # 产品名称
        title = self._generate_product_name(genre, opportunity.target_market)

        prd = ProductRequirementDoc(
            prd_id=prd_id,
            title=title,
            genre=genre,
            opportunity_id=opportunity.opportunity_id or f"opp_{uuid.uuid4().hex[:8]}",
            vision=f"打造{opportunity.target_audience or '目标用户'}喜爱的{genre}游戏",
            target_audience=opportunity.target_audience or "全年龄休闲玩家",
            target_market=opportunity.target_market or "Global",
            core_gameplay=template.core_gameplay,
            meta_loop=template.meta_loop,
            monetization_model=template.monetization_model,
            kpi_targets=kpi_targets,
            key_features=template.key_features,
            target_dau=opportunity.budget_usd / 3.0 if opportunity.budget_usd > 0 else self.config.default_target_dau,
            budget_usd=opportunity.budget_usd or self.config.default_budget_usd,
            timeline_months=opportunity.timeline_months or self.config.default_timeline_months,
            risk_assessment=risk_assessment,
            go_no_go=go_no_go,
            created_at=now,
        )

        # 持久化
        self._persist_prd(prd)

        # 广播事件
        self._broadcast_event("prd_generated", {
            "prd_id": prd.prd_id,
            "title": prd.title,
            "genre": prd.genre,
            "go_no_go": prd.go_no_go,
        })

        # 回流 CEO Memory
        self._write_ceo_memory({
            "execution_id": prd.prd_id,
            "action_id": f"prd_gen_{prd.prd_id}",
            "decision_id": prd.opportunity_id,
            "game_id": prd.title,
            "strategy_type": "product_prd",
            "domain": "product",
            "action_type": "prd_generation",
            "status": "success",
            "success": True,
            "real_api_called": False,
            "rolled_back": False,
            "detail": f"PRD generated: {prd.title} ({prd.genre}), go_no_go={prd.go_no_go}",
        })

        logger.info("PRD generated: %s (%s), go_no_go=%s", prd.title, prd.genre, prd.go_no_go)
        return prd

    def generate_gdd(self, prd_id: str) -> GameDesignDocument:
        """从 PRD 生成 GDD.

        Args:
            prd_id: 关联的 PRD ID

        Returns:
            GameDesignDocument 实例
        """
        prd = self._load_prd(prd_id)
        if prd is None:
            raise ValueError(f"PRD not found: {prd_id}")

        template = self.config.genre_templates.get(prd.genre, self.config.genre_templates["Merge"])

        gdd_id = f"gdd_{uuid.uuid4().hex[:12]}"
        now = _now_iso()

        gdd = GameDesignDocument(
            gdd_id=gdd_id,
            prd_id=prd.prd_id,
            game_name=prd.title,
            genre=prd.genre,
            core_loop=template.core_loop_steps,
            meta_loop=template.meta_loop_steps,
            mechanics=template.mechanics,
            economy_system=template.economy_template,
            progression=template.progression_template,
            art_style=template.art_style,
            narrative=f"{prd.title} 的故事围绕{prd.target_audience}展开，通过{prd.core_gameplay}驱动叙事",
            retention_features=template.retention_features,
            social_features=template.social_features,
            created_at=now,
        )

        # 持久化
        self._persist_gdd(gdd)

        # 广播事件
        self._broadcast_event("gdd_generated", {
            "gdd_id": gdd.gdd_id,
            "prd_id": gdd.prd_id,
            "game_name": gdd.game_name,
        })

        # 回流 CEO Memory
        self._write_ceo_memory({
            "execution_id": gdd.gdd_id,
            "action_id": f"gdd_gen_{gdd.gdd_id}",
            "decision_id": gdd.prd_id,
            "game_id": gdd.game_name,
            "strategy_type": "product_gdd",
            "domain": "product",
            "action_type": "gdd_generation",
            "status": "success",
            "success": True,
            "real_api_called": False,
            "rolled_back": False,
            "detail": f"GDD generated: {gdd.game_name}, mechanics={len(gdd.mechanics)}",
        })

        logger.info("GDD generated: %s (mechanics=%d)", gdd.game_name, len(gdd.mechanics))
        return gdd

    def prioritize_features(self, prd_id: str) -> list[FeatureItem]:
        """从 PRD 生成并排序 Feature 列表.

        Args:
            prd_id: 关联的 PRD ID

        Returns:
            排序后的 FeatureItem 列表（按 priority_score 降序）
        """
        prd = self._load_prd(prd_id)
        if prd is None:
            raise ValueError(f"PRD not found: {prd_id}")

        template = self.config.genre_templates.get(prd.genre, self.config.genre_templates["Merge"])

        # 构建 Feature 列表
        features: list[FeatureItem] = []
        for i, feat_name in enumerate(template.key_features):
            # 优先级计算：核心玩法 > Meta > 变现 > 社交
            if i == 0:
                priority = 95.0
                category = "ENGAGEMENT"
                impact = "核心玩法，直接影响留存"
                effort = 30
            elif "Meta" in feat_name or "meta" in feat_name:
                priority = 85.0
                category = "RETENTION"
                impact = "Meta 循环，驱动长期留存"
                effort = 25
            elif "经济" in feat_name or "Energy" in feat_name:
                priority = 80.0
                category = "MONETIZATION"
                impact = "经济系统，影响变现"
                effort = 15
            elif "社交" in feat_name or "Social" in feat_name:
                priority = 65.0
                category = "ACQUISITION"
                impact = "社交裂变，降低 CPI"
                effort = 20
            else:
                priority = 70.0
                category = "ENGAGEMENT"
                impact = "增强参与度"
                effort = 10

            features.append(FeatureItem(
                feature_id=f"feat_{uuid.uuid4().hex[:8]}",
                title=feat_name,
                category=category,
                description=f"{feat_name} — {prd.title}",
                priority_score=priority,
                expected_impact=impact,
                effort_days=effort,
                sprint=(i // 3) + 1,
            ))

        # 按 priority_score 降序排序
        features.sort(key=lambda f: f.priority_score, reverse=True)

        # 持久化
        self._persist_features(prd_id, features)

        # 广播事件
        self._broadcast_event("features_prioritized", {
            "prd_id": prd_id,
            "feature_count": len(features),
            "top_feature": features[0].title if features else "",
        })

        logger.info("Features prioritized: %d items for %s", len(features), prd.title)
        return features

    def create_roadmap(self, prd_id: str) -> ProductRoadmap:
        """从 PRD 生成产品路线图.

        Args:
            prd_id: 关联的 PRD ID

        Returns:
            ProductRoadmap 实例
        """
        prd = self._load_prd(prd_id)
        if prd is None:
            raise ValueError(f"PRD not found: {prd_id}")

        now = datetime.now(timezone.utc)
        timeline_months = prd.timeline_months or self.config.default_timeline_months
        total_sprints = max((timeline_months * 4) // self.config.sprint_weeks, 4)
        end_date = now + timedelta(days=timeline_months * 30)

        # 里程碑定义
        milestones: list[RoadmapMilestone] = [
            RoadmapMilestone(
                milestone_id=f"ms_{uuid.uuid4().hex[:8]}",
                title="Prototype / Vertical Slice",
                target_date=(now + timedelta(days=timeline_months * 30 * 0.2)).date().isoformat(),
                status="PLANNED",
                deliverables=["核心玩法原型", "美术风格验证", "技术架构"],
                sprint=1,
            ),
            RoadmapMilestone(
                milestone_id=f"ms_{uuid.uuid4().hex[:8]}",
                title="Alpha Build",
                target_date=(now + timedelta(days=timeline_months * 30 * 0.5)).date().isoformat(),
                status="PLANNED",
                deliverables=["完整核心循环", "Meta 系统初版", "内部测试"],
                sprint=max(total_sprints // 3, 2),
            ),
            RoadmapMilestone(
                milestone_id=f"ms_{uuid.uuid4().hex[:8]}",
                title="Beta / Soft Launch",
                target_date=(now + timedelta(days=timeline_months * 30 * 0.75)).date().isoformat(),
                status="PLANNED",
                deliverables=["功能完整", "Bug 修复", "Soft Launch (1-2 地区)"],
                sprint=max(total_sprints * 2 // 3, 3),
            ),
            RoadmapMilestone(
                milestone_id=f"ms_{uuid.uuid4().hex[:8]}",
                title="Global Launch",
                target_date=end_date.date().isoformat(),
                status="PLANNED",
                deliverables=["全球发布", "UA 投放启动", "LiveOps 上线"],
                sprint=total_sprints,
            ),
        ]

        roadmap = ProductRoadmap(
            roadmap_id=f"rm_{uuid.uuid4().hex[:12]}",
            prd_id=prd.prd_id,
            game_name=prd.title,
            start_date=now.date().isoformat(),
            end_date=end_date.date().isoformat(),
            milestones=milestones,
            total_sprints=total_sprints,
            created_at=_now_iso(),
        )

        # 持久化
        self._persist_roadmap(roadmap)

        # 广播事件
        self._broadcast_event("roadmap_created", {
            "roadmap_id": roadmap.roadmap_id,
            "prd_id": prd_id,
            "total_sprints": total_sprints,
            "milestones": len(milestones),
        })

        logger.info("Roadmap created: %s (%d sprints, %d milestones)",
                    roadmap.game_name, total_sprints, len(milestones))
        return roadmap

    def list_prds(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有 PRD."""
        path = Path(self.data_dir) / "product" / "prds.jsonl"
        return _read_jsonl(path, limit)

    def get_prd(self, prd_id: str) -> dict[str, Any] | None:
        """获取单个 PRD."""
        for prd in self.list_prds(limit=500):
            if prd.get("prd_id") == prd_id:
                return prd
        return None

    def list_gdds(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有 GDD."""
        path = Path(self.data_dir) / "product" / "gdds.jsonl"
        return _read_jsonl(path, limit)

    def get_gdd(self, gdd_id: str) -> dict[str, Any] | None:
        """获取单个 GDD."""
        for gdd in self.list_gdds(limit=500):
            if gdd.get("gdd_id") == gdd_id:
                return gdd
        return None

    def list_roadmaps(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有路线图."""
        path = Path(self.data_dir) / "product" / "roadmaps.jsonl"
        return _read_jsonl(path, limit)

    def get_stats(self) -> dict[str, Any]:
        """产品统计概览."""
        prds = self.list_prds(limit=1000)
        gdds = self.list_gdds(limit=1000)
        roadmaps = self.list_roadmaps(limit=1000)

        genre_dist: dict[str, int] = {}
        go_no_go_dist: dict[str, int] = {}
        for p in prds:
            g = p.get("genre", "unknown")
            genre_dist[g] = genre_dist.get(g, 0) + 1
            gng = p.get("go_no_go", "unknown")
            go_no_go_dist[gng] = go_no_go_dist.get(gng, 0) + 1

        return {
            "total_prds": len(prds),
            "total_gdds": len(gdds),
            "total_roadmaps": len(roadmaps),
            "genre_distribution": genre_dist,
            "go_no_go_distribution": go_no_go_dist,
            "recent_prds": prds[:5],
        }

    # ── 内部方法 ─────────────────────────────────────────────

    def _assess_go_no_go(
        self, opportunity: MarketOpportunity, template: GenreTemplate, risk_factors: list[str]
    ) -> str:
        """Go/No-Go 评估."""
        score = 70  # 基础分

        # 预算充裕度
        if opportunity.budget_usd >= self.config.default_budget_usd:
            score += 10
        elif opportunity.budget_usd < self.config.default_budget_usd * 0.5:
            score -= 15

        # 周期合理性
        if opportunity.timeline_months >= self.config.default_timeline_months:
            score += 5
        elif opportunity.timeline_months < self.config.default_timeline_months * 0.6:
            score -= 10

        # 风险因子数量
        score -= len(risk_factors) * 5

        if score >= 70:
            return "GO"
        elif score >= 50:
            return "REVIEW"
        else:
            return "NO_GO"

    def _generate_product_name(self, genre: str, market: str) -> str:
        """生成产品名称."""
        genre_prefix = {
            "Merge": "Merge",
            "Match3": "Match",
            "Simulation": "Sim",
        }.get(genre, genre)
        market_suffix = {
            "US": "Stars",
            "JP": "Sakura",
            "KR": "Legend",
            "Global": "World",
        }.get(market, "Saga")
        unique = uuid.uuid4().hex[:4]
        return f"{genre_prefix} {market_suffix} {unique}"

    # ── 持久化 ─────────────────────────────────────────────

    def _persist_prd(self, prd: ProductRequirementDoc) -> None:
        path = Path(self.data_dir) / "product" / "prds.jsonl"
        _append_jsonl(path, prd.to_dict())

    def _persist_gdd(self, gdd: GameDesignDocument) -> None:
        path = Path(self.data_dir) / "product" / "gdds.jsonl"
        _append_jsonl(path, gdd.to_dict())

    def _persist_features(self, prd_id: str, features: list[FeatureItem]) -> None:
        path = Path(self.data_dir) / "product" / "features.jsonl"
        record = {
            "prd_id": prd_id,
            "features": [f.to_dict() for f in features],
            "created_at": _now_iso(),
        }
        _append_jsonl(path, record)

    def _persist_roadmap(self, roadmap: ProductRoadmap) -> None:
        path = Path(self.data_dir) / "product" / "roadmaps.jsonl"
        _append_jsonl(path, roadmap.to_dict())

    def _load_prd(self, prd_id: str) -> ProductRequirementDoc | None:
        """从 JSONL 加载 PRD."""
        data = self.get_prd(prd_id)
        if data is None:
            return None
        kpi_targets = [
            KPIDefinition(
                metric=k.get("metric", ""),
                target=k.get("target", 0.0),
                benchmark=k.get("benchmark", 0.0),
                measurement=k.get("measurement", ""),
            )
            for k in data.get("kpi_targets", [])
        ]
        return ProductRequirementDoc(
            prd_id=data["prd_id"],
            title=data["title"],
            genre=data["genre"],
            opportunity_id=data.get("opportunity_id", ""),
            vision=data.get("vision", ""),
            target_audience=data.get("target_audience", ""),
            target_market=data.get("target_market", ""),
            core_gameplay=data.get("core_gameplay", ""),
            meta_loop=data.get("meta_loop", ""),
            monetization_model=data.get("monetization_model", ""),
            kpi_targets=kpi_targets,
            key_features=data.get("key_features", []),
            target_dau=data.get("target_dau", 0),
            budget_usd=data.get("budget_usd", 0.0),
            timeline_months=data.get("timeline_months", 6),
            risk_assessment=data.get("risk_assessment", ""),
            go_no_go=data.get("go_no_go", ""),
            created_at=data.get("created_at", ""),
        )

    # ── 跨 Agent 协同 ──────────────────────────────────────

    def _broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """通过 MessageBus 广播产品事件."""
        if self._message_bus is None or self._agent_identity is None:
            return
        try:
            from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                AgentMessage, MessageType, MessagePriority,
            )
            message = AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:12]}",
                sender=self._agent_identity,
                receiver=None,
                message_type=MessageType.BROADCAST,
                subject=f"product:{event_type}",
                body={"event_type": event_type, "source_agent": "product", **payload},
                priority=MessagePriority.NORMAL,
                ttl_seconds=600.0,
            )
            self._message_bus.send(message)
        except Exception as exc:
            logger.warning("ProductAgent broadcast event failed: %s", exc)

    def _write_ceo_memory(self, record: dict[str, Any]) -> None:
        """写入 CEO Memory（data/ceo/execution_memory.jsonl）."""
        ceo_memory_path = Path(self.data_dir) / "ceo" / "execution_memory.jsonl"
        ceo_memory_path.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("created_at", _now_iso())
        with ceo_memory_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 字符串."""
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """追加写入 JSONL 文件 (带轮转保护)."""
    from .jsonl_rotator import get_default_rotator
    rotator = get_default_rotator(data_dir=str(path.parent.parent) if path.parent.parent else "data")
    rotator.maybe_rotate(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    """读取 JSONL 文件最后 N 条记录."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.reverse()
    return records
