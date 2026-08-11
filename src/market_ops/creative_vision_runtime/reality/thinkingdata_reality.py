"""E12.1 — ThinkingData Reality Connector。

在 ThinkingDataClient 之上构建统一门面层，将数数玩家行为数据
转换为 E11 Evolution 可消费的 ProductBehaviorRecord。

设计原则：
  - 薄门面：不重复实现 API 逻辑，纯桥接
  - 默认 sandbox（mock），生产环境通过 config 切换
  - 支持按 Campaign ID / 项目 / 日期范围拉取
  - 输出统一 ProductBehaviorRecord（含生命周期、留存、付费、进度）

数据流：
  ThinkingData Open API
       │
       ▼
  ThinkingDataClient (clients/thinkingdata.py)
       │
       ▼
  ThinkingDataReality (本文件)
       │
       ▼
  ProductBehaviorRecord[]
       │
       ▼
  RealityDataHub → RealitySnapshot → E11 Evolution

Usage:
    from market_ops.clients.thinkingdata import ThinkingDataClient
    from market_ops.creative_vision_runtime.reality import ThinkingDataReality

    client = ThinkingDataClient("https://www.starmoondata.com:8996", "token")
    reality = ThinkingDataReality(client)
    records = reality.fetch_campaign_users(102, ["camp_001", "camp_002"])
    records = reality.fetch_recent_retention(102, lookback_days=7)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from .models import ProductBehaviorRecord

if TYPE_CHECKING:
    from market_ops.clients.thinkingdata import ThinkingDataClient

logger = logging.getLogger(__name__)


class ThinkingDataReality:
    """ThinkingData 玩家行为统一门面层。

    封装 ThinkingDataClient，提供 E11 友好的产品行为数据拉取接口。

    Attributes:
        client:            底层 ThinkingDataClient
        total_fetched:     累计拉取记录数
        last_fetched_at:   上次拉取时间
    """

    # 留存数据缓存 TTL（秒），避免 Lifecycle + Retention 分析器重复 API 调用
    _RETENTION_CACHE_TTL = timedelta(minutes=5)

    def __init__(
        self,
        client: ThinkingDataClient | None = None,
    ) -> None:
        self._client = client

        self.total_fetched: int = 0
        self.last_fetched_at: datetime | None = None

        # 留存数据缓存：{(project_id, lookback_days): (cached_at, records)}
        self._retention_cache: dict[tuple[int, int], tuple[datetime, list[ProductBehaviorRecord]]] = {}

    # ── Public API ───────────────────────────────────────

    def fetch_campaign_users(
        self,
        project_id: int,
        campaign_ids: list[str],
        date_range: dict[str, str] | None = None,
    ) -> list[ProductBehaviorRecord]:
        """拉取指定 Campaign 下所有用户的行为数据。

        通过数数 SQL 查询拉取按 campaign 分组的用户行为画像。

        Args:
            project_id:    数数项目 ID
            campaign_ids:  投放 Campaign ID 列表
            date_range:    {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

        Returns:
            ProductBehaviorRecord 列表
        """
        if not campaign_ids:
            return []

        records: list[ProductBehaviorRecord] = []

        if not self._client:
            for cid in campaign_ids:
                records.extend(self._mock_campaign_users(project_id, cid))
            self.total_fetched += len(records)
            self.last_fetched_at = datetime.now(timezone.utc)
            return records

        # 构建 SQL：按 campaign 聚合用户行为
        campaign_filter = ", ".join(f"'{cid}'" for cid in campaign_ids)
        date_clause = ""
        if date_range:
            date_clause = f"AND event_date BETWEEN '{date_range['start']}' AND '{date_range['end']}'"

        sql = (
            f"SELECT "
            f"  user_id, "
            f"  MIN(event_date) AS install_date, "
            f"  MAX(event_date) AS last_active_date, "
            f"  COUNT(DISTINCT event_date) AS active_days, "
            f"  COUNT(DISTINCT session_id) AS session_count, "
            f"  MAX(level) AS level, "
            f"  SUM(CASE WHEN event_name = 'purchase' THEN revenue ELSE 0 END) AS total_revenue, "
            f"  COUNT(DISTINCT CASE WHEN event_name = 'purchase' THEN event_date END) AS pay_count, "
            f"  MIN(CASE WHEN event_name = 'purchase' THEN event_date END) AS first_pay_date, "
            f"  MAX(IFNULL(country, '')) AS country, "
            f"  MAX(IFNULL(channel, '')) AS channel, "
            f"  MAX(IFNULL(campaign_id, '')) AS campaign_id, "
            f"  MAX(IFNULL(platform, '')) AS platform "
            f"FROM v_event_{project_id} "
            f"WHERE campaign_id IN ({campaign_filter}) "
            f"{date_clause} "
            f"GROUP BY user_id"
        )

        try:
            result = self._client.sql_query(project_id, sql)
            rows = result.get("data", result.get("rows", []))
            for row in rows:
                records.append(self._row_to_record(project_id, row))
        except Exception as exc:
            logger.warning(
                f"ThinkingDataReality: SQL query failed for campaigns {campaign_ids}: {exc}"
            )
            # 降级到 mock
            for cid in campaign_ids:
                records.extend(self._mock_campaign_users(project_id, cid))

        self.total_fetched += len(records)
        self.last_fetched_at = datetime.now(timezone.utc)

        logger.info(
            f"ThinkingDataReality: fetched {len(records)} user records "
            f"from {len(campaign_ids)} campaigns "
            f"(total: {self.total_fetched})"
        )
        return records

    def fetch_recent_retention(
        self,
        project_id: int,
        lookback_days: int = 7,
        use_cache: bool = True,
    ) -> list[ProductBehaviorRecord]:
        """拉取最近 N 天的留存分析数据。

        通过数数留存分析 API 拉取按渠道/日期的留存数据。
        结果会缓存 TTL 5 分钟，避免 Lifecycle + Retention 分析器重复调用。

        Args:
            project_id:    数数项目 ID
            lookback_days: 回溯天数
            use_cache:     是否启用缓存（默认 True，测试时可关闭）

        Returns:
            ProductBehaviorRecord 列表（每条代表一个渠道的留存画像）
        """
        # 缓存命中：直接返回，跳过 API 调用
        cache_key = (project_id, lookback_days)
        if use_cache and cache_key in self._retention_cache:
            cached_at, records = self._retention_cache[cache_key]
            if datetime.now(timezone.utc) - cached_at < self._RETENTION_CACHE_TTL:
                logger.debug(
                    f"ThinkingDataReality: retention cache hit for "
                    f"project={project_id}, lookback={lookback_days}"
                )
                return records

        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()

        if not self._client:
            records = self._mock_retention_records(project_id, start, end)
            self.total_fetched += len(records)
            self.last_fetched_at = datetime.now(timezone.utc)
            self._retention_cache[cache_key] = (datetime.now(timezone.utc), records)
            return records

        # 调用留存分析 API
        payload = {
            "events": [
                {
                    "eventName": "ta_app_install",
                    "analysis": "RETENTION",
                    "retentionType": "N_DAY_RETENTION",
                    "retentionDays": [1, 7, 30],
                }
            ],
            "timeRange": {"start": start, "end": end},
            "groupBy": ["channel"],
        }

        try:
            result = self._client.retention_analyze(project_id, payload)
            records = self._retention_result_to_records(
                project_id, result, start, end,
            )
        except Exception as exc:
            logger.warning(
                f"ThinkingDataReality: retention_analyze failed: {exc}"
            )
            records = self._mock_retention_records(project_id, start, end)

        self.total_fetched += len(records)
        self.last_fetched_at = datetime.now(timezone.utc)
        self._retention_cache[cache_key] = (datetime.now(timezone.utc), records)

        logger.info(
            f"ThinkingDataReality: fetched {len(records)} retention records "
            f"for project {project_id} (total: {self.total_fetched})"
        )
        return records

    def fetch_user_cluster(
        self,
        project_id: int,
        cluster_name: str,
    ) -> list[ProductBehaviorRecord]:
        """拉取指定用户分群的用户列表。

        从数数用户分群拉取用户，并转换为 ProductBehaviorRecord。

        Args:
            project_id:    数数项目 ID
            cluster_name:  分群名称（如"付费用户"、"流失风险用户"）

        Returns:
            ProductBehaviorRecord 列表
        """
        if not self._client:
            records = self._mock_cluster_users(project_id, cluster_name)
            self.total_fetched += len(records)
            self.last_fetched_at = datetime.now(timezone.utc)
            return records

        try:
            detail = self._client.get_user_cluster_detail(
                project_id, cluster_name,
            )
            user_ids = detail.get("user_ids", [])
            records = []
            for uid in user_ids:
                records.append(ProductBehaviorRecord(
                    project_id=project_id,
                    user_id=uid,
                    lifecycle_stage=self._cluster_to_stage(cluster_name),
                    payer_segment=self._cluster_to_payer_segment(cluster_name),
                ))
        except Exception as exc:
            logger.warning(
                f"ThinkingDataReality: get_user_cluster_detail failed "
                f"for '{cluster_name}': {exc}"
            )
            records = self._mock_cluster_users(project_id, cluster_name)

        self.total_fetched += len(records)
        self.last_fetched_at = datetime.now(timezone.utc)

        logger.info(
            f"ThinkingDataReality: fetched {len(records)} users "
            f"from cluster '{cluster_name}' (total: {self.total_fetched})"
        )
        return records

    def fetch_multi_revenue(
        self,
        project_id: int,
        campaign_ids: list[str],
        date_range: dict[str, str] | None = None,
    ) -> list[ProductBehaviorRecord]:
        """批量拉取多个 Campaign 的付费用户行为数据。

        聚焦付费维度，用于投放对账。

        Args:
            project_id:    数数项目 ID
            campaign_ids:  Campaign ID 列表
            date_range:    {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

        Returns:
            ProductBehaviorRecord 列表（仅付费用户）
        """
        all_records = self.fetch_campaign_users(
            project_id, campaign_ids, date_range,
        )
        payer_records = [r for r in all_records if r.is_payer]

        logger.info(
            f"ThinkingDataReality: {len(payer_records)} payers "
            f"out of {len(all_records)} users"
        )
        return payer_records

    def is_connected(self) -> bool:
        """检查是否已连接 ThinkingData API。"""
        if not self._client:
            return False
        return True

    def clear_retention_cache(self) -> None:
        """清空留存数据缓存（用于测试或强制刷新）。"""
        self._retention_cache.clear()

    # ── Internal ────────────────────────────────────────

    def _row_to_record(
        self,
        project_id: int,
        row: dict[str, Any] | list[Any],
    ) -> ProductBehaviorRecord:
        """将 SQL 查询结果行转换为 ProductBehaviorRecord。

        支持字典和列表两种行格式。
        """
        if isinstance(row, dict):
            get = row.get
        else:
            # 列表格式：按位置映射
            keys = [
                "user_id", "install_date", "last_active_date",
                "active_days", "session_count", "level",
                "total_revenue", "pay_count", "first_pay_date",
                "country", "channel", "campaign_id", "platform",
            ]
            get = lambda k: row[keys.index(k)] if k in keys else ""

        total_revenue = float(get("total_revenue") or 0)
        pay_count = int(get("pay_count") or 0)
        is_payer = total_revenue > 0 or pay_count > 0

        # 推断生命周期阶段
        last_active = get("last_active_date") or ""
        lifecycle_stage = self._infer_lifecycle_stage(last_active, is_payer)

        # 推断付费分层
        payer_segment = self._infer_payer_segment(total_revenue, pay_count)

        return ProductBehaviorRecord(
            project_id=project_id,
            user_id=str(get("user_id") or ""),
            install_date=str(get("install_date") or ""),
            last_active_date=str(last_active),
            lifecycle_stage=lifecycle_stage,
            session_count=int(get("session_count") or 0),
            level=int(get("level") or 0),
            is_payer=is_payer,
            first_pay_date=str(get("first_pay_date") or ""),
            total_revenue=total_revenue,
            pay_count=pay_count,
            payer_segment=payer_segment,
            arpu=round(total_revenue, 2),
            channel=str(get("channel") or ""),
            campaign_id=str(get("campaign_id") or ""),
            country=str(get("country") or ""),
            platform=str(get("platform") or ""),
        )

    def _retention_result_to_records(
        self,
        project_id: int,
        result: dict[str, Any],
        start_date: str,
        end_date: str,
    ) -> list[ProductBehaviorRecord]:
        """将留存分析 API 结果转换为 ProductBehaviorRecord 列表。"""
        records: list[ProductBehaviorRecord] = []

        # 数数留存分析返回格式：data → [rows] → 每行含 group + retention values
        data = result.get("data", result.get("result", {}))
        rows = data.get("rows", data.get("series", []))

        for row in rows:
            group_values = row.get("groups", row.get("groupBy", []))
            channel = group_values[0] if group_values else ""

            # 留存值按 day 索引
            retention_values = row.get("values", row.get("retention", []))
            d1 = self._safe_retention(retention_values, 0)
            d7 = self._safe_retention(retention_values, 1)
            d30 = self._safe_retention(retention_values, 2)

            records.append(ProductBehaviorRecord(
                project_id=project_id,
                user_id=f"channel:{channel}",
                lifecycle_stage="retention",
                d1_retention=d1,
                d7_retention=d7,
                d30_retention=d30,
                channel=channel,
                install_date=start_date,
                last_active_date=end_date,
            ))

        return records

    @staticmethod
    def _safe_retention(values: list, index: int) -> float:
        """安全提取留存值。"""
        if index < len(values) and values[index] is not None:
            return round(float(values[index]), 4)
        return 0.0

    @staticmethod
    def _infer_lifecycle_stage(last_active_date: str, is_payer: bool) -> str:
        """根据最后活跃日期推断生命周期阶段。"""
        if not last_active_date:
            return "install"
        try:
            last = date.fromisoformat(last_active_date[:10])
            days_inactive = (date.today() - last).days
            if days_inactive <= 1:
                return "engagement"
            if days_inactive <= 7:
                return "retention"
            if days_inactive <= 30:
                return "churn"
            return "churn"
        except (ValueError, IndexError):
            return "retention"

    @staticmethod
    def _infer_payer_segment(total_revenue: float, pay_count: int) -> str:
        """根据付费金额和次数推断付费分层。"""
        if pay_count == 0 or total_revenue <= 0:
            return "non_payer"
        if pay_count == 1:
            return "first_payer"
        if total_revenue >= 500.0:
            return "whale"
        return "repeat_payer"

    @staticmethod
    def _cluster_to_stage(cluster_name: str) -> str:
        """根据分群名称推断生命周期阶段。"""
        name = cluster_name.lower()
        if "流失" in cluster_name or "churn" in name:
            return "churn"
        if "新" in cluster_name or "new" in name:
            return "activation"
        if "付费" in cluster_name or "payer" in name:
            return "engagement"
        if "高价值" in cluster_name or "whale" in name:
            return "engagement"
        return "retention"

    @staticmethod
    def _cluster_to_payer_segment(cluster_name: str) -> str:
        """根据分群名称推断付费分层。"""
        name = cluster_name.lower()
        if "鲸鱼" in cluster_name or "whale" in name or "高价值" in cluster_name:
            return "whale"
        if "付费" in cluster_name or "payer" in name:
            return "repeat_payer"
        if "未付费" in cluster_name or "non_payer" in name:
            return "non_payer"
        return "non_payer"

    # ── Mock (sandbox) ──────────────────────────────────

    def _mock_campaign_users(
        self,
        project_id: int,
        campaign_id: str,
    ) -> list[ProductBehaviorRecord]:
        """生成 mock Campaign 用户行为数据。"""
        seed = sum(ord(c) for c in campaign_id) % 100 + 1
        records: list[ProductBehaviorRecord] = []

        # 模拟 10 个用户
        for i in range(10):
            uid = f"{campaign_id}_user_{i + 1}"
            is_payer = (seed + i) % 3 == 0
            revenue = round(5.0 + (seed + i) * 2.5, 2) if is_payer else 0.0
            pay_count = 1 if is_payer else 0
            if revenue >= 100:
                pay_count = 3 + (i % 2)

            records.append(ProductBehaviorRecord(
                project_id=project_id,
                user_id=uid,
                install_date=f"2026-07-{10 + i:02d}",
                last_active_date=f"2026-08-0{(i % 5) + 1}",
                lifecycle_stage="retention" if i % 3 != 0 else "churn",
                d1_retention=round(0.45 - i * 0.02, 4),
                d7_retention=round(0.25 - i * 0.01, 4),
                d30_retention=round(0.10 - i * 0.005, 4),
                session_count=5 + i * 3,
                avg_session_duration=round(180.0 + i * 15, 2),
                level=10 + i * 3,
                stage=f"chapter_{(i % 4) + 1}",
                is_payer=is_payer,
                first_pay_date=f"2026-07-{15 + i:02d}" if is_payer else "",
                total_revenue=revenue,
                pay_count=pay_count,
                payer_segment=self._infer_payer_segment(revenue, pay_count),
                arpu=revenue,
                channel="meta" if i % 2 == 0 else "google",
                campaign_id=campaign_id,
                creative_id=f"{campaign_id}_creative_{(i % 3) + 1}",
                country="US" if i % 2 == 0 else "JP",
                device="iPhone" if i % 3 == 0 else "Android",
                platform="ios" if i % 3 == 0 else "android",
            ))

        return records

    def _mock_retention_records(
        self,
        project_id: int,
        start_date: str,
        end_date: str,
    ) -> list[ProductBehaviorRecord]:
        """生成 mock 留存数据。"""
        channels = ["meta", "google", "asa", "tiktok", "organic"]
        records: list[ProductBehaviorRecord] = []

        for i, channel in enumerate(channels):
            seed = sum(ord(c) for c in channel) % 100 + 1
            records.append(ProductBehaviorRecord(
                project_id=project_id,
                user_id=f"channel:{channel}",
                lifecycle_stage="retention",
                d1_retention=round(0.45 - i * 0.03, 4),
                d7_retention=round(0.25 - i * 0.02, 4),
                d30_retention=round(0.10 - i * 0.01, 4),
                channel=channel,
                install_date=start_date,
                last_active_date=end_date,
            ))

        return records

    def _mock_cluster_users(
        self,
        project_id: int,
        cluster_name: str,
    ) -> list[ProductBehaviorRecord]:
        """生成 mock 用户分群数据。"""
        seed = sum(ord(c) for c in cluster_name) % 100 + 1
        count = 5 + seed % 5
        stage = self._cluster_to_stage(cluster_name)
        payer_seg = self._cluster_to_payer_segment(cluster_name)
        is_payer = payer_seg != "non_payer"

        records: list[ProductBehaviorRecord] = []
        for i in range(count):
            revenue = round(10.0 + (seed + i) * 5.0, 2) if is_payer else 0.0
            records.append(ProductBehaviorRecord(
                project_id=project_id,
                user_id=f"{cluster_name}_user_{i + 1}",
                lifecycle_stage=stage,
                is_payer=is_payer,
                total_revenue=revenue,
                payer_segment=payer_seg,
                arpu=revenue,
                level=20 + i * 5,
            ))

        return records

    def __repr__(self) -> str:
        return f"ThinkingDataReality(fetched={self.total_fetched})"
