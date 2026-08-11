"""
E15.2.5+ — Feishu group-bot notifier for the IAA Monetization Daily Report.

Sends an interactive card to a Feishu custom-bot webhook:
  header  : account / date / H·O·R (Health·Opportunity·Risk, color-coded by state)
  totals  : revenue / impressions / eCPM / waterfall depth
  scorecard: three orthogonal scores (Health state / Opportunity upside / Risk fragility)
  guardrail: ARPDAU user-side guardrail (pending until Adjust/Firebase wired)
  actions : three execution layers (Safe / Experiment / Observe) with value score
  loop    : closed-loop reconciliation summary (what got fixed since last run)
  thinking: optimization methodology derived from the fired rules

Webhook url can be passed explicitly or stored in
credentials/notify.json -> {"feishu_webhook": "..."} (gitignored dir).
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict, List, Optional

from operation.optimizer.intel_models import MonetizationDailyReport

NOTIFY_STORE = os.path.join("credentials", "notify.json")

_PRIO_ICON = {"P0": "\U0001F534", "P1": "\U0001F7E0",
              "P2": "\U0001F7E1", "P3": "\U0001F535"}

# Rule -> one-line "why we do this" methodology (the optimization thinking)
_RULE_THINKING = {
    "zombie_network": (
        "**砍僵尸渠道**：请求量大但几乎不出展示、不产收入的渠道，"
        "只消耗瀑布深度（延迟+SDK开销）。先砍零风险的浪费，是 ROI 最高的一步。"),
    "hidden_winner": (
        "**放大隐形冠军**：eCPM 显著高于账号均值但展示占比极低的渠道，"
        "说明它有高价需求却在竞价里拿不到量——给它更多竞价机会，用高价展示替换低价展示。"),
    "bid_floor": (
        "**用底价卡回填吸血**：兜底渠道以极低 eCPM 吃走大量展示，"
        "每次展示都在挤占高价渠道的机会。设置 bid floor 砍掉最差的展示，宁缺毋滥。"),
    "waterfall_waste": (
        "**控瀑布效率**：每个展示背后的请求次数（深度）越高，延迟越大、用户体验越差。"
        "砍掉无效层，深度下降 = 每次广告机会的变现效率上升。"),
    "revenue_concentration": (
        "**盯集中度风险**：收入过度依赖单一 App/渠道/国家时，任何一个政策变动"
        "（渠道调价、平台下架、geo 波动）都可能腰斩收入。优化的同时必须分散风险。"),
    "geo_opportunity": (
        "**高价 geo 反哺买量**：某些国家 eCPM 远超均值但量极小——"
        "这是给 UA 的信号：往这些 geo 投放，LTV 天花板更高（移交 Growth OS 执行）。"),
}


def load_webhook(store: str = NOTIFY_STORE) -> Optional[str]:
    if os.path.exists(store):
        try:
            with open(store, encoding="utf-8") as f:
                return json.load(f).get("feishu_webhook")
        except (OSError, ValueError):
            return None
    return None


def save_webhook(url: str, store: str = NOTIFY_STORE) -> None:
    os.makedirs(os.path.dirname(store) or ".", exist_ok=True)
    data = {}
    if os.path.exists(store):
        try:
            with open(store, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
    data["feishu_webhook"] = url
    with open(store, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class FeishuNotifier:
    def __init__(self, webhook_url: Optional[str] = None,
                 timeout: int = 15) -> None:
        self.webhook_url = webhook_url or load_webhook()
        if not self.webhook_url:
            raise ValueError("Feishu webhook url missing "
                             "(pass explicitly or set credentials/notify.json)")
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    def send_report(self, report: MonetizationDailyReport,
                    loop_summary: Optional[Dict] = None,
                    extra_note: str = "") -> Dict:
        card = self.build_card(report, loop_summary, extra_note)
        return self._post({"msg_type": "interactive", "card": card})

    def send_text(self, text: str) -> Dict:
        return self._post({"msg_type": "text", "content": {"text": text}})

    def send_markdown_card(self, title: str, markdown: str,
                           color: str = "blue") -> Dict:
        """Push an arbitrary markdown body as a single-section interactive
        card. Used for secondary daily cards (e.g. the per-app fleet
        verdict) without coupling to MonetizationDailyReport internals.
        Rate-limit aware via _post's backoff."""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"template": color,
                       "title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "markdown", "content": markdown}],
        }
        return self._post({"msg_type": "interactive", "card": card})

    # ------------------------------------------------------------------ #
    def build_card(self, r: MonetizationDailyReport,
                   loop_summary: Optional[Dict] = None,
                   extra_note: str = "") -> Dict:
        h, o, risk = r.health_score, r.opportunity_score, r.risk_score
        # header color reads the *state* (Health). A healthy-looking account
        # with HIGH concentration risk still gets a caution tint so ops does
        # not read "green" as "safe".
        if h >= 80:
            color = "green"
        elif h >= 60:
            color = "blue"
        elif h >= 40:
            color = "orange"
        else:
            color = "red"
        if color == "green" and risk >= 75:
            color = "orange"
        title = (f"IAA 变现日报 · {r.account} · {r.date}  "
                 f"\U0001F49A H{h} \U0001F680 O{o} \u26A0\uFE0F R{risk}")

        totals_md = (
            f"**周期** {r.period_start} ~ {r.period_end}\n"
            f"**收入** ${r.revenue:,.2f}    "
            f"**展示** {r.impressions:,}    "
            f"**混合eCPM** ${r.blended_ecpm:.2f}\n"
            f"**请求** {r.attempts:,}    "
            f"**瀑布深度** {r.waterfall_depth:.1f} 请求/展示")

        elements: List[Dict] = [
            {"tag": "markdown", "content": totals_md},
            {"tag": "hr"},
            {"tag": "markdown", "content": self._scorecard_md(r)},
            {"tag": "hr"},
            {"tag": "markdown", "content": self._guardrail_md(r)},
            {"tag": "hr"},
            {"tag": "markdown",
             "content": "**\U0001F525 行动分层（是否值得执行）**\n"
                        + self._actions_md(r, loop_summary)},
        ]

        # E15.2.6 — IAA Growth Report as the HEADLINE block. This is the
        # only section the operator needs to read: did Revenue/DAU go up
        # at equal DAU, and which AI actions moved it. Inserted at the top.
        if r.growth_report:
            from operation.optimizer.reports.growth_report import (
                render_growth_card,
            )
            growth_block = (
                "**\U0001F4C8 IAA Growth Report — 核心 KPI：Revenue / DAU**\n"
                + render_growth_card(r.growth_report))
            elements = [
                {"tag": "markdown", "content": growth_block},
                {"tag": "hr"},
            ] + elements

        # E15.2.6 — Auto-Executor decision layer as a compact block right
        # after the Growth Report: how many actions are AI-auto-approved
        # (human applies in MAX) vs need approval vs observe-only.
        if r.auto_executor:
            _ae = r.auto_executor
            _c = _ae.get("counts", {})
            _head = ("\U0001F916 **Auto-Executor（决策自动 + 人工落子）**  "
                     f"✅自动批准 {_c.get('auto', 0)} · "
                     f"\u26A0\uFE0F需审批 {_c.get('approval', 0)} · "
                     f"\U0001F441仅观察 {_c.get('observe', 0)}")
            _body = _head
            for d in _ae.get("auto", []):
                _body += (f"\n  ✅ {d['target']} — {d['apply_instruction']}")
            for d in _ae.get("approval", []):
                _body += f"\n  \u26A0\uFE0F {d['target']} [{d['action']}] 需审批"
            elements = elements + [
                {"tag": "hr"},
                {"tag": "markdown", "content": _body},
            ]

        if r.experiments:
            elements += [{"tag": "hr"},
                         {"tag": "markdown",
                          "content": "**\U0001F9EA Experiments（核销）**\n"
                                     + self._experiments_md(r)}]

        if r.config_recommendations:
            elements += [{"tag": "hr"},
                         {"tag": "markdown",
                          "content": "**\U0001F39B Target MAX Config（建议，后台手动执行）**\n"
                                     + self._config_md(r)}]

        if r.ecpm_forecasts:
            elements += [{"tag": "hr"},
                         {"tag": "markdown",
                          "content": "**\U0001F4C8 eCPM Forecast（预测）**\n"
                                     + self._forecast_md(r)}]

        if loop_summary:
            elements += [{"tag": "hr"},
                         {"tag": "markdown",
                          "content": self._loop_md(loop_summary)}]

        elements += [{"tag": "hr"},
                     {"tag": "markdown",
                      "content": "**\U0001F9E0 优化思路**\n" + self._thinking_md(r)}]

        if r.risks:
            elements += [{"tag": "hr"},
                         {"tag": "markdown",
                          "content": "**\u26A0\uFE0F 风险**\n"
                                     + "\n".join(f"- {x}" for x in r.risks)}]

        note = ("Phase 1：仅诊断建议，系统零写入 MAX；执行后次日自动核销闭环。"
                + ((" " + extra_note) if extra_note else ""))
        elements += [{"tag": "hr"},
                     {"tag": "note",
                      "elements": [{"tag": "plain_text", "content": note}]}]

        return {
            "config": {"wide_screen_mode": True},
            "header": {"template": color,
                       "title": {"tag": "plain_text", "content": title}},
            "elements": elements,
        }

    # ------------------------------------------------------------------ #
    def _experiments_md(self, r: MonetizationDailyReport) -> str:
        _EXP_ICON = {"ACTIVE": "\U0001F9EA", "SUCCESS": "\u2705",
                     "FAIL": "\u274C", "PROPOSED": "\U0001F195",
                     "INCONCLUSIVE": "\u2753", "ARCHIVED": "\U0001F5DC\uFE0F",
                     "APPLIED": "\U0001F527", "WINNER": "\U0001F3C6",
                     "ROLLBACK": "\u21A9\uFE0F", "MEMORIZED": "\U0001F9E0"}
        lines = []
        for e in r.experiments:
            st = e.get("status", "PROPOSED")
            icon = _EXP_ICON.get(st, "\u2022")
            guard = e.get("last_arpdau_guardrail") or "n/a"
            delta = e.get("last_arpdau_delta_pct")
            g = f"ARPDAU:{guard}"
            if delta is not None:
                g += f" ({delta:+.1f}%)"
            row = (f"{icon} **[{st}] {e.get('action_type')} → "
                   f"{e.get('target')}**  `{g}`\n    "
                   f"{e.get('result_note', '')}")
            imp = e.get("impact") or {}
            ni = imp.get("net_impact_pct")
            if e.get("applied_at") and isinstance(ni, (int, float)):
                row += (f"\n    💰 ${imp.get('before_rev_per_day', 0):.2f}/d"
                        f" → ${imp.get('after_rev_per_day', 0):.2f}/d ·"
                        f" 净增量 **{ni:+.1f}%/d**"
                        f" · {imp.get('verdict', 'OBSERVING')}"
                        + (f" · 决策 **{e.get('decision')}**"
                           if e.get("decision") else ""))
            prior = (e.get("params") or {}).get("prior")
            if prior:
                row += f"\n    🧠 {prior}"
            lines.append(row)
        return "\n".join(lines) if lines else "暂无跟踪实验"

    # ------------------------------------------------------------------ #
    def _config_md(self, r: MonetizationDailyReport) -> str:
        rec = (r.config_recommendations or [{}])[0]
        summ = rec.get("summary", {})
        demote: Dict[str, int] = {}
        floor: Dict[str, List[float]] = {}
        for seg in rec.get("segments", []):
            for n in seg.get("demote_candidates", []):
                demote[n] = demote.get(n, 0) + 1
            for n, fl in seg.get("floor_suggestions", {}).items():
                floor[n] = fl.get("recommended_floor_range", [])
        head = (f"分段分析 {summ.get('segments')} · "
                f"降级候选 {summ.get('demote_candidates')} · "
                f"底价建议 {summ.get('floor_suggestions')} "
                f"（完整排名见 config_recommendations 工件）")
        if not demote:
            return head
        lines = [head, "**建议降级/提底价渠道（跨分段）：**"]
        for n in sorted(demote, key=lambda x: -demote[x]):
            fr = floor.get(n)
            ftag = (f" → 底价 ${fr[0]:.2f}-${fr[1]:.2f}"
                    ) if fr else ""
            lines.append(f"- **{n}**（{demote[n]} 段）{ftag}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    def _forecast_md(self, r: MonetizationDailyReport) -> str:
        fc = (r.ecpm_forecasts or [{}])[0]
        summ = fc.get("summary", {})
        _ARROW = {"UP": "\u2191", "DOWN": "\u2193", "FLAT": "\u2192"}
        head = (f"预测分段 {summ.get('total')} · "
                f"\u2191{summ.get('up')} \u2193{summ.get('down')} "
                f"\u2192{summ.get('flat')} · "
                f"\u26A0\uFE0F 早警 {summ.get('early_warning')}")
        demote_nets = set()
        for crec in (r.config_recommendations or []):
            for seg in crec.get("segments", []):
                demote_nets.update(seg.get("demote_candidates", []))
        lines = [head, "**Top 分段（按量）：**"]
        for f in fc.get("forecasts", [])[:8]:
            arrow = _ARROW.get(f.get("trend"), "\u2192")
            warn = " \u26A0\uFE0F" if f.get("early_warning") else ""
            hit = (" (↔🎛)" if f.get("network") in demote_nets else "")
            seg = f.get("segment", "")
            if len(seg) > 42:
                seg = seg[:42] + "…"
            lines.append(
                f"{arrow} **{seg}** ${f.get('last_ecpm'):.2f}→"
                f"${f.get('predicted_ecpm'):.2f}[{f.get('confidence')}]"
                f"{warn}{hit}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    def _scorecard_md(self, r: MonetizationDailyReport) -> str:
        return (
            "**\U0001F3AF Scorecard（三维分离）**\n"
            "| 维度 | 分 | 等级 | 含义 |\n"
            "|---|---|---|---|\n"
            f"| \U0001F49A Health | **{r.health_score}** | {r.health_grade} "
            f"| 当前变现效率（现状） |\n"
            f"| \U0001F680 Opportunity | **{r.opportunity_score}** | {r.opportunity_grade} "
            f"| 可追回的应用内上行空间 |\n"
            f"| \u26A0\uFE0F Risk | **{r.risk_score}** | {r.risk_grade} "
            f"| 收入脆弱度（集中度） |\n"
            f"> Health 是*状态*不是*判决*；Opportunity 是空间。"
            f"低 Health / 高 Opportunity = 被低估，不是没救。")

    def _guardrail_md(self, r: MonetizationDailyReport) -> str:
        um = r.user_metrics or {}
        if um.get("available"):
            return (
                "**\U0001F6E1\uFE0F 用户护栏 (ARPDAU)**\n"
                f"- ARPDAU ${um.get('arpdau', 0):.4f}（DAU {um.get('dau', 0):,}）\n"
                f"- 广告/人 {um.get('ads_per_user', 0):.2f} · "
                f"激励/人 {um.get('rewarded_per_user', 0):.2f} · "
                f"插屏/人 {um.get('interstitial_per_user', 0):.2f}\n"
                f"- 来源 `{um.get('source')}`")
        return (
            "**\U0001F6E1\uFE0F 用户护栏 (ARPDAU)**\n"
            f"_待接入 — {um.get('note', '未配置用户侧数据源')}。"
            f"优化前接 Adjust/Firebase，才能在 Experiment 层验证"
            f"「收入涨了，但广告负载没涨」_")

    # ------------------------------------------------------------------ #
    def _actions_md(self, r: MonetizationDailyReport,
                    loop_summary: Optional[Dict]) -> str:
        status_by_id = {}
        if loop_summary:
            for bucket, tag in (("new", "\U0001F195 NEW"),
                                ("still_open", None)):
                for item in loop_summary.get(bucket, []):
                    if tag:
                        status_by_id[item["action_id"]] = tag
                    else:
                        status_by_id[item["action_id"]] = (
                            f"\u23F3 OPEN {item.get('age_days', 0)}d")
        grouped = {"safe": [], "experiment": [], "observe": []}
        for v in r.validated_actions:
            grouped.setdefault(v.get("layer", "observe"),
                               grouped["observe"]).append(v)
        layer_meta = [
            ("safe", "\U0001F525 今日执行 (Safe)",
             "高置信·可回滚·零风险 — Phase 3 自动执行候选"),
            ("experiment", "\U0001F9EA 先实验 (Experiment)",
             "真实收入/填充影响 — 用 A/B 验证后再放量"),
            ("observe", "\U0001F440 监控/移交 (Observe)",
             "建议性或越界 — 仅观察，不写 MAX"),
        ]
        if not r.validated_actions:
            return "今日无需动作 ✅"
        lines = []
        for key, heading, blurb in layer_meta:
            items = grouped.get(key)
            if not items:
                continue
            lines.append(f"**{heading}**  _{blurb}_")
            for v in items:
                icon = _PRIO_ICON.get(v.get("priority"), "\u25AA")
                aid = loop_action_id(r.account, v["action"], v["target"])
                st = status_by_id.get(aid, "")
                st = f"  `{st}`" if st else ""
                manual = (" *(需在 MAX 后台手动执行)*"
                          if v.get("requires_manual_apply") else "")
                f0 = v["factors"].get("confidence", 0.0)
                f1 = v["factors"].get("safety", 0.0)
                f2 = v["factors"].get("reversibility", 0.0)
                lines.append(
                    f"{icon} **{v['priority']} | {v['title']}**{st}\n"
                    f"   动作：{v['action']} → `{v['target']}`{manual}\n"
                    f"   价值分：{v['value_score']:.2f} · "
                    f"conf {f0:.0%} / safety {f1:.0%} / rev {f2:.0%}\n"
                    f"   预期：{v['expected_impact']}\n"
                    f"   判据：{v['rationale']}")
        return "\n".join(lines)

    def _loop_md(self, s: Dict) -> str:
        parts = [f"**\U0001F501 闭环状态**  新增 {len(s.get('new', []))} · "
                 f"待执行 {len(s.get('still_open', []))} · "
                 f"已生效 {len(s.get('resolved', []))}"]
        for item in s.get("resolved", []):
            parts.append(f"- \u2705 已生效：{item['action']} → "
                         f"`{item['target']}`（信号消失，"
                         f"发出 {item.get('age_days', '?')} 天后核销）")
        aged = [i for i in s.get("still_open", [])
                if i.get("age_days", 0) >= 3]
        for item in aged:
            parts.append(f"- \u23F0 超时提醒：{item['action']} → "
                         f"`{item['target']}` 已挂起 {item['age_days']} 天未执行")
        return "\n".join(parts)

    def _thinking_md(self, r: MonetizationDailyReport) -> str:
        fired = []
        for s in r.signals:
            if s.rule in _RULE_THINKING and s.rule not in fired:
                fired.append(s.rule)
        if not fired:
            return "指标健康，本期无需干预；持续监控渠道效率与集中度。"
        return "\n".join(f"{i}. {_RULE_THINKING[k]}"
                         for i, k in enumerate(fired, 1))

    # ------------------------------------------------------------------ #
    # Feishu custom-bot rate limit (~100/min, burst 5/s). Batch pushes of
    # several cards back-to-back trip code 11232 "frequency limited" — a
    # transient condition, so retry with backoff instead of failing the run.
    RATE_LIMIT_CODES = {11232, 9499}
    RATE_LIMIT_RETRIES = 3
    RATE_LIMIT_BACKOFF_S = 20          # 20s, 40s, 60s

    def _post(self, payload: Dict) -> Dict:
        import time as _time
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last: Dict = {}
        for attempt in range(self.RATE_LIMIT_RETRIES + 1):
            req = urllib.request.Request(
                self.webhook_url, data=data,
                headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            out = json.loads(resp.read() or b"{}")
            # Feishu success: {"code":0,...} (new) or {"StatusCode":0,...}
            code = out.get("code", out.get("StatusCode", -1))
            if code == 0:
                return out
            last = out
            limited = (code in self.RATE_LIMIT_CODES
                       or "frequency limited" in str(out.get("msg", "")))
            if limited and attempt < self.RATE_LIMIT_RETRIES:
                _time.sleep(self.RATE_LIMIT_BACKOFF_S * (attempt + 1))
                continue
            break
        raise RuntimeError(f"Feishu webhook rejected: {last}")


def loop_action_id(account: str, action: str, target: str) -> str:
    """Stable id shared with the action ledger."""
    import hashlib
    return hashlib.sha1(f"{account}|{action}|{target}".encode()).hexdigest()[:12]


def send_markdown_card(title: str, markdown: str, color: str = "blue",
                       webhook_url: Optional[str] = None) -> Optional[Dict]:
    """Module-level generic helper — push an arbitrary markdown card without
    constructing ``FeishuNotifier`` explicitly.

    Returns the Feishu API response dict on success, or ``None`` when no
    webhook is configured (so batch jobs / daily cards don't crash on a
    missing credential). Other errors (e.g. rate-limit exhaustion) still
    raise and should be caught by the caller's ``try/except``.

    This is the canonical entry point for secondary daily cards (per-app
    fleet verdicts, weekly growth briefing, the unified morning digest) so
    callers no longer need the ``FeishuNotifier(None).send_markdown_card(...)``
    idiom.
    """
    try:
        notifier = FeishuNotifier(webhook_url)
    except ValueError:
        return None
    return notifier.send_markdown_card(title, markdown, color=color)
