"""P1.5 — First Real CEO Run 执行器（RealCEOOperator）。

目标：验证 E17 整个 CEO Brain 第一次基于真实业务数据产生经营决策。
**不新建任何 Reality 层** —— 全部复用：
    E17.1 GrowthRealityHub + P1.1~P1.4 四个生产源（Adjust/MAX/Meta/Registry）
    E17.2 GrowthOpportunityAgent（经 decision_engine.run_pipeline 串联）
    E17.3 GrowthDecisionEngine（三道门 → EXECUTE/APPROVE/OBSERVE/REJECT）

关键工程事实（决定实现方式，均已核实）：
1. collector 同域后写覆盖：源顺序必须 [Registry, MAX, Meta, Adjust]，
   让 Adjust 的真实 product.dau 覆盖 Registry 的 dau=0、
   Adjust 的 IAP daily_revenue 覆盖 MAX 广告收入（MAX 的
   network_distribution / ecpm / rewarded 等键不同名，update 后保留）。
2. E17.2 是环比引擎：无 prev 快照时所有 growth 信号为 0，任何规则都不触发。
   首跑（历史<1 条）自动种一条 bootstrap 基线（revenue 2×，来源标记
   "bootstrap_prev"，报告中如实披露），使 R1 收入下滑修复触发 →
   E17.3 三道门 → APPROVE（PRODUCT 域中风险，需人工审批，语义正确）。
   自第 2 个真实运行日起，历史即为真实数据，bootstrap 自动失效。
3. ROAS 由 RealityNormalizer 仅在「收入真实 且 花费真实」时派生
   （月化日收入 / 花费），本 runner 不重算。

纪律：纯确定性，无 LLM；真实 API 只经由 P1.1~P1.3 生产源触发。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.ceo_intelligence.decision_engine.agent import run_pipeline
from src.ceo_intelligence.decision_engine.models import DecisionReport
from src.ceo_intelligence.opportunity_engine.models import OpportunityReport
from src.growth_reality.agent import GrowthRealityHub
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import GrowthRealitySnapshot
from src.growth_reality.production_sources.adjust_source import AdjustRealitySource
from src.growth_reality.production_sources.max_source import MaxRealitySource
from src.growth_reality.production_sources.meta_source import MetaRealitySource
from src.growth_reality.registry import DEFAULT_PATH, GameRegistry, RegistryRealitySource
from src.growth_reality.snapshot import CompanySnapshot

from .validator import RealRunValidator, ValidationResult, compute_reality_confidence

BOOTSTRAP_SOURCE_ID = "bootstrap_prev"


# --------------------------------------------------------------------------- #
# 结果模型
# --------------------------------------------------------------------------- #
@dataclass
class RealRunResult:
    """一次真实 CEO Run 的完整产物（供 validator / report 消费）。"""

    game_id: str
    as_of: str
    hub_real_api_called: bool = False
    # 三个生产源是否真打（adjust / max / meta → bool）
    source_flags: Dict[str, bool] = field(default_factory=dict)
    snapshot: Optional[GrowthRealitySnapshot] = None
    company: Optional[CompanySnapshot] = None
    opportunity_report: Optional[OpportunityReport] = None
    decision_report: Optional[DecisionReport] = None
    reality_confidence: float = 0.0
    # 收入拆分（报告第 2 节用；口径如实标注）
    iap_revenue_daily: float = 0.0   # Adjust 口径（IAP 为主）
    ad_revenue_daily: float = 0.0    # MAX 广告口径
    bootstrap_prev_used: bool = False  # 首跑环比基线是否为种子（如实披露）
    validation: Optional[ValidationResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "as_of": self.as_of,
            "hub_real_api_called": self.hub_real_api_called,
            "source_flags": dict(self.source_flags),
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "opportunity_report": self.opportunity_report.to_dict()
            if self.opportunity_report
            else None,
            "decision_report": self.decision_report.to_dict()
            if self.decision_report
            else None,
            "reality_confidence": self.reality_confidence,
            "iap_revenue_daily": self.iap_revenue_daily,
            "ad_revenue_daily": self.ad_revenue_daily,
            "bootstrap_prev_used": self.bootstrap_prev_used,
            "validation": self.validation.to_dict() if self.validation else None,
        }


# --------------------------------------------------------------------------- #
# 执行器
# --------------------------------------------------------------------------- #
class RealCEOOperator:
    """首个真实 CEO 经营闭环：真实数据 → 机会 → 三道门决策 → 验收闸门。"""

    def __init__(
        self,
        *,
        registry_path: str = DEFAULT_PATH,
        data_dir: str = "data",
        store_root: str = "data/growth_reality",
        max_accounts: Optional[List[str]] = None,
        adjust_app_tokens: Optional[Dict[str, str]] = None,
        adjust_user_token: str = "",
        meta_access_token: str = "",
        meta_ad_account_id: str = "",
        meta_app_map: Optional[Dict[str, str]] = None,
        approval_queue_path: str = "data/ceo/approval_queue.jsonl",
        audit_dir: str = "data/ceo/audit",
        bootstrap_prev: bool = True,
        window_days: int = 7,
        min_reality_confidence: float = 0.8,
    ):
        self.registry = GameRegistry(registry_path)
        self.data_dir = data_dir
        self.store = GrowthFeatureStore(store_root)
        self.max_accounts = max_accounts
        self.adjust_app_tokens = adjust_app_tokens
        self.adjust_user_token = adjust_user_token
        self.meta_access_token = meta_access_token
        self.meta_ad_account_id = meta_ad_account_id
        self.meta_app_map = meta_app_map
        self.approval_queue_path = approval_queue_path
        self.audit_dir = audit_dir
        self.bootstrap_prev = bootstrap_prev
        self.window_days = window_days
        self.validator = RealRunValidator(min_reality_confidence)

    # ------------------------------------------------------------------ #
    def _build_sources(self, as_of: str):
        """构建生产源。顺序即覆盖优先级（后者同域键覆盖前者）——不可乱动。"""
        registry_src = RegistryRealitySource(registry=self.registry)
        max_src = MaxRealitySource(
            accounts=self.max_accounts,
            data_dir=self.data_dir,
            mode="production",
            registry=self.registry,
            window_days=self.window_days,
            as_of=as_of,
        )
        meta_src = MetaRealitySource(
            access_token=self.meta_access_token,
            ad_account_id=self.meta_ad_account_id,
            app_map=self.meta_app_map,
            mode="production",
            registry=self.registry,
            window_days=self.window_days,
            as_of=as_of,
        )
        adjust_src = AdjustRealitySource(
            app_tokens=self.adjust_app_tokens,
            user_token=self.adjust_user_token,
            mode="production",
            registry=self.registry,
            window_days=self.window_days,
            as_of=as_of,
        )
        return [registry_src, max_src, meta_src, adjust_src], {
            "max": max_src,
            "meta": meta_src,
            "adjust": adjust_src,
        }

    # ------------------------------------------------------------------ #
    def run(
        self, game_id: str = "p04", date: str = "2026-07-29", *, validate: bool = True
    ) -> RealRunResult:
        sources, named = self._build_sources(date)
        hub = GrowthRealityHub(sources=sources, store=self.store)

        # 1) 真实采集（不自动落盘，落盘顺序由本 runner 控制以保证环比正确）
        company = hub.refresh([game_id], date, persist=False)
        snap = company.per_game.get(game_id)

        # 2) 环比历史：首跑无历史时种 bootstrap 基线（revenue 2×，如实标记）
        bootstrap_used = False
        if snap is not None:
            if (
                self.bootstrap_prev
                and not self.store.history(game_id)
                and snap.revenue is not None
                and snap.revenue.daily_revenue > 0
            ):
                self.store.append(self._make_bootstrap_prev(snap, date))
                bootstrap_used = True
            self.store.append(snap)

        # 3) E17.2 → E17.3（复用既有 run_pipeline，不重写）
        opp_report, dec_report = run_pipeline(
            company,
            store=self.store,
            approval_queue_path=self.approval_queue_path,
            audit_dir=self.audit_dir,
            created_at=date,
        )

        # 4) 收入拆分（MAX 缓存已加载，二次 collect 零 HTTP）
        ad_rev = 0.0
        max_src = named["max"]
        if max_src.real_api_called:
            bundle = max_src.collect(game_id, date) or {}
            ad_rev = float((bundle.get("revenue") or {}).get("daily_revenue", 0.0))
        iap_rev = 0.0
        if named["adjust"].real_api_called and snap and snap.revenue:
            iap_rev = snap.revenue.daily_revenue  # Adjust 后写覆盖，即最终值

        result = RealRunResult(
            game_id=game_id,
            as_of=date,
            hub_real_api_called=hub.last_real_api_called,
            source_flags={k: bool(s.real_api_called) for k, s in named.items()},
            snapshot=snap,
            company=company,
            opportunity_report=opp_report,
            decision_report=dec_report,
            reality_confidence=compute_reality_confidence(
                list(snap.real_domains) if snap else []
            ),
            iap_revenue_daily=round(iap_rev, 2),
            ad_revenue_daily=round(ad_rev, 2),
            bootstrap_prev_used=bootstrap_used,
        )

        # 5) 验收闸门（不 raise，把结果挂回 result；脚本层再决定 assert_valid）
        if validate:
            result.validation = self.validator.validate(result)
        return result

    # ------------------------------------------------------------------ #
    @staticmethod
    def _make_bootstrap_prev(
        snap: GrowthRealitySnapshot, as_of: str
    ) -> GrowthRealitySnapshot:
        """首跑环比基线：前一日 revenue 2×（触发 R1 收入下滑修复），来源如实标记。"""
        prev = GrowthRealitySnapshot.from_dict(snap.to_dict())
        prev.timestamp = _day_before(as_of)
        if prev.revenue is not None:
            prev.revenue.daily_revenue = round(prev.revenue.daily_revenue * 2, 2)
        prev.sources = [BOOTSTRAP_SOURCE_ID]
        return prev


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _day_before(as_of: str) -> str:
    try:
        d = datetime.strptime(as_of, "%Y-%m-%d")
    except ValueError:
        d = datetime.utcnow()
    return (d - timedelta(days=1)).strftime("%Y-%m-%d")


__all__ = ["BOOTSTRAP_SOURCE_ID", "RealCEOOperator", "RealRunResult"]
