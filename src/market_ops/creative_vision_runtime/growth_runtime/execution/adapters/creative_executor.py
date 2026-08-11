"""E13.7 Creative Executor — 创意生产执行器.

连接 E11 Creative Evolution 和外部创意生产平台 (Lovart 等)，
实现创意 DNA → 素材生成 → 上传 → 投放的完整链路。

支持的动作:
  - CREATE_CREATIVE: 创建新素材 (DNA → Asset)
  - MUTATE_CREATIVE: 素材变异 (DNA Mutation → New Asset)
  - UPLOAD_CREATIVE: 上传素材到平台
  - PAUSE_CREATIVE: 暂停素材

核心流程:
  CreativeDNA → Creative Hypothesis → Asset Generation → Platform Upload → Ad Creation

连接:
  E11 Creative Evolution → E13.7 CreativeExecutor → Lovart → MetaUpload
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..base_executor import (
    BaseExecutor,
    ExecutionResult,
    ExecutionResultStatus,
    GuardContext,
)
from ..models import ExecutionAction, ExecutionActionType, ExecutionDomain
from .adapter_models import (
    APIRequest,
    APIResponse,
    AdapterMetrics,
    ExecutionMode,
    PlatformType,
    RealExecutionResult,
)


# ═══════════════════════════════════════════════════════════════
# Creative Asset
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeAsset:
    """创意素材 — 生成后的素材实体.

    Attributes:
        asset_id: 素材唯一标识
        dna_id: 关联的 Creative DNA ID
        hypothesis_id: 关联的创意假设 ID
        name: 素材名称
        asset_type: 素材类型 (VIDEO / IMAGE / CAROUSEL)
        format: 格式 (mp4 / jpg / png)
        resolution: 分辨率
        duration_seconds: 时长
        file_size_bytes: 文件大小
        video_url: 视频 URL
        thumbnail_url: 缩略图 URL
        tags: 标签
        generation: 代数
        parent_asset_id: 父素材 ID (变异来源)
        metadata: 扩展元数据
    """
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dna_id: str = ""
    hypothesis_id: str = ""
    name: str = ""
    asset_type: str = "VIDEO"
    format: str = "mp4"
    resolution: str = "1080x1920"
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    video_url: str = ""
    thumbnail_url: str = ""
    tags: list[str] = field(default_factory=list)
    generation: int = 1
    parent_asset_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "dna_id": self.dna_id,
            "hypothesis_id": self.hypothesis_id,
            "name": self.name,
            "asset_type": self.asset_type,
            "format": self.format,
            "resolution": self.resolution,
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "tags": self.tags,
            "generation": self.generation,
            "parent_asset_id": self.parent_asset_id,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Creative Generation Client
# ═══════════════════════════════════════════════════════════════


class CreativeGenerationClient:
    """创意生成客户端 — 封装外部创意平台的调用.

    支持模式:
      - mock: 返回模拟素材数据
      - real: 调用 Lovart / internal pipeline
    """

    def __init__(self, use_mock: bool = True, api_endpoint: str = ""):
        self._use_mock = use_mock
        self._api_endpoint = api_endpoint
        self._generation_count: int = 0

    def generate_asset(
        self,
        dna_id: str,
        name: str,
        asset_type: str = "VIDEO",
        hypothesis_id: str = "",
        generation: int = 1,
        parent_asset_id: str = "",
        specs: dict[str, Any] | None = None,
    ) -> CreativeAsset:
        """生成创意素材.

        Args:
            dna_id: Creative DNA ID
            name: 素材名称
            asset_type: 素材类型
            hypothesis_id: 创意假设 ID
            generation: 代数
            parent_asset_id: 父素材 ID
            specs: 生成规格

        Returns:
            CreativeAsset: 生成的素材
        """
        self._generation_count += 1

        if self._use_mock:
            return self._mock_generate(
                dna_id, name, asset_type, hypothesis_id, generation, parent_asset_id
            )

        # In production: call Lovart or internal pipeline
        return self._mock_generate(
            dna_id, name, asset_type, hypothesis_id, generation, parent_asset_id
        )

    def mutate_asset(
        self,
        parent_asset: CreativeAsset,
        mutation_params: dict[str, Any],
    ) -> CreativeAsset:
        """变异素材 — 基于父素材生成变体.

        Args:
            parent_asset: 父素材
            mutation_params: 变异参数 (基因调整)

        Returns:
            CreativeAsset: 变异后的素材
        """
        self._generation_count += 1

        if self._use_mock:
            return self._mock_generate(
                dna_id=parent_asset.dna_id,
                name=f"{parent_asset.name}_M{parent_asset.generation + 1}",
                asset_type=parent_asset.asset_type,
                hypothesis_id=parent_asset.hypothesis_id,
                generation=parent_asset.generation + 1,
                parent_asset_id=parent_asset.asset_id,
            )

        return self._mock_generate(
            dna_id=parent_asset.dna_id,
            name=f"{parent_asset.name}_M{parent_asset.generation + 1}",
            asset_type=parent_asset.asset_type,
            hypothesis_id=parent_asset.hypothesis_id,
            generation=parent_asset.generation + 1,
            parent_asset_id=parent_asset.asset_id,
        )

    def _mock_generate(
        self,
        dna_id: str,
        name: str,
        asset_type: str,
        hypothesis_id: str,
        generation: int,
        parent_asset_id: str,
    ) -> CreativeAsset:
        """生成模拟素材."""
        asset_id = f"ca_{uuid.uuid4().hex[:12]}"
        return CreativeAsset(
            asset_id=asset_id,
            dna_id=dna_id,
            hypothesis_id=hypothesis_id,
            name=name,
            asset_type=asset_type,
            format="mp4" if asset_type == "VIDEO" else "jpg",
            resolution="1080x1920",
            duration_seconds=30.0 if asset_type == "VIDEO" else 0.0,
            file_size_bytes=5_000_000,
            video_url=f"https://cdn.example.com/creatives/{asset_id}.mp4",
            thumbnail_url=f"https://cdn.example.com/creatives/{asset_id}_thumb.jpg",
            tags=["ai_generated", f"gen_{generation}"],
            generation=generation,
            parent_asset_id=parent_asset_id,
            metadata={
                "dna_id": dna_id,
                "hypothesis_id": hypothesis_id,
                "generation_method": "mock",
            },
        )

    @property
    def generation_count(self) -> int:
        return self._generation_count


# ═══════════════════════════════════════════════════════════════
# Creative Executor
# ═══════════════════════════════════════════════════════════════


class CreativeExecutor(BaseExecutor):
    """创意执行器 — 管理创意生命周期.

    用法:
        gen_client = CreativeGenerationClient(use_mock=True)
        executor = CreativeExecutor(generation_client=gen_client, mode=ExecutionMode.MOCK)
        result = executor.execute(action, guard_context)
    """

    SUPPORTED_ACTIONS = {
        ExecutionActionType.CREATE_CREATIVE,
        ExecutionActionType.MUTATE_CREATIVE,
        ExecutionActionType.UPLOAD_CREATIVE,
        ExecutionActionType.PAUSE_CREATIVE,
    }

    def __init__(
        self,
        generation_client: CreativeGenerationClient | None = None,
        upload_client: Any = None,
        mode: ExecutionMode = ExecutionMode.MOCK,
        name: str = "CreativeExecutor",
    ):
        super().__init__(name=name)
        self._gen_client = generation_client or CreativeGenerationClient(use_mock=True)
        self._upload_client = upload_client
        self._mode = mode
        self._metrics = AdapterMetrics(
            adapter_name=name,
            platform=PlatformType.INTERNAL,
        )
        self._asset_registry: dict[str, CreativeAsset] = {}

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @mode.setter
    def mode(self, value: ExecutionMode) -> None:
        self._mode = value

    @property
    def metrics(self) -> AdapterMetrics:
        return self._metrics

    # ── 主执行逻辑 ────────────────────────────────────────────

    def _do_execute(
        self,
        action: ExecutionAction,
        guard_context: GuardContext,
    ) -> ExecutionResult:
        """执行创意动作."""
        action_type = action.action_type

        if action_type not in self.SUPPORTED_ACTIONS:
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action_type,
                status=ExecutionResultStatus.SKIPPED,
                executor=self._name,
                reason=f"unsupported_action: {action_type.value}",
            )

        if self._mode == ExecutionMode.DRY_RUN:
            return self._dry_run(action)

        try:
            if action_type == ExecutionActionType.CREATE_CREATIVE:
                asset = self._create_creative(action)
            elif action_type == ExecutionActionType.MUTATE_CREATIVE:
                asset = self._mutate_creative(action)
            elif action_type == ExecutionActionType.UPLOAD_CREATIVE:
                asset = self._upload_creative(action)
            elif action_type == ExecutionActionType.PAUSE_CREATIVE:
                return self._pause_creative(action)
            else:
                return ExecutionResult(
                    action_id=action.action_id,
                    action_type=action_type,
                    status=ExecutionResultStatus.FAILED,
                    executor=self._name,
                    error_message=f"unknown_action: {action_type}",
                )

            return ExecutionResult(
                action_id=action.action_id,
                action_type=action_type,
                status=ExecutionResultStatus.SUCCESS,
                executor=self._name,
                before=action.parameters,
                after=asset.to_dict(),
                reason=f"creative_{action_type.value}",
                confidence=guard_context.confidence,
                metadata={
                    "asset_id": asset.asset_id,
                    "dna_id": asset.dna_id,
                    "generation": asset.generation,
                    "mode": self._mode.value,
                },
            )

        except Exception as e:
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action_type,
                status=ExecutionResultStatus.FAILED,
                executor=self._name,
                error_message=str(e),
            )

    # ── 创意创建 ──────────────────────────────────────────────

    def _create_creative(self, action: ExecutionAction) -> CreativeAsset:
        """创建新素材."""
        params = action.parameters
        asset = self._gen_client.generate_asset(
            dna_id=params.get("dna_id", ""),
            name=params.get("name", "AI Creative"),
            asset_type=params.get("asset_type", "VIDEO"),
            hypothesis_id=params.get("hypothesis_id", ""),
            generation=1,
            specs=params.get("specs"),
        )
        self._asset_registry[asset.asset_id] = asset
        return asset

    def _mutate_creative(self, action: ExecutionAction) -> CreativeAsset:
        """变异素材."""
        params = action.parameters
        parent_asset_id = params.get("parent_asset_id", action.target_entity)

        # 查找父素材
        parent = self._asset_registry.get(parent_asset_id)
        if not parent:
            parent = CreativeAsset(asset_id=parent_asset_id)

        asset = self._gen_client.mutate_asset(
            parent_asset=parent,
            mutation_params=params.get("mutation_params", {}),
        )
        self._asset_registry[asset.asset_id] = asset
        return asset

    def _upload_creative(self, action: ExecutionAction) -> CreativeAsset:
        """上传素材到平台."""
        params = action.parameters
        asset_id = params.get("asset_id", action.target_entity)

        asset = self._asset_registry.get(asset_id)
        if not asset:
            asset = CreativeAsset(
                asset_id=asset_id,
                name=params.get("name", "Uploaded Creative"),
                video_url=params.get("video_url", ""),
            )

        # 如果有上传客户端，执行真实上传
        if self._upload_client:
            # self._upload_client.upload(asset)
            pass

        asset.metadata["uploaded"] = True
        asset.metadata["uploaded_at"] = datetime.now(timezone.utc).isoformat()
        return asset

    def _pause_creative(self, action: ExecutionAction) -> ExecutionResult:
        """暂停素材."""
        asset_id = action.target_entity
        if asset_id in self._asset_registry:
            self._asset_registry[asset_id].metadata["paused"] = True
            self._asset_registry[asset_id].metadata["paused_at"] = datetime.now(timezone.utc).isoformat()

        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ExecutionResultStatus.SUCCESS,
            executor=self._name,
            reason=f"creative_paused: {asset_id}",
        )

    # ── 干运行 ────────────────────────────────────────────────

    def _dry_run(self, action: ExecutionAction) -> ExecutionResult:
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ExecutionResultStatus.SUCCESS,
            executor=self._name,
            reason=f"dry_run_{action.action_type.value}",
            metadata={"mode": "dry_run", "would_execute": True},
        )

    # ── 回滚 ──────────────────────────────────────────────────

    def _rollback(self, action: ExecutionAction) -> ExecutionResult:
        action_type = action.action_type

        if action_type in {ExecutionActionType.CREATE_CREATIVE, ExecutionActionType.MUTATE_CREATIVE}:
            # 回滚: 删除生成的素材
            asset_id = action.metadata.get("asset_id", "")
            if asset_id and asset_id in self._asset_registry:
                self._asset_registry[asset_id].metadata["rolled_back"] = True
                self._asset_registry[asset_id].metadata["rolled_back_at"] = datetime.now(timezone.utc).isoformat()

            return ExecutionResult(
                action_id=action.action_id,
                action_type=action_type,
                status=ExecutionResultStatus.ROLLED_BACK,
                executor=self._name,
                reason=f"rollback: marked asset {asset_id} as rolled_back",
            )

        return ExecutionResult(
            action_id=action.action_id,
            action_type=action_type,
            status=ExecutionResultStatus.ROLLED_BACK,
            executor=self._name,
            reason="rollback: creative rollback",
        )

    # ── 查询 ──────────────────────────────────────────────────

    def get_asset(self, asset_id: str) -> CreativeAsset | None:
        return self._asset_registry.get(asset_id)

    def get_assets_by_dna(self, dna_id: str) -> list[CreativeAsset]:
        return [a for a in self._asset_registry.values() if a.dna_id == dna_id]

    def get_assets_by_generation(self, generation: int) -> list[CreativeAsset]:
        return [a for a in self._asset_registry.values() if a.generation == generation]

    def get_asset_registry(self) -> dict[str, CreativeAsset]:
        return dict(self._asset_registry)

    def clear_registry(self) -> None:
        self._asset_registry.clear()