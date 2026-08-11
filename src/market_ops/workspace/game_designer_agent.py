"""Game Designer Agent — 从 GDD 细化为可执行的游戏设计.

接收 Product Agent 生成的 GDD（游戏设计文档），输出可执行的关卡设计、
数值平衡配置、系统规格和难度曲线，接入 workspace 组织架构。

设计原则（继承 LiveOps/Product Agent 纪律红线）:
  - 复用 v9_company/product_division/economy_manager 的数据模型，不新增算法层
  - 默认 dry_run：设计产物只生成不执行
  - 设计参数走配置（GenreDesignConfig），禁止硬编码模板
  - 接入 MessageBus 广播设计事件
  - 执行结果回流 CEO Memory（domain="design"）

依赖注入:
  economy_manager 可在 __init__ 注入（便于测试），
  默认懒加载 v9_company/product_division 的真实实例。当真实模块不可导入时
  （如纯 workspace 部署），优雅降级到内置模板。

数据流:
  Product Agent GDD → Game Designer Agent → LevelDesign / EconomyBalance /
                                          SystemSpec / DifficultyCurve / DesignDocument
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


@dataclass
class LevelDefinition:
    """单个关卡定义."""

    level_id: str
    level_number: int
    chapter: int                    # 所属章节
    difficulty: str                 # EASY / NORMAL / HARD / EXPERT
    objective: str                  # 通关目标描述
    reward_type: str                # coin / gem / item / star
    reward_amount: int              # 奖励数量
    energy_cost: int                # 能量消耗
    estimated_attempts: int         # 预估尝试次数
    unlock_condition: str           # 解锁条件

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LevelDesign:
    """关卡设计 — 完整关卡列表和章节结构."""

    design_id: str
    gdd_id: str
    game_name: str
    genre: str
    total_levels: int
    total_chapters: int
    levels: list[LevelDefinition]
    chapter_structure: list[dict[str, Any]]  # 章节概要
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_id": self.design_id,
            "gdd_id": self.gdd_id,
            "game_name": self.game_name,
            "genre": self.genre,
            "total_levels": self.total_levels,
            "total_chapters": self.total_chapters,
            "levels": [l.to_dict() for l in self.levels],
            "chapter_structure": self.chapter_structure,
            "created_at": self.created_at,
        }


@dataclass
class CurrencyConfig:
    """单个货币配置."""

    currency_name: str              # Gems / Coins / Energy
    currency_type: str              # hard / soft / energy
    daily_faucet: float             # 日产出
    daily_sink: float               # 日消耗
    initial_amount: float           # 初始数量
    max_capacity: float             # 上限

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ItemPricing:
    """道具定价."""

    item_id: str
    item_name: str
    category: str                   # consumable / permanent / cosmetic
    price_currency: str             # 货币类型
    price_amount: float
    production_cost: float          # 生产成本

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EconomyBalance:
    """经济数值平衡 — 货币/产出/消耗/定价."""

    balance_id: str
    gdd_id: str
    game_name: str
    currencies: list[CurrencyConfig]
    item_pricing: list[ItemPricing]
    sink_to_faucet_ratio: float     # 消耗/产出比（目标 >1.0）
    inflation_target: float         # 通胀目标
    pay_points: list[str]           # 付费点
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "balance_id": self.balance_id,
            "gdd_id": self.gdd_id,
            "game_name": self.game_name,
            "currencies": [c.to_dict() for c in self.currencies],
            "item_pricing": [p.to_dict() for p in self.item_pricing],
            "sink_to_faucet_ratio": round(self.sink_to_faucet_ratio, 4),
            "inflation_target": round(self.inflation_target, 4),
            "pay_points": self.pay_points,
            "created_at": self.created_at,
        }


@dataclass
class SystemSpecification:
    """单个系统规格."""

    system_id: str
    name: str                       # Merge Board / Match3 Engine / Building System
    system_type: str                # core / meta / economy / social / progression
    description: str
    parameters: dict[str, Any]      # 系统参数
    interactions: list[str]         # 与其他系统的交互
    balance_targets: dict[str, float]  # 平衡目标
    complexity: str                 # low / medium / high

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DifficultyStage:
    """难度曲线阶段."""

    stage_id: str
    stage_name: str                 # Onboarding / Early / Mid / Late / Endgame
    level_range: str                # "1-20"
    difficulty_score: float         # 0..1
    retention_focus: str            # 留存重点
    churn_risk: str                 # low / medium / high

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DifficultyCurve:
    """难度曲线 — 分阶段难度配置."""

    curve_id: str
    gdd_id: str
    game_name: str
    stages: list[DifficultyStage]
    slope_parameter: float          # 整体斜率
    plateau_levels: list[int]       # 平台期关卡编号
    spike_levels: list[int]         # 难度突增关卡编号
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "curve_id": self.curve_id,
            "gdd_id": self.gdd_id,
            "game_name": self.game_name,
            "stages": [s.to_dict() for s in self.stages],
            "slope_parameter": round(self.slope_parameter, 4),
            "plateau_levels": self.plateau_levels,
            "spike_levels": self.spike_levels,
            "created_at": self.created_at,
        }


@dataclass
class DesignDocument:
    """完整设计文档 — 聚合关卡/数值/系统/难度."""

    document_id: str
    gdd_id: str
    game_name: str
    genre: str
    level_design: dict[str, Any]
    economy_balance: dict[str, Any]
    system_specs: list[dict[str, Any]]
    difficulty_curve: dict[str, Any]
    design_summary: str             # 设计总结
    ready_for_dev: bool             # 是否可交付开发
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "gdd_id": self.gdd_id,
            "game_name": self.game_name,
            "genre": self.genre,
            "level_design": self.level_design,
            "economy_balance": self.economy_balance,
            "system_specs": self.system_specs,
            "difficulty_curve": self.difficulty_curve,
            "design_summary": self.design_summary,
            "ready_for_dev": self.ready_for_dev,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 品类设计模板配置（禁止硬编码，参数走配置）
# ═══════════════════════════════════════════════════════════════


@dataclass
class GenreDesignTemplate:
    """品类设计模板 — 控制 LevelDesign/EconomyBalance 生成参数."""

    total_levels: int
    levels_per_chapter: int
    base_energy_cost: int
    base_reward: int
    difficulty_slope: float         # 难度增长斜率
    currencies: list[dict[str, Any]]
    item_catalog: list[dict[str, Any]]
    sink_to_faucet_target: float
    inflation_target: float
    pay_points: list[str]
    system_specs: list[dict[str, Any]]
    difficulty_stages: list[dict[str, Any]]


# 默认品类设计模板
_DEFAULT_DESIGN_TEMPLATES: dict[str, GenreDesignTemplate] = {
    "Merge": GenreDesignTemplate(
        total_levels=200,
        levels_per_chapter=20,
        base_energy_cost=5,
        base_reward=50,
        difficulty_slope=0.015,
        currencies=[
            {"name": "Gems", "type": "hard", "daily_faucet": 50, "daily_sink": 55, "initial": 100, "max": 9999},
            {"name": "Coins", "type": "soft", "daily_faucet": 5000, "daily_sink": 5200, "initial": 1000, "max": 999999},
            {"name": "Energy", "type": "energy", "daily_faucet": 1200, "daily_sink": 1100, "initial": 100, "max": 200},
        ],
        item_catalog=[
            {"id": "energy_refill", "name": "能量回满", "category": "consumable", "price_currency": "Gems", "price": 30, "cost": 5},
            {"id": "merge_booster", "name": "合并助推器", "category": "consumable", "price_currency": "Gems", "price": 50, "cost": 10},
            {"id": "decoration_pack", "name": "装饰礼包", "category": "permanent", "price_currency": "Gems", "price": 200, "cost": 50},
            {"id": "coin_pack_s", "name": "金币包 S", "category": "consumable", "price_currency": "Gems", "price": 20, "cost": 3},
            {"id": "vip_card", "name": "VIP 月卡", "category": "permanent", "price_currency": "Gems", "price": 300, "cost": 80},
        ],
        sink_to_faucet_target=1.08,
        inflation_target=0.02,
        pay_points=["Day 3", "Day 7", "Day 14", "Day 30"],
        system_specs=[
            {"name": "Merge Board", "type": "core", "description": "拖拽合并棋盘核心玩法", "parameters": {"board_size": "5x5", "max_items": 25, "merge_chain": 8}, "interactions": ["Energy System", "Coin Rewards"], "balance_targets": {"merge_rate": 0.7, "board_fill_rate": 0.6}, "complexity": "medium"},
            {"name": "Energy System", "type": "economy", "description": "能量限制合并次数", "parameters": {"max_energy": 200, "regen_per_min": 0.5, "cost_per_merge": 5}, "interactions": ["Merge Board"], "balance_targets": {"session_length_min": 8, "daily_sessions": 3}, "complexity": "low"},
            {"name": "Decoration System", "type": "meta", "description": "装饰系统驱动 Meta 进度", "parameters": {"slots": 50, "tiers": 5}, "interactions": ["Story Unlock", "Coin Economy"], "balance_targets": {"decoration_unlock_rate": 0.3}, "complexity": "medium"},
            {"name": "Story Unlock", "type": "progression", "description": "剧情章节解锁", "parameters": {"chapters": 10, "unlock_threshold": 0.8}, "interactions": ["Decoration System"], "balance_targets": {"chapter_completion_rate": 0.6}, "complexity": "low"},
        ],
        difficulty_stages=[
            {"name": "Onboarding", "range": "1-20", "score": 0.1, "focus": "教学引导", "churn_risk": "low"},
            {"name": "Early", "range": "21-60", "score": 0.25, "focus": "核心玩法熟练", "churn_risk": "low"},
            {"name": "Mid", "range": "61-120", "score": 0.5, "focus": "Meta 系统引入", "churn_risk": "medium"},
            {"name": "Late", "range": "121-180", "score": 0.75, "focus": "深度内容", "churn_risk": "medium"},
            {"name": "Endgame", "range": "181-200", "score": 0.95, "focus": "挑战与社交", "churn_risk": "high"},
        ],
    ),
    "Match3": GenreDesignTemplate(
        total_levels=500,
        levels_per_chapter=25,
        base_energy_cost=1,
        base_reward=30,
        difficulty_slope=0.012,
        currencies=[
            {"name": "Gems", "type": "hard", "daily_faucet": 40, "daily_sink": 45, "initial": 80, "max": 9999},
            {"name": "Coins", "type": "soft", "daily_faucet": 3000, "daily_sink": 3200, "initial": 800, "max": 999999},
            {"name": "Lives", "type": "energy", "daily_faucet": 240, "daily_sink": 220, "initial": 5, "max": 5},
        ],
        item_catalog=[
            {"id": "life_refill", "name": "生命回满", "category": "consumable", "price_currency": "Gems", "price": 25, "cost": 4},
            {"id": "boost_hammer", "name": "锤子道具", "category": "consumable", "price_currency": "Gems", "price": 40, "cost": 8},
            {"id": "boost_shuffle", "name": "洗牌道具", "category": "consumable", "price_currency": "Gems", "price": 35, "cost": 7},
            {"id": "extra_moves", "name": "额外步数", "category": "consumable", "price_currency": "Gems", "price": 20, "cost": 3},
            {"id": "vip_card", "name": "VIP 月卡", "category": "permanent", "price_currency": "Gems", "price": 280, "cost": 70},
        ],
        sink_to_faucet_target=1.10,
        inflation_target=0.018,
        pay_points=["Day 1", "Day 5", "Day 10", "Day 21"],
        system_specs=[
            {"name": "Match3 Engine", "type": "core", "description": "三消匹配引擎", "parameters": {"grid_size": "8x8", "colors": 6, "min_match": 3}, "interactions": ["Level Design", "Booster System"], "balance_targets": {"win_rate": 0.7, "avg_moves": 25}, "complexity": "high"},
            {"name": "Level Design System", "type": "progression", "description": "关卡设计系统", "parameters": {"objectives": ["score", "collect", "clear"], "move_limits": [15, 30]}, "interactions": ["Match3 Engine"], "balance_targets": {"first_try_win_rate": 0.6}, "complexity": "high"},
            {"name": "Booster System", "type": "economy", "description": "道具系统", "parameters": {"types": ["hammer", "shuffle", "extra_moves"]}, "interactions": ["Match3 Engine", "Gem Economy"], "balance_targets": {"usage_rate": 0.4}, "complexity": "low"},
            {"name": "Building System", "type": "meta", "description": "建设 Meta 系统", "parameters": {"buildings": 30, "tiers": 3}, "interactions": ["Star Rewards", "Story"], "balance_targets": {"build_rate": 0.5}, "complexity": "medium"},
        ],
        difficulty_stages=[
            {"name": "Onboarding", "range": "1-50", "score": 0.08, "focus": "三消教学", "churn_risk": "low"},
            {"name": "Early", "range": "51-150", "score": 0.2, "focus": "机制引入", "churn_risk": "low"},
            {"name": "Mid", "range": "151-300", "score": 0.45, "focus": "难度提升", "churn_risk": "medium"},
            {"name": "Late", "range": "301-450", "score": 0.7, "focus": "挑战关卡", "churn_risk": "medium"},
            {"name": "Endgame", "range": "451-500", "score": 0.92, "focus": "极限挑战", "churn_risk": "high"},
        ],
    ),
    "Simulation": GenreDesignTemplate(
        total_levels=100,
        levels_per_chapter=10,
        base_energy_cost=10,
        base_reward=100,
        difficulty_slope=0.02,
        currencies=[
            {"name": "Diamonds", "type": "hard", "daily_faucet": 30, "daily_sink": 35, "initial": 50, "max": 9999},
            {"name": "Gold", "type": "soft", "daily_faucet": 8000, "daily_sink": 8500, "initial": 2000, "max": 9999999},
            {"name": "Energy", "type": "energy", "daily_faucet": 600, "daily_sink": 550, "initial": 50, "max": 100},
        ],
        item_catalog=[
            {"id": "time_skip", "name": "时间加速", "category": "consumable", "price_currency": "Diamonds", "price": 20, "cost": 3},
            {"id": "resource_pack", "name": "资源包", "category": "consumable", "price_currency": "Diamonds", "price": 60, "cost": 15},
            {"id": "premium_building", "name": "高级建筑", "category": "permanent", "price_currency": "Diamonds", "price": 150, "cost": 40},
            {"id": "character_slot", "name": "角色栏位", "category": "permanent", "price_currency": "Diamonds", "price": 100, "cost": 25},
            {"id": "vip_card", "name": "VIP 月卡", "category": "permanent", "price_currency": "Diamonds", "price": 350, "cost": 90},
        ],
        sink_to_faucet_target=1.06,
        inflation_target=0.025,
        pay_points=["Day 5", "Day 14", "Day 30"],
        system_specs=[
            {"name": "Resource Management", "type": "core", "description": "资源管理核心", "parameters": {"resource_types": 5, "storage_limits": [1000, 5000, 10000]}, "interactions": ["Building System", "Quest System"], "balance_targets": {"resource_utilization": 0.7}, "complexity": "high"},
            {"name": "Building System", "type": "meta", "description": "建造系统", "parameters": {"categories": 4, "buildings_per_category": 10}, "interactions": ["Resource Management", "Character System"], "balance_targets": {"build_rate": 0.4}, "complexity": "medium"},
            {"name": "Character System", "type": "engagement", "description": "角色系统", "parameters": {"max_characters": 20, "rarity_tiers": 4}, "interactions": ["Building System", "Quest System"], "balance_targets": {"collection_rate": 0.5}, "complexity": "medium"},
            {"name": "Quest System", "type": "progression", "description": "任务系统", "parameters": {"daily_quests": 5, "story_quests": 100}, "interactions": ["Resource Management", "Character System"], "balance_targets": {"completion_rate": 0.7}, "complexity": "low"},
        ],
        difficulty_stages=[
            {"name": "Onboarding", "range": "1-10", "score": 0.12, "focus": "经营教学", "churn_risk": "low"},
            {"name": "Early", "range": "11-30", "score": 0.3, "focus": "系统解锁", "churn_risk": "low"},
            {"name": "Mid", "range": "31-60", "score": 0.55, "focus": "扩展经营", "churn_risk": "medium"},
            {"name": "Late", "range": "61-90", "score": 0.8, "focus": "高级内容", "churn_risk": "medium"},
            {"name": "Endgame", "range": "91-100", "score": 0.95, "focus": "极限经营", "churn_risk": "high"},
        ],
    ),
}


@dataclass
class GenreDesignConfig:
    """设计配置 — 控制关卡/数值/难度生成参数（禁止硬编码）."""

    templates: dict[str, GenreDesignTemplate] = field(
        default_factory=lambda: {k: v for k, v in _DEFAULT_DESIGN_TEMPLATES.items()}
    )
    default_total_levels: int = 200
    reward_growth_rate: float = 1.05   # 每关奖励增长率
    energy_growth_rate: float = 1.02   # 每关能量消耗增长率


# ═══════════════════════════════════════════════════════════════
# Game Designer Agent
# ═══════════════════════════════════════════════════════════════


class GameDesignerAgent:
    """Game Designer Agent — 从 GDD 细化为可执行设计.

    用法:
        agent = GameDesignerAgent(data_dir="data")
        levels = agent.design_levels(gdd_id)
        economy = agent.balance_economy(gdd_id)
        systems = agent.specify_systems(gdd_id)
        curve = agent.generate_difficulty_curve(gdd_id)
        doc = agent.create_design_document(gdd_id)
    """

    def __init__(
        self,
        data_dir: str = "data",
        config: GenreDesignConfig | None = None,
        economy_manager: Any = None,
        message_bus: Any = None,
        agent_identity: Any = None,
    ) -> None:
        self.data_dir = data_dir
        self.config = config or GenreDesignConfig()
        self._economy_manager = economy_manager
        self._message_bus = message_bus
        self._agent_identity = agent_identity

    # ── 懒加载依赖（复用 v9_company，不导入则降级）──────────────

    def _get_economy_manager(self) -> Any:
        if self._economy_manager is not None:
            return self._economy_manager
        try:
            from src.market_ops.game_company.v9_company.product_division.economy_manager import EconomyManager
            self._economy_manager = EconomyManager()
        except ImportError as exc:
            logger.warning("EconomyManager unavailable, using built-in templates: %s", exc)
            self._economy_manager = None
        return self._economy_manager

    # ── 核心方法 ─────────────────────────────────────────────

    def design_levels(self, gdd_id: str) -> LevelDesign:
        """从 GDD 生成关卡设计.

        Args:
            gdd_id: 关联的 GDD ID

        Returns:
            LevelDesign 实例
        """
        gdd = self._load_gdd(gdd_id)
        if gdd is None:
            raise ValueError(f"GDD not found: {gdd_id}")

        template = self.config.templates.get(gdd["genre"], self.config.templates["Merge"])

        total_levels = template.total_levels
        levels_per_chapter = template.levels_per_chapter
        total_chapters = math.ceil(total_levels / levels_per_chapter)

        levels: list[LevelDefinition] = []
        for i in range(1, total_levels + 1):
            chapter = math.ceil(i / levels_per_chapter)
            progress = i / total_levels

            # 难度分级
            if progress < 0.1:
                difficulty = "EASY"
            elif progress < 0.4:
                difficulty = "NORMAL"
            elif progress < 0.7:
                difficulty = "HARD"
            else:
                difficulty = "EXPERT"

            # 奖励和能量消耗递增
            reward = int(template.base_reward * (self.config.reward_growth_rate ** (i - 1)))
            energy = int(template.base_energy_cost * (self.config.energy_growth_rate ** (i - 1)))

            # 关卡目标
            objective = self._generate_level_objective(gdd["genre"], i, difficulty)

            # 解锁条件
            if i == 1:
                unlock = "初始解锁"
            elif i <= levels_per_chapter:
                unlock = f"通过关卡 {i - 1}"
            else:
                unlock = f"完成第 {chapter - 1} 章"

            levels.append(LevelDefinition(
                level_id=f"lvl_{uuid.uuid4().hex[:8]}",
                level_number=i,
                chapter=chapter,
                difficulty=difficulty,
                objective=objective,
                reward_type="coin" if i % 5 != 0 else "gem",
                reward_amount=reward,
                energy_cost=energy,
                estimated_attempts=max(1, int(1 + progress * 3)),
                unlock_condition=unlock,
            ))

        # 章节结构
        chapter_structure: list[dict[str, Any]] = []
        for ch in range(1, total_chapters + 1):
            start = (ch - 1) * levels_per_chapter + 1
            end = min(ch * levels_per_chapter, total_levels)
            chapter_structure.append({
                "chapter": ch,
                "level_range": f"{start}-{end}",
                "level_count": end - start + 1,
                "theme": self._get_chapter_theme(gdd["genre"], ch, total_chapters),
                "boss_level": end,
            })

        design = LevelDesign(
            design_id=f"lvl_design_{uuid.uuid4().hex[:12]}",
            gdd_id=gdd_id,
            game_name=gdd.get("game_name", ""),
            genre=gdd["genre"],
            total_levels=total_levels,
            total_chapters=total_chapters,
            levels=levels,
            chapter_structure=chapter_structure,
            created_at=_now_iso(),
        )

        # 持久化
        self._persist_level_design(design)

        # 广播事件
        self._broadcast_event("levels_designed", {
            "design_id": design.design_id,
            "gdd_id": gdd_id,
            "total_levels": total_levels,
            "total_chapters": total_chapters,
        })

        # 回流 CEO Memory
        self._write_ceo_memory({
            "execution_id": design.design_id,
            "action_id": f"level_design_{design.design_id}",
            "decision_id": gdd_id,
            "game_id": design.game_name,
            "strategy_type": "game_design_level",
            "domain": "design",
            "action_type": "level_design",
            "status": "success",
            "success": True,
            "real_api_called": False,
            "rolled_back": False,
            "detail": f"Level design: {design.game_name}, {total_levels} levels, {total_chapters} chapters",
        })

        logger.info("Level design: %s (%d levels, %d chapters)",
                    design.game_name, total_levels, total_chapters)
        return design

    def balance_economy(self, gdd_id: str) -> EconomyBalance:
        """从 GDD 生成经济数值平衡.

        Args:
            gdd_id: 关联的 GDD ID

        Returns:
            EconomyBalance 实例
        """
        gdd = self._load_gdd(gdd_id)
        if gdd is None:
            raise ValueError(f"GDD not found: {gdd_id}")

        template = self.config.templates.get(gdd["genre"], self.config.templates["Merge"])

        # 尝试复用 EconomyManager
        eco_manager = self._get_economy_manager()

        # 货币配置
        currencies: list[CurrencyConfig] = []
        for c in template.currencies:
            currencies.append(CurrencyConfig(
                currency_name=c["name"],
                currency_type=c["type"],
                daily_faucet=c["daily_faucet"],
                daily_sink=c["daily_sink"] * template.sink_to_faucet_target,
                initial_amount=c["initial"],
                max_capacity=c["max"],
            ))

        # 道具定价
        item_pricing: list[ItemPricing] = []
        for item in template.item_catalog:
            item_pricing.append(ItemPricing(
                item_id=item["id"],
                item_name=item["name"],
                category=item["category"],
                price_currency=item["price_currency"],
                price_amount=item["price"],
                production_cost=item["cost"],
            ))

        # 实际消耗/产出比
        total_faucet = sum(c.daily_faucet for c in currencies)
        total_sink = sum(c.daily_sink for c in currencies)
        actual_ratio = total_sink / max(total_faucet, 1.0)

        balance = EconomyBalance(
            balance_id=f"eco_{uuid.uuid4().hex[:12]}",
            gdd_id=gdd_id,
            game_name=gdd.get("game_name", ""),
            currencies=currencies,
            item_pricing=item_pricing,
            sink_to_faucet_ratio=actual_ratio,
            inflation_target=template.inflation_target,
            pay_points=list(template.pay_points),
            created_at=_now_iso(),
        )

        # 持久化
        self._persist_economy_balance(balance)

        # 广播事件
        self._broadcast_event("economy_balanced", {
            "balance_id": balance.balance_id,
            "gdd_id": gdd_id,
            "sink_to_faucet_ratio": round(actual_ratio, 4),
            "currency_count": len(currencies),
        })

        # 回流 CEO Memory
        self._write_ceo_memory({
            "execution_id": balance.balance_id,
            "action_id": f"economy_balance_{balance.balance_id}",
            "decision_id": gdd_id,
            "game_id": balance.game_name,
            "strategy_type": "game_design_economy",
            "domain": "design",
            "action_type": "economy_balance",
            "status": "success",
            "success": True,
            "real_api_called": False,
            "rolled_back": False,
            "detail": f"Economy balance: {balance.game_name}, ratio={actual_ratio:.2f}, currencies={len(currencies)}",
        })

        logger.info("Economy balance: %s (ratio=%.2f, %d currencies)",
                    balance.game_name, actual_ratio, len(currencies))
        return balance

    def specify_systems(self, gdd_id: str) -> list[SystemSpecification]:
        """从 GDD 生成系统规格列表.

        Args:
            gdd_id: 关联的 GDD ID

        Returns:
            SystemSpecification 列表
        """
        gdd = self._load_gdd(gdd_id)
        if gdd is None:
            raise ValueError(f"GDD not found: {gdd_id}")

        template = self.config.templates.get(gdd["genre"], self.config.templates["Merge"])

        systems: list[SystemSpecification] = []
        for spec_def in template.system_specs:
            systems.append(SystemSpecification(
                system_id=f"sys_{uuid.uuid4().hex[:8]}",
                name=spec_def["name"],
                system_type=spec_def["type"],
                description=spec_def["description"],
                parameters=spec_def.get("parameters", {}),
                interactions=spec_def.get("interactions", []),
                balance_targets=spec_def.get("balance_targets", {}),
                complexity=spec_def.get("complexity", "medium"),
            ))

        # 持久化
        self._persist_system_specs(gdd_id, systems)

        # 广播事件
        self._broadcast_event("systems_specified", {
            "gdd_id": gdd_id,
            "system_count": len(systems),
            "system_names": [s.name for s in systems],
        })

        # 回流 CEO Memory
        self._write_ceo_memory({
            "execution_id": f"sys_specs_{gdd_id}",
            "action_id": f"system_specs_{gdd_id}",
            "decision_id": gdd_id,
            "game_id": gdd.get("game_name", ""),
            "strategy_type": "game_design_system",
            "domain": "design",
            "action_type": "system_specification",
            "status": "success",
            "success": True,
            "real_api_called": False,
            "rolled_back": False,
            "detail": f"System specs: {gdd.get('game_name', '')}, {len(systems)} systems",
        })

        logger.info("System specs: %s (%d systems)", gdd.get("game_name", ""), len(systems))
        return systems

    def generate_difficulty_curve(self, gdd_id: str) -> DifficultyCurve:
        """从 GDD 生成难度曲线.

        Args:
            gdd_id: 关联的 GDD ID

        Returns:
            DifficultyCurve 实例
        """
        gdd = self._load_gdd(gdd_id)
        if gdd is None:
            raise ValueError(f"GDD not found: {gdd_id}")

        template = self.config.templates.get(gdd["genre"], self.config.templates["Merge"])

        # 难度阶段
        stages: list[DifficultyStage] = []
        for stage_def in template.difficulty_stages:
            stages.append(DifficultyStage(
                stage_id=f"stage_{uuid.uuid4().hex[:8]}",
                stage_name=stage_def["name"],
                level_range=stage_def["range"],
                difficulty_score=stage_def["score"],
                retention_focus=stage_def["focus"],
                churn_risk=stage_def["churn_risk"],
            ))

        # 平台期和突增点
        total_levels = template.total_levels
        plateau_levels = [
            int(total_levels * 0.15),
            int(total_levels * 0.45),
            int(total_levels * 0.75),
        ]
        spike_levels = [
            int(total_levels * 0.3),
            int(total_levels * 0.6),
            int(total_levels * 0.9),
        ]

        curve = DifficultyCurve(
            curve_id=f"curve_{uuid.uuid4().hex[:12]}",
            gdd_id=gdd_id,
            game_name=gdd.get("game_name", ""),
            stages=stages,
            slope_parameter=template.difficulty_slope,
            plateau_levels=plateau_levels,
            spike_levels=spike_levels,
            created_at=_now_iso(),
        )

        # 持久化
        self._persist_difficulty_curve(curve)

        # 广播事件
        self._broadcast_event("difficulty_curve_generated", {
            "curve_id": curve.curve_id,
            "gdd_id": gdd_id,
            "stage_count": len(stages),
            "slope": round(template.difficulty_slope, 4),
        })

        # 回流 CEO Memory
        self._write_ceo_memory({
            "execution_id": curve.curve_id,
            "action_id": f"difficulty_curve_{curve.curve_id}",
            "decision_id": gdd_id,
            "game_id": curve.game_name,
            "strategy_type": "game_design_difficulty",
            "domain": "design",
            "action_type": "difficulty_curve",
            "status": "success",
            "success": True,
            "real_api_called": False,
            "rolled_back": False,
            "detail": f"Difficulty curve: {curve.game_name}, {len(stages)} stages, slope={template.difficulty_slope}",
        })

        logger.info("Difficulty curve: %s (%d stages, slope=%.4f)",
                    curve.game_name, len(stages), template.difficulty_slope)
        return curve

    def create_design_document(self, gdd_id: str) -> DesignDocument:
        """从 GDD 生成完整设计文档（聚合关卡/数值/系统/难度）.

        Args:
            gdd_id: 关联的 GDD ID

        Returns:
            DesignDocument 实例
        """
        gdd = self._load_gdd(gdd_id)
        if gdd is None:
            raise ValueError(f"GDD not found: {gdd_id}")

        # 聚合所有设计产物
        level_design = self.design_levels(gdd_id)
        economy_balance = self.balance_economy(gdd_id)
        system_specs = self.specify_systems(gdd_id)
        difficulty_curve = self.generate_difficulty_curve(gdd_id)

        # 评估可交付性
        ready_for_dev = (
            level_design.total_levels > 0
            and len(economy_balance.currencies) > 0
            and len(system_specs) > 0
            and len(difficulty_curve.stages) > 0
        )

        summary = (
            f"{gdd.get('game_name', '')} 设计文档: "
            f"{level_design.total_levels} 关卡 / {level_design.total_chapters} 章节, "
            f"{len(economy_balance.currencies)} 货币 (消耗比 {economy_balance.sink_to_faucet_ratio:.2f}), "
            f"{len(system_specs)} 系统, {len(difficulty_curve.stages)} 难度阶段"
        )

        doc = DesignDocument(
            document_id=f"doc_{uuid.uuid4().hex[:12]}",
            gdd_id=gdd_id,
            game_name=gdd.get("game_name", ""),
            genre=gdd.get("genre", ""),
            level_design=level_design.to_dict(),
            economy_balance=economy_balance.to_dict(),
            system_specs=[s.to_dict() for s in system_specs],
            difficulty_curve=difficulty_curve.to_dict(),
            design_summary=summary,
            ready_for_dev=ready_for_dev,
            created_at=_now_iso(),
        )

        # 持久化
        self._persist_design_document(doc)

        # 广播事件
        self._broadcast_event("design_document_created", {
            "document_id": doc.document_id,
            "gdd_id": gdd_id,
            "ready_for_dev": ready_for_dev,
        })

        # 回流 CEO Memory
        self._write_ceo_memory({
            "execution_id": doc.document_id,
            "action_id": f"design_doc_{doc.document_id}",
            "decision_id": gdd_id,
            "game_id": doc.game_name,
            "strategy_type": "game_design_document",
            "domain": "design",
            "action_type": "design_document",
            "status": "success",
            "success": True,
            "real_api_called": False,
            "rolled_back": False,
            "detail": f"Design document: {doc.game_name}, ready={ready_for_dev}",
        })

        logger.info("Design document: %s (ready_for_dev=%s)", doc.game_name, ready_for_dev)
        return doc

    # ── 查询方法 ─────────────────────────────────────────────

    def list_level_designs(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有关卡设计."""
        path = Path(self.data_dir) / "design" / "level_designs.jsonl"
        return _read_jsonl(path, limit)

    def list_economy_balances(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有经济平衡."""
        path = Path(self.data_dir) / "design" / "economy_balances.jsonl"
        return _read_jsonl(path, limit)

    def list_system_specs(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有系统规格."""
        path = Path(self.data_dir) / "design" / "system_specs.jsonl"
        return _read_jsonl(path, limit)

    def list_difficulty_curves(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有难度曲线."""
        path = Path(self.data_dir) / "design" / "difficulty_curves.jsonl"
        return _read_jsonl(path, limit)

    def list_design_documents(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有设计文档."""
        path = Path(self.data_dir) / "design" / "design_documents.jsonl"
        return _read_jsonl(path, limit)

    def get_design_document(self, document_id: str) -> dict[str, Any] | None:
        """获取单个设计文档."""
        for doc in self.list_design_documents(limit=500):
            if doc.get("document_id") == document_id:
                return doc
        return None

    def get_stats(self) -> dict[str, Any]:
        """设计统计概览."""
        level_designs = self.list_level_designs(limit=1000)
        economy_balances = self.list_economy_balances(limit=1000)
        system_specs = self.list_system_specs(limit=1000)
        difficulty_curves = self.list_difficulty_curves(limit=1000)
        design_docs = self.list_design_documents(limit=1000)

        genre_dist: dict[str, int] = {}
        for d in level_designs:
            g = d.get("genre", "unknown")
            genre_dist[g] = genre_dist.get(g, 0) + 1

        ready_count = sum(1 for d in design_docs if d.get("ready_for_dev"))

        return {
            "total_level_designs": len(level_designs),
            "total_economy_balances": len(economy_balances),
            "total_system_specs": len(system_specs),
            "total_difficulty_curves": len(difficulty_curves),
            "total_design_documents": len(design_docs),
            "ready_for_dev_count": ready_count,
            "genre_distribution": genre_dist,
            "recent_documents": design_docs[:5],
        }

    # ── 内部方法 ─────────────────────────────────────────────

    def _generate_level_objective(self, genre: str, level: int, difficulty: str) -> str:
        """生成关卡目标描述."""
        if genre == "Merge":
            objectives = [
                "合并指定物品达到目标等级",
                "在限定步数内完成合并",
                "收集 N 个指定物品",
                "清除棋盘障碍物",
            ]
        elif genre == "Match3":
            objectives = [
                "达到目标分数",
                "收集指定颜色方块",
                "清除冰块/果冻",
                "在限定步数内通关",
            ]
        elif genre == "Simulation":
            objectives = [
                "建造指定建筑",
                "达到目标收入",
                "招募 N 个角色",
                "完成经营目标",
            ]
        else:
            objectives = ["完成关卡目标"]

        idx = (level - 1) % len(objectives)
        return f"{objectives[idx]} ({difficulty})"

    def _get_chapter_theme(self, genre: str, chapter: int, total_chapters: int) -> str:
        """生成章节主题."""
        if genre == "Merge":
            themes = ["花园", "厨房", "客厅", "卧室", "阁楼", "庭院", "地下室", "阳台", "书房", "车库"]
        elif genre == "Match3":
            themes = ["糖果森林", "冰雪山脉", "火焰峡谷", "水晶洞穴", "天空之城",
                      "深海王国", "沙漠绿洲", "暗夜古堡", "彩虹桥梁", "星辰之巅"]
        elif genre == "Simulation":
            themes = ["小镇起步", "商业街区", "工业园区", "科技园区", "港口码头",
                      "文化中心", "旅游胜地", "金融中心", "创新基地", "未来都市"]
        else:
            themes = [f"章节 {chapter}"]

        idx = (chapter - 1) % len(themes)
        return themes[idx]

    def _load_gdd(self, gdd_id: str) -> dict[str, Any] | None:
        """加载 GDD — 从 product/gdds.jsonl 读取."""
        gdd_path = Path(self.data_dir) / "product" / "gdds.jsonl"
        if not gdd_path.exists():
            return None
        try:
            text = gdd_path.read_text(encoding="utf-8")
        except OSError:
            return None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("gdd_id") == gdd_id:
                    return record
            except json.JSONDecodeError:
                continue
        return None

    # ── 持久化 ─────────────────────────────────────────────

    def _persist_level_design(self, design: LevelDesign) -> None:
        path = Path(self.data_dir) / "design" / "level_designs.jsonl"
        _append_jsonl(path, design.to_dict())

    def _persist_economy_balance(self, balance: EconomyBalance) -> None:
        path = Path(self.data_dir) / "design" / "economy_balances.jsonl"
        _append_jsonl(path, balance.to_dict())

    def _persist_system_specs(self, gdd_id: str, systems: list[SystemSpecification]) -> None:
        path = Path(self.data_dir) / "design" / "system_specs.jsonl"
        record = {
            "gdd_id": gdd_id,
            "systems": [s.to_dict() for s in systems],
            "created_at": _now_iso(),
        }
        _append_jsonl(path, record)

    def _persist_difficulty_curve(self, curve: DifficultyCurve) -> None:
        path = Path(self.data_dir) / "design" / "difficulty_curves.jsonl"
        _append_jsonl(path, curve.to_dict())

    def _persist_design_document(self, doc: DesignDocument) -> None:
        path = Path(self.data_dir) / "design" / "design_documents.jsonl"
        _append_jsonl(path, doc.to_dict())

    # ── 跨 Agent 协同 ──────────────────────────────────────

    def _broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """通过 MessageBus 广播设计事件."""
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
                subject=f"design:{event_type}",
                body={"event_type": event_type, "source_agent": "designer", **payload},
                priority=MessagePriority.NORMAL,
                ttl_seconds=600.0,
            )
            self._message_bus.send(message)
        except Exception as exc:
            logger.warning("GameDesignerAgent broadcast event failed: %s", exc)

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
