"""E15.0.9 Creative Adapter — 创意平台适配器.

连接 E11 Creative Evolution Engine，将 GrowthAction 转换为创意生成/变异操作。

支持:
  - GENERATE_CREATIVE: 从 Creative DNA 生成新素材
  - MUTATE_CREATIVE:   对现有素材进行变异

Phase 2: Mock 实现 (模拟创意生成)
Phase 3: 连接 Lovart API / Creative Evolution Engine
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..adapter_base import (
    AdapterExecutionResult,
    ExecutionAdapter,
)
from ..growth_action import ActionType, GrowthAction


class CreativeAdapter(ExecutionAdapter):
    """创意平台适配器 — 连接 E11 Creative Evolution.

    支持的 ActionType:
      - GENERATE_CREATIVE
      - MUTATE_CREATIVE

    用法:
        adapter = CreativeAdapter()
        result = adapter.execute(action)
    """

    SUPPORTED_ACTIONS: set[ActionType] = {
        ActionType.GENERATE_CREATIVE,
        ActionType.MUTATE_CREATIVE,
    }

    def __init__(
        self,
        name: str = "CreativeAdapter",
    ):
        super().__init__(name=name)
        self._generated_assets: list[dict[str, Any]] = []
        self._mutated_assets: list[dict[str, Any]] = []

    # ── Execute ───────────────────────────────────────────────

    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        """执行创意动作."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            self._record_failure()
            return AdapterExecutionResult.failure_result(
                action,
                error=f"Unsupported action: {action.action_type.value}",
                adapter_name=self._name,
            )

        try:
            if action.action_type == ActionType.GENERATE_CREATIVE:
                return self._generate_creative(action)
            elif action.action_type == ActionType.MUTATE_CREATIVE:
                return self._mutate_creative(action)
            else:
                return AdapterExecutionResult.failure_result(
                    action, error=f"Unhandled action: {action.action_type.value}",
                    adapter_name=self._name,
                )
        except Exception as e:
            self._record_failure()
            return AdapterExecutionResult.failure_result(
                action, error=str(e), adapter_name=self._name,
            )

    # ── Validate ──────────────────────────────────────────────

    def validate(self, action: GrowthAction) -> bool:
        """校验创意动作."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False

        if action.action_type == ActionType.GENERATE_CREATIVE:
            # 需要 creative_dna 或 hypothesis_id
            return (
                "creative_dna" in action.parameters
                or "hypothesis_id" in action.parameters
            )
        elif action.action_type == ActionType.MUTATE_CREATIVE:
            # 需要 source_creative_id
            return (
                "source_creative_id" in action.parameters
                and bool(action.parameters["source_creative_id"])
            )

        return True

    # ── Rollback ──────────────────────────────────────────────

    def rollback(
        self,
        action: GrowthAction,
        result: AdapterExecutionResult,
    ) -> AdapterExecutionResult:
        """回滚创意动作 — 删除生成的素材."""
        self._record_rollback()

        return AdapterExecutionResult.success_result(
            action,
            external_id=result.external_id,
            adapter_name=self._name,
            rollback_action="delete_asset",
            deleted_asset_id=result.external_id,
        )

    # ── Private: Action Handlers ──────────────────────────────

    def _generate_creative(self, action: GrowthAction) -> AdapterExecutionResult:
        creative_dna = action.parameters.get("creative_dna", {})
        hypothesis_id = action.parameters.get("hypothesis_id", "")
        asset_type = action.parameters.get("asset_type", "VIDEO")

        asset_id = f"creative_asset_{uuid.uuid4().hex[:12]}"
        asset = {
            "asset_id": asset_id,
            "game_id": action.game_id,
            "creative_dna": creative_dna,
            "hypothesis_id": hypothesis_id,
            "asset_type": asset_type,
            "format": "mp4" if asset_type == "VIDEO" else "jpg",
            "resolution": action.parameters.get("resolution", "1080x1920"),
            "duration_seconds": action.parameters.get("duration_seconds", 15),
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._generated_assets.append(asset)

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=asset_id,
            adapter_name=self._name,
            platform="creative",
            asset_type=asset_type,
            hypothesis_id=hypothesis_id,
        )

    def _mutate_creative(self, action: GrowthAction) -> AdapterExecutionResult:
        source_creative_id = action.parameters["source_creative_id"]
        mutation_type = action.parameters.get("mutation_type", "visual")
        mutation_params = action.parameters.get("mutation_params", {})

        mutated_id = f"creative_mutant_{uuid.uuid4().hex[:12]}"
        asset = {
            "asset_id": mutated_id,
            "game_id": action.game_id,
            "source_creative_id": source_creative_id,
            "mutation_type": mutation_type,
            "mutation_params": mutation_params,
            "status": "mutated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._mutated_assets.append(asset)

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=mutated_id,
            adapter_name=self._name,
            platform="creative",
            mutation_type=mutation_type,
            source_creative_id=source_creative_id,
        )

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        base = super().stats()
        base.update({
            "generated_assets": len(self._generated_assets),
            "mutated_assets": len(self._mutated_assets),
        })
        return base


__all__ = ["CreativeAdapter"]