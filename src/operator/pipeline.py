"""P3.1 — Daily Operator Pipeline（11 阶段编排，薄胶水层）。

    1  reality_refresh   E17.1 hub.refresh（或预置 company）
    2  audit             P1.7 RealityAuditor
    3  opportunities     ┐
    4  simulations       ├ 由 E17.9 DailyGrowthOperatorAgent 一次跑出，此处提取统计
    5  decisions         ┘
    6  approval          P2.1 build_contract → P2.3 ApprovalService.submit
    7  executions        P2.4 SafeExecutor.execute（唯一执行出口）
    8  monitor           P2.5 ExecutionMonitor.observe_batch
    9  recovery          P2.6 RecoveryEngine.handle（仅失败 outcome）
    10 memory            校验 E17.9 跨日记忆落盘（P2.5/2.6 回流已在各自层自动发生）
    11 strategy_loop     P3.3 策略反馈控制器：读历史+当日结果 → 策略洞察/建议（不执行）
    12 portfolio         P3.4.5 PortfolioOptimizer：跨游戏资源编排（只建议不执行）
    13 ceo_report        P3.2 聚合既有产物 -> 运营决策单 daily_report.md + .json + actions.json
    14 report            工程日志（可追溯）：engineering_report.md

纪律：
- 每阶段独立 try/except 兜底 → StageResult(failed)，一段失败不毁整轮；
- 本层不决策（E17.3）、不直调 Provider（P2.4 唯一出口）、不改策略；
- portfolio 阶段只编排不决策：消费 Reality/Strategy 快照，跑 P3.4.5 编排器，
  产出 PortfolioOptimizationResult（recommendation-only），real_api_called 恒 False；
- 默认 DRY_RUN，real_api_called 恒 False；PRODUCTION 必须持 P2.3 授权。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.ceo_intelligence.daily_operator.models import ActionKind
from src.execution.contracts import build_contract
from src.execution.safe_executor.models import VERDICT_BLOCKED
from src.ceo_intelligence.growth_memory_graph.controller import MemoryControllerAdvisor
from src.operator.portfolio import (
    AllocationConstraints,
    PortfolioAssembler,
    PortfolioOptimizationInput,
    PortfolioOptimizationResult,
    PortfolioOptimizer,
)

from .context import OperatorContext
from .models import (
    STAGE_APPROVAL,
    STAGE_AUDIT,
    STAGE_CEO_REPORT,
    STAGE_DECISIONS,
    STAGE_EXECUTIONS,
    STAGE_FAILED,
    STAGE_MEMORY,
    STAGE_MONITOR,
    STAGE_OK,
    STAGE_OPPORTUNITIES,
    STAGE_PORTFOLIO,
    STAGE_REALITY,
    STAGE_RECOVERY,
    STAGE_REPORT,
    STAGE_SIMULATIONS,
    STAGE_SKIPPED,
    STAGE_STRATEGY,
    STAGE_LIVEOPS,
    StageResult,
)
from .report.builder import build_ceo_report, write_outputs
from .strategy.guard import StrategyGuard
from .strategy.loop import StrategyLoop, write_strategy_outputs
from .strategy.memory import StrategyMemoryAdapter
from .strategy.mutation import StrategyMutationEngine


class DailyOperatorPipeline:
    """execute(business_date) -> (List[StageResult], aggregates dict)。"""

    def __init__(
        self, context: OperatorContext, feedback_recorder: Any = None
    ):
        self.ctx = context
        # P3.5.2（可选）：决策学习写入器。None → 不记录 CEO 决策（零回归）。
        # 由 Operator Layer（本 pipeline 的 portfolio / strategy_loop 阶段）消费
        # 各阶段 Result 后统一写入 Knowledge Graph——业务计算层不感知存储。
        self.feedback_recorder = feedback_recorder

    # ------------------------------------------------------------------ #
    def execute(
        self, business_date: str, run_id: str = ""
    ) -> Tuple[List[StageResult], Dict[str, Any]]:
        stages: List[StageResult] = []
        # 阶段间共享状态（进程内引用，不序列化）
        s: Dict[str, Any] = {
            "company": self.ctx.company,
            "daily": None,          # E17.9 DailyRunResult
            "audit_report": None,   # P1.7 AuditReport
            "executable": [],       # 已获授权/自动批准的 ExecutionRequest
            "paired": [],           # [(request, SafeExecutionOutcome)]
            "exec_report": None,    # P2.5 ExecutionDailyReport
            "recoveries": [],       # P2.6 RecoveryResult
        }
        runner = (
            (STAGE_REALITY, self._reality),
            (STAGE_AUDIT, self._audit),
            (STAGE_OPPORTUNITIES, self._opportunities),
            (STAGE_SIMULATIONS, self._simulations),
            (STAGE_DECISIONS, self._decisions),
            (STAGE_APPROVAL, self._approval),
            (STAGE_EXECUTIONS, self._executions),
            (STAGE_MONITOR, self._monitor),
            (STAGE_RECOVERY, self._recovery),
            (STAGE_MEMORY, self._memory),
            (STAGE_LIVEOPS, self._liveops),
            (STAGE_STRATEGY, self._strategy_loop),
            (STAGE_PORTFOLIO, self._portfolio),
            (STAGE_CEO_REPORT, self._ceo_report),
            (STAGE_REPORT, self._report),
        )
        for name, fn in runner:
            try:
                stages.append(fn(business_date, s, run_id))
            except Exception as exc:  # noqa: BLE001 — 阶段兜底红线
                stages.append(StageResult(
                    stage=name, status=STAGE_FAILED,
                    detail=f"{type(exc).__name__}: {exc}",
                ))
        return stages, self._aggregates(stages, s)

    # ------------------------------------------------------------------ #
    # 1. reality_refresh
    # ------------------------------------------------------------------ #
    def _reality(self, date: str, s: Dict, run_id: str) -> StageResult:
        company = s["company"]
        if company is None:
            if self.ctx.agent.hub is None:
                raise ValueError(
                    "无预置 company 且未配置 hub=GrowthRealityHub"
                )
            company = self.ctx.agent.hub.refresh(self.ctx.game_ids, date)
            s["company"] = company
        # E17.9 幂等门交由 P3.1 OperatorRunStore 统一负责 → 恒 force=True
        daily = self.ctx.agent.run_daily_for_company(company, date, force=True)
        s["daily"] = daily
        return StageResult(
            stage=STAGE_REALITY,
            detail=f"{company.game_count} 游戏快照就绪，E17 循环完成",
            payload={
                "game_count": company.game_count,
                "company_status": daily.summary.get("company_status", ""),
                "real_api_called": daily.summary.get("real_api_called", False),
            },
        )

    # ------------------------------------------------------------------ #
    # 2. audit（P1.7）
    # ------------------------------------------------------------------ #
    def _audit(self, date: str, s: Dict, run_id: str) -> StageResult:
        company = s["company"]
        if company is None:
            return StageResult(STAGE_AUDIT, STAGE_SKIPPED, "无公司快照")
        report = self.ctx.auditor.audit(company)
        s["audit_report"] = report
        low = [
            e.game_id for e in report.entries
            if e.score is not None and e.score.composite < 0.5
        ]
        detail = (
            f"GREEN {report.green} / YELLOW {report.yellow} / "
            f"RED {report.red}，可决策 {report.decision_ready}/{report.total_games}"
        )
        return StageResult(
            stage=STAGE_AUDIT,
            detail=detail,
            payload={
                "green": report.green,
                "yellow": report.yellow,
                "red": report.red,
                "decision_ready": report.decision_ready,
                "total_games": report.total_games,
                "low_confidence_games": low[:20],
            },
        )

    # ------------------------------------------------------------------ #
    # 3–5. opportunities / simulations / decisions（提取 E17.9 统计）
    # ------------------------------------------------------------------ #
    def _opportunities(self, date: str, s: Dict, run_id: str) -> StageResult:
        daily = s["daily"]
        if daily is None:
            return StageResult(STAGE_OPPORTUNITIES, STAGE_SKIPPED, "E17 循环未运行")
        opp_ids = {
            d.opportunity_id for d in daily.dec_report.decisions
            if d.opportunity_id
        }
        return StageResult(
            stage=STAGE_OPPORTUNITIES,
            detail=f"识别机会 {len(opp_ids)} 个",
            payload={"opportunities": len(opp_ids)},
        )

    def _simulations(self, date: str, s: Dict, run_id: str) -> StageResult:
        daily = s["daily"]
        if daily is None:
            return StageResult(STAGE_SIMULATIONS, STAGE_SKIPPED, "E17 循环未运行")
        sims = daily.sim_report.simulations
        gates: Dict[str, int] = {}
        for sim in sims:
            st = sim.flag.status
            key = st.value if hasattr(st, "value") else str(st)
            gates[key] = gates.get(key, 0) + 1
        return StageResult(
            stage=STAGE_SIMULATIONS,
            detail=f"模拟 {len(sims)} 项，闸门分布 {gates}",
            payload={"simulations": len(sims), "gates": gates},
        )

    def _decisions(self, date: str, s: Dict, run_id: str) -> StageResult:
        daily = s["daily"]
        if daily is None:
            return StageResult(STAGE_DECISIONS, STAGE_SKIPPED, "E17 循环未运行")
        counts: Dict[str, int] = {"total": len(daily.dec_report.decisions)}
        for d in daily.dec_report.decisions:
            t = d.decision_type
            key = t.value if hasattr(t, "value") else str(t)
            counts[key] = counts.get(key, 0) + 1
        return StageResult(
            stage=STAGE_DECISIONS,
            detail=f"决策 {counts['total']} 条：{counts}",
            payload=counts,
        )

    # ------------------------------------------------------------------ #
    # 6. approval（P2.1 合同 → P2.3 审批工作流）
    # ------------------------------------------------------------------ #
    def _approval(self, date: str, s: Dict, run_id: str) -> StageResult:
        daily = s["daily"]
        if daily is None:
            return StageResult(STAGE_APPROVAL, STAGE_SKIPPED, "E17 循环未运行")
        dec_by_id = {d.audit_id: d for d in daily.dec_report.decisions}
        counts = {
            "contracts": 0, "blocked": 0, "auto_approved": 0,
            "pending": 0, "denied": 0,
        }
        executable = []
        for action in daily.actions:
            # 只把可落地的行动接进执行合同层（BLOCK 已被模拟闸门拦下）
            if action.kind not in (ActionKind.AUTO, ActionKind.APPROVAL):
                continue
            decision = dec_by_id.get(action.decision_audit_id)
            if decision is None:
                continue
            contract = build_contract(
                decision, self.ctx.registry, mode=self.ctx.mode
            )
            counts["contracts"] += 1
            if contract.request is None:  # 未登记/权限 blocked
                counts["blocked"] += 1
                continue
            # 单一审批路径：一律走 P2.3 工作流（auto 即时拿令牌）
            sub = self.ctx.approval_service.submit(
                contract.request, requested_by=f"p3.1:{run_id or date}"
            )
            if sub.auto_approved:
                counts["auto_approved"] += 1
                executable.append(contract.request)
            elif sub.outcome == "deny":
                counts["denied"] += 1
            else:
                counts["pending"] += 1
        s["executable"] = executable
        return StageResult(
            stage=STAGE_APPROVAL,
            detail=(
                f"合同 {counts['contracts']}：自动批准 {counts['auto_approved']}，"
                f"待人工 {counts['pending']}，拒绝 {counts['denied']}，"
                f"未登记拦截 {counts['blocked']}"
            ),
            payload=counts,
        )

    # ------------------------------------------------------------------ #
    # 7. executions（P2.4 SafeExecutor —— 唯一执行出口）
    # ------------------------------------------------------------------ #
    def _executions(self, date: str, s: Dict, run_id: str) -> StageResult:
        executable = s["executable"]
        if not executable:
            return StageResult(
                STAGE_EXECUTIONS, STAGE_SKIPPED, "无已授权可执行请求"
            )
        paired = []
        counts = {"total": 0, "ok": 0, "blocked": 0, "failed": 0}
        real_api = False
        for req in executable:
            outcome = self.ctx.safe_executor.execute(req)
            paired.append((req, outcome))
            counts["total"] += 1
            if outcome.ok:
                counts["ok"] += 1
            elif outcome.verdict == VERDICT_BLOCKED:
                counts["blocked"] += 1
            else:
                counts["failed"] += 1
            if outcome.result is not None and getattr(
                outcome.result, "real_api_called", False
            ):
                real_api = True
        s["paired"] = paired
        counts["real_api_called"] = real_api
        return StageResult(
            stage=STAGE_EXECUTIONS,
            detail=(
                f"执行 {counts['total']}：成功 {counts['ok']}，"
                f"拦截 {counts['blocked']}，失败 {counts['failed']}"
            ),
            payload=counts,
        )

    # ------------------------------------------------------------------ #
    # 8. monitor（P2.5）
    # ------------------------------------------------------------------ #
    def _monitor(self, date: str, s: Dict, run_id: str) -> StageResult:
        paired = s["paired"]
        if not paired:
            return StageResult(STAGE_MONITOR, STAGE_SKIPPED, "无执行 outcome 可观察")
        results, report = self.ctx.monitor.observe_batch(paired, date)
        s["exec_report"] = report
        return StageResult(
            stage=STAGE_MONITOR,
            detail=(
                f"观察 {len(results)} 次执行，健康 {report.health_level}，"
                f"异常告警 {len(report.warnings)}"
            ),
            payload={
                "observed": len(results),
                "health_level": report.health_level,
                "warnings": list(report.warnings)[:10],
                "report_id": report.report_id,
            },
        )

    # ------------------------------------------------------------------ #
    # 9. recovery（P2.6 —— 仅失败 outcome，BLOCKED 不算失败）
    # ------------------------------------------------------------------ #
    def _recovery(self, date: str, s: Dict, run_id: str) -> StageResult:
        paired = s["paired"]
        candidates = [
            (req, out) for req, out in paired
            if not out.ok and out.verdict != VERDICT_BLOCKED
        ]
        if not candidates:
            return StageResult(STAGE_RECOVERY, STAGE_SKIPPED, "无失败执行需要恢复")
        counts: Dict[str, int] = {"incidents": 0}
        recoveries = []
        for req, out in candidates:
            result = self.ctx.recovery.handle(out, req)
            recoveries.append(result)
            counts["incidents"] += 1
            status = str(getattr(result, "status", ""))
            counts[status] = counts.get(status, 0) + 1
        s["recoveries"] = recoveries
        return StageResult(
            stage=STAGE_RECOVERY,
            detail=f"处理失败事件 {counts['incidents']} 起：{counts}",
            payload=counts,
        )

    # ------------------------------------------------------------------ #
    # 10. memory（校验落盘；经验回流已由 P2.5/P2.6 桥自动完成）
    # ------------------------------------------------------------------ #
    def _memory(self, date: str, s: Dict, run_id: str) -> StageResult:
        daily = s["daily"]
        if daily is None:
            return StageResult(STAGE_MEMORY, STAGE_SKIPPED, "E17 循环未运行")
        rec = self.ctx.agent.operator_memory.get(date)
        if rec is None:
            return StageResult(
                STAGE_MEMORY, STAGE_FAILED, "E17.9 跨日记忆未落盘"
            )
        return StageResult(
            stage=STAGE_MEMORY,
            detail="跨日记忆已落盘；执行/恢复经验已由 P2.5/P2.6 回流",
            payload={
                "operator_day_record": rec.to_dict(),
                "execution_experiences": len(s["paired"]),
                "recovery_experiences": len(s["recoveries"]),
            },
        )

    # ------------------------------------------------------------------ #
    # 10.5 liveops（跨 Agent 协同：CEO 触发 LiveOps 流失分析 + 回流活动设计）
    # ------------------------------------------------------------------ #
    def _liveops(self, date: str, s: Dict, run_id: str) -> StageResult:
        """LiveOps 阶段 — CEO Daily Run 自动触发 LiveOps Agent.

        流程:
          1. 遍历 ctx.game_ids，对每个游戏触发流失分析
          2. 若发现高价值流失用户 (high_value_at_risk > 0)，自动设计回流活动
          3. 所有活动以 dry_run=True 生成执行计划 (不真实下发，等人工审批)
          4. 结果写入 s["liveops_campaigns"] 供后续 CEO 报告引用

        协同方向: CEO → LiveOps (单向触发)
        回流通道: LiveOps 执行结果已通过 _write_ceo_memory 写入 CEO memory
        """
        liveops = getattr(self.ctx, "liveops_agent", None)
        if liveops is None:
            return StageResult(
                STAGE_LIVEOPS, STAGE_SKIPPED,
                "未注入 LiveOpsAgent，跳过 LiveOps 阶段",
            )
        company = s.get("company")
        game_ids = list(self.ctx.game_ids)
        if not game_ids and company is not None:
            # 从公司快照提取 game_ids
            game_ids = [
                getattr(g, "game_id", str(g))
                for g in getattr(company, "per_game", []) or []
            ]
        if not game_ids:
            return StageResult(
                STAGE_LIVEOPS, STAGE_SKIPPED,
                "无 game_ids，跳过 LiveOps 流失分析",
            )

        analyses_count = 0
        campaigns_count = 0
        high_risk_total = 0
        campaign_summaries: List[Dict[str, Any]] = []

        for game_id in game_ids:
            try:
                analysis = liveops.analyze_churn_risk(game_id)
                analyses_count += 1
                high_risk = getattr(analysis, "high_value_at_risk", 0)
                high_risk_total += high_risk
                # 发现高价值流失用户 → 自动设计回流活动
                if high_risk > 0:
                    campaign = liveops.design_winback_campaign(game_id, analysis)
                    campaigns_count += 1
                    campaign_summaries.append({
                        "campaign_id": campaign.campaign_id,
                        "game_id": game_id,
                        "campaign_type": campaign.campaign_type,
                        "target_segment": campaign.target_segment,
                        "target_count": campaign.target_count,
                        "rewards_pool": campaign.rewards_pool,
                    })
            except Exception:  # noqa: BLE001 — 单游戏失败不阻断其他游戏
                continue

        s["liveops_campaigns"] = campaign_summaries
        s["liveops_high_risk_total"] = high_risk_total

        detail = (
            f"分析 {analyses_count} 款游戏，高价值流失用户 {high_risk_total} 人，"
            f"设计回流活动 {campaigns_count} 个 (dry_run)"
        )
        return StageResult(
            stage=STAGE_LIVEOPS,
            detail=detail,
            payload={
                "analyses_count": analyses_count,
                "campaigns_count": campaigns_count,
                "high_value_at_risk_total": high_risk_total,
                "campaign_summaries": campaign_summaries,
            },
        )

    # ------------------------------------------------------------------ #
    # 11. strategy_loop（P3.3 — 策略反馈控制器，只读+产建议，不执行）
    # ------------------------------------------------------------------ #
    def _strategy_loop(self, date: str, s: Dict, run_id: str) -> StageResult:
        daily = s["daily"]
        if daily is None:
            return StageResult(
                STAGE_STRATEGY, STAGE_SKIPPED, "E17 循环未运行，无策略反馈源"
            )
        # 策略经验持久化于 out_dir 同级的 strategy_memory.jsonl（隔离、可累积）
        strategy_store = str(
            Path(self.ctx.out_dir) / "strategy_memory.jsonl"
        )
        adapter = StrategyMemoryAdapter(store_path=strategy_store)
        loop = StrategyLoop(
            memory_adapter=adapter,
            mutation_engine=StrategyMutationEngine(),
            guard=StrategyGuard(),
            graph=getattr(self.ctx.agent, "pipeline", None) and getattr(
                self.ctx.agent.pipeline, "memory_graph", None
            ),
            # P3.6.1：Memory 进入生产决策路径（读侧）。None → 零回归。
            advisor=(
                MemoryControllerAdvisor(self.ctx.memory_controller, role="strategy")
                if getattr(self.ctx, "memory_controller", None) is not None
                else None
            ),
        )
        result = loop.run(
            daily,
            exec_report=s.get("exec_report"),
            recoveries=s.get("recoveries"),
            date=date,
        )
        # P3.5.2（Operator Layer 反馈）：策略决策 + 所用经验 + 模拟结果 -> Knowledge Graph
        if self.feedback_recorder is not None:
            from .feedback import record_strategy_feedback

            record_strategy_feedback(self.feedback_recorder, result)
        paths = write_strategy_outputs(date, self.ctx.out_dir, result)
        s["strategy_patterns"] = result.patterns
        s["strategy_insights"] = [i.to_dict() for i in result.insights]
        s["strategy_proposals"] = [p.to_dict() for p in result.proposals]
        s["strategy_states"] = {
            k: v.to_dict() for k, v in result.states.items()
        }
        s["strategy_insights_path"] = paths["strategy_insights"]
        s["strategy_proposals_path"] = paths["strategy_proposals"]
        s["strategy_states_path"] = paths["strategy_states"]
        return StageResult(
            stage=STAGE_STRATEGY,
            detail=(
                f"策略反馈：洞察 {len(result.insights)} 条，"
                f"建议 {len(result.proposals)} 条"
                f"（均须过 Simulation 闸门，未执行）"
            ),
            payload=paths,
        )

    # ------------------------------------------------------------------ #
    # 11.5 portfolio（P3.4.5 —— 跨游戏资源编排，只建议不执行）
    # ------------------------------------------------------------------ #
    def _portfolio(self, date: str, s: Dict, run_id: str) -> StageResult:
        company = s.get("company")
        if company is None or not getattr(company, "per_game", None):
            return StageResult(
                STAGE_PORTFOLIO, STAGE_SKIPPED, "无公司快照，无法组装组合优化输入"
            )
        realities = list(company.per_game.values())
        try:
            snapshot = PortfolioAssembler().assemble_fleet(
                realities, generated_at=getattr(company, "as_of", "") or date
            )
            # 当前预算占用（仅作证据/对账，绝不覆写 baseline）
            current_allocation = {
                g.game_id: (
                    g.acquisition.spend if g.acquisition else 0.0
                )
                for g in realities
            }
            constraints = AllocationConstraints(
                total_budget=(
                    getattr(company, "total_spend", 0.0)
                    or snapshot.total_spend or 0.0
                )
            )
            # P3.6.1：Memory 进入生产决策路径（G1 闭环）。
            # 注入 MemoryController 时，经 MemoryControllerAdvisor 复用既有 advisor 注入点
            # （不新增构造参数）；None → 零回归，走纯规则编排。
            optimizer = PortfolioOptimizer()
            if getattr(self.ctx, "memory_controller", None) is not None:
                from src.operator.portfolio.optimizer import build_portfolio_optimizer

                optimizer = build_portfolio_optimizer(
                    advisor=MemoryControllerAdvisor(
                        self.ctx.memory_controller, role="portfolio"
                    )
                )
            result = optimizer.optimize(
                PortfolioOptimizationInput(
                    snapshots=snapshot,
                    rankings=[],
                    constraints=constraints,
                    current_allocation=current_allocation,
                    as_of=getattr(company, "as_of", "") or date,
                )
            )
        except Exception as exc:  # noqa: BLE001 — 组合层异常降级为 SKIP，不毁整轮
            return StageResult(
                STAGE_PORTFOLIO, STAGE_SKIPPED,
                f"组合优化跳过：{type(exc).__name__}: {exc}",
            )
        s["portfolio_result"] = result
        # P3.5.2（Operator Layer 反馈）：组合决策 + 所用经验 -> Knowledge Graph
        if self.feedback_recorder is not None:
            from .feedback import record_portfolio_feedback

            record_portfolio_feedback(self.feedback_recorder, result)
        return StageResult(
            stage=STAGE_PORTFOLIO,
            detail=(
                f"组合优化：{result.status.value}，"
                f"{len(result.ranked_games)} 游戏排名；"
                f"verdict={result.to_report_section().get('guard_verdict', '')}；"
                f"real_api_called={result.real_api_called}"
            ),
            payload={
                "optimization_id": result.optimization_id,
                "status": result.status.value,
                "real_api_called": result.real_api_called,
            },
        )

    # ------------------------------------------------------------------ #
    # 12. report（汇总单一日报）
    # ------------------------------------------------------------------ #
    def _report(self, date: str, s: Dict, run_id: str) -> StageResult:
        daily = s["daily"]
        out_dir = Path(self.ctx.out_dir) / date
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "engineering_report.md"

        md: List[str] = [f"# 工程日志（每日增长经营日报）— {date}", ""]
        md.append(f"> run_id：{run_id or '-'} ｜ 模式：{self.ctx.mode.value} ｜ "
                  f"P3.1 Daily Operator")
        md.append("")

        # 一、CEO 晨报（E17.9）
        md.append("## 一、CEO 晨报（E17.9）")
        md.append("")
        if daily is not None and daily.reports.get("ceo"):
            md.append(daily.reports["ceo"])
        else:
            md.append("_E17 循环未运行，无晨报。_")
        md.append("")

        # 二、真实数据审计（P1.7）
        md.append("## 二、真实数据审计（P1.7）")
        md.append("")
        audit_report = s["audit_report"]
        if audit_report is not None:
            md.append(audit_report.to_markdown())
        else:
            md.append("_审计未运行。_")
        md.append("")

        # 三、执行链（P2）
        md.append("## 三、执行链（P2.1→P2.4）")
        md.append("")
        exec_report = s["exec_report"]
        if exec_report is not None:
            md.append(
                f"- 执行总数：{exec_report.total_executions} ｜ "
                f"成功 {exec_report.success} ｜ 失败 {exec_report.failed} ｜ "
                f"回滚 {exec_report.rollback} ｜ 拦截 {exec_report.blocked}"
            )
            md.append(f"- 健康等级：{exec_report.health_level}")
            for w in exec_report.warnings:
                md.append(f"- ⚠️ {w}")
            for l in exec_report.learnings:
                md.append(f"- 📚 {l}")
        else:
            md.append("_今日无已授权执行（决策全部处于待审批 / 观察 / 拦截）。_")
        md.append("")

        # 四、恢复与升级（P2.6）
        md.append("## 四、恢复与升级（P2.6）")
        md.append("")
        recoveries = s["recoveries"]
        if recoveries:
            for r in recoveries:
                md.append(
                    f"- 事件 {getattr(r, 'incident_id', '?')}：结局 "
                    f"{getattr(r, 'status', '?')}"
                )
        else:
            md.append("_今日无失败执行，无需恢复。_")
        md.append("")

        # 四·五、LiveOps 跨 Agent 协同（CEO → LiveOps）
        liveops_campaigns = s.get("liveops_campaigns") or []
        high_risk = s.get("liveops_high_risk_total", 0)
        md.append("## 五、LiveOps 跨 Agent 协同")
        md.append("")
        if liveops_campaigns:
            md.append(
                f"- 高价值流失用户：{high_risk} 人 ｜ "
                f"自动设计回流活动：{len(liveops_campaigns)} 个 (dry_run)"
            )
            for c in liveops_campaigns:
                md.append(
                    f"  - [{c['game_id']}] {c['campaign_type']} → "
                    f"{c['target_segment']} ({c['target_count']} 人, "
                    f"${c['rewards_pool']:.2f})"
                )
            md.append("- 回流活动执行结果已写入 CEO execution_memory（跨 Agent 可感知）")
        else:
            md.append("_今日无高价值流失用户，未触发回流活动设计。_")
        md.append("")

        path.write_text("\n".join(md), encoding="utf-8")
        s["engineering_report_path"] = str(path)
        return StageResult(
            stage=STAGE_REPORT,
            detail=f"工程日志已生成：{path}",
            payload={"engineering_report_path": str(path)},
        )

    # ------------------------------------------------------------------ #
    # 11.5 ceo_report（P3.2 — 运营决策单，聚合既有产物，零重算）
    # ------------------------------------------------------------------ #
    def _ceo_report(self, date: str, s: Dict, run_id: str) -> StageResult:
        daily = s["daily"]
        if daily is None:
            return StageResult(
                STAGE_CEO_REPORT, STAGE_SKIPPED, "E17 循环未运行，无决策单"
            )
        # P3.6.1：Memory Reasoning——CEO 报告能回答"为什么这么建议"（G3 闭环）。
        # 注入 MemoryController 时，全量召回一次知识，挂进报告（空 bundle 优雅省略）。
        if (
            getattr(self.ctx, "memory_controller", None) is not None
            and s.get("memory_bundle") is None
        ):
            from src.ceo_intelligence.growth_memory_graph.controller import MemoryContext

            bundle = self.ctx.memory_controller.retrieve(
                MemoryContext(query_reason="report_explain")
            )
            s["memory_bundle"] = bundle.to_dict()
        # P3.6.2：战略规律（Strategic Memory 段）——长期规律召回
        strategic_bundle = None
        if (
            getattr(self.ctx, "memory_controller", None) is not None
            and s.get("strategic_bundle") is None
        ):
            from src.ceo_intelligence.growth_memory_graph.controller import MemoryContext

            strategic_bundle = self.ctx.memory_controller.retrieve(
                MemoryContext(query_reason="strategic")
            )
            s["strategic_bundle"] = strategic_bundle.to_dict()
        else:
            strategic_bundle = s.get("strategic_bundle")
        # P3.6.3：Memory Reflection——对 date 周期的昨日决策复盘（wins/mistakes/
        # changed_beliefs/new_rules）。经 controller.reflection_inputs 读图（fail-open），
        # MemoryReflectionBuilder 纯计算；空窗口 → 空复盘（报告优雅省略）。
        reflection = None
        if (
            getattr(self.ctx, "memory_controller", None) is not None
            and s.get("reflection") is None
        ):
            from src.ceo_intelligence.growth_memory_graph.reflection_builder import (
                MemoryReflectionBuilder,
            )

            inputs = self.ctx.memory_controller.reflection_inputs(date)
            reflection = MemoryReflectionBuilder().build(period=date, **inputs)
            s["reflection"] = reflection.to_dict()
            # Close the loop: persist the reflection through the sole writer.
            if self.feedback_recorder is not None:
                from src.ceo_intelligence.growth_memory_graph.reflection_store import (
                    ReflectionStore,
                )
                ReflectionStore(self.feedback_recorder).save(reflection)
        else:
            reflection = s.get("reflection")
        # P3.6.4：Reflection 后、Report 前执行治理（纯计算 + 唯一写入口）。
        governance = s.get("governance")
        if (
            getattr(self.ctx, "memory_controller", None) is not None
            and governance is None
        ):
            from src.ceo_intelligence.growth_memory_graph.governance_engine import (
                GovernanceEngine,
            )
            from src.ceo_intelligence.growth_memory_graph.governance_store import (
                GovernanceStore,
            )

            governance_inputs = self.ctx.memory_controller.governance_inputs(date)
            governance_records = GovernanceEngine().run(
                as_of=date, **governance_inputs
            )
            if self.feedback_recorder is not None:
                GovernanceStore(self.feedback_recorder).save_all(governance_records)
            states = governance_inputs["states"]
            targets = {
                str(item.get("node_id", ""))
                for item in (
                    governance_inputs["ceo_records"]
                    + governance_inputs["strategic_insights"]
                ) if item.get("node_id")
            }
            governance = ({
                "records": [item.to_dict() for item in governance_records],
                "health": {
                    "active": sum(1 for target in targets if states.get(target, "active") == "active"),
                    "obsolete": sum(1 for target in targets if states.get(target, "active") == "obsolete"),
                    "archived": sum(1 for target in targets if states.get(target, "active") == "archived"),
                    "conflicted": sum(1 for target in targets if states.get(target, "active") == "conflicted"),
                },
                "real_api_called": False,
            } if governance_records else None)
            s["governance"] = governance
        report = build_ceo_report(
            daily,
            company=s.get("company"),
            exec_report=s.get("exec_report"),
            audit_report=s.get("audit_report"),
            recoveries=s.get("recoveries"),
            patterns=s.get("strategy_patterns"),
            portfolio_recommendation=s.get("portfolio_result"),
            memory_reasoning=s.get("memory_bundle"),
            strategic_memory=strategic_bundle,
            reflection=reflection,
            governance=governance,
        )
        paths = write_outputs(date, self.ctx.out_dir, report)
        s["ceo_report_path"] = paths["report_path"]
        s["ceo_report_json"] = paths["ceo_report_json"]
        s["actions_path"] = paths["actions_path"]
        return StageResult(
            stage=STAGE_CEO_REPORT,
            detail=(
                f"决策单已生成：{paths['report_path']} "
                f"（AUTO {report.health_summary.auto_count} / "
                f"APPROVAL {report.health_summary.approval_count} / "
                f"BLOCKED {report.health_summary.blocked_count}）"
                + (
                    f" ｜ Portfolio：{report.portfolio_recommendation['status']}"
                    if report.portfolio_recommendation else ""
                )
            ),
            payload=paths,
        )

    # ------------------------------------------------------------------ #
    # 汇总
    # ------------------------------------------------------------------ #
    def _aggregates(
        self, stages: List[StageResult], s: Dict
    ) -> Dict[str, Any]:
        daily = s["daily"]
        by_name = {st.stage: st for st in stages}

        decisions: Dict[str, int] = {}
        if STAGE_DECISIONS in by_name and by_name[STAGE_DECISIONS].payload:
            decisions = {
                k: v for k, v in by_name[STAGE_DECISIONS].payload.items()
                if isinstance(v, int)
            }

        approvals = by_name.get(STAGE_APPROVAL)
        executions_stage = by_name.get(STAGE_EXECUTIONS)
        recovery_stage = by_name.get(STAGE_RECOVERY)
        executions = {
            "auto": len(s["executable"]),
            "approval_pending": (
                approvals.payload.get("pending", 0) if approvals else 0
            ),
            "blocked": (
                (approvals.payload.get("blocked", 0) if approvals else 0)
                + (executions_stage.payload.get("blocked", 0)
                   if executions_stage else 0)
            ),
            "recovered": (
                recovery_stage.payload.get("recovered", 0)
                if recovery_stage else 0
            ),
            "escalated": (
                recovery_stage.payload.get("escalated", 0)
                if recovery_stage else 0
            ),
        }

        real_api = bool(
            (daily is not None and daily.summary.get("real_api_called"))
            or (executions_stage is not None
                and executions_stage.payload.get("real_api_called"))
        )

        portfolio_result = s.get("portfolio_result")
        portfolio_status = (
            portfolio_result.status.value if portfolio_result is not None else None
        )

        return {
            "decisions": decisions,
            "executions": executions,
            "real_api_called": real_api,
            "report_path": s.get("ceo_report_path", s.get("report_path", "")),
            "ceo_report_path": s.get("ceo_report_path", ""),
            "ceo_report_json": s.get("ceo_report_json", ""),
            "actions_path": s.get("actions_path", ""),
            "engineering_report_path": s.get("engineering_report_path", ""),
            "strategy_insights_path": s.get("strategy_insights_path", ""),
            "strategy_proposals_path": s.get("strategy_proposals_path", ""),
            "strategy_states_path": s.get("strategy_states_path", ""),
            "portfolio_status": portfolio_status,
            "summary": {
                "company_status": (
                    daily.summary.get("company_status", "") if daily else ""
                ),
                "e17_summary": dict(daily.summary) if daily else {},
                "audit": (
                    by_name[STAGE_AUDIT].payload
                    if STAGE_AUDIT in by_name else {}
                ),
                "portfolio": (
                    portfolio_result.to_report_section()
                    if portfolio_result is not None else None
                ),
            },
        }


__all__ = ["DailyOperatorPipeline"]
