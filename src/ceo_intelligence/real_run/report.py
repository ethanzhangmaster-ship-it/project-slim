"""P1.5 — 真实 CEO 报告生成器（build_ceo_report）。

把 RealCEOOperator.run() 的产物（RealRunResult + ValidationResult）渲染为
一份可发给运营负责人 / 存档的中文经营报告（Markdown）。

诚实原则（P1.5 验收的核心）：
- 顶部「数据来源与诚实声明」必须如实标注本次运行的真实性边界：
  1) REAL_API_CALLED 链路：Adjust/Meta 经真实 urllib 发起 HTTP（验收环境端点被
     替换为本地 mock-server；生产环境填真实 token 即直连官方 API，代码路径不变）。
  2) MAX 读真实报表文件（data/max/ 下 ACCT_*_report.json）。
  3) 首跑环比基线（前一日 revenue×2）为种子，用于触发 E17.2 收入环比规则并验证
     决策链路；自第 2 个真实运行日起，基线自动替换为真实历史。
- 报告不粉饰、不虚构任何数字；所有金额/指标直接来自 RealRunResult 实测字段。

结构（5 节 + 验收闸门表）：
  1) 数据来源与诚实声明
  2) Business Snapshot（经营快照）
  3) Revenue Breakdown（IAP vs Ad 拆分）
  4) Growth Diagnosis（E17.2 增长诊断）
  5) Decision Recommendation（E17.3 决策建议）
  6) Execution Route（E17.6 执行路由）
  + 验收闸门表（Gates 1-4）
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .validator import ValidationResult

if TYPE_CHECKING:  # pragma: no cover
    from .runner import RealRunResult

# --------------------------------------------------------------------------- #
# 格式化工具
# --------------------------------------------------------------------------- #
def _money(x: float) -> str:
    return f"${x:,.2f}"


def _money0(x: float) -> str:
    return f"${x:,.0f}"


def _pct(x: float) -> str:
    return f"{x:+.1%}" if x >= 0 else f"{x:.1%}"


def _int(x: float) -> str:
    return f"{int(round(x)):,}"


# --------------------------------------------------------------------------- #
# 主函数
# --------------------------------------------------------------------------- #
def build_ceo_report(
    result: "RealRunResult",
    validation: Optional[ValidationResult] = None,
) -> str:
    """渲染一份真实 CEO 经营报告（Markdown）。"""
    validation = validation or result.validation
    snap = result.snapshot
    v = result.validation if validation is None else validation

    lines: list[str] = []
    lines.append(f"# P1.5 真实 CEO 经营报告 — `{result.game_id}`")
    lines.append("")
    lines.append(f"> 生成基准日（as_of）：**{result.as_of}**  ")
    lines.append(f"> 真实 API 链路触发（hub.last_real_api_called）："
                 f"**{result.hub_real_api_called}**")
    lines.append("")

    # ----------------------------------------------------------------- #
    # 1) 数据来源与诚实声明
    # ----------------------------------------------------------------- #
    lines.append("## 1. 数据来源与诚实声明")
    lines.append("")
    flags = result.source_flags
    real_flags = " / ".join(
        f"{k.upper()}={flags.get(k, False)}" for k in ("adjust", "max", "meta")
    )
    lines.append(
        f"- **真实 API 源触发情况**：{real_flags}（Hub 级 "
        f"real_api_called = {result.hub_real_api_called}）。"
    )
    lines.append(
        "- **Adjust / Meta**：本次验收经本地 mock-server 真实 urllib 调用"
        "（HTTP 链路真实建立、REAL_API_CALLED=True）；生产环境填入真实 token 即"
        "直连官方 API，**代码路径不变**，仅 endpoint 在验收环境被替换为本地服务。"
    )
    lines.append(
        "- **MAX**：读取真实报表文件（`data/max/ACCT_*_report.json` + "
        "`outputs/user_metrics/ACCT_*.json` 的 app_dau），无 mock。"
    )
    if result.bootstrap_prev_used:
        lines.append(
            "- **⚠️ 环比基线为种子数据**：目标游戏历史不足，首跑自动种入前一日"
            "基线（revenue×2，来源标记 `bootstrap_prev`）。该基线仅用于触发 E17.2"
            "收入环比规则、验证「真实数据→决策」链路闭环；**自第 2 个真实运行日起，"
            "基线自动替换为真实历史，不再使用种子**。"
        )
    else:
        lines.append(
            "- 环比基线：使用真实历史（已积累 ≥1 条运行记录）。"
        )
    lines.append(
        "- 本报告所有金额/指标均直接来自 RealCEOOperator 实测字段，未做任何"
        "人工修饰或虚构。"
    )
    lines.append("")

    # ----------------------------------------------------------------- #
    # 2) Business Snapshot
    # ----------------------------------------------------------------- #
    lines.append("## 2. Business Snapshot（经营快照）")
    lines.append("")
    if snap is None:
        lines.append("- 无快照数据，无法生成经营快照。")
    else:
        rev = snap.revenue
        acq = snap.acquisition
        prod = snap.product
        rows = [
            ("游戏 ID", result.game_id),
            ("基准日", result.as_of),
            ("日收入（IAP，Adjust 口径）", _money(rev.daily_revenue) if rev else "—"),
            ("日广告收入（MAX 口径）", _money(result.ad_revenue_daily)),
            ("日花费（UA Spend，Meta 口径）",
             _money(acq.spend) if acq else "—"),
            ("DAU（Adjust 口径）", _int(prod.dau) if prod else "—"),
            ("ROAS（月化日收入 / 月花费）",
             f"{acq.roas:.2f}" if acq and acq.roas else "—"),
            ("CPI", _money(acq.cpi) if acq and acq.cpi else "—"),
            ("Installs", _int(acq.installs) if acq else "—"),
            ("ARPDAU（IAP）", _money(rev.arpdau) if rev else "—"),
            ("发布状态", prod.release_status if prod else "—"),
            ("真实域覆盖", ", ".join(snap.real_domains) if snap.real_domains else "—"),
            ("Reality 置信度", f"{result.reality_confidence:.2f}"),
        ]
        lines.append("| 指标 | 数值 |")
        lines.append("|---|---|")
        for k, val in rows:
            lines.append(f"| {k} | {val} |")
        lines.append("")

    # ----------------------------------------------------------------- #
    # 3) Revenue Breakdown（IAP vs Ad）
    # ----------------------------------------------------------------- #
    lines.append("## 3. Revenue Breakdown（收入拆分：IAP vs Ad）")
    lines.append("")
    iap = result.iap_revenue_daily
    ad = result.ad_revenue_daily
    total = iap + ad
    iap_share = (iap / total) if total else 0.0
    ad_share = (ad / total) if total else 0.0
    lines.append(f"- **IAP 日收入（Adjust 口径）**：{_money(iap)} "
                 f"（占比 {iap_share:.1%}）")
    lines.append(f"- **广告日收入（MAX 口径）**：{_money(ad)} "
                 f"（占比 {ad_share:.1%}）")
    lines.append(f"- **混合日收入**：{_money(total)}")
    lines.append("")

    if snap and snap.revenue and snap.revenue.network_distribution:
        nd = snap.revenue.network_distribution
        lines.append("**广告收入网络分布（MAX）**：")
        lines.append("")
        lines.append("| 广告网络 | 收入占比 |")
        lines.append("|---|---|")
        for net, share in sorted(nd.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {net} | {share:.1%} |")
        lines.append("")
        rv = snap.revenue
        if rv.ecpm:
            lines.append(f"- 混合 eCPM：{_money(rv.ecpm)}  "
                         f"｜ 曝光：{_int(rv.impressions)}  "
                         f"｜ 激励视频收入：{_money(rv.rewarded_video_revenue)}")
            lines.append("")
    else:
        lines.append("- _无 MAX 网络分布数据（广告收入拆分不可用）。_")
        lines.append("")

    # ----------------------------------------------------------------- #
    # 4) Growth Diagnosis（E17.2）
    # ----------------------------------------------------------------- #
    lines.append("## 4. Growth Diagnosis（增长诊断 · E17.2）")
    lines.append("")
    opp = result.opportunity_report
    if opp is None:
        lines.append("- 无机会报告。")
    else:
        rs = opp.risk_summary or {}
        lines.append(
            f"- 机会总数：**{opp.total_opportunities}**  "
            f"｜ 风险分布：高 {rs.get('high',0)} / 中 {rs.get('medium',0)} / "
            f"低 {rs.get('low',0)}  "
            f"｜ 组合预期收入影响：{_pct(rs.get('total_expected_impact', 0.0))}"
        )
        lines.append("")
        if opp.top_priority:
            lines.append("**优先级最高的机会**：")
            lines.append("")
            lines.append("| 类型 | 问题 | 优先级 | 预期影响 | 置信 | 风险 |")
            lines.append("|---|---|---|---|---|---|")
            for o in opp.top_priority[:10]:
                lines.append(
                    f"| {o.type.value} | {o.problem} | {o.priority:.3f} | "
                    f"{_pct(o.expected_impact)} | {o.confidence:.0%} | "
                    f"{o.risk:.0%} |"
                )
            lines.append("")
            top = opp.top_priority[0]
            if top.evidence:
                lines.append(f"**首要机会「{top.title}」证据**：")
                for ev in top.evidence:
                    lines.append(f"- {ev}")
                lines.append("")
            if top.suggested_actions:
                lines.append("**建议动作**：")
                for a in top.suggested_actions:
                    lines.append(f"- {a}")
                lines.append("")
        else:
            lines.append("_E17.2 未产出可行动机会（环比信号不足）。_")
            lines.append("")

    # ----------------------------------------------------------------- #
    # 5) Decision Recommendation（E17.3）
    # ----------------------------------------------------------------- #
    lines.append("## 5. Decision Recommendation（决策建议 · E17.3）")
    lines.append("")
    dec = result.decision_report
    if dec is None:
        lines.append("- 无决策报告。")
    else:
        s = dec.summary or {}
        lines.append(
            f"- 决策总数：**{dec.total_decisions}**  "
            f"｜ 出口：自动执行 {s.get('execute',0)} / 待审批 "
            f"{s.get('approve',0)} / 仅观察 {s.get('observe',0)} / "
            f"拒绝 {s.get('reject',0)}"
        )
        lines.append("")
        if dec.decisions:
            lines.append("| # | 游戏 | 动作 | 出口 | 预期收益 | 置信 | 风险 | 理由 |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for i, d in enumerate(dec.decisions, 1):
                lines.append(
                    f"| {i} | {d.game_id} | {d.action} | {d.decision_type.value} | "
                    f"{_pct(d.expected_value)} | {d.confidence:.0%} | "
                    f"{d.risk:.0%} | {d.reason} |"
                )
            lines.append("")
        else:
            lines.append("_E17.3 未产出决策。_")
            lines.append("")

    # ----------------------------------------------------------------- #
    # 6) Execution Route（E17.6 形态）
    # ----------------------------------------------------------------- #
    lines.append("## 6. Execution Route（执行路由 · E17.6 形态）")
    lines.append("")
    if dec and dec.decisions:
        exec_items = [d for d in dec.decisions if d.decision_type.value == "execute"]
        appr_items = [d for d in dec.decisions if d.decision_type.value == "approve"]
        obs_items = [d for d in dec.decisions if d.decision_type.value == "observe"]
        rej_items = [d for d in dec.decisions if d.decision_type.value == "reject"]

        if exec_items:
            lines.append("**🔁 自动执行（EXECUTE）** — 经 E17.6 落地，"
                         "SIM 纪律下不触发真实 API：")
            for d in exec_items:
                lines.append(f"- `{d.game_id}` · {d.action}（audit={d.audit_id}）")
            lines.append("")
        if appr_items:
            lines.append("**👤 人工审批（APPROVE）** — 进入 JsonlApprovalQueue，"
                         "需运营负责人确认后执行：")
            for d in appr_items:
                lines.append(f"- `{d.game_id}` · {d.action}（audit={d.audit_id}）")
            lines.append("")
        if obs_items:
            lines.append("**👁 仅观察（OBSERVE）** — 置信不足，持续监控：")
            for d in obs_items:
                lines.append(f"- `{d.game_id}` · {d.action}")
            lines.append("")
        if rej_items:
            lines.append("**⛔ 拒绝（REJECT）** — 无正向收益预期：")
            for d in rej_items:
                lines.append(f"- `{d.game_id}` · {d.action}")
            lines.append("")
    else:
        lines.append("- 无执行项。")
        lines.append("")

    # ----------------------------------------------------------------- #
    # 验收闸门表
    # ----------------------------------------------------------------- #
    lines.append("## 验收闸门（Gates 1–4）")
    lines.append("")
    if v is None:
        lines.append("- 未运行验收闸门。")
    else:
        overall = "✅ PASS" if v.passed else "❌ FAIL"
        lines.append(f"**总判定：{overall}** ｜ Reality 置信度："
                     f"{v.reality_confidence:.2f}")
        lines.append("")
        lines.append("| 闸门 | 结果 | 明细 |")
        lines.append("|---|---|---|")
        for g in v.gates:
            mark = "✅" if g.passed else "❌"
            det = "；".join(g.details) if g.details else "—"
            lines.append(f"| {g.name} | {mark} | {det} |")
        lines.append("")

    lines.append("---")
    lines.append(f"_由 P1.5 RealCEOOperator 生成 · as_of={result.as_of} · "
                 f"hub_real_api_called={result.hub_real_api_called}_")

    return "\n".join(lines)


__all__ = ["build_ceo_report"]
