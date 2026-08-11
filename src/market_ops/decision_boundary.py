"""AI / 规则 决策边界配置

显式声明：哪些决策由AI（模型/Bandit）决定，哪些由规则引擎决定。

设计目的：
- 避免 AI 和规则互相干扰
- 让每个决策域可独立调优
- 决策可审计（知道谁做了什么、为什么）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set


# ---------------------------------------------------------------------------
# Decision Domain
# ---------------------------------------------------------------------------

class DecisionDomain(str, Enum):
    """决策域归属"""
    AI = "ai"  # AI 决策：模型/Bandit/生成式AI
    RULE = "rule"  # 规则决策：显式 if-then 规则
    HYBRID = "hybrid"  # 混合：AI 建议 + 规则审核


class DecisionCategory(str, Enum):
    """决策类别"""
    # 创意类
    IMAGE_STYLE = "image_style"  # 图片风格
    IMAGE_COMPOSITION = "image_composition"  # 图片构图
    IMAGE_COLOR = "image_color"  # 图片配色
    PROMPT_GENERATION = "prompt_generation"  # Prompt 生成
    HEADLINE = "headline"  # 文案 Headline
    PRIMARY_TEXT = "primary_text"  # 文案 Primary Text
    DESCRIPTION = "description"  # 文案 Description
    CTA = "cta"  # 行动号召
    VIDEO_STYLE = "video_style"  # 视频风格

    # 投放类
    BUDGET_ALLOCATION = "budget_allocation"  # 预算分配
    BUDGET_CAP = "budget_cap"  # 预算上限
    BID_AMOUNT = "bid_amount"  # 出价金额
    PAUSE_DECISION = "pause_decision"  # 暂停决策
    KILL_DECISION = "kill_decision"  # 关停决策
    SCALE_UP = "scale_up"  # 扩大投放
    SCALE_DOWN = "scale_down"  # 缩减投放
    DUPLICATE = "duplicate"  # 复制广告

    # 定向类
    AUDIENCE_SELECTION = "audience_selection"  # 受众选择
    COUNTRY_SELECTION = "country_selection"  # 国家选择
    PLACEMENT = "placement"  # 版位选择
    TARGETING_EXPANSION = "targeting_expansion"  # 定向扩展

    # 策略类
    CAMPAIGN_STRUCTURE = "campaign_structure"  # ABO/CBO/ASC 选择
    OPTIMIZATION_GOAL = "optimization_goal"  # 优化目标
    ATTRIBUTION_WINDOW = "attribution_window"  # 归因窗口

    # 学习类
    WINNER_IDENTIFICATION = "winner_identification"  # 赢家识别
    LOSER_IDENTIFICATION = "loser_identification"  # 输家识别
    PATTERN_DISCOVERY = "pattern_discovery"  # 模式发现
    KNOWLEDGE_UPDATE = "knowledge_update"  # 知识库更新


# ---------------------------------------------------------------------------
# Boundary Config
# ---------------------------------------------------------------------------

@dataclass
class DomainAssignment:
    """单个决策的域归属"""
    category: DecisionCategory
    domain: DecisionDomain
    responsible_module: str  # 负责的模块
    reason: str  # 为什么归这个域
    override_conditions: List[str] = field(default_factory=list)  # 什么情况下可以被另一个域覆盖


class DecisionBoundary:
    """AI / 规则 决策边界

    声明每个决策的归属，以及 AI 和规则的交互方式。
    """

    # ── 核心边界声明 ──
    # AI 决定：创意内容（生成式AI + Bandit）
    # 规则决定：投放控制（预算、暂停、扩缩、关停）
    # 混合决定：策略选择（AI建议 + 规则审核）

    BOUNDARY: Dict[str, DomainAssignment] = {
        # === AI 域 - 创意内容 ===
        # AI 擅长生成创意内容，规则无法替代
        DecisionCategory.IMAGE_STYLE: DomainAssignment(
            category=DecisionCategory.IMAGE_STYLE,
            domain=DecisionDomain.AI,
            responsible_module="creative_strategy_matrix.py + creative_closed_loop.py",
            reason="图片风格是创意决策，AI/Bandit 通过素材表现反馈学习最佳风格",
            override_conditions=["合规要求（如某些国家禁止特定内容）"],
        ),
        DecisionCategory.IMAGE_COMPOSITION: DomainAssignment(
            category=DecisionCategory.IMAGE_COMPOSITION,
            domain=DecisionDomain.AI,
            responsible_module="creative_strategy_matrix.py + creative_dna.py",
            reason="构图是创意决策，AI 通过 DNA 分析和 Bandit 反馈学习最佳构图",
        ),
        DecisionCategory.IMAGE_COLOR: DomainAssignment(
            category=DecisionCategory.IMAGE_COLOR,
            domain=DecisionDomain.AI,
            responsible_module="creative_strategy_matrix.py + creative_dna.py",
            reason="配色是创意决策，不同国家/受众偏好不同，AI 通过数据学习",
        ),
        DecisionCategory.PROMPT_GENERATION: DomainAssignment(
            category=DecisionCategory.PROMPT_GENERATION,
            domain=DecisionDomain.AI,
            responsible_module="prompt_builder.py",
            reason="Prompt 生成是纯创意任务，由 AI 根据基因+变异生成",
        ),
        DecisionCategory.HEADLINE: DomainAssignment(
            category=DecisionCategory.HEADLINE,
            domain=DecisionDomain.AI,
            responsible_module="copy_generator.py",
            reason="文案 Headline 是创意内容，AI 根据 Hook/Emotion/Reward 生成多语言文案",
            override_conditions=["合规要求（如禁止使用特定词汇）"],
        ),
        DecisionCategory.PRIMARY_TEXT: DomainAssignment(
            category=DecisionCategory.PRIMARY_TEXT,
            domain=DecisionDomain.AI,
            responsible_module="copy_generator.py",
            reason="文案 Primary Text 是创意内容，AI 根据游戏类型/受众生成",
        ),
        DecisionCategory.DESCRIPTION: DomainAssignment(
            category=DecisionCategory.DESCRIPTION,
            domain=DecisionDomain.AI,
            responsible_module="copy_generator.py",
            reason="Description 是创意内容，AI 根据游戏类型生成",
        ),
        DecisionCategory.CTA: DomainAssignment(
            category=DecisionCategory.CTA,
            domain=DecisionDomain.AI,
            responsible_module="copy_generator.py",
            reason="CTA 文案是创意内容，AI 可根据变体策略选择不同CTA文案",
            override_conditions=["Facebook 平台限制（某些CTA类型需审批）"],
        ),
        DecisionCategory.VIDEO_STYLE: DomainAssignment(
            category=DecisionCategory.VIDEO_STYLE,
            domain=DecisionDomain.AI,
            responsible_module="video_generator.py (待实现)",
            reason="视频风格是创意决策，AI 根据素材表现反馈学习",
        ),

        # === 规则域 - 投放控制 ===
        # 规则适合处理有明确边界和风险控制的决策
        DecisionCategory.BUDGET_ALLOCATION: DomainAssignment(
            category=DecisionCategory.BUDGET_ALLOCATION,
            domain=DecisionDomain.RULE,
            responsible_module="final_bandit.py + distribution_controller.py",
            reason="预算分配需要三层保护（Budget Clamp + Exploration Floor + Kill-Switch），规则保证安全",
        ),
        DecisionCategory.BUDGET_CAP: DomainAssignment(
            category=DecisionCategory.BUDGET_CAP,
            domain=DecisionDomain.RULE,
            responsible_module="guarded_execution.py",
            reason="预算上限是风控决策，必须由规则严格控制，不能由AI自由决定",
        ),
        DecisionCategory.BID_AMOUNT: DomainAssignment(
            category=DecisionCategory.BID_AMOUNT,
            domain=DecisionDomain.RULE,
            responsible_module="campaign_strategy.py",
            reason="出价是资金风险决策，规则根据目标CPI和ROAS设定上限",
        ),
        DecisionCategory.PAUSE_DECISION: DomainAssignment(
            category=DecisionCategory.PAUSE_DECISION,
            domain=DecisionDomain.RULE,
            responsible_module="kpi_action_rulebook.py",
            reason="暂停是高风险决策，需要明确的规则触发（如ROAS过低），AI不能随意暂停",
        ),
        DecisionCategory.KILL_DECISION: DomainAssignment(
            category=DecisionCategory.KILL_DECISION,
            domain=DecisionDomain.RULE,
            responsible_module="kpi_action_rulebook.py + guarded_execution.py",
            reason="关停是最高风险决策，必须由规则明确触发，AI不能直接关停",
        ),
        DecisionCategory.SCALE_UP: DomainAssignment(
            category=DecisionCategory.SCALE_UP,
            domain=DecisionDomain.RULE,
            responsible_module="kpi_action_rulebook.py",
            reason="扩量需要规则审核（ROAS>2、CPI<目标），满足条件才允许，AI不能无限制扩量",
        ),
        DecisionCategory.SCALE_DOWN: DomainAssignment(
            category=DecisionCategory.SCALE_DOWN,
            domain=DecisionDomain.RULE,
            responsible_module="kpi_action_rulebook.py",
            reason="缩量由规则触发（ROAS下降、CPM飙升），AI不能随意缩量导致数据中断",
        ),
        DecisionCategory.DUPLICATE: DomainAssignment(
            category=DecisionCategory.DUPLICATE,
            domain=DecisionDomain.RULE,
            responsible_module="facebook_executor.py",
            reason="复制广告是工程操作，需要规则确认（源广告状态、预算容量），不是AI决策",
        ),

        # === 混合域 - 策略选择 ===
        # AI 提供建议，规则做最终审核
        DecisionCategory.CAMPAIGN_STRUCTURE: DomainAssignment(
            category=DecisionCategory.CAMPAIGN_STRUCTURE,
            domain=DecisionDomain.HYBRID,
            responsible_module="campaign_strategy.py",
            reason="ABO/CBO/ASC 选择：AI 根据历史数据建议，规则根据预算和风险审核",
            override_conditions=["预算<$500 → 规则强制ABO", "广告组>=3 → 规则推荐CBO"],
        ),
        DecisionCategory.AUDIENCE_SELECTION: DomainAssignment(
            category=DecisionCategory.AUDIENCE_SELECTION,
            domain=DecisionDomain.HYBRID,
            responsible_module="campaign_strategy.py + kpi_action_rulebook.py",
            reason="受众选择：AI 根据素材/游戏类型推荐，规则根据CPM和ROAS审核",
        ),
        DecisionCategory.COUNTRY_SELECTION: DomainAssignment(
            category=DecisionCategory.COUNTRY_SELECTION,
            domain=DecisionDomain.HYBRID,
            responsible_module="campaign_strategy.py + growth_priorities.py",
            reason="国家选择：AI根据增长优先级推荐，规则根据预算分配审核",
        ),
        DecisionCategory.PLACEMENT: DomainAssignment(
            category=DecisionCategory.PLACEMENT,
            domain=DecisionDomain.HYBRID,
            responsible_module="campaign_strategy.py",
            reason="版位选择：AI 根据游戏类型推荐，规则根据平台限制审核",
        ),
        DecisionCategory.WINNER_IDENTIFICATION: DomainAssignment(
            category=DecisionCategory.WINNER_IDENTIFICATION,
            domain=DecisionDomain.HYBRID,
            responsible_module="winner_engine.py + decision_engine.py",
            reason="赢家识别：AI（Bandit）根据统计显著性建议，规则根据最小样本量审核",
        ),
        DecisionCategory.LOSER_IDENTIFICATION: DomainAssignment(
            category=DecisionCategory.LOSER_IDENTIFICATION,
            domain=DecisionDomain.HYBRID,
            responsible_module="loser_engine.py + kpi_action_rulebook.py",
            reason="输家识别：AI 根据表现排序建议，规则根据最小花费和展示量审核",
        ),
        DecisionCategory.PATTERN_DISCOVERY: DomainAssignment(
            category=DecisionCategory.PATTERN_DISCOVERY,
            domain=DecisionDomain.AI,
            responsible_module="creative_dna.py + creative_clusters.py",
            reason="模式发现是纯AI任务，通过聚类和统计分析发现赢家模式",
        ),
        DecisionCategory.KNOWLEDGE_UPDATE: DomainAssignment(
            category=DecisionCategory.KNOWLEDGE_UPDATE,
            domain=DecisionDomain.AI,
            responsible_module="feedback_learning.py + learning_memory.py",
            reason="知识更新是AI学习任务，根据反馈数据更新知识库",
        ),
    }

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # 查询方法
    # ------------------------------------------------------------------

    def get_domain(self, category: DecisionCategory) -> DecisionDomain:
        """查询某个决策类别归属哪个域"""
        if category.value in self.BOUNDARY:
            return self.BOUNDARY[category.value].domain
        return DecisionDomain.HYBRID  # 默认混合

    def get_responsible_module(self, category: DecisionCategory) -> str:
        """查询负责模块"""
        if category.value in self.BOUNDARY:
            return self.BOUNDARY[category.value].responsible_module
        return "unknown"

    def is_ai_decision(self, category: DecisionCategory) -> bool:
        """是否完全由AI决策"""
        return self.get_domain(category) == DecisionDomain.AI

    def is_rule_decision(self, category: DecisionCategory) -> bool:
        """是否完全由规则决策"""
        return self.get_domain(category) == DecisionDomain.RULE

    def is_hybrid_decision(self, category: DecisionCategory) -> bool:
        """是否混合决策"""
        return self.get_domain(category) == DecisionDomain.HYBRID

    def get_ai_categories(self) -> List[DecisionCategory]:
        """获取所有AI域决策类别"""
        result = []
        for key, assignment in self.BOUNDARY.items():
            if assignment.domain == DecisionDomain.AI:
                try:
                    result.append(DecisionCategory(key))
                except ValueError:
                    pass
        return result

    def get_rule_categories(self) -> List[DecisionCategory]:
        """获取所有规则域决策类别"""
        result = []
        for key, assignment in self.BOUNDARY.items():
            if assignment.domain == DecisionDomain.RULE:
                try:
                    result.append(DecisionCategory(key))
                except ValueError:
                    pass
        return result

    def get_hybrid_categories(self) -> List[DecisionCategory]:
        """获取所有混合域决策类别"""
        result = []
        for key, assignment in self.BOUNDARY.items():
            if assignment.domain == DecisionDomain.HYBRID:
                try:
                    result.append(DecisionCategory(key))
                except ValueError:
                    pass
        return result

    def get_all_assignments(self) -> Dict[str, DomainAssignment]:
        """获取所有领域分配"""
        return dict(self.BOUNDARY)

    # ------------------------------------------------------------------
    # 审计方法
    # ------------------------------------------------------------------

    def audit_decision(self, category: DecisionCategory, actual_domain: DecisionDomain) -> Dict:
        """审计一个决策是否在正确的域中执行

        Returns:
            {
                "valid": bool,
                "expected_domain": DecisionDomain,
                "actual_domain": DecisionDomain,
                "message": str
            }
        """
        expected = self.get_domain(category)
        valid = expected == actual_domain
        return {
            "valid": valid,
            "expected_domain": expected,
            "actual_domain": actual_domain,
            "message": (
                f"OK: {category.value} 在 {expected.value} 域执行"
                if valid
                else f"WARNING: {category.value} 应在 {expected.value} 域执行，实际在 {actual_domain.value} 域"
            ),
        }

    def export_boundary_map(self) -> List[Dict]:
        """导出完整的边界映射表"""
        return [
            {
                "category": key,
                "domain": assignment.domain.value,
                "responsible_module": assignment.responsible_module,
                "reason": assignment.reason,
                "override_conditions": assignment.override_conditions,
            }
            for key, assignment in self.BOUNDARY.items()
        ]