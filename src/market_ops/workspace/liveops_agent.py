"""LiveOps Agent — 消费流失信号，自动设计回流活动.

桥接 operation/player_monetization 的流失检测能力（LifecycleDetector /
PlayerSegmenter / EventCollector），自动生成回流活动方案，接入 workspace
组织架构。

设计原则（继承 Spec §1 纪律红线）:
  - 复用 player_monetization 现有模块，不新增算法层
  - 默认 dry_run：活动方案只生成不执行
  - 活动参数走配置（WinbackCampaignConfig），禁止硬编码模板
  - 不导入 v9_company/liveops_manager.py

依赖注入:
  collector / detector / segmenter 可在 __init__ 注入（便于测试），
  默认懒加载 operation.player_monetization 的真实实例。当真实模块不可
  导入时（如纯 workspace 部署），优雅降级到空分析。
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据模型（Spec §2.2）
# ═══════════════════════════════════════════════════════════════


@dataclass
class ChurnAnalysis:
    """流失分析结果 — 风险用户分群和建议."""

    game_id: str
    analysis_date: str
    total_players: int
    at_risk_count: int           # at_risk_churn 分群数
    lapsed_count: int            # LAPSED 阶段数
    churning_count: int          # CHURNING 阶段数
    avg_churn_risk: float        # 平均流失风险分 (0..1)
    segments: dict[str, int]     # 分群分布
    lifecycle_stages: dict[str, int]  # 生命周期阶段分布
    high_value_at_risk: int      # 高价值流失风险用户数

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CampaignAction:
    """回流活动单个动作."""

    action_type: str             # push_notification / in_app_message / reward_grant / email
    target_count: int
    content: str
    trigger_delay_hours: int     # 延迟触发小时数

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WinbackCampaign:
    """回流活动方案."""

    campaign_id: str
    game_id: str
    campaign_type: str           # login_bonus / discount / special_offer / push_re-engagement
    target_segment: str          # at_risk_churn / lapsed / churning
    target_count: int
    rewards_pool: float
    duration_days: int
    expected_participation: float
    expected_retention_uplift: float
    actions: list[CampaignAction]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "game_id": self.game_id,
            "campaign_type": self.campaign_type,
            "target_segment": self.target_segment,
            "target_count": self.target_count,
            "rewards_pool": round(self.rewards_pool, 2),
            "duration_days": self.duration_days,
            "expected_participation": round(self.expected_participation, 4),
            "expected_retention_uplift": round(self.expected_retention_uplift, 4),
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
        }


@dataclass
class CampaignEvaluation:
    """活动效果评估."""

    campaign_id: str
    participation_rate: float
    retention_uplift: float
    revenue_uplift: float
    player_satisfaction: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "participation_rate": round(self.participation_rate, 4),
            "retention_uplift": round(self.retention_uplift, 4),
            "revenue_uplift": round(self.revenue_uplift, 4),
            "player_satisfaction": round(self.player_satisfaction, 4),
        }


# ═══════════════════════════════════════════════════════════════
# 活动配置（禁止硬编码模板，参数走配置）
# ═══════════════════════════════════════════════════════════════


@dataclass
class CampaignTemplate:
    """单个活动模板配置 — 由 target_segment 索引."""

    campaign_type: str
    rewards_pool_per_user: float
    duration_days: int
    expected_participation: float
    expected_retention_uplift: float
    actions: list[dict[str, Any]]  # action_type / content / trigger_delay_hours


# 默认活动配置（可通过 WinbackCampaignConfig 覆盖）
_DEFAULT_TEMPLATES: dict[str, CampaignTemplate] = {
    "at_risk_churn": CampaignTemplate(
        campaign_type="login_bonus",
        rewards_pool_per_user=0.50,
        duration_days=3,
        expected_participation=0.45,
        expected_retention_uplift=0.08,
        actions=[
            {"action_type": "in_app_message", "content": "连续登录奖励已解锁，今日领取", "trigger_delay_hours": 0},
            {"action_type": "push_notification", "content": "你的登录奖励即将过期，快回来领取", "trigger_delay_hours": 24},
            {"action_type": "reward_grant", "content": "发放 3 日连续登录奖励", "trigger_delay_hours": 0},
        ],
    ),
    "churning": CampaignTemplate(
        campaign_type="special_offer",
        rewards_pool_per_user=1.50,
        duration_days=5,
        expected_participation=0.30,
        expected_retention_uplift=0.12,
        actions=[
            {"action_type": "in_app_message", "content": "专属回归礼包限时 5 折", "trigger_delay_hours": 0},
            {"action_type": "push_notification", "content": "特惠礼包仅剩 24 小时", "trigger_delay_hours": 24},
            {"action_type": "reward_grant", "content": "发放回归礼包（金币 + 道具）", "trigger_delay_hours": 0},
            {"action_type": "email", "content": "我们想念你了 — 专属回归奖励", "trigger_delay_hours": 48},
        ],
    ),
    "lapsed": CampaignTemplate(
        campaign_type="push_re-engagement",
        rewards_pool_per_user=2.00,
        duration_days=7,
        expected_participation=0.15,
        expected_retention_uplift=0.05,
        actions=[
            {"action_type": "push_notification", "content": "新版本上线，老玩家专属奖励", "trigger_delay_hours": 0},
            {"action_type": "push_notification", "content": "你的好友在等你，回归组队有奖", "trigger_delay_hours": 72},
            {"action_type": "email", "content": "长期未登录提醒 — 回归即送大礼包", "trigger_delay_hours": 0},
        ],
    ),
}


@dataclass
class WinbackCampaignConfig:
    """回流活动配置 — 控制活动参数（禁止硬编码）."""

    templates: dict[str, CampaignTemplate] = field(
        default_factory=lambda: {k: v for k, v in _DEFAULT_TEMPLATES.items()}
    )
    high_value_threshold: float = 0.50  # 高价值用户 value_score 阈值 (PlayerSegment.value_score 0..100 -> /100)


# ═══════════════════════════════════════════════════════════════
# LiveOps Agent
# ═══════════════════════════════════════════════════════════════


class LiveOpsAgent:
    """LiveOps Agent — 消费流失信号，自动设计回流活动.

    用法:
        agent = LiveOpsAgent(data_dir="data")
        analysis = agent.analyze_churn_risk("cooking_fever")
        campaign = agent.design_winback_campaign("cooking_fever", analysis)
        evaluation = agent.evaluate_campaign(campaign.campaign_id)
    """

    def __init__(
        self,
        data_dir: str = "data",
        collector: Any = None,
        detector: Any = None,
        segmenter: Any = None,
        config: WinbackCampaignConfig | None = None,
        executor: Any = None,
        message_bus: Any = None,
        agent_identity: Any = None,
    ) -> None:
        self.data_dir = data_dir
        self._collector = collector
        self._detector = detector
        self._segmenter = segmenter
        self.config = config or WinbackCampaignConfig()
        self._executor = executor
        # 跨 Agent 协同：消息总线 + Agent 身份
        self._message_bus = message_bus
        self._agent_identity = agent_identity

    # ── 懒加载依赖（复用 player_monetization，不导入则降级）─────

    def _get_collector(self) -> Any:
        if self._collector is not None:
            return self._collector
        try:
            from operation.player_monetization.events.collector import EventCollector
            self._collector = EventCollector()
        except ImportError as exc:
            logger.warning("EventCollector unavailable, churn analysis will be empty: %s", exc)
            self._collector = None
        return self._collector

    def _get_detector(self) -> Any:
        if self._detector is not None:
            return self._detector
        try:
            from operation.player_monetization.user_profile.lifecycle import LifecycleDetector
            self._detector = LifecycleDetector()
        except ImportError as exc:
            logger.warning("LifecycleDetector unavailable: %s", exc)
            self._detector = None
        return self._detector

    def _get_segmenter(self) -> Any:
        if self._segmenter is not None:
            return self._segmenter
        try:
            from operation.player_monetization.user_profile.player_segment import PlayerSegmenter
            self._segmenter = PlayerSegmenter()
        except ImportError as exc:
            logger.warning("PlayerSegmenter unavailable: %s", exc)
            self._segmenter = None
        return self._segmenter

    # ── 核心方法 ──────────────────────────────────────────────

    def analyze_churn_risk(self, game_id: str) -> ChurnAnalysis:
        """分析流失风险，返回风险用户分群和建议.

        复用 EventCollector 收集玩家 profile, 用 LifecycleDetector 和
        PlayerSegmenter 分类, 输出 ChurnAnalysis.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        profiles = self._collect_profiles(game_id)

        detector = self._get_detector()
        segmenter = self._get_segmenter()

        segments: dict[str, int] = {}
        lifecycle_stages: dict[str, int] = {}
        at_risk_count = 0
        lapsed_count = 0
        churning_count = 0
        high_value_at_risk = 0
        risk_sum = 0.0

        for profile in profiles:
            # 生命周期阶段
            stage = "ENGAGED"
            if detector is not None:
                stage = detector.stage(profile)
            lifecycle_stages[stage] = lifecycle_stages.get(stage, 0) + 1
            if stage == "LAPSED":
                lapsed_count += 1
            elif stage == "CHURNING":
                churning_count += 1

            # 分群
            seg_name = "new_player"
            value_score = 0.0
            churn_risk = 0.0
            if segmenter is not None:
                seg = segmenter.classify(profile)
                seg_name = seg.segment
                value_score = seg.value_score / 100.0  # 0..1
                churn_risk = seg.churn_risk
            segments[seg_name] = segments.get(seg_name, 0) + 1
            risk_sum += churn_risk

            if seg_name == "at_risk_churn":
                at_risk_count += 1
                if value_score >= self.config.high_value_threshold:
                    high_value_at_risk += 1

        total = len(profiles)
        avg_risk = round(risk_sum / total, 4) if total else 0.0

        analysis = ChurnAnalysis(
            game_id=game_id,
            analysis_date=today,
            total_players=total,
            at_risk_count=at_risk_count,
            lapsed_count=lapsed_count,
            churning_count=churning_count,
            avg_churn_risk=avg_risk,
            segments=segments,
            lifecycle_stages=lifecycle_stages,
            high_value_at_risk=high_value_at_risk,
        )
        self._persist_analysis(analysis)
        return analysis

    def design_winback_campaign(
        self,
        game_id: str,
        analysis: ChurnAnalysis,
    ) -> WinbackCampaign:
        """基于流失分析设计回流活动方案.

        根据流失分群自动选择活动类型 (at_risk_churn → login_bonus,
        churning → special_offer, lapsed → push_re-engagement).
        默认 dry_run: 只生成方案不执行.
        """
        # 优先级: lapsed > churning > at_risk_churn
        target_segment = "at_risk_churn"
        target_count = analysis.at_risk_count
        if analysis.lapsed_count > 0:
            target_segment = "lapsed"
            target_count = analysis.lapsed_count
        elif analysis.churning_count > 0:
            target_segment = "churning"
            target_count = analysis.churning_count

        # 无流失用户时，仍生成一个针对 at_risk_churn 的预防性方案
        if target_count == 0:
            target_segment = "at_risk_churn"
            target_count = analysis.at_risk_count or max(analysis.total_players // 10, 1)

        template = self.config.templates.get(target_segment)
        if template is None:
            # 兜底: 使用 at_risk_churn 模板
            template = self.config.templates.get(
                "at_risk_churn", _DEFAULT_TEMPLATES["at_risk_churn"]
            )

        rewards_pool = round(target_count * template.rewards_pool_per_user, 2)
        actions = [
            CampaignAction(
                action_type=a["action_type"],
                target_count=target_count,
                content=a["content"],
                trigger_delay_hours=a["trigger_delay_hours"],
            )
            for a in template.actions
        ]

        campaign = WinbackCampaign(
            campaign_id=f"wb-{game_id}-{uuid.uuid4().hex[:8]}",
            game_id=game_id,
            campaign_type=template.campaign_type,
            target_segment=target_segment,
            target_count=target_count,
            rewards_pool=rewards_pool,
            duration_days=template.duration_days,
            expected_participation=template.expected_participation,
            expected_retention_uplift=template.expected_retention_uplift,
            actions=actions,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._persist_campaign(campaign)
        logger.info(
            "LiveOpsAgent: designed campaign %s for %s (segment=%s, target=%d, type=%s)",
            campaign.campaign_id, game_id, target_segment, target_count, campaign.campaign_type,
        )

        # 跨 Agent 协同：发现高价值流失用户时广播 churn_alert
        if analysis.high_value_at_risk > 0:
            self._broadcast_event("churn_alert", {
                "game_id": game_id,
                "campaign_id": campaign.campaign_id,
                "high_value_at_risk": analysis.high_value_at_risk,
                "target_segment": target_segment,
                "target_count": target_count,
                "rewards_pool": rewards_pool,
            })

        return campaign

    def evaluate_campaign(self, campaign_id: str) -> CampaignEvaluation:
        """评估活动效果（对比前后指标）.

        由于不接入真实活动管理系统，基于活动方案的预期值生成确定性估算
        （expected_participation * 实际参与衰减系数）.
        """
        campaign = self._load_campaign(campaign_id)
        if campaign is None:
            return CampaignEvaluation(
                campaign_id=campaign_id,
                participation_rate=0.0,
                retention_uplift=0.0,
                revenue_uplift=0.0,
                player_satisfaction=0.0,
            )

        # 确定性估算: 预期参与率 * 衰减系数（基于 campaign_type）
        decay = {
            "login_bonus": 0.90,
            "special_offer": 0.75,
            "discount": 0.70,
            "push_re-engagement": 0.55,
        }.get(campaign.campaign_type, 0.70)

        participation = round(campaign.expected_participation * decay, 4)
        retention_uplift = round(campaign.expected_retention_uplift * decay, 4)
        # 收入提升: 基于奖励池和参与率的简单估算
        revenue_uplift = round(
            (campaign.rewards_pool * participation * 1.5) / max(campaign.target_count, 1), 4
        )
        satisfaction = round(0.5 + 0.4 * decay, 4)  # 0.5..0.9

        return CampaignEvaluation(
            campaign_id=campaign_id,
            participation_rate=participation,
            retention_uplift=retention_uplift,
            revenue_uplift=revenue_uplift,
            player_satisfaction=satisfaction,
        )

    # ── 活动列表 ─────────────────────────────────────────────

    def list_campaigns(self, game_id: str | None = None) -> list[WinbackCampaign]:
        """列出活动方案（可按 game_id 过滤）."""
        records = self._read_campaigns_jsonl()
        campaigns: list[WinbackCampaign] = []
        for r in records:
            if game_id and r.get("game_id") != game_id:
                continue
            campaigns.append(self._dict_to_campaign(r))
        return campaigns

    def get_campaign(self, campaign_id: str) -> WinbackCampaign | None:
        """获取单个活动方案."""
        return self._load_campaign(campaign_id)

    # ── 活动执行 (接入 ApprovalGate + 执行引擎) ─────────────

    def _get_executor(self) -> Any:
        """懒加载 WinbackCampaignExecutor (依赖注入)."""
        if self._executor is not None:
            return self._executor
        try:
            from .liveops_executor import WinbackCampaignExecutor
            self._executor = WinbackCampaignExecutor(data_dir=self.data_dir)
        except ImportError as exc:
            logger.warning("WinbackCampaignExecutor unavailable: %s", exc)
            self._executor = None
        return self._executor

    def execute_campaign(
        self,
        campaign_id: str,
        dry_run: bool = True,
    ) -> Any:
        """执行回流活动方案 — 接入 ApprovalGate 与执行引擎.

        Args:
            campaign_id: 活动方案 ID
            dry_run: True=只生成执行计划不真实下发; False=走完整审批+执行流程

        Returns:
            CampaignExecutionResult (含审批决策和每个动作的执行状态)

        Raises:
            ValueError: 活动方案不存在
        """
        campaign = self._load_campaign(campaign_id)
        if campaign is None:
            raise ValueError(f"Campaign {campaign_id} not found")

        executor = self._get_executor()
        if executor is None:
            raise RuntimeError("WinbackCampaignExecutor unavailable")

        # 动态切换 dry_run 模式
        original_dry_run = getattr(executor, "dry_run", True)
        if hasattr(executor, "dry_run"):
            executor.dry_run = dry_run
        if hasattr(executor, "adapter"):
            executor.adapter.dry_run = dry_run

        try:
            result = executor.execute_campaign(campaign)
        finally:
            # 恢复原始 dry_run 设置
            if hasattr(executor, "dry_run"):
                executor.dry_run = original_dry_run
            if hasattr(executor, "adapter"):
                executor.adapter.dry_run = original_dry_run

        # 回流到 CEO Memory (跨 Agent 可感知)
        self._write_ceo_memory(result)

        # 跨 Agent 协同：广播活动执行事件
        self._broadcast_event("campaign_executed", {
            "execution_id": result.execution_id,
            "campaign_id": campaign_id,
            "game_id": result.game_id,
            "status": result.status,
            "approval_level": result.approval_level,
            "dry_run": dry_run,
            "rewards_pool": result.rewards_pool,
            "action_count": len(result.actions),
        })

        logger.info(
            "LiveOpsAgent: executed campaign %s (status=%s, level=%d, dry_run=%s)",
            campaign_id, result.status, result.approval_level, dry_run,
        )
        return result

    def approve_campaign(
        self,
        execution_id: str,
        approver: str = "admin",
    ) -> Any:
        """人工审批通过 — 执行阻塞的活动."""
        executor = self._get_executor()
        if executor is None:
            raise RuntimeError("WinbackCampaignExecutor unavailable")
        result = executor.approve(execution_id, approver=approver)
        if result is not None:
            # 审批执行后回流到 CEO Memory
            self._write_ceo_memory(result)
            # 跨 Agent 协同：广播审批通过事件
            self._broadcast_event("campaign_approved", {
                "execution_id": result.execution_id,
                "campaign_id": result.campaign_id,
                "game_id": result.game_id,
                "approver": approver,
                "status": result.status,
                "rewards_distributed": result.rewards_pool,
            })
        return result

    def reject_campaign(
        self,
        execution_id: str,
        approver: str = "admin",
        reason: str = "",
    ) -> Any:
        """人工审批拒绝."""
        executor = self._get_executor()
        if executor is None:
            raise RuntimeError("WinbackCampaignExecutor unavailable")
        result = executor.reject(execution_id, approver=approver, reason=reason)
        if result is not None:
            # 拒绝也回流到 CEO Memory (记录拒绝决策)
            self._write_ceo_memory(result)
            # 跨 Agent 协同：广播拒绝事件
            self._broadcast_event("campaign_rejected", {
                "execution_id": result.execution_id,
                "campaign_id": result.campaign_id,
                "game_id": result.game_id,
                "approver": approver,
                "reason": reason,
            })
        return result

    def get_execution(self, execution_id: str) -> Any:
        """查询活动执行状态."""
        executor = self._get_executor()
        if executor is None:
            return None
        return executor.get_execution(execution_id)

    def list_executions(
        self, campaign_id: str | None = None
    ) -> list[Any]:
        """列出活动执行记录 (可按 campaign_id 过滤)."""
        executor = self._get_executor()
        if executor is None:
            return []
        return executor.list_executions(campaign_id=campaign_id)

    def list_pending_approvals(self) -> list[Any]:
        """列出待审批的活动执行."""
        executor = self._get_executor()
        if executor is None:
            return []
        return executor.list_pending_approvals()

    # ── CEO Memory 回流 (跨 Agent 可感知) ─────────────────────

    def _write_ceo_memory(self, result: Any) -> None:
        """把 LiveOps 执行结果写入 CEO execution_memory.jsonl.

        让 CEO / Growth / Data 等 Agent 能感知 LiveOps 的执行情况，
        用于跨 Agent 决策协同和经验学习。

        格式对齐 data/ceo/execution_memory.jsonl 现有 schema:
          execution_id / action_id / decision_id / game_id
          strategy_type / domain / action_type / status / success
          real_api_called / rolled_back / detail / created_at
        """
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        ceo_memory_path = Path(self.data_dir) / "ceo" / "execution_memory.jsonl"
        try:
            ceo_memory_path.parent.mkdir(parents=True, exist_ok=True)
            # 状态映射: LiveOps → CEO memory schema
            status_map = {
                "completed": "success",
                "blocked": "waiting_approval",
                "dry_run": "skipped",
                "failed": "failed",
                "rejected": "rejected",
                "approved": "success",
                "pending": "pending",
            }
            mapped_status = status_map.get(result.status, result.status)
            success = result.status == "completed"
            real_api_called = (not result.dry_run) and success

            with ceo_memory_path.open("a", encoding="utf-8") as f:
                for action in result.actions:
                    record = {
                        "execution_id": result.execution_id,
                        "action_id": action.action_id,
                        "decision_id": result.campaign_id,  # 活动方案 ID 作为决策 ID
                        "game_id": result.game_id,
                        "strategy_type": result.campaign_type,
                        "domain": "liveops",
                        "action_type": action.action_type,
                        "status": status_map.get(action.status, action.status),
                        "success": action.status == "completed",
                        "real_api_called": real_api_called,
                        "rolled_back": action.status == "failed",
                        "detail": (
                            f"liveops campaign={result.campaign_type} "
                            f"segment={result.target_segment} "
                            f"target={action.target_count} "
                            f"delivered={action.platform_response.get('delivered_count', 0)} "
                            f"rewards=${action.rewards_amount:.2f} "
                            f"level=L{action.approval_level} "
                            f"dry_run={result.dry_run}"
                        ),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("LiveOpsAgent: write CEO memory failed: %s", exc)

    def _broadcast_event(self, event_type: str, payload: dict) -> None:
        """通过 MessageBus 广播 LiveOps 事件，让其他 Agent 可订阅.

        事件类型:
          - campaign_executed: 活动执行完成 (含 status/level/rewards)
          - campaign_approved: 活动审批通过
          - campaign_rejected: 活动被拒绝
          - churn_alert: 发现高价值流失用户

        协同方向: LiveOps → All (广播)
        订阅方: CEO/Growth/Data Agent 可通过 MessageBus.subscribe 注册 handler
        """
        if self._message_bus is None or self._agent_identity is None:
            return  # 未注入消息总线，静默降级
        try:
            from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
                AgentMessage,
                MessageType,
                MessagePriority,
                MessageStatus,
            )
            from datetime import datetime, timezone
            import uuid as _uuid

            priority = MessagePriority.NORMAL
            if event_type in ("churn_alert", "campaign_approved"):
                priority = MessagePriority.HIGH

            message = AgentMessage(
                message_id=f"msg_{_uuid.uuid4().hex[:12]}",
                correlation_id="",
                sender=self._agent_identity,
                receiver=None,  # BROADCAST
                message_type=MessageType.BROADCAST,
                standard_type=None,
                subject=f"liveops:{event_type}",
                body={
                    "event_type": event_type,
                    "source_agent": "liveops",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **payload,
                },
                priority=priority,
                status=MessageStatus.CREATED,
                created_at=datetime.now(timezone.utc).isoformat(),
                sent_at="",
                delivered_at="",
                processed_at="",
                expires_at="",
                ttl_seconds=600.0,
                metadata={},
            )
            self._message_bus.send(message)
            logger.info(
                "LiveOpsAgent: broadcast event %s (subject=liveops:%s)",
                event_type, event_type,
            )
        except Exception as exc:
            logger.warning("LiveOpsAgent: broadcast event failed: %s", exc)

    # ── 持久化 ────────────────────────────────────────────────

    def _collect_profiles(self, game_id: str) -> list[Any]:
        """通过 EventCollector 收集玩家 profile."""
        collector = self._get_collector()
        if collector is None:
            return []
        try:
            return collector.collect(app_id=game_id)
        except Exception as exc:
            logger.warning("EventCollector.collect failed for %s: %s", game_id, exc)
            return []

    def _campaigns_path(self) -> Path:
        return Path(self.data_dir) / "liveops" / "campaigns.jsonl"

    def _analysis_path(self, game_id: str) -> Path:
        return Path(self.data_dir) / "liveops" / "churn_analysis" / f"{game_id}.jsonl"

    def _ensure_dir(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def _persist_analysis(self, analysis: ChurnAnalysis) -> None:
        path = self._analysis_path(analysis.game_id)
        try:
            self._ensure_dir(path)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(analysis.to_dict(), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Failed to persist analysis: %s", exc)

    def _persist_campaign(self, campaign: WinbackCampaign) -> None:
        path = self._campaigns_path()
        try:
            self._ensure_dir(path)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(campaign.to_dict(), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Failed to persist campaign: %s", exc)

    def _read_campaigns_jsonl(self) -> list[dict[str, Any]]:
        path = self._campaigns_path()
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def _load_campaign(self, campaign_id: str) -> WinbackCampaign | None:
        for r in self._read_campaigns_jsonl():
            if r.get("campaign_id") == campaign_id:
                return self._dict_to_campaign(r)
        return None

    @staticmethod
    def _dict_to_campaign(r: dict[str, Any]) -> WinbackCampaign:
        actions = [
            CampaignAction(
                action_type=a.get("action_type", ""),
                target_count=int(a.get("target_count", 0)),
                content=a.get("content", ""),
                trigger_delay_hours=int(a.get("trigger_delay_hours", 0)),
            )
            for a in (r.get("actions") or [])
        ]
        return WinbackCampaign(
            campaign_id=r.get("campaign_id", ""),
            game_id=r.get("game_id", ""),
            campaign_type=r.get("campaign_type", ""),
            target_segment=r.get("target_segment", ""),
            target_count=int(r.get("target_count", 0)),
            rewards_pool=float(r.get("rewards_pool", 0.0)),
            duration_days=int(r.get("duration_days", 0)),
            expected_participation=float(r.get("expected_participation", 0.0)),
            expected_retention_uplift=float(r.get("expected_retention_uplift", 0.0)),
            actions=actions,
            created_at=r.get("created_at", ""),
        )


# ═══════════════════════════════════════════════════════════════
# Agent 身份工厂（供 agent_message.create_liveops_agent_identity 调用）
# ═══════════════════════════════════════════════════════════════

LIVEOPS_CAPABILITIES = [
    "churn_analysis",
    "winback_campaign_design",
    "lifecycle_segmentation",
    "retention_uplift",
    "player_re_engagement",
]


def create_liveops_agent() -> LiveOpsAgent:
    """创建默认 LiveOpsAgent 实例（workspace 单例入口）."""
    return LiveOpsAgent(data_dir="data")
