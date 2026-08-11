"""Creative Mapping Engine — Delivery Bridge 交付桥接层 (v1.5).

将映射记录 (CreativeMappingRecord) 桥接到广告投放系统 (AdPublishingLayer)，
实现 Eagle 素材 → Facebook Ads 的正向交付闭环。

核心流程:
  1. 查询可投递记录 (MATCHED/REVIEW_APPROVED + UNDISPATCHED/FAILED)
  2. 解析 eagle_path → Publisher 可用的素材路径
  3. 调用 AdPublishingLayer.publish_to_meta() 执行投递 (dry_run 默认)
  4. 回写 publish_id / ad_id / ad_creative_id 到映射记录
  5. 更新 delivery_status，支持失败重试

安全规则 (对齐 p4_contract.md):
  - 默认 dry_run=True
  - 单次批量投递上限 MAX_DELIVERIES_PER_RUN=5
  - 连续 3 次失败触发 circuit breaker 暂停
  - 重试上限 5 次 (delivery_attempts >= 5 需人工介入)
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import CreativeMappingRecord, MappingDeliveryStatus, MappingStatus, now_iso

logger = logging.getLogger(__name__)


# ── 常量 ──────────────────────────────────────────────────────

MAX_DELIVERIES_PER_RUN = 5
CIRCUIT_BREAKER_THRESHOLD = 3
MAX_DELIVERY_ATTEMPTS = 5


# ── 结果数据结构 ──────────────────────────────────────────────

@dataclass
class DeliveryResult:
    """单条投递结果。"""

    success: bool
    mapping_id: str
    publish_id: str = ""
    ad_id: str = ""
    ad_creative_id: str = ""
    delivery_status: MappingDeliveryStatus = MappingDeliveryStatus.UNDISPATCHED
    error: str = ""
    elapsed_ms: float = 0.0
    dry_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "mapping_id": self.mapping_id,
            "publish_id": self.publish_id,
            "ad_id": self.ad_id,
            "ad_creative_id": self.ad_creative_id,
            "delivery_status": self.delivery_status.value,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "dry_run": self.dry_run,
        }


@dataclass
class BatchDeliveryResult:
    """批量投递结果。"""

    total: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    results: list[DeliveryResult] = field(default_factory=list)
    circuit_breaker_triggered: bool = False
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "results": [r.to_dict() for r in self.results],
            "circuit_breaker_triggered": self.circuit_breaker_triggered,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


# ── DeliveryBridge ────────────────────────────────────────────

class DeliveryBridge:
    """映射记录 → 广告投放系统的交付桥接层。

    Usage::

        bridge = DeliveryBridge(engine=engine)
        result = bridge.dispatch(
            mapping_id="map_abc123",
            ad_account_id="act_123",
            campaign_id="cmp_456",
            adset_id="set_789",
            page_id="page_001",
            dry_run=True,
        )
    """

    def __init__(
        self,
        engine: Any,
        publishing_layer: Optional[Any] = None,
        data_dir: Optional[str] = None,
    ):
        """初始化 DeliveryBridge。

        Args:
            engine: CreativeMappingEngine 实例
            publishing_layer: AdPublishingLayer 实例 (None 时仅支持 dry_run)
            data_dir: 数据目录 (默认 engine 的 data_dir)
        """
        self._engine = engine
        self._publishing_layer = publishing_layer
        if data_dir:
            self._data_dir = Path(data_dir)
        else:
            # 从 engine.store 推断 data_dir
            store = engine.store
            self._data_dir = store._dir  # type: ignore[attr-defined]
        self._audit_path = self._data_dir / "delivery_audit.jsonl"

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def publishing_layer(self) -> Optional[Any]:
        return self._publishing_layer

    # ── 查询 ──────────────────────────────────────────────────

    def get_dispatchable(self, limit: int = 50) -> list[CreativeMappingRecord]:
        """查询可投递记录 (MATCHED/REVIEW_APPROVED + UNDISPATCHED/FAILED)。

        Args:
            limit: 最多返回记录数

        Returns:
            按 confidence 降序排列的可投递记录列表
        """
        capped_limit = min(limit, MAX_DELIVERIES_PER_RUN * 10)
        return self._engine.get_dispatchable_records(limit=capped_limit)

    def get_delivery_status(self, mapping_id: str) -> dict[str, Any]:
        """查询单条记录的投递状态。"""
        record = self._engine.get_record(mapping_id)
        if record is None:
            return {
                "success": False,
                "error": "mapping not found",
                "mapping_id": mapping_id,
            }
        return {
            "success": True,
            "mapping_id": mapping_id,
            "delivery_status": record.delivery_status.value,
            "publish_id": record.publish_id,
            "ad_id": record.ad_id,
            "ad_creative_id": record.ad_creative_id,
            "delivered_at": record.delivered_at,
            "delivery_error": record.delivery_error,
            "delivery_attempts": record.delivery_attempts,
            "eagle_path": record.eagle_path,
            "confidence": record.confidence,
            "status": record.status.value,
        }

    # ── 投递 ──────────────────────────────────────────────────

    def dispatch(
        self,
        mapping_id: str,
        ad_account_id: str,
        campaign_id: str,
        adset_id: str,
        page_id: str,
        dry_run: bool = True,
        creative_name: str = "",
        creative_body: str = "",
        access_token: str = "",
    ) -> DeliveryResult:
        """单条投递：将映射记录的素材投递到 Facebook Ads。

        Args:
            mapping_id: 映射记录 ID
            ad_account_id: Facebook 广告账户 ID
            campaign_id: 目标 Campaign ID
            adset_id: 目标 AdSet ID
            page_id: Facebook Page ID
            dry_run: True=模拟投递不调用真实 API (默认)
            creative_name: adcreative 标题 (空则用 facebook_creative_name)
            creative_body: adcreative 正文 (预留，v1.5 不使用)
            access_token: Facebook API access_token (dry_run=False 时必需)

        Returns:
            DeliveryResult
        """
        t0 = time.time()
        result = DeliveryResult(
            success=False,
            mapping_id=mapping_id,
            dry_run=dry_run,
        )

        # 1. 加载映射记录
        record = self._engine.get_record(mapping_id)
        if record is None:
            result.error = "mapping not found"
            result.elapsed_ms = (time.time() - t0) * 1000
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            return result

        # 2. 校验 status
        if record.status not in (MappingStatus.MATCHED, MappingStatus.REVIEW_APPROVED):
            result.error = f"invalid status: {record.status.value}"
            result.elapsed_ms = (time.time() - t0) * 1000
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            return result

        # 3. 校验 delivery_status
        if record.delivery_status == MappingDeliveryStatus.PUBLISHED:
            result.error = "already published"
            result.delivery_status = MappingDeliveryStatus.PUBLISHED
            result.ad_id = record.ad_id
            result.publish_id = record.publish_id
            result.elapsed_ms = (time.time() - t0) * 1000
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            return result

        if record.delivery_status not in (
            MappingDeliveryStatus.UNDISPATCHED,
            MappingDeliveryStatus.FAILED,
        ):
            result.error = f"cannot dispatch in delivery_status: {record.delivery_status.value}"
            result.elapsed_ms = (time.time() - t0) * 1000
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            return result

        # 4. 校验 eagle_path
        if not record.eagle_path:
            result.error = "no eagle_path"
            result.elapsed_ms = (time.time() - t0) * 1000
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            return result

        eagle_path = Path(record.eagle_path)
        if not eagle_path.exists():
            result.error = f"file not found: {record.eagle_path}"
            result.elapsed_ms = (time.time() - t0) * 1000
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            return result

        # 5. dry_run 模式：模拟成功
        if dry_run:
            mock_publish_id = f"pub_dry_{uuid.uuid4().hex[:8]}"
            mock_ad_id = f"dry_ad_{uuid.uuid4().hex[:8]}"
            result.success = True
            result.publish_id = mock_publish_id
            result.ad_id = mock_ad_id
            result.ad_creative_id = f"dry_crt_{uuid.uuid4().hex[:8]}"
            result.delivery_status = MappingDeliveryStatus.PUBLISHED
            result.elapsed_ms = (time.time() - t0) * 1000

            # dry_run 不回写 delivery_status (仍保持 UNDISPATCHED)
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            logger.info(
                "DeliveryBridge dry_run dispatch: mapping=%s → mock_ad=%s",
                mapping_id, mock_ad_id,
            )
            return result

        # 6. 真实投递
        if self._publishing_layer is None:
            result.error = "no publishing_layer configured (dry_run=False requires one)"
            result.elapsed_ms = (time.time() - t0) * 1000
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            return result

        if not access_token:
            result.error = "access_token required for dry_run=False"
            result.elapsed_ms = (time.time() - t0) * 1000
            self._write_audit(result, ad_account_id, campaign_id, adset_id)
            return result

        # 7. 调用 AdPublishingLayer
        try:
            # 先注册 creative (AdPublishingLayer 要求)
            publish_id = self._publishing_layer.register_creative_for_publish(
                creative_id=record.facebook_creative_id,
                template_id="cme_mapping",
                layout_ast_id="",
                render_id=record.mapping_id,
                compiler_version=15,
            )

            cr_name = creative_name or record.facebook_creative_name

            pub_record = self._publishing_layer.publish_to_meta(
                publish_id=publish_id,
                access_token=access_token,
                ad_account_id=ad_account_id,
                campaign_id=campaign_id,
                adset_id=adset_id,
                image_path=str(eagle_path),
                page_id=page_id,
                creative_name=cr_name,
            )

            result.publish_id = publish_id

            if pub_record.status == "published" and pub_record.ad_id:
                result.success = True
                result.ad_id = pub_record.ad_id
                result.ad_creative_id = pub_record.image_hash
                result.delivery_status = MappingDeliveryStatus.PUBLISHED

                # 回写 PUBLISHED
                self._engine.update_delivery_status(
                    mapping_id=mapping_id,
                    delivery_status=MappingDeliveryStatus.PUBLISHED,
                    publish_id=publish_id,
                    ad_id=pub_record.ad_id,
                    ad_creative_id=pub_record.image_hash,
                    increment_attempts=True,
                )
            else:
                result.error = pub_record.error_message or "publish failed"
                result.delivery_status = MappingDeliveryStatus.FAILED

                # 回写 FAILED
                self._engine.update_delivery_status(
                    mapping_id=mapping_id,
                    delivery_status=MappingDeliveryStatus.FAILED,
                    publish_id=publish_id,
                    delivery_error=result.error,
                    increment_attempts=True,
                )

        except Exception as exc:
            result.error = f"publishing_layer raised: {exc}"
            result.delivery_status = MappingDeliveryStatus.FAILED
            self._engine.update_delivery_status(
                mapping_id=mapping_id,
                delivery_status=MappingDeliveryStatus.FAILED,
                delivery_error=result.error,
                increment_attempts=True,
            )
            logger.exception("DeliveryBridge dispatch failed: mapping=%s", mapping_id)

        result.elapsed_ms = (time.time() - t0) * 1000
        self._write_audit(result, ad_account_id, campaign_id, adset_id)
        return result

    def dispatch_batch(
        self,
        ad_account_id: str,
        campaign_id: str,
        adset_id: str,
        page_id: str,
        filter_status: Optional[list[MappingStatus]] = None,
        limit: int = MAX_DELIVERIES_PER_RUN,
        dry_run: bool = True,
        access_token: str = "",
    ) -> BatchDeliveryResult:
        """批量投递：自动选取可投递记录批量推送。

        Args:
            ad_account_id: Facebook 广告账户 ID
            campaign_id: 目标 Campaign ID
            adset_id: 目标 AdSet ID
            page_id: Facebook Page ID
            filter_status: 筛选 MappingStatus (默认 [MATCHED, REVIEW_APPROVED])
            limit: 单次批量上限 (强制 ≤ MAX_DELIVERIES_PER_RUN)
            dry_run: True=模拟投递 (默认)
            access_token: Facebook API access_token (dry_run=False 时必需)

        Returns:
            BatchDeliveryResult
        """
        t0 = time.time()
        capped_limit = min(limit, MAX_DELIVERIES_PER_RUN)
        result = BatchDeliveryResult()

        # 查询可投递记录
        records = self._engine.get_dispatchable_records(
            limit=capped_limit,
            filter_status=filter_status,
        )
        result.total = len(records)

        consecutive_failures = 0

        for record in records:
            # circuit breaker 检查
            if consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                result.circuit_breaker_triggered = True
                logger.warning(
                    "DeliveryBridge circuit breaker triggered after %d consecutive failures",
                    consecutive_failures,
                )
                break

            dr = self.dispatch(
                mapping_id=record.mapping_id,
                ad_account_id=ad_account_id,
                campaign_id=campaign_id,
                adset_id=adset_id,
                page_id=page_id,
                dry_run=dry_run,
                access_token=access_token,
            )

            if dr.success:
                result.success_count += 1
                consecutive_failures = 0
            elif dr.error in (
                "mapping not found",
                "invalid status",
                "already published",
            ) or dr.error.startswith("cannot dispatch"):
                # 跳过类错误 (状态不符/重复投递)
                result.skipped_count += 1
            else:
                result.failed_count += 1
                consecutive_failures += 1

            result.results.append(dr)

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    def redeliver(
        self,
        mapping_id: str,
        ad_account_id: str,
        campaign_id: str,
        adset_id: str,
        page_id: str,
        dry_run: bool = True,
        access_token: str = "",
    ) -> DeliveryResult:
        """重试失败的投递 (delivery_status=FAILED)。

        约束:
          - 仅 delivery_status=FAILED 的记录可重试
          - delivery_attempts < MAX_DELIVERY_ATTEMPTS (超过需人工介入)
        """
        record = self._engine.get_record(mapping_id)
        if record is None:
            return DeliveryResult(
                success=False,
                mapping_id=mapping_id,
                error="mapping not found",
                dry_run=dry_run,
            )

        if record.delivery_status != MappingDeliveryStatus.FAILED:
            return DeliveryResult(
                success=False,
                mapping_id=mapping_id,
                error=f"not in FAILED state: {record.delivery_status.value}",
                delivery_status=record.delivery_status,
                dry_run=dry_run,
            )

        if record.delivery_attempts >= MAX_DELIVERY_ATTEMPTS:
            return DeliveryResult(
                success=False,
                mapping_id=mapping_id,
                error=f"max delivery attempts reached ({MAX_DELIVERY_ATTEMPTS}), manual intervention required",
                delivery_status=record.delivery_status,
                dry_run=dry_run,
            )

        # 清除错误信息后重新投递
        self._engine.update_delivery_status(
            mapping_id=mapping_id,
            delivery_status=MappingDeliveryStatus.UNDISPATCHED,
            delivery_error="",
        )

        return self.dispatch(
            mapping_id=mapping_id,
            ad_account_id=ad_account_id,
            campaign_id=campaign_id,
            adset_id=adset_id,
            page_id=page_id,
            dry_run=dry_run,
            access_token=access_token,
        )

    # ── 审计日志 ──────────────────────────────────────────────

    def _write_audit(
        self,
        result: DeliveryResult,
        ad_account_id: str,
        campaign_id: str,
        adset_id: str,
    ) -> None:
        """写入投递审计日志 (append-only JSONL)。"""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": now_iso(),
            "mapping_id": result.mapping_id,
            "action": "dispatch",
            "dry_run": result.dry_run,
            "ad_account_id": ad_account_id,
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "success": result.success,
            "publish_id": result.publish_id,
            "ad_id": result.ad_id,
            "ad_creative_id": result.ad_creative_id,
            "delivery_status": result.delivery_status.value,
            "elapsed_ms": round(result.elapsed_ms, 2),
            "error": result.error,
        }
        with open(self._audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── v1.6: 投放结构自动创建 ──────────────────────────────────

    def dispatch_with_auto_structure(
        self,
        mapping_id: str,
        ad_account_id: str,
        page_id: str,
        project_name: str,
        daily_budget: float,
        countries: list[str],
        game_category: str = "casual",
        adset_count: int = 1,
        is_broad: bool = False,
        target_cpi: Optional[float] = None,
        use_advantage_plus: bool = False,
        dry_run: bool = True,
        access_token: str = "",
        headlines: Optional[list[str]] = None,
        primary_texts: Optional[list[str]] = None,
    ) -> "AutoStructureResult":
        """自动创建投放结构并投递 (v1.6).

        流程:
          1. 校验映射记录存在且可投递
          2. CampaignStrategyBuilder.build_full_campaign() 生成 Campaign + AdSet 配置
          3. (dry_run=False) 通过 FacebookPublisher 创建 Campaign + AdSet
          4. 回写 auto_campaign_id / auto_adset_id 到映射记录
          5. 调用 dispatch() 用新创建的 campaign_id/adset_id 投递

        Args:
            mapping_id: 映射记录 ID
            ad_account_id: Facebook 广告账户 ID
            page_id: Facebook Page ID
            project_name: 项目名 (用于 Campaign/AdSet 命名)
            daily_budget: 日预算 (USD)
            countries: 投放国家列表
            game_category: 游戏类别 (casual/hardcore/midcore)
            adset_count: AdSet 数量
            is_broad: 是否宽泛定向
            target_cpi: 目标 CPI
            use_advantage_plus: 是否使用 ASC
            dry_run: True=模拟 (默认)
            access_token: Facebook API token
            headlines: 广告标题列表
            primary_texts: 广告正文列表

        Returns:
            AutoStructureResult
        """
        result = AutoStructureResult(success=False)

        # 1. 加载映射记录
        record = self._engine.get_record(mapping_id)
        if record is None:
            result.error = "mapping not found"
            return result

        # 2. 校验 status
        if record.status not in (MappingStatus.MATCHED, MappingStatus.REVIEW_APPROVED):
            result.error = f"invalid status: {record.status.value}"
            return result

        # 3. 校验 delivery_status
        if record.delivery_status == MappingDeliveryStatus.PUBLISHED:
            result.error = "already published"
            result.delivery_result = DeliveryResult(
                success=False,
                mapping_id=mapping_id,
                error="already published",
                delivery_status=MappingDeliveryStatus.PUBLISHED,
                dry_run=dry_run,
            )
            return result

        # 4. 校验 eagle_path
        if not record.eagle_path:
            result.error = "no eagle_path"
            return result

        # 5. 生成投放结构配置 (用 importlib 加载数字开头的模块)
        CampaignStrategyBuilder = None
        try:
            import importlib
            mod = importlib.import_module(
                "market_ops.creative_growth_loop.14_publish.campaign_strategy"
            )
            CampaignStrategyBuilder = getattr(mod, "CampaignStrategyBuilder", None)
        except Exception as exc:
            logger.warning("CampaignStrategyBuilder import failed: %s", exc)

        campaign_config = None
        adset_configs: list = []
        strategy_name = ""

        if CampaignStrategyBuilder is not None:
            try:
                builder = CampaignStrategyBuilder()
                full = builder.build_full_campaign(
                    project_name=project_name,
                    daily_budget=daily_budget,
                    countries=countries,
                    game_category=game_category,
                    adset_count=adset_count,
                    is_broad=is_broad,
                    target_cpi=target_cpi,
                    use_advantage_plus=use_advantage_plus,
                )
                campaign_config = full.get("campaign")
                adset_configs = full.get("adsets", [])
                if campaign_config is not None:
                    raw_strategy = getattr(campaign_config, "strategy", "")
                    if hasattr(raw_strategy, "value"):
                        raw_strategy = raw_strategy.value
                    strategy_name = str(raw_strategy) if raw_strategy else ""
            except Exception as exc:
                logger.warning(
                    "CampaignStrategyBuilder.build_full_campaign failed: %s", exc
                )

        # 6. dry_run: 不创建真实结构, 仅返回配置
        if dry_run:
            result.success = True
            result.campaign_id = f"dry_cmp_{uuid.uuid4().hex[:8]}"
            result.adset_id = f"dry_set_{uuid.uuid4().hex[:8]}"
            result.strategy = strategy_name
            # dry_run 投递
            delivery = self.dispatch(
                mapping_id=mapping_id,
                ad_account_id=ad_account_id,
                campaign_id=result.campaign_id,
                adset_id=result.adset_id,
                page_id=page_id,
                dry_run=True,
                access_token="",
            )
            result.delivery_result = delivery
            self._write_audit(
                delivery, ad_account_id, result.campaign_id, result.adset_id
            )
            return result

        # 7. 真实模式: 通过 FacebookPublisher 创建结构
        if not access_token:
            result.error = "access_token required for real delivery"
            return result

        campaign_id = ""
        adset_id = ""

        try:
            import importlib as _imp
            pub_mod = _imp.import_module(
                "market_ops.creative_growth_loop.14_publish.facebook_publisher"
            )
            FacebookPublisher = getattr(pub_mod, "FacebookPublisher", None)
            if FacebookPublisher is None:
                result.error = "FacebookPublisher not found"
                return result
            publisher = FacebookPublisher(
                access_token=access_token,
                ad_account_id=ad_account_id,
                page_id=page_id,
            )
            # 创建 Campaign
            if campaign_config is not None:
                campaign_id = publisher.create_campaign_from_config(campaign_config)
            if not campaign_id:
                result.error = "failed to create campaign"
                return result
            # 创建第一个 AdSet
            if adset_configs:
                cfg = adset_configs[0]
                cfg.campaign_id = campaign_id
                adset_id = publisher.create_adset_from_config(cfg)
            if not adset_id:
                result.error = "failed to create adset"
                return result
        except Exception as exc:
            result.error = f"publisher raised: {exc}"
            return result

        # 8. 回写 auto-structure 字段
        self._engine.update_auto_structure(
            mapping_id=mapping_id,
            auto_campaign_id=campaign_id,
            auto_adset_id=adset_id,
            auto_strategy=strategy_name,
        )

        # 9. 用新创建的结构投递
        delivery = self.dispatch(
            mapping_id=mapping_id,
            ad_account_id=ad_account_id,
            campaign_id=campaign_id,
            adset_id=adset_id,
            page_id=page_id,
            dry_run=False,
            access_token=access_token,
        )
        result.success = delivery.success
        result.campaign_id = campaign_id
        result.adset_id = adset_id
        result.strategy = strategy_name
        result.delivery_result = delivery
        if not delivery.success:
            result.error = delivery.error
        return result


@dataclass
class AutoStructureResult:
    """自动创建投放结构的结果 (v1.6)."""

    success: bool
    campaign_id: str = ""
    adset_id: str = ""
    strategy: str = ""
    error: str = ""
    delivery_result: Optional[DeliveryResult] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "strategy": self.strategy,
            "error": self.error,
            "delivery_result": (
                self.delivery_result.to_dict()
                if self.delivery_result is not None
                else None
            ),
        }


__all__ = [
    "DeliveryBridge",
    "DeliveryResult",
    "BatchDeliveryResult",
    "AutoStructureResult",
    "MAX_DELIVERIES_PER_RUN",
    "CIRCUIT_BREAKER_THRESHOLD",
    "MAX_DELIVERY_ATTEMPTS",
]
