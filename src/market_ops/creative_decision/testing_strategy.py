"""Module 8: Testing Strategy Generator

自动生成 A/B Test 方案。
保证一次只改一个变量。
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ABTestCell:
    cell_id: str                        # e.g. "A", "B"
    variant_id: str
    changed_dimension: str
    changed_value: str
    budget_usd: float = 0.0
    placement: str = ""


@dataclass
class AdSetPlan:
    adset_id: str
    adset_name: str
    target_audience: dict
    budget_usd: float = 0.0
    cells: list[ABTestCell] = field(default_factory=list)


@dataclass
class CampaignPlan:
    campaign_id: str
    campaign_name: str
    campaign_type: str
    objective: str
    total_budget_usd: float = 0.0
    adsets: list[AdSetPlan] = field(default_factory=list)


class TestingStrategyGenerator:
    """A/B 测试策略生成器
    
    核心原则：一次只改一个变量。
    
    测试分组策略：
    1. 按 changed_dimension 分组：
       - 所有 "creature_0_color" 的 variant 可以互相 A/B test
       - 所有 "environment_type" 的 variant 可以互相 A/B test
    2. 每个 Campaign 测试同一维度的变体
    3. 每个 AdSet 包含 2-4 个 cell（A/B/C/D）
    4. 预算按 Score 比例分配
    
    输出格式：
    Campaign: "Dragon Color Test"
      AdSet A: "Blue vs Pink Dragon"
        Cell A: V001 (blue dragon)  $150
        Cell B: V002 (pink dragon)  $150
      AdSet B: "Blue vs Green Dragon"
        Cell A: V001 (blue dragon)  $100
        Cell C: V003 (green dragon) $100
    """

    def _get_changed_dimension(self, variant: dict) -> str:
        """获取 variant 的 changed_dimension，支持多层嵌套。"""
        dim = variant.get("changed_dimension", "")
        if dim:
            return dim
        # 尝试从 dna / features / test_info 读取
        for key in ("dna", "features", "test_info"):
            nested = variant.get(key, {})
            if isinstance(nested, dict):
                dim = nested.get("changed_dimension", "")
                if dim:
                    return dim
        return "unknown"

    def _get_changed_value(self, variant: dict) -> str:
        """获取 variant 的 changed_value。"""
        val = variant.get("changed_value", "")
        if val:
            return val
        for key in ("dna", "features", "test_info"):
            nested = variant.get(key, {})
            if isinstance(nested, dict):
                val = nested.get("changed_value", "")
                if val:
                    return val
        return "unknown"

    def _get_dimension_display_name(self, dim: str) -> str:
        """将维度 key 转换为可读名称。"""
        mapping = {
            "creature_type": "Creature",
            "creature_0_color": "Creature Color",
            "character_type": "Character",
            "background_type": "Background",
            "environment_type": "Environment",
            "hook_type": "Hook",
            "lighting_type": "Lighting",
            "color_theme": "Color Theme",
            "aspect_ratio": "Aspect Ratio",
            "pace": "Pace",
        }
        return mapping.get(dim, dim.replace("_", " ").title())

    def _group_by_dimension(self, variants: list[dict]) -> dict[str, list[dict]]:
        """按 changed_dimension 分组"""
        groups: dict[str, list[dict]] = {}
        for v in variants:
            dim = self._get_changed_dimension(v)
            groups.setdefault(dim, []).append(v)
        # 过滤掉 unknown 且只有一个元素的维度（无法做 A/B）
        filtered = {}
        for dim, members in groups.items():
            if dim == "unknown" and len(members) < 2:
                continue
            filtered[dim] = members
        return filtered

    def _create_adset_name(self, base_value: str, compare_value: str, dim_display: str) -> str:
        """生成 AdSet 名称。"""
        return f"{base_value} vs {compare_value} {dim_display}"

    def _create_campaign(self, dim: str, variants: list[dict], campaign_idx: int) -> CampaignPlan:
        """为单个维度创建 Campaign"""
        dim_display = self._get_dimension_display_name(dim)

        # 按 overall_score 降序
        sorted_variants = sorted(
            variants,
            key=lambda x: x.get("overall_score", 0.0),
            reverse=True,
        )

        # 获取基准 variant（分数最高者）
        base = sorted_variants[0]
        base_vid = base.get("variant_id", "")
        base_val = self._get_changed_value(base)

        # Campaign 名称
        first_creature = base.get("creature_type", base.get("dna", {}).get("creature_type", "Creative"))
        campaign_name = f"{first_creature} {dim_display} Test"

        # 构建 AdSets：每次拿 base 和一个对比 variant 组成 2-cell AdSet
        adsets: list[AdSetPlan] = []
        total_budget = 0.0

        for i, comp in enumerate(sorted_variants[1:], start=1):
            comp_vid = comp.get("variant_id", "")
            comp_val = self._get_changed_value(comp)

            adset_name = self._create_adset_name(base_val, comp_val, dim_display)
            adset_id = f"ADSET_{campaign_idx}_{i}"

            # 预算按 score 比例分配（每个 cell 最低 $50）
            base_score = base.get("overall_score", 60.0)
            comp_score = comp.get("overall_score", 60.0)
            sum_score = base_score + comp_score
            if sum_score <= 0:
                sum_score = 1.0
            base_budget = max(50.0, round(200.0 * base_score / sum_score, 2))
            comp_budget = max(50.0, round(200.0 * comp_score / sum_score, 2))

            cells = [
                ABTestCell(
                    cell_id="A",
                    variant_id=base_vid,
                    changed_dimension=dim,
                    changed_value=base_val,
                    budget_usd=base_budget,
                    placement="",
                ),
                ABTestCell(
                    cell_id="B",
                    variant_id=comp_vid,
                    changed_dimension=dim,
                    changed_value=comp_val,
                    budget_usd=comp_budget,
                    placement="",
                ),
            ]

            adset_budget = sum(c.budget_usd for c in cells)
            total_budget += adset_budget

            adsets.append(
                AdSetPlan(
                    adset_id=adset_id,
                    adset_name=adset_name,
                    target_audience={},
                    budget_usd=adset_budget,
                    cells=cells,
                )
            )

        return CampaignPlan(
            campaign_id=f"CAMP_{campaign_idx}",
            campaign_name=campaign_name,
            campaign_type="ASC",
            objective="INSTALL",
            total_budget_usd=round(total_budget, 2),
            adsets=adsets,
        )

    def generate_test_plan(self, top_variants: list[dict]) -> list[CampaignPlan]:
        """生成完整的 A/B 测试计划
        
        Args:
            top_variants: Decision Engine 选出的最终 Top N variants
        """
        if not top_variants:
            return []

        groups = self._group_by_dimension(top_variants)
        plans: list[CampaignPlan] = []

        for idx, (dim, variants) in enumerate(groups.items(), start=1):
            if len(variants) < 2:
                continue
            campaign = self._create_campaign(dim, variants, idx)
            if campaign.adsets:
                plans.append(campaign)

        return plans
