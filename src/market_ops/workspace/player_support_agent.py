"""Player Support Agent — 玩家服务与舆情管理.

与 LiveOps Agent 的边界:
  - LiveOps: 偏活动设计 (召回活动/礼包配置/活动执行)
  - Player Support: 偏用户沟通 (工单/FAQ/客诉/舆情)

设计原则（继承纪律红线）:
  - 默认 dry_run：自动回复只生成不发送
  - 参数走配置（PlayerSupportConfig），禁止硬编码
  - 接入 MessageBus 广播支持事件
  - 执行结果回流 CEO Memory（domain="player_support"）

数据流:
  玩家反馈(工单/评论/评分) → PlayerSupportAgent → TicketRecord /
  FAQEntry / SentimentReport / VIPServiceRecord / SatisfactionReport
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
# 数据模型
# ═══════════════════════════════════════════════════════════════


@dataclass
class TicketRecord:
    """工单记录."""

    ticket_id: str
    game_id: str
    player_id: str
    category: str               # payment / bug / account / gameplay / other
    priority: str               # low / medium / high / critical
    subject: str
    description: str
    status: str                 # open / in_progress / resolved / escalated / closed
    assigned_to: str            # auto / human / vip_team
    auto_reply: str             # 自动回复内容
    sla_deadline: str           # SLA 截止时间
    resolution_time_hours: float  # 解决时长 (小时)
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "game_id": self.game_id,
            "player_id": self.player_id,
            "category": self.category,
            "priority": self.priority,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "auto_reply": self.auto_reply,
            "sla_deadline": self.sla_deadline,
            "resolution_time_hours": round(self.resolution_time_hours, 2),
            "created_at": self.created_at,
        }


@dataclass
class FAQEntry:
    """FAQ 知识库条目."""

    faq_id: str
    game_id: str
    question: str
    answer: str
    category: str               # payment / gameplay / account / technical / social
    view_count: int
    helpful_count: int
    helpful_rate: float         # 帮助率 (0..1)
    last_updated: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "faq_id": self.faq_id,
            "game_id": self.game_id,
            "question": self.question,
            "answer": self.answer,
            "category": self.category,
            "view_count": self.view_count,
            "helpful_count": self.helpful_count,
            "helpful_rate": round(self.helpful_rate, 4),
            "last_updated": self.last_updated,
            "created_at": self.created_at,
        }


@dataclass
class SentimentReport:
    """舆情报告 — 评分/评论/社媒情绪."""

    report_id: str
    game_id: str
    period: str
    avg_rating: float            # 平均评分 (0..5)
    total_reviews: int
    sentiment_score: float       # 情绪分 (0..100, 越高越正面)
    positive_count: int
    negative_count: int
    neutral_count: int
    top_complaints: list[dict[str, Any]]  # 主要投诉点
    top_praises: list[str]       # 主要好评点
    trend: str                   # improving / stable / declining
    crisis_alerts: list[dict[str, Any]]  # 危机告警
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "game_id": self.game_id,
            "period": self.period,
            "avg_rating": round(self.avg_rating, 2),
            "total_reviews": self.total_reviews,
            "sentiment_score": round(self.sentiment_score, 1),
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "neutral_count": self.neutral_count,
            "top_complaints": self.top_complaints,
            "top_praises": self.top_praises,
            "trend": self.trend,
            "crisis_alerts": self.crisis_alerts,
            "created_at": self.created_at,
        }


@dataclass
class VIPServiceRecord:
    """VIP 服务记录."""

    service_id: str
    game_id: str
    player_id: str
    vip_level: str               # gold / platinum / diamond
    service_type: str            # dedicated_channel / priority_response / gift / exclusive_content
    request: str
    response: str
    response_time_minutes: float  # 响应时长 (分钟)
    satisfaction: float          # 满意度 (0..1)
    handled_by: str              # vip_team / dedicated_manager
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "game_id": self.game_id,
            "player_id": self.player_id,
            "vip_level": self.vip_level,
            "service_type": self.service_type,
            "request": self.request,
            "response": self.response,
            "response_time_minutes": round(self.response_time_minutes, 1),
            "satisfaction": round(self.satisfaction, 2),
            "handled_by": self.handled_by,
            "created_at": self.created_at,
        }


@dataclass
class SatisfactionReport:
    """满意度报告 — CSAT/NPS."""

    report_id: str
    game_id: str
    period: str
    csat_score: float            # CSAT (0..100)
    nps_score: float             # NPS (-100..100)
    total_responses: int
    promoter_count: int          # 推荐者 (9-10)
    passive_count: int           # 中立者 (7-8)
    detractor_count: int         # 贬损者 (0-6)
    csat_by_category: dict[str, float]  # 按工单类别 CSAT
    improvement_areas: list[str]  # 改进建议
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "game_id": self.game_id,
            "period": self.period,
            "csat_score": round(self.csat_score, 1),
            "nps_score": round(self.nps_score, 1),
            "total_responses": self.total_responses,
            "promoter_count": self.promoter_count,
            "passive_count": self.passive_count,
            "detractor_count": self.detractor_count,
            "csat_by_category": {
                k: round(v, 1) for k, v in self.csat_by_category.items()
            },
            "improvement_areas": self.improvement_areas,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# 配置（禁止硬编码，参数走配置）
# ═══════════════════════════════════════════════════════════════


@dataclass
class PlayerSupportConfig:
    """玩家服务配置."""

    sla_hours_by_priority: dict[str, float] = field(
        default_factory=lambda: {
            "critical": 1.0,
            "high": 4.0,
            "medium": 24.0,
            "low": 72.0,
        }
    )
    auto_reply_enabled: bool = True
    vip_threshold_revenue: float = 500.0   # 累计消费达到此值视为 VIP
    sentiment_crisis_threshold: float = 40.0  # 情绪分低于此值触发危机告警
    min_nps_survey_responses: int = 50     # NPS 调查最小响应数


# ═══════════════════════════════════════════════════════════════
# 反馈数据输入
# ═══════════════════════════════════════════════════════════════


@dataclass
class PlayerFeedback:
    """玩家反馈数据输入 — 从客服系统/应用商店/社媒获取."""

    game_id: str
    total_tickets: int = 120
    tickets_by_category: dict[str, int] = field(
        default_factory=lambda: {
            "payment": 35,
            "bug": 28,
            "account": 20,
            "gameplay": 25,
            "other": 12,
        }
    )
    avg_rating: float = 4.2
    total_reviews: int = 8500
    positive_reviews: int = 6120
    negative_reviews: int = 1530
    neutral_reviews: int = 850
    vip_players: int = 45
    csat_score: float = 82.0
    nps_responses: int = 320
    promoters: int = 180
    passives: int = 90
    detractors: int = 50
    sample_complaints: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"topic": "充值未到账", "count": 85, "severity": "high"},
            {"topic": "闪退/卡顿", "count": 62, "severity": "medium"},
            {"topic": "账号丢失", "count": 28, "severity": "critical"},
            {"topic": "难度过高", "count": 45, "severity": "low"},
        ]
    )
    sample_praises: list[str] = field(
        default_factory=lambda: [
            "画面精美，玩法有趣",
            "客服响应及时，问题解决快",
            "活动丰富，奖励丰厚",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════
# Player Support Agent
# ═══════════════════════════════════════════════════════════════


class PlayerSupportAgent:
    """Player Support Agent — 玩家服务与舆情管理.

    用法:
        agent = PlayerSupportAgent(data_dir="data")
        ticket = agent.process_ticket(game_id, player_id, category, subject, description)
        faqs = agent.manage_faq(game_id, action="list")
        sentiment = agent.monitor_sentiment(game_id, feedback)
        vip = agent.serve_vip(game_id, player_id, vip_level, request)
        satisfaction = agent.analyze_satisfaction(game_id, feedback)
    """

    def __init__(
        self,
        data_dir: str = "data",
        config: PlayerSupportConfig | None = None,
        message_bus: Any = None,
        agent_identity: Any = None,
    ) -> None:
        self.data_dir = data_dir
        self.config = config or PlayerSupportConfig()
        self._message_bus = message_bus
        self._agent_identity = agent_identity

    # ── 核心方法 ─────────────────────────────────────────────

    def process_ticket(
        self, game_id: str, player_id: str, category: str,
        subject: str, description: str, priority: str = "medium"
    ) -> TicketRecord:
        """处理工单 — 自动分类/路由/回复.

        Args:
            game_id: 游戏 ID
            player_id: 玩家 ID
            category: 工单类别 (payment/bug/account/gameplay/other)
            subject: 工单主题
            description: 工单描述
            priority: 优先级 (low/medium/high/critical)

        Returns:
            TicketRecord 实例
        """
        # 优先级判定（如果未指定，根据类别自动判定）
        if priority == "medium" and category in ("payment", "account"):
            priority = "high"

        # 自动路由
        assigned_to = self._route_ticket(category, priority)

        # 自动回复
        auto_reply = self._generate_auto_reply(category, subject, priority)

        # SLA 截止时间
        sla_hours = self.config.sla_hours_by_priority.get(priority, 24.0)

        # 模拟解决时长（自动处理的快，人工的慢）
        if assigned_to == "auto":
            resolution_time = sla_hours * 0.1  # 自动处理 10% SLA 时间
            status = "resolved"
        else:
            resolution_time = sla_hours * 0.5  # 人工处理 50% SLA 时间
            status = "in_progress"

        ticket = TicketRecord(
            ticket_id=f"tk_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            player_id=player_id,
            category=category,
            priority=priority,
            subject=subject,
            description=description,
            status=status,
            assigned_to=assigned_to,
            auto_reply=auto_reply,
            sla_deadline=_now_iso(),  # 简化：用当前时间作为 SLA 基准
            resolution_time_hours=resolution_time,
            created_at=_now_iso(),
        )

        self._persist_ticket(ticket)
        self._broadcast_event("ticket_processed", {
            "ticket_id": ticket.ticket_id, "game_id": game_id,
            "category": category, "priority": priority,
            "status": status, "assigned_to": assigned_to,
        })
        self._write_ceo_memory({
            "execution_id": ticket.ticket_id,
            "action_id": f"ticket_{ticket.ticket_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "ticket_management",
            "domain": "player_support",
            "action_type": "ticket_management",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"Ticket {category}/{priority}, assigned={assigned_to}, status={status}",
        })

        logger.info("Ticket processed: %s (%s/%s, assigned=%s)",
                    ticket.ticket_id, category, priority, assigned_to)
        return ticket

    def manage_faq(
        self, game_id: str, action: str = "list",
        question: str = "", answer: str = "", category: str = "other",
        faq_id: str = ""
    ) -> dict[str, Any]:
        """FAQ 知识库管理.

        Args:
            game_id: 游戏 ID
            action: 操作 (list/create/update/search)
            question: 问题 (create/update 时必填)
            answer: 答案 (create/update 时必填)
            category: 类别
            faq_id: FAQ ID (update 时必填)

        Returns:
            操作结果 dict
        """
        if action == "list":
            faqs = self.list_faqs()
            return {"action": "list", "total": len(faqs), "faqs": faqs}

        elif action == "create":
            if not question or not answer:
                return {"action": "create", "success": False, "error": "question and answer required"}
            faq = FAQEntry(
                faq_id=f"faq_{uuid.uuid4().hex[:12]}",
                game_id=game_id,
                question=question,
                answer=answer,
                category=category,
                view_count=0,
                helpful_count=0,
                helpful_rate=0.0,
                last_updated=_now_iso(),
                created_at=_now_iso(),
            )
            self._persist_faq(faq)
            self._broadcast_event("faq_created", {
                "faq_id": faq.faq_id, "game_id": game_id,
                "category": category,
            })
            self._write_ceo_memory({
                "execution_id": faq.faq_id,
                "action_id": f"faq_{faq.faq_id}",
                "decision_id": game_id,
                "game_id": game_id,
                "strategy_type": "faq_management",
                "domain": "player_support",
                "action_type": "faq_knowledge_base",
                "status": "success", "success": True,
                "real_api_called": False, "rolled_back": False,
                "detail": f"FAQ created: {question[:50]}",
            })
            return {"action": "create", "success": True, "faq": faq.to_dict()}

        elif action == "search":
            faqs = self.list_faqs(limit=100)
            results = [
                f for f in faqs
                if question.lower() in f.get("question", "").lower()
                or question.lower() in f.get("answer", "").lower()
            ]
            return {"action": "search", "query": question, "results": results[:10]}

        return {"action": action, "success": False, "error": f"unknown action: {action}"}

    def monitor_sentiment(
        self, game_id: str, feedback: PlayerFeedback
    ) -> SentimentReport:
        """舆情监控 — 评分/评论/社媒情绪分析.

        Args:
            game_id: 游戏 ID
            feedback: 反馈数据

        Returns:
            SentimentReport 实例
        """
        # 情绪分计算
        positive_ratio = feedback.positive_reviews / max(feedback.total_reviews, 1)
        negative_ratio = feedback.negative_reviews / max(feedback.total_reviews, 1)
        sentiment_score = positive_ratio * 100 - negative_ratio * 30
        sentiment_score = max(0, min(100, sentiment_score))

        # 趋势判断
        if feedback.avg_rating >= 4.5:
            trend = "improving"
        elif feedback.avg_rating >= 4.0:
            trend = "stable"
        else:
            trend = "declining"

        # 危机告警
        crisis_alerts: list[dict[str, Any]] = []
        if sentiment_score < self.config.sentiment_crisis_threshold:
            crisis_alerts.append({
                "type": "low_sentiment",
                "severity": "critical",
                "message": f"情绪分 {sentiment_score:.0f} 低于危机阈值 {self.config.sentiment_crisis_threshold}",
            })
        for complaint in feedback.sample_complaints:
            if complaint.get("severity") == "critical":
                crisis_alerts.append({
                    "type": "critical_complaint",
                    "severity": "critical",
                    "message": f"严重投诉: {complaint['topic']} ({complaint['count']} 起)",
                })

        # 主要投诉点排序
        top_complaints = sorted(
            feedback.sample_complaints,
            key=lambda x: x.get("count", 0), reverse=True
        )[:5]

        report = SentimentReport(
            report_id=f"sent_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            period=datetime.now(timezone.utc).strftime("%Y-W%W"),
            avg_rating=feedback.avg_rating,
            total_reviews=feedback.total_reviews,
            sentiment_score=sentiment_score,
            positive_count=feedback.positive_reviews,
            negative_count=feedback.negative_reviews,
            neutral_count=feedback.neutral_reviews,
            top_complaints=top_complaints,
            top_praises=feedback.sample_praises,
            trend=trend,
            crisis_alerts=crisis_alerts,
            created_at=_now_iso(),
        )

        self._persist_sentiment_report(report)
        self._broadcast_event("sentiment_monitored", {
            "report_id": report.report_id, "game_id": game_id,
            "sentiment_score": round(sentiment_score, 1),
            "trend": trend,
            "crisis_count": len(crisis_alerts),
        })
        self._write_ceo_memory({
            "execution_id": report.report_id,
            "action_id": f"sentiment_{report.report_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "sentiment_monitoring",
            "domain": "player_support",
            "action_type": "sentiment_monitoring",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"Sentiment={sentiment_score:.0f}, rating={feedback.avg_rating:.1f}, trend={trend}",
        })

        logger.info("Sentiment monitored: %s (score=%.1f, trend=%s, %d crises)",
                    game_id, sentiment_score, trend, len(crisis_alerts))
        return report

    def serve_vip(
        self, game_id: str, player_id: str, vip_level: str, request: str
    ) -> VIPServiceRecord:
        """VIP 服务 — 高价值玩家专属服务.

        Args:
            game_id: 游戏 ID
            player_id: 玩家 ID
            vip_level: VIP 等级 (gold/platinum/diamond)
            request: 服务请求

        Returns:
            VIPServiceRecord 实例
        """
        # 根据等级决定服务类型和响应时间
        service_configs = {
            "diamond": {
                "service_type": "dedicated_channel",
                "response_time": 5.0,
                "handled_by": "dedicated_manager",
                "satisfaction": 0.95,
            },
            "platinum": {
                "service_type": "priority_response",
                "response_time": 15.0,
                "handled_by": "vip_team",
                "satisfaction": 0.90,
            },
            "gold": {
                "service_type": "priority_response",
                "response_time": 30.0,
                "handled_by": "vip_team",
                "satisfaction": 0.85,
            },
        }
        cfg = service_configs.get(vip_level, service_configs["gold"])

        # 生成响应
        response = self._generate_vip_response(request, vip_level)

        record = VIPServiceRecord(
            service_id=f"vip_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            player_id=player_id,
            vip_level=vip_level,
            service_type=cfg["service_type"],
            request=request,
            response=response,
            response_time_minutes=cfg["response_time"],
            satisfaction=cfg["satisfaction"],
            handled_by=cfg["handled_by"],
            created_at=_now_iso(),
        )

        self._persist_vip_record(record)
        self._broadcast_event("vip_served", {
            "service_id": record.service_id, "game_id": game_id,
            "vip_level": vip_level,
            "response_time": cfg["response_time"],
        })
        self._write_ceo_memory({
            "execution_id": record.service_id,
            "action_id": f"vip_{record.service_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "vip_service",
            "domain": "player_support",
            "action_type": "vip_service",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"VIP {vip_level} served in {cfg['response_time']:.0f}min, satisfaction={cfg['satisfaction']:.0%}",
        })

        logger.info("VIP served: %s (%s, %s, %.0fmin)",
                    player_id, vip_level, cfg["service_type"], cfg["response_time"])
        return record

    def analyze_satisfaction(
        self, game_id: str, feedback: PlayerFeedback
    ) -> SatisfactionReport:
        """满意度分析 — CSAT/NPS 跟踪.

        Args:
            game_id: 游戏 ID
            feedback: 反馈数据

        Returns:
            SatisfactionReport 实例
        """
        # NPS = 推荐者% - 贬损者%
        total = max(feedback.nps_responses, 1)
        promoter_pct = feedback.promoters / total
        detractor_pct = feedback.detractors / total
        nps_score = (promoter_pct - detractor_pct) * 100

        # 按类别 CSAT（模拟）
        csat_by_category: dict[str, float] = {
            "payment": feedback.csat_score - 5.0,
            "bug": feedback.csat_score - 8.0,
            "account": feedback.csat_score + 2.0,
            "gameplay": feedback.csat_score + 5.0,
            "other": feedback.csat_score,
        }

        # 改进建议
        improvement_areas: list[str] = []
        if nps_score < 30:
            improvement_areas.append(f"NPS {nps_score:.0f} 偏低，需提升整体体验")
        if csat_by_category.get("bug", 0) < 75:
            improvement_areas.append("Bug 类工单 CSAT 偏低，需提升 Bug 修复速度")
        if csat_by_category.get("payment", 0) < 80:
            improvement_areas.append("支付类工单 CSAT 偏低，需优化支付流程")
        if feedback.detractors / total > 0.2:
            improvement_areas.append(f"贬损者占比 {feedback.detractors/total:.0%}，需主动跟进")
        if not improvement_areas:
            improvement_areas.append("满意度指标健康，持续监控")

        report = SatisfactionReport(
            report_id=f"sat_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            period=datetime.now(timezone.utc).strftime("%Y-W%W"),
            csat_score=feedback.csat_score,
            nps_score=nps_score,
            total_responses=feedback.nps_responses,
            promoter_count=feedback.promoters,
            passive_count=feedback.passives,
            detractor_count=feedback.detractors,
            csat_by_category=csat_by_category,
            improvement_areas=improvement_areas,
            created_at=_now_iso(),
        )

        self._persist_satisfaction_report(report)
        self._broadcast_event("satisfaction_analyzed", {
            "report_id": report.report_id, "game_id": game_id,
            "csat": round(feedback.csat_score, 1),
            "nps": round(nps_score, 1),
        })
        self._write_ceo_memory({
            "execution_id": report.report_id,
            "action_id": f"satisfaction_{report.report_id}",
            "decision_id": game_id,
            "game_id": game_id,
            "strategy_type": "satisfaction_analysis",
            "domain": "player_support",
            "action_type": "satisfaction_analysis",
            "status": "success", "success": True,
            "real_api_called": False, "rolled_back": False,
            "detail": f"CSAT={feedback.csat_score:.0f}, NPS={nps_score:.0f}, responses={feedback.nps_responses}",
        })

        logger.info("Satisfaction analyzed: %s (CSAT=%.1f, NPS=%.1f)",
                    game_id, feedback.csat_score, nps_score)
        return report

    # ── 查询方法 ─────────────────────────────────────────────

    def list_tickets(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "player_support" / "tickets.jsonl"
        return _read_jsonl(path, limit)

    def list_faqs(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "player_support" / "faqs.jsonl"
        return _read_jsonl(path, limit)

    def list_sentiment_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "player_support" / "sentiment_reports.jsonl"
        return _read_jsonl(path, limit)

    def list_vip_records(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "player_support" / "vip_records.jsonl"
        return _read_jsonl(path, limit)

    def list_satisfaction_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        path = Path(self.data_dir) / "player_support" / "satisfaction_reports.jsonl"
        return _read_jsonl(path, limit)

    def get_stats(self) -> dict[str, Any]:
        tickets = self.list_tickets(limit=1000)
        faqs = self.list_faqs(limit=1000)
        sentiments = self.list_sentiment_reports(limit=1000)
        vip_records = self.list_vip_records(limit=1000)
        satisfactions = self.list_satisfaction_reports(limit=1000)

        # 工单状态分布
        ticket_status_dist: dict[str, int] = {}
        for t in tickets:
            s = t.get("status", "unknown")
            ticket_status_dist[s] = ticket_status_dist.get(s, 0) + 1

        # 工单类别分布
        ticket_category_dist: dict[str, int] = {}
        for t in tickets:
            c = t.get("category", "unknown")
            ticket_category_dist[c] = ticket_category_dist.get(c, 0) + 1

        return {
            "total_tickets": len(tickets),
            "total_faqs": len(faqs),
            "total_sentiment_reports": len(sentiments),
            "total_vip_records": len(vip_records),
            "total_satisfaction_reports": len(satisfactions),
            "ticket_status_distribution": ticket_status_dist,
            "ticket_category_distribution": ticket_category_dist,
            "recent_sentiment": sentiments[:5],
        }

    # ── 内部方法 ─────────────────────────────────────────────

    def _route_ticket(self, category: str, priority: str) -> str:
        """工单路由 — 决定分配给自动/人工/VIP 团队."""
        if priority == "critical":
            return "human"
        if category in ("payment", "account") and priority == "high":
            return "human"
        if category == "bug" and priority in ("high", "critical"):
            return "human"
        return "auto"

    def _generate_auto_reply(self, category: str, subject: str, priority: str) -> str:
        """生成自动回复."""
        templates = {
            "payment": (
                f"感谢您反馈【{subject}】。我们已收到您的支付相关问题工单，"
                f"客服团队将在 {self.config.sla_hours_by_priority.get(priority, 24):.0f} 小时内处理。"
                f"如涉及充值未到账，请提供订单号和支付凭证以加速处理。"
            ),
            "bug": (
                f"感谢您反馈【{subject}】。我们已记录此 Bug，"
                f"开发团队将优先排查。请提供设备型号、系统版本和复现步骤以便定位问题。"
            ),
            "account": (
                f"感谢您反馈【{subject}】。账号安全问题已优先处理，"
                f"请提供您的玩家 ID 和注册邮箱以验证身份。"
            ),
            "gameplay": (
                f"感谢您反馈【{subject}】。您的游戏玩法建议已转交产品团队，"
                f"我们会在后续版本更新中评估。"
            ),
            "other": (
                f"感谢您反馈【{subject}】。我们已收到您的工单，"
                f"客服团队将在 {self.config.sla_hours_by_priority.get(priority, 24):.0f} 小时内回复。"
            ),
        }
        return templates.get(category, templates["other"])

    def _generate_vip_response(self, request: str, vip_level: str) -> str:
        """生成 VIP 响应."""
        return (
            f"尊敬的 {vip_level.upper()} 会员，您好！\n"
            f"您的请求【{request}】已由专属团队处理。\n"
            f"作为 {vip_level} 会员，您享有优先处理权益，"
            f"如有其他需求请随时联系您的专属客服经理。"
        )

    # ── 持久化 ─────────────────────────────────────────────

    def _persist_ticket(self, ticket: TicketRecord) -> None:
        path = Path(self.data_dir) / "player_support" / "tickets.jsonl"
        _append_jsonl(path, ticket.to_dict())

    def _persist_faq(self, faq: FAQEntry) -> None:
        path = Path(self.data_dir) / "player_support" / "faqs.jsonl"
        _append_jsonl(path, faq.to_dict())

    def _persist_sentiment_report(self, report: SentimentReport) -> None:
        path = Path(self.data_dir) / "player_support" / "sentiment_reports.jsonl"
        _append_jsonl(path, report.to_dict())

    def _persist_vip_record(self, record: VIPServiceRecord) -> None:
        path = Path(self.data_dir) / "player_support" / "vip_records.jsonl"
        _append_jsonl(path, record.to_dict())

    def _persist_satisfaction_report(self, report: SatisfactionReport) -> None:
        path = Path(self.data_dir) / "player_support" / "satisfaction_reports.jsonl"
        _append_jsonl(path, report.to_dict())

    # ── 跨 Agent 协同 ──────────────────────────────────────

    def _broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
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
                subject=f"player_support:{event_type}",
                body={"event_type": event_type, "source_agent": "player_support", **payload},
                priority=MessagePriority.NORMAL,
                ttl_seconds=600.0,
            )
            self._message_bus.send(message)
        except Exception as exc:
            logger.warning("PlayerSupportAgent broadcast event failed: %s", exc)

    def _write_ceo_memory(self, record: dict[str, Any]) -> None:
        ceo_memory_path = Path(self.data_dir) / "ceo" / "execution_memory.jsonl"
        ceo_memory_path.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("created_at", _now_iso())
        with ceo_memory_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _now_iso() -> str:
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
