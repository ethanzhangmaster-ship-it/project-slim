"""E13.3.3 Creative Executor — 创意机会 → 执行动作映射.

规则:
  - CREATIVE_SCALE → CLONE_DNA + GENERATE_VARIANTS + LAUNCH_AB_TEST
  - CREATIVE_REFRESH → MUTATE_HOOK + MUTATE_VISUAL + CREATE_POPULATION + REPLACE_CREATIVE
  - CREATIVE_MUTATION → MUTATE_HOOK + MUTATE_VISUAL + CREATE_POPULATION

连接 E11:
  - CLONE_DNA → E11 Evolution Integration Engine
  - MUTATE_HOOK → E11 Mutation Operator
  - CREATE_POPULATION → E11 Population Manager
  - LAUNCH_AB_TEST → E11 Evolution Orchestrator
"""

from __future__ import annotations

from typing import Any

from ..models import (
    ApprovalLevel,
    ExecutionAction,
    ExecutionActionType,
    GrowthOpportunity,
    OpportunityPriority,
    OpportunityType,
)


class CreativeExecutor:
    """创意执行器 — 将创意机会转换为可执行的创意操作.

    对接 E11 Creative Evolution Engine:
      - CLONE_DNA → EvolutionIntegrationEngine
      - MUTATE_HOOK/VISUAL → MutationOperator
      - CREATE_POPULATION → GenomeManager
      - LAUNCH_AB_TEST → EvolutionOrchestrator
    """

    def execute(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        """将创意机会转换为执行动作列表.

        Args:
            opportunity: 创意类 GrowthOpportunity

        Returns:
            list[ExecutionAction]: 可执行的创意操作列表
        """
        if opportunity.opportunity_type == OpportunityType.CREATIVE_SCALE:
            return self._execute_scale(opportunity)
        elif opportunity.opportunity_type == OpportunityType.CREATIVE_REFRESH:
            return self._execute_refresh(opportunity)
        elif opportunity.opportunity_type == OpportunityType.CREATIVE_MUTATION:
            return self._execute_mutation(opportunity)
        return []

    # ═══════════════════════════════════════════════════════════
    # Creative Scale → Clone DNA + Generate Variants + AB Test
    # ═══════════════════════════════════════════════════════════

    def _execute_scale(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        actions: list[ExecutionAction] = []

        params = opportunity.recommended_params
        entity_id = opportunity.entity_id
        opp_id = opportunity.opportunity_id

        # Action 1: Clone winning DNA
        clone_action = ExecutionAction(
            action_type=ExecutionActionType.CLONE_DNA,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=opportunity.priority,
            confidence=opportunity.confidence,
            params={
                "source_creative_id": entity_id,
                "clone_hook": True,
                "clone_visual": True,
                "clone_gameplay": True,
                "preserve_psychological_mechanism": True,
            },
            approval_level=ApprovalLevel.AUTO,
            expected_impact=f"Clone winning DNA from {entity_id} for scaling",
            rollback_action=ExecutionActionType.REPLACE_CREATIVE,
            explanation=f"Clone the DNA of winner creative {entity_id} to create scalable variants.",
        )
        actions.append(clone_action)

        # Action 2: Generate variants
        variant_count = params.get("mutation_count", 5)
        generate_action = ExecutionAction(
            action_type=ExecutionActionType.GENERATE_VARIANTS,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=opportunity.priority,
            confidence=opportunity.confidence * 0.9,
            params={
                "source_creative_id": entity_id,
                "variant_count": variant_count,
                "mutation_rate": 0.15,
                "preserve_core_hook": True,
                "scale_factor": params.get("scale_factor", 1.5),
            },
            approval_level=ApprovalLevel.AUTO,
            expected_impact=f"Generate {variant_count} variants from winner DNA",
            rollback_action=ExecutionActionType.REPLACE_CREATIVE,
            explanation=f"Generate {variant_count} creative variants by mutating the winning DNA "
                        f"with low mutation rate to preserve winning characteristics.",
        )
        actions.append(generate_action)

        # Action 3: Launch AB test
        test_budget = params.get("test_budget", 500)
        ab_action = ExecutionAction(
            action_type=ExecutionActionType.LAUNCH_AB_TEST,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=opportunity.priority,
            confidence=opportunity.confidence * 0.85,
            params={
                "control_creative_id": entity_id,
                "variant_count": variant_count,
                "test_budget": test_budget,
                "test_duration_hours": 72,
                "success_metric": "d30_roas",
                "min_confidence": 0.9,
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"AB test {variant_count} variants with ${test_budget:.0f} budget",
            rollback_action=ExecutionActionType.REPLACE_CREATIVE,
            explanation=f"Launch AB test comparing {variant_count} variants against "
                        f"original {entity_id} with ${test_budget:.0f} test budget.",
        )
        actions.append(ab_action)

        return actions

    # ═══════════════════════════════════════════════════════════
    # Creative Refresh → Mutate Hook + Visual + Population + Replace
    # ═══════════════════════════════════════════════════════════

    def _execute_refresh(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        actions: list[ExecutionAction] = []

        params = opportunity.recommended_params
        entity_id = opportunity.entity_id
        opp_id = opportunity.opportunity_id

        # Action 1: Mutate Hook
        hook_delta = params.get("hook_contrast_delta", 0.20)
        mutate_hook_action = ExecutionAction(
            action_type=ExecutionActionType.MUTATE_HOOK,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=opportunity.priority,
            confidence=opportunity.confidence,
            params={
                "source_creative_id": entity_id,
                "hook_contrast_delta": hook_delta,
                "reward_speed_delta": params.get("reward_speed_delta", 0.15),
                "mutation_strategy": "contrast_boost",
                "preserve_core_mechanism": True,
            },
            approval_level=ApprovalLevel.AUTO,
            expected_impact=f"Boost hook contrast by +{hook_delta*100:.0f}%",
            rollback_action=ExecutionActionType.REPLACE_CREATIVE,
            explanation=f"Mutate hook of fatigued creative {entity_id}: "
                        f"increase contrast by +{hook_delta*100:.0f}%, "
                        f"boost reward speed by +{params.get('reward_speed_delta', 0.15)*100:.0f}%.",
        )
        actions.append(mutate_hook_action)

        # Action 2: Mutate Visual Style
        visual_delta = params.get("visual_density_delta", 0.10)
        mutate_visual_action = ExecutionAction(
            action_type=ExecutionActionType.MUTATE_VISUAL,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=opportunity.priority,
            confidence=opportunity.confidence * 0.9,
            params={
                "source_creative_id": entity_id,
                "visual_density_delta": visual_delta,
                "color_palette_shift": True,
                "camera_angle_variation": True,
                "mutation_strategy": "visual_freshness",
            },
            approval_level=ApprovalLevel.AUTO,
            expected_impact=f"Refresh visual style: density +{visual_delta*100:.0f}%",
            rollback_action=ExecutionActionType.REPLACE_CREATIVE,
            explanation=f"Refresh visual style of fatigued creative {entity_id}: "
                        f"increase visual density by +{visual_delta*100:.0f}%, "
                        f"shift color palette and camera angles.",
        )
        actions.append(mutate_visual_action)

        # Action 3: Create Population
        pop_size = params.get("population_size", 6)
        create_pop_action = ExecutionAction(
            action_type=ExecutionActionType.CREATE_POPULATION,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=OpportunityPriority.MEDIUM,
            confidence=opportunity.confidence * 0.8,
            params={
                "source_creative_id": entity_id,
                "population_size": pop_size,
                "generation": 1,
                "parent_lineage": entity_id,
                "mutation_weights": {
                    "hook": 0.6,
                    "visual": 0.4,
                },
            },
            approval_level=ApprovalLevel.AUTO,
            expected_impact=f"Create new population of {pop_size} genomes",
            rollback_action=None,
            explanation=f"Create a new population of {pop_size} creative genomes "
                        f"from mutated {entity_id} DNA.",
        )
        actions.append(create_pop_action)

        # Action 4: Replace Creative
        replace_action = ExecutionAction(
            action_type=ExecutionActionType.REPLACE_CREATIVE,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=opportunity.priority,
            confidence=opportunity.confidence * 0.75,
            params={
                "fatigued_creative_id": entity_id,
                "replacement_strategy": "gradual",
                "transition_period_hours": 24,
                "keep_original_as_control": True,
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"Replace fatigued creative {entity_id} with fresh variants",
            rollback_action=None,
            explanation=f"Schedule gradual replacement of fatigued creative {entity_id} "
                        f"over 24h transition period, keeping original as control.",
        )
        actions.append(replace_action)

        return actions

    # ═══════════════════════════════════════════════════════════
    # Creative Mutation → Mutate Hook + Visual + Population
    # ═══════════════════════════════════════════════════════════

    def _execute_mutation(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        actions: list[ExecutionAction] = []

        params = opportunity.recommended_params
        entity_id = opportunity.entity_id
        opp_id = opportunity.opportunity_id
        mutation_rate = params.get("mutation_rate", 0.25)

        # Action 1: Mutate Hook
        mutate_hook_action = ExecutionAction(
            action_type=ExecutionActionType.MUTATE_HOOK,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=opportunity.priority,
            confidence=opportunity.confidence,
            params={
                "source_creative_id": entity_id,
                "mutation_rate": mutation_rate,
                "hook_mutation_weight": params.get("hook_mutation_weight", 0.6),
                "mutation_strategy": "deep_exploration",
            },
            approval_level=ApprovalLevel.AUTO,
            expected_impact=f"Deep mutation of hook at rate {mutation_rate*100:.0f}%",
            rollback_action=ExecutionActionType.REPLACE_CREATIVE,
            explanation=f"Apply deep mutation to hook of {entity_id} "
                        f"at {mutation_rate*100:.0f}% rate for exploration.",
        )
        actions.append(mutate_hook_action)

        # Action 2: Mutate Visual Style
        mutate_visual_action = ExecutionAction(
            action_type=ExecutionActionType.MUTATE_VISUAL,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=opportunity.priority,
            confidence=opportunity.confidence * 0.85,
            params={
                "source_creative_id": entity_id,
                "mutation_rate": mutation_rate,
                "visual_mutation_weight": params.get("visual_mutation_weight", 0.4),
                "mutation_strategy": "deep_exploration",
            },
            approval_level=ApprovalLevel.AUTO,
            expected_impact=f"Deep mutation of visual style at rate {mutation_rate*100:.0f}%",
            rollback_action=ExecutionActionType.REPLACE_CREATIVE,
            explanation=f"Apply deep mutation to visual style of {entity_id} "
                        f"at {mutation_rate*100:.0f}% rate for exploration.",
        )
        actions.append(mutate_visual_action)

        # Action 3: Create Population
        pop_size = params.get("population_size", 5)
        create_pop_action = ExecutionAction(
            action_type=ExecutionActionType.CREATE_POPULATION,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="creative",
            priority=OpportunityPriority.MEDIUM,
            confidence=opportunity.confidence * 0.75,
            params={
                "source_creative_id": entity_id,
                "population_size": pop_size,
                "generation": 1,
                "parent_lineage": entity_id,
                "mutation_rate": mutation_rate,
            },
            approval_level=ApprovalLevel.AUTO,
            expected_impact=f"Create mutation population of {pop_size} genomes",
            rollback_action=None,
            explanation=f"Create a mutation population of {pop_size} genomes "
                        f"from mutated {entity_id} DNA at {mutation_rate*100:.0f}% rate.",
        )
        actions.append(create_pop_action)

        return actions