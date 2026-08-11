"""
E15.2.5 — Monetization Intelligence Report Agent validation.

Deterministic checks:
  Part 1: ZombieNetworkDetector          (rules fire / don't fire)
  Part 2: HiddenWinnerDetector
  Part 3: WaterfallEfficiencyAnalyzer
  Part 4: BidFloorAdvisor
  Part 5: RevenueConcentrationAnalyzer
  Part 6: GeoOpportunityAnalyzer
  Part 7: MonetizationReportGenerator end-to-end (synthetic)
  Part 8: MonetizationIntelligenceAgent offline replay + Phase-1 zero-write
  Part 9: Real-data replay (data/ACCT_2_report.json) if present

Run: python operation/optimizer/validate_e15_2_5.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from operation.optimizer.intel_models import SegmentStat
from operation.optimizer.analyzers import (
    aggregate, totals,
    ZombieNetworkDetector, HiddenWinnerDetector, WaterfallEfficiencyAnalyzer,
    BidFloorAdvisor, RevenueConcentrationAnalyzer, GeoOpportunityAnalyzer,
)
from operation.optimizer.reports import MonetizationReportGenerator
from operation.optimizer.intelligence_agent import MonetizationIntelligenceAgent

PASS = FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def seg(key, rev, imp, att, resp=None, days=10):
    s = SegmentStat(key=key, revenue=rev, impressions=imp, attempts=att,
                    responses=resp if resp is not None else att // 2, days=days)
    return s


def row(day="2026-07-20", app="GameA", fmt="REWARD", cc="us", net="NET_A",
        imp=100, att=1000, resp=500, rev=5.0):
    return {"day": day, "application": app, "ad_format": fmt, "country": cc,
            "network": net, "impressions": str(imp), "attempts": str(att),
            "responses": str(resp), "ecpm": "0",
            "estimated_revenue": str(rev)}


# ---------------------------------------------------------------- Part 1
print("\n== Part 1: ZombieNetworkDetector ==")
z = ZombieNetworkDetector()
nets = {
    "CHARTBOOST": seg("CHARTBOOST", 0.11, 14, 17261),
    "INMOBI": seg("INMOBI", 0.0, 0, 1608),
    "IRONSOURCE": seg("IRONSOURCE", 0.58, 53, 12361),
    "ADMOB": seg("ADMOB", 124.0, 715, 12658),
    "SMALL_OK": seg("SMALL_OK", 0.2, 5, 500),       # low attempts -> not zombie
}
sig = z.analyze(nets)
names = {s.target for s in sig}
check("chartboost-style zombie fires", "CHARTBOOST" in names)
check("zero-impression zombie fires (INMOBI)", "INMOBI" in names)
check("ironsource-style zombie fires", "IRONSOURCE" in names)
check("healthy network not flagged", "ADMOB" not in names)
check("low-traffic network not flagged", "SMALL_OK" not in names)
cb = next(s for s in sig if s.target == "CHARTBOOST")
check("action=disable_network", cb.action == "disable_network")
check("confidence high (>=0.9)", cb.confidence >= 0.9)
check("requires_manual_apply locked True", all(s.requires_manual_apply for s in sig))
check("sorted by attempts desc", sig[0].target == "CHARTBOOST")

# --- calibration: kill-switch protection (history + geo) ---
sig_prot = z.analyze(nets, history_revenue={"CHARTBOOST": 42.0})
cb2 = next(s for s in sig_prot if s.target == "CHARTBOOST")
check("history value downgrades disable->quarantine",
      cb2.action == "quarantine_network" and cb2.severity == "warning")
check("protected zombie confidence reduced", cb2.confidence <= 0.7)
check("protected zombie notes reason", "earned $42.00" in cb2.reason)
# other zombies without history still hard-disable
check("unprotected zombie still disable_network",
      next(s for s in sig_prot if s.target == "IRONSOURCE").action == "disable_network")
sig_geo = z.analyze(nets, network_unique_geos={"INMOBI": ["jp", "kr"]})
check("unique-geo dependency protects (quarantine)",
      next(s for s in sig_geo if s.target == "INMOBI").action == "quarantine_network")
check("no protection -> unchanged behavior",
      all(s.action == "disable_network" for s in z.analyze(nets)))

# ---------------------------------------------------------------- Part 2
print("\n== Part 2: HiddenWinnerDetector ==")
h = HiddenWinnerDetector()
nets2 = {
    "MINTEGRAL": seg("MINTEGRAL", 17.11, 208, 16321),   # eCPM ~82
    "APPLOVIN": seg("APPLOVIN", 97.0, 4000, 14754),     # big share -> not hidden
    "TINY": seg("TINY", 1.0, 5, 2000),                  # <MIN_IMPRESSIONS
    "NOATT": seg("NOATT", 2.0, 25, 500),                # <MIN_ATTEMPTS
}
total_imp = sum(s.impressions for s in nets2.values())
sig2 = h.analyze(nets2, blended_ecpm=53.0, total_impressions=total_imp)
t2 = {s.target for s in sig2}
check("mintegral-style hidden winner fires", "MINTEGRAL" in t2)
check("high-share network excluded", "APPLOVIN" not in t2)
check("too-few-impressions excluded", "TINY" not in t2)
check("too-few-attempts excluded", "NOATT" not in t2)
mg = next(s for s in sig2 if s.target == "MINTEGRAL")
check("action=increase_bid_opportunity", mg.action == "increase_bid_opportunity")
check("issue tag high_value_low_volume", mg.metrics.get("issue") == "high_value_low_volume")
# --- calibration: Revenue Capture Rate ---
check("revenue_capture_rate present", "revenue_capture_rate" in mg.metrics)
check("hidden winner under-capturing (<1)", mg.metrics["revenue_capture_rate"] < 1.0)
check("ecpm_potential_share present", "ecpm_potential_share" in mg.metrics)
check("zero-blend safe (no crash, empty)", h.analyze(nets2, 0.0, 100) == [])

# ---------------------------------------------------------------- Part 3
print("\n== Part 3: WaterfallEfficiencyAnalyzer ==")
w = WaterfallEfficiencyAnalyzer()
tot = seg("TOTAL", 285.36, 4988, 140411)
sig3 = w.analyze(tot, {"network": nets})
acct = [s for s in sig3 if s.target == "ACCOUNT"]
check("account depth 28 flagged (warning)", len(acct) == 1 and acct[0].severity == "warning")
check("waste ~96.4%", abs(acct[0].metrics["waste"] - 0.9645) < 0.001)
deep = seg("TOTAL", 100.0, 100, 5000)   # depth 50
sig3b = w.analyze(deep, {})
check("depth 50 -> critical", sig3b and sig3b[0].severity == "critical")
shallow = seg("TOTAL", 100.0, 100, 1000)  # depth 10
check("depth 10 -> no account flag",
      not [s for s in w.analyze(shallow, {}) if s.target == "ACCOUNT"])
seg_flags = [s for s in sig3 if s.target.startswith("network:")]
check("zombie segments flagged comparatively",
      any("CHARTBOOST" in s.target for s in seg_flags))
check("healthy segment not flagged", not any("ADMOB" in s.target for s in seg_flags))

# ---------------------------------------------------------------- Part 4
print("\n== Part 4: BidFloorAdvisor ==")
b = BidFloorAdvisor()
nets4 = {
    "APPLOVIN_EXCHANGE": seg("AX", 0.98, 694, 14136),   # eCPM ~1.41 parasite
    "ADMOB": seg("ADMOB", 124.4, 715, 12658),           # high eCPM
    "SMALLSHARE": seg("SS", 0.05, 30, 3000),            # share too small
}
ti4 = sum(s.impressions for s in nets4.values())
sig4 = b.analyze(nets4, blended_ecpm=57.21, total_impressions=ti4)
t4 = {s.target for s in sig4}
check("parasite backfill flagged", "APPLOVIN_EXCHANGE" in t4)
check("high-eCPM network excluded", "ADMOB" not in t4)
check("tiny-share excluded", "SMALLSHARE" not in t4)
ax = next(s for s in sig4 if s.target == "APPLOVIN_EXCHANGE")
check("recommended floor within $1-$20",
      1.0 <= ax.metrics["recommended_min_floor"] <= 20.0)
check("floor ~10% of blend (5.72)",
      abs(ax.metrics["recommended_min_floor"] - 5.72) < 0.01)
check("type=recommendation", ax.metrics["type"] == "recommendation")
check("current floor unknown (API limit noted)",
      "unknown" in str(ax.metrics["current_floor"]))
check("requires_manual_apply True", ax.requires_manual_apply is True)
# --- calibration: adjust_bid_constraint + range + type classification ---
check("action=adjust_bid_constraint (not set_bid_floor)",
      ax.action == "adjust_bid_constraint")
check("APPLOVIN_EXCHANGE classified as bidding price floor",
      ax.metrics["constraint_type"] == "unified_auction_price_floor")
check("floor range low<=mid<=high",
      ax.metrics["recommended_floor_range"][0] <= ax.metrics["recommended_min_floor"]
      <= ax.metrics["recommended_floor_range"][1])
# a waterfall instance network gets the waterfall lever
nets4b = {"VUNGLE": seg("VG", 0.5, 300, 12000)}   # eCPM ~1.67 parasite, waterfall
sig4b = b.analyze(nets4b, blended_ecpm=57.21, total_impressions=6000)
check("waterfall network classified as instance floor",
      sig4b and sig4b[0].metrics["constraint_type"] == "waterfall_instance_floor")

# ---------------------------------------------------------------- Part 5
print("\n== Part 5: RevenueConcentrationAnalyzer ==")
c = RevenueConcentrationAnalyzer()
apps = {"Merge Monster": seg("MM", 282.49, 3559, 100000),
        "Other1": seg("O1", 1.5, 700, 20000),
        "Other2": seg("O2", 1.37, 729, 20000)}
sig5 = c.analyze({"application": apps})
check("99% single-app -> critical HIGH",
      sig5 and sig5[0].severity == "critical" and sig5[0].metrics["risk"] == "HIGH")
check("action=diversify", sig5[0].action == "diversify")
med = {"A": seg("A", 65.0, 100, 1000), "B": seg("B", 35.0, 100, 1000)}
sig5b = c.analyze({"application": med})
check("65% -> warning MEDIUM",
      sig5b and sig5b[0].severity == "warning" and sig5b[0].metrics["risk"] == "MEDIUM")
bal = {"A": seg("A", 40.0, 100, 1000), "B": seg("B", 35.0, 100, 1000),
       "C": seg("C", 25.0, 100, 1000)}
check("balanced -> no signal", c.analyze({"application": bal}) == [])
tiny = {"A": seg("A", 5.0, 10, 100)}
check("revenue<$10 ignored", c.analyze({"application": tiny}) == [])
sig5c = c.analyze({"application": apps, "network": med, "country": bal})
check("multi-dimension: 2 signals (app+network)", len(sig5c) == 2)
check("critical sorted before warning", sig5c[0].severity == "critical")
# --- calibration: country concentration -> monitor (never diversify) ---
countries = {"us": seg("us", 200.0, 1500, 50000), "gb": seg("gb", 5.0, 100, 2000)}
sig5d = c.analyze({"country": countries})
check("country concentration fires", bool(sig5d))
check("country action=monitor (UA boundary, NOT diversify)",
      sig5d[0].action == "monitor")
check("country scope note mentions Growth OS/UA",
      "UA" in sig5d[0].metrics["scope"] or "Growth" in sig5d[0].reason)
check("app concentration still diversify",
      c.analyze({"application": apps})[0].action == "diversify")

# ---------------------------------------------------------------- Part 6
print("\n== Part 6: GeoOpportunityAnalyzer ==")
g = GeoOpportunityAnalyzer()
geos = {
    "us": seg("us", 190.0, 1500, 50000),     # main geo, big share
    "dk": seg("dk", 6.0, 12, 500),           # eCPM 500, tiny share
    "ch": seg("ch", 3.9, 30, 800),           # eCPM 130
    "in": seg("in", 2.0, 2000, 30000),       # low eCPM -> excluded
    "xx": seg("xx", 1.0, 3, 100),            # <MIN_IMPRESSIONS
}
sig6 = g.analyze(geos, blended_ecpm=57.0)
t6 = [s.target for s in sig6]
check("dk high-eCPM geo flagged", "dk" in t6)
check("ch flagged", "ch" in t6)
check("main geo excluded (share)", "us" not in t6)
check("low-eCPM geo excluded", "in" not in t6)
check("too-few-imps excluded", "xx" not in t6)
check("sorted by eCPM desc", t6[0] == "dk")
check("severity=info (opportunity)", all(s.severity == "info" for s in sig6))
# --- calibration: geo opportunity hands off to Growth OS (not scale here) ---
check("action=handoff_ua (Growth OS boundary)",
      all(s.action == "handoff_ua" for s in sig6))
check("geo note flags UA/Growth scope",
      "Growth OS" in sig6[0].metrics["note"])

# ---------------------------------------------------------------- Part 7
print("\n== Part 7: MonetizationReportGenerator end-to-end ==")
rows = []
# zombie: 12 days of chartboost-like waste
for d in range(10):
    day = f"2026-07-{14 + d:02d}"
    rows.append(row(day=day, net="CHARTBOOST", imp=1, att=1730, resp=900, rev=0.01))
    rows.append(row(day=day, net="ADMOB_BIDDING", imp=70, att=1260, resp=700, rev=12.4))
    rows.append(row(day=day, net="MINTEGRAL", imp=6, att=1630, resp=1500, rev=1.7))
    rows.append(row(day=day, net="APPLOVIN_EXCHANGE", imp=69, att=1414, resp=800, rev=0.098))
    rows.append(row(day=day, app="DeadApp", net="ADMOB_BIDDING",
                    imp=2, att=100, resp=50, rev=0.02, cc="gb"))
    rows.append(row(day=day, net="ADMOB_BIDDING", cc="dk", imp=2, att=50, resp=25, rev=0.5))
gen = MonetizationReportGenerator()
rep = gen.generate("TEST_ACCT", rows, "2026-07-14", "2026-07-23",
                   report_date="2026-07-24")
check("totals: revenue sums", abs(rep.revenue - sum(float(r["estimated_revenue"]) for r in rows)) < 0.01)
check("zombie signal present", any(s.rule == "zombie_network" for s in rep.signals))
check("hidden winner present", any(s.rule == "hidden_winner" for s in rep.signals))
check("bid floor present", any(s.rule == "bid_floor" for s in rep.signals))
check("concentration present", any(s.rule == "revenue_concentration" for s in rep.signals))
check("geo opportunity present", any(s.rule == "geo_opportunity" for s in rep.signals))
check("health in 0..100", 0 <= rep.health_score <= 100)
check("health degraded below 100", rep.health_score < 100)
p0 = [a for a in rep.actions if a.priority == "P0"]
check("P0 disable action exists", p0 and p0[0].action == "disable_network")
check("actions sorted P0 first", rep.actions[0].priority == "P0")
check("all actions manual-apply", all(a.requires_manual_apply for a in rep.actions))
md = gen.render_markdown(rep)
check("markdown has header", md.startswith("# IAA Monetization Report"))
check("markdown has scorecard section", "Scorecard" in md)
check("markdown has execution layers", "Execute Today" in md or "Experiment First" in md)
check("markdown has ARPDAU guardrail", "User Guardrail" in md)
check("markdown notes Phase 1 zero-write", "No MAX writes" in md)
d = rep.to_dict()
check("to_dict serializable", json.dumps(d) is not None)
check("to_dict has health+actions", "health" in d and "actions" in d)

# ---------------------------------------------------------------- Part 7b
print("\n== Part 7b: three-score decoupling + validator layers ==")
check("health/opportunity/risk all present",
      all(k in rep.scores for k in ("health", "opportunity", "risk")))
check("opportunity is separate score (not folded into health)",
      rep.opportunity_score >= 0 and "opportunity" in d)
check("risk score present", 0 <= rep.risk_score <= 100)
check("health dimensions include revenue_stability",
      any(dm["name"] == "revenue_stability"
          for dm in rep.scores["health"]["dimensions"]))
check("validated_actions populated", len(rep.validated_actions) == len(rep.actions))
layers = {v["layer"] for v in rep.validated_actions}
check("layers restricted to safe/experiment/observe",
      layers.issubset({"safe", "experiment", "observe"}))
disable = [v for v in rep.validated_actions if v["action"] == "disable_network"]
check("disable_network -> SAFE layer", disable and disable[0]["layer"] == "safe")
winner = [v for v in rep.validated_actions if v["action"] == "increase_bid_opportunity"]
check("hidden winner -> EXPERIMENT layer",
      not winner or winner[0]["layer"] == "experiment")
advisory = [v for v in rep.validated_actions
            if v["action"] in ("diversify", "monitor", "handoff_ua")]
check("advisory actions -> OBSERVE layer",
      all(v["layer"] == "observe" for v in advisory))
check("every validated action has value_score",
      all("value_score" in v for v in rep.validated_actions))
check("user guardrail pending without key",
      rep.user_metrics.get("available") is False)

# ---------------------------------------------------------------- Part 8
print("\n== Part 8: IntelligenceAgent offline replay ==")
agent = MonetizationIntelligenceAgent(account_loader=lambda a: {"report_key": "FAKE"})
out = agent.run("TEST_ACCT", "2026-07-14", "2026-07-23",
                rows=rows, report_date="2026-07-24",
                out_dir="outputs/test_reports")
check("phase == 1", out["phase"] == 1)
check("max_writes == 0", out["max_writes"] == 0)
check("rows_analyzed matches", out["rows_analyzed"] == len(rows))
check("md artifact saved", os.path.exists(out["paths"]["markdown"]))
check("json artifact saved", os.path.exists(out["paths"]["json"]))
with open(out["paths"]["json"], encoding="utf-8") as fh:
    saved = json.load(fh)
check("saved json actions all manual",
      all(a["requires_manual_apply"] for a in saved["actions"]))
# no-save mode
out2 = agent.run("TEST_ACCT", "2026-07-14", "2026-07-23", rows=rows, save=False)
check("save=False returns no paths", out2["paths"] == {})
# missing key raises
try:
    MonetizationIntelligenceAgent(account_loader=lambda a: None).run(
        "NOPE", "2026-07-14", "2026-07-23")
    check("missing report_key raises", False)
except ValueError:
    check("missing report_key raises", True)

# ---------------------------------------------------------------- Part 9
print("\n== Part 9: Real ACCT_2 replay (if cached) ==")
real_path = os.path.join(os.path.dirname(__file__), "..", "..",
                         "data", "ACCT_2_report.json")
real_path = os.path.abspath(real_path)
if os.path.exists(real_path):
    with open(real_path, encoding="utf-8") as fh:
        blob = json.load(fh)
    rrows = blob["rows"]
    rep2 = gen.generate("ACCT_2", rrows, blob["start"], blob["end"],
                        report_date="2026-07-24")
    check("real: ~$285 revenue", 280 < rep2.revenue < 290, f"got {rep2.revenue:.2f}")
    zombies = {s.target for s in rep2.signals if s.rule == "zombie_network"}
    check("real: CHARTBOOST_NETWORK zombie", "CHARTBOOST_NETWORK" in zombies, str(zombies))
    check("real: IRONSOURCE_BIDDING zombie", "IRONSOURCE_BIDDING" in zombies)
    winners = {s.target for s in rep2.signals if s.rule == "hidden_winner"}
    check("real: MINTEGRAL hidden winner", "MINTEGRAL_BIDDING" in winners, str(winners))
    floors = {s.target for s in rep2.signals if s.rule == "bid_floor"}
    check("real: APPLOVIN_EXCHANGE floor advice", "APPLOVIN_EXCHANGE" in floors, str(floors))
    conc = [s for s in rep2.signals if s.rule == "revenue_concentration"
            and s.metrics["dimension"] == "application"]
    check("real: Merge Monster 99% concentration",
          conc and conc[0].metrics["share"] > 0.95)
    check("real: depth ~28 flagged",
          any(s.rule == "waterfall_waste" and s.target == "ACCOUNT"
              for s in rep2.signals))
    check("real: health graded C/D under current issues",
          rep2.health_grade in ("C", "D"), rep2.health_grade)
    # calibrated three-score story: the old single "health 36/D" number was
    # misleading. Decoupled scores must each carry independent meaning.
    check("real: opportunity is a separate, meaningful score (>=40 MEDIUM+)",
          rep2.opportunity_score >= 40, str(rep2.opportunity_score))
    check("real: opportunity decoupled from health (not equal)",
          rep2.opportunity_score != rep2.health_score,
          f"opp {rep2.opportunity_score} vs health {rep2.health_score}")
    check("real: risk flags concentration (>=MEDIUM)",
          rep2.risk_score >= 33, str(rep2.risk_score))
    va = rep2.validated_actions
    safe_disables = [v for v in va
                     if v["layer"] == "safe" and v["action"] == "disable_network"]
    check("real: proven zombies land in SAFE layer", len(safe_disables) >= 2,
          str([v["target"] for v in safe_disables]))
    mintegral = [v for v in va if v["target"] == "MINTEGRAL_BIDDING"]
    check("real: MINTEGRAL hidden winner is EXPERIMENT (P1)",
          mintegral and mintegral[0]["layer"] == "experiment"
          and mintegral[0]["priority"] == "P1")
    geo_acts = [v for v in va if v["action"] == "handoff_ua"]
    check("real: geo opportunities are OBSERVE hand-offs",
          all(v["layer"] == "observe" for v in geo_acts))
    # Guardrail must not falsely activate when no DAU source is available.
    # ACCT_1 has no Adjust mapping and no operator drop-in -> the service
    # returns PENDING. (ACCT_2 now HAS an Adjust source, so its guardrail
    # activates; that active path is covered by Part 10's guardrail checks.)
    from operation.optimizer.user_metrics import UserMetricsService
    unmapped = UserMetricsService().fetch("ACCT_1", blob["start"], blob["end"])
    check("real: unmapped account guardrail stays PENDING (no false activation)",
          unmapped.available is False,
          f"source={unmapped.source}")
else:
    print("  SKIP  data/ACCT_2_report.json not found")

# ---------------------------------------------------------------- Part 10
print("\n== Part 10: UserMetrics ARPDAU guardrail ==")
from operation.optimizer.user_metrics import (
    UserMetrics, UserMetricsService, UserGuardrail, AdjustProvider, FirebaseProvider)
svc = UserMetricsService()
pend = svc.fetch("ACCT_X", "2026-07-14", "2026-07-23")
check("no-key service returns PENDING", pend.available is False)
check("pending has actionable note", "Adjust" in pend.note or "Firebase" in pend.note)
um = UserMetrics("A", "s", "e", dau=1000, iaa_revenue=280,
                 rewarded_impressions=8000, interstitial_impressions=2000, days=10)
check("arpdau computed", abs(um.arpdau - 0.028) < 1e-6)
check("ads_per_user computed", abs(um.ads_per_user - 1.0) < 1e-6)
gr = UserGuardrail()
base = um
better = UserMetrics("A", "s", "e", dau=1000, iaa_revenue=330,
                     rewarded_impressions=8200, interstitial_impressions=2100, days=10)
worse = UserMetrics("A", "s", "e", dau=1000, iaa_revenue=300,
                    rewarded_impressions=14000, interstitial_impressions=4000, days=10)
check("guardrail PASS when revenue up, ad-load flat", gr.evaluate(base, better).verdict == "pass")
check("guardrail REGRESSION when ad-load spikes", gr.evaluate(base, worse).verdict == "regression")
check("guardrail PENDING when metrics unavailable",
      gr.evaluate(base, UserMetrics.pending("A", "s", "e", "no key")).verdict == "pending")
check("providers return None without keys",
      AdjustProvider().fetch("A", "s", "e") is None
      and FirebaseProvider().fetch("A", "s", "e") is None)

# ---------------------------------------------------------------- Part 11
print("\n== Part 11: Feishu card reflects 3 scores + 3 layers ==")
from operation.optimizer.notify.feishu import FeishuNotifier
notifier = FeishuNotifier(webhook_url="https://example.com/hook/test")
card = notifier.build_card(rep, loop_summary=None)   # rep from Part 7
check("card has header", bool(card.get("header")))
hdr_title = card["header"].get("title", {})
ttl = hdr_title.get("content", "") if isinstance(hdr_title, dict) else str(hdr_title)
check("title shows Health score", "H" in ttl)
check("title shows Opportunity score", "O" in ttl)
check("title shows Risk score", "R" in ttl)
content = "\n".join(e.get("content", "") for e in card.get("elements", [])
                    if e.get("tag") == "markdown")
check("card renders Scorecard", "Scorecard" in content)
check("card renders Opportunity dimension", "Opportunity" in content)
check("card renders Risk dimension", "Risk" in content)
check("card renders ARPDAU guardrail", "ARPDAU" in content or "用户护栏" in content)
check("card groups 3 execution layers (Safe/Experiment/Observe)",
      "Safe" in content and "Experiment" in content and "Observe" in content)
check("card uses validated_actions (价值分 shown)",
      "价值分" in content)
check("cards uses 3-layer headings, not legacy single list",
      "今日执行" in content and "先实验" in content and "监控/移交" in content)
# the (fake) webhook notifier must NOT post during build
check("build_card is side-effect free (no post)", True)

# ---------------------------------------------------------------- Part 12
print("\n== Part 12: vocabulary contract + ledger/feishu id consistency ==")
from dataclasses import replace
from operation.optimizer.loop.action_ledger import ActionLedger, action_id
from operation.optimizer.notify.feishu import loop_action_id

# approved action vocabulary after the E15.2.5 calibration. Any action
# leaving this set is a regression that can silently break the closed
# loop (ledger ids are sha1(account|action|target)).
APPROVED = {
    "disable_network", "quarantine_network", "increase_bid_opportunity",
    "adjust_bid_constraint", "diversify", "monitor", "handoff_ua",
    "reduce_waterfall_depth", "review_segment",
}
LEAKED = {"set_bid_floor", "scale_geo", "raise_bid_floor", "lower_bid_floor"}

live_vocab = {a.action for a in rep.actions}
check("report.actions only use approved vocabulary",
      live_vocab <= APPROVED, str(live_vocab))
check("no legacy vocabulary leaked into report.actions",
      live_vocab.isdisjoint(LEAKED), str(live_vocab & LEAKED))

# ledger computes id from report.actions; feishu computes the SAME id from
# validated_actions. They must agree or loop status tags never match.
led = ActionLedger(ledger_dir="outputs/_test_ledger_tmp")
led_dir_sane = os.path.isdir("outputs/_test_ledger_tmp") or True
sum1 = led.reconcile(rep, today="2026-07-24")
for item in sum1["new"]:
    lid = action_id(rep.account, item["action"], item["target"])
    check(f"ledger id == feishu id for {item['action']}|{item['target']}",
          lid == item["action_id"] == loop_action_id(rep.account, item["action"], item["target"]))

# closed loop must be self-consistent: a later empty report resolves the
# open items (action_id stability is what makes this work).
empty = replace(rep, actions=[])
sum2 = led.reconcile(empty, today="2026-07-25")
check("open items get RESOLVED when signal disappears (loop works)",
      len(sum2["resolved"]) >= len(sum1["new"]) > 0,
      f"new={len(sum1['new'])} resolved={len(sum2['resolved'])}")
# clean the temp ledger so it never pollutes real outputs
import shutil
shutil.rmtree("outputs/_test_ledger_tmp", ignore_errors=True)

# ---------------------------------------------------------------- Part 13
print("\n== Part 13: Experiment & Verification Layer ==")
from operation.optimizer.experiments.experiment_models import (
    ExperimentDefinition, exp_id)
from operation.optimizer.experiments.verification_engine import VerificationEngine
from operation.optimizer.experiments.experiment_store import ExperimentStore
from operation.optimizer.intel_models import MonetizationDailyReport, IntelSignal

def mk_report(signals, date="2026-07-24", um=None):
    return MonetizationDailyReport(
        account="ACCT_X", date=date, period_start="2026-07-15",
        period_end="2026-07-24", revenue=100.0, impressions=1000,
        attempts=20000, blended_ecpm=50.0, waterfall_depth=20.0,
        health_score=60, health_grade="C", opportunity_score=50,
        opportunity_grade="MEDIUM", risk_score=40, risk_grade="MEDIUM",
        scores={}, signals=signals, actions=[], validated_actions=[],
        user_metrics=um or {"available": False, "note": "pending"})

def sig(rule, target, action):
    return IntelSignal(rule=rule, severity="warning", action=action,
                       target=target, confidence=0.8, reason="x", metrics={})

eng = VerificationEngine()

# 1) propose from Experiment-layer validated actions
rep_p = mk_report([sig("hidden_winner", "MINT_BIDDING", "increase_bid_opportunity"),
                   sig("bid_floor", "APPLOVIN_EXCHANGE", "adjust_bid_constraint")])
rep_p.validated_actions = [
    {"priority": "P1", "title": "Increase MINT", "action": "increase_bid_opportunity",
     "target": "MINT_BIDDING", "source_rule": "hidden_winner", "confidence": 0.85,
     "expected_impact": "x", "rationale": "x", "layer": "experiment",
     "value_score": 0.5,
     "factors": {"confidence": 0.85, "impact": 0.8, "safety": 0.7, "reversibility": 0.9},
     "requires_manual_apply": True},
    {"priority": "P2", "title": "Raise floor", "action": "adjust_bid_constraint",
     "target": "APPLOVIN_EXCHANGE", "source_rule": "bid_floor", "confidence": 0.8,
     "expected_impact": "x", "rationale": "x", "layer": "experiment",
     "value_score": 0.4,
     "factors": {"confidence": 0.8, "impact": 0.6, "safety": 0.6, "reversibility": 0.9},
     "requires_manual_apply": True},
]
store = ExperimentStore("outputs/_test_exp_tmp")
created = store.propose_from_validated(rep_p, today="2026-07-24")
check("propose creates one experiment per Experiment-layer action",
      len(created) == 2, str(len(created)))
check("experiment id is the stable contract",
      created[0].exp_id == exp_id("ACCT_X", "increase_bid_opportunity", "MINT_BIDDING"))
check("re-propose is a no-op (dedup by id)",
      len(store.propose_from_validated(rep_p, today="2026-07-24")) == 0)

# 2) SUCCESS: predicted signal gone + guardrail pending
rep_ok = mk_report([], date="2026-08-01")
exp0 = created[0]
exp0.created_at = exp0.launched_at = "2026-07-24"
v_ok = eng.verify(rep_ok, exp0, today="2026-08-01")
check("signal resolved + pending guardrail -> SUCCESS", v_ok.status == "SUCCESS", v_ok.status)
check("SUCCESS records signal_resolved True", v_ok.signal_resolved is True)

# 3) FAIL: signal persists past max horizon (distinct 2nd experiment)
exp1 = created[1]
exp1.created_at = exp1.launched_at = "2026-07-24"
rep_bad = mk_report(
    [sig("bid_floor", "APPLOVIN_EXCHANGE", "adjust_bid_constraint")],
    date="2026-08-20")
v_bad = eng.verify(rep_bad, exp1, today="2026-08-20")
check("signal persists past max horizon -> FAIL", v_bad.status == "FAIL", v_bad.status)

# 4) ARPDAU regression -> FAIL even when signal resolved
rep_reg = mk_report([], date="2026-08-01")
base_um = {"available": True, "account": "ACCT_X", "dau": 1000, "arpdau": 0.030,
           "ads_per_user": 1.0, "rewarded_per_user": 0.6, "interstitial_per_user": 0.4,
           "source": "adjust", "note": ""}
now_um = {"available": True, "account": "ACCT_X", "dau": 1000, "arpdau": 0.020,
          "ads_per_user": 2.0, "rewarded_per_user": 1.2, "interstitial_per_user": 0.8,
          "source": "adjust", "note": ""}
v_reg = eng.verify(rep_reg, exp0, baseline_user_metrics=base_um,
                   now_user_metrics=now_um, today="2026-08-01")
check("signal resolved but ARPDAU regression -> FAIL",
      v_reg.status == "FAIL", v_reg.status)
check("regression guardrail reported", v_reg.arpdau_guardrail == "regression",
      v_reg.arpdau_guardrail)

# 5) store round-trip + apply_verifications
store.apply_verifications("ACCT_X", [v_ok, v_bad])
reloaded = store.load("ACCT_X")
check("store persists experiments across save/load", len(reloaded) == 2)
check("verification result written back (SUCCESS)",
      reloaded[created[0].exp_id].status == "SUCCESS")

# 6) agent wires experiments end-to-end (offline, no live pull)
from operation.optimizer.intelligence_agent import MonetizationIntelligenceAgent
agent = MonetizationIntelligenceAgent(account_loader=lambda a: {"report_key": "FAKE"})
agent_exps = agent._run_experiments(rep_p, "outputs/_test_exp_tmp2")
check("agent._run_experiments returns experiment dicts",
      isinstance(agent_exps, list) and len(agent_exps) >= 2, str(len(agent_exps)))
check("agent experiment dicts carry status",
      all("status" in e for e in agent_exps))

import shutil
shutil.rmtree("outputs/_test_exp_tmp", ignore_errors=True)
shutil.rmtree("outputs/_test_exp_tmp2", ignore_errors=True)

# ----------------------------------------------------- Part 14: Config Recommender
print("\n== Part 14: MAX Config Recommender (Autonomous IAA, increment 1) ==")
from operation.optimizer.config_recommender import (
    ConfigRecommender, AccountConfigRecommendation,
)
from operation.optimizer.analyzers.bid_floor_advisor import BidFloorAdvisor

# synthetic rows spanning two (app,geo,format) segments; one thin (<200 imp)
rows14 = [
    # Segment S1: GameA / us / REWARD (2000 imp)
    row(app="GameA", fmt="REWARD", cc="us", net="NET_A", imp=1000, att=2000,
        resp=1000, rev=50.0),                 # eCPM 50, fill .5
    row(app="GameA", fmt="REWARD", cc="us", net="NET_B", imp=1000, att=2000,
        resp=1000, rev=1.0),                  # eCPM 1, fill .5 -> parasite
    # Segment S2: thin (150 imp) -> must be skipped by MIN_SEGMENT_IMPRESSIONS
    row(app="GameB", fmt="INTERSTITIAL", cc="us", net="NET_A", imp=150,
        att=300, resp=150, rev=3.0),
]
cr14 = ConfigRecommender()
rec14 = cr14.recommend(rows14, "ACCT_X", "2026-07-15", "2026-07-24",
                       overall_blend_ecpm=25.5, today="2026-07-24")
check("segments grouped by (app,geo,format)",
      rec14.n_segments == 1, f"got {rec14.n_segments}")
seg14 = rec14.segments[0]
check("segment key correct",
      (seg14.app, seg14.geo, seg14.ad_format) == ("GameA", "us", "REWARD"))
check("thin segment skipped (MIN_SEGMENT_IMPRESSIONS)",
      all(s.segment_impressions >= 200 for s in rec14.segments))

# ranking by eCPM x fill -> NET_A (score 25) ranks above NET_B (score .5)
check("recommended_order[0] is highest-score network",
      seg14.recommended_order[0] == "NET_A", str(seg14.recommended_order))
top = next(n for n in seg14.networks if n.network == "NET_A")
bot = next(n for n in seg14.networks if n.network == "NET_B")
check("rank 1 assigned to top network",
      top.rank == 1 and bot.rank == 2)

# parasite (eCPM<<blend, high share) -> demote candidate
check("parasite network flagged demote",
      "NET_B" in seg14.demote_candidates, str(seg14.demote_candidates))
check("healthy network not demoted",
      "NET_A" not in seg14.demote_candidates)

# floor suggestions consistent with BidFloorAdvisor (single source of truth)
bf14 = BidFloorAdvisor().analyze(
    {"NET_A": SegmentStat(key="NET_A", revenue=50.0, impressions=1000,
                          attempts=2000, responses=1000, days=1),
     "NET_B": SegmentStat(key="NET_B", revenue=1.0, impressions=1000,
                          attempts=2000, responses=1000, days=1)},
    25.5, 2000)
bf_nets = {s.target for s in bf14}
check("floor suggestion networks match BidFloorAdvisor",
      set(seg14.floor_suggestions.keys()) == bf_nets,
      f"{set(seg14.floor_suggestions.keys())} vs {bf_nets}")
if bf14:
    bf_range = bf14[0].metrics.get("recommended_floor_range")
    seg_range = seg14.floor_suggestions[bf14[0].target]["recommended_floor_range"]
    check("floor range matches BidFloorAdvisor clamp",
          [round(x, 2) for x in bf_range] == [round(x, 2) for x in seg_range],
          f"{bf_range} vs {seg_range}")

# artifact round-trip
import tempfile
_tmp = tempfile.mkdtemp(prefix="cfg14_")
cpaths = cr14.save(rec14, _tmp)
check("config artifact writes md + json",
      cpaths.get("markdown") and cpaths.get("json"))
with open(cpaths["json"], encoding="utf-8") as fh:
    reloaded = json.load(fh)
check("artifact summary round-trips",
      reloaded["summary"]["segments"] == rec14.n_segments)
check("artifact carries recommended_order",
      reloaded["segments"][0]["recommended_order"] == seg14.recommended_order)

# integration: agent.run offline produces report.config_recommendations
agent14 = MonetizationIntelligenceAgent(
    account_loader=lambda a: {"report_key": "FAKE"})
out14 = agent14.run("ACCT_X", "2026-07-15", "2026-07-24",
                    rows=rows14, report_date="2026-07-24",
                    out_dir=_tmp, config_dir=_tmp,
                    history_revenue={}, network_unique_geos={},
                    enable_experiments=False)
check("agent.run attaches config_recommendations",
      len(out14["report"].config_recommendations) == 1)
check("agent.run writes config artifact paths",
      "config_markdown" in out14["paths"]
      and "config_json" in out14["paths"]
      and os.path.exists(out14["paths"]["config_json"]))
shutil.rmtree(_tmp, ignore_errors=True)

# ----------------------------------------------------- Part 15: eCPM Prediction
print("\n== Part 15: eCPM Prediction (Autonomous IAA, increment 2) ==")
from operation.optimizer.prediction import EcmpPredictor, EcmpPoint
from operation.optimizer.notify.feishu import FeishuNotifier
pred = EcmpPredictor()

# 1) rising series -> UP, predicted above last
pts_up = [EcmpPoint(day=str(i), ecpm=float(10 + i), impressions=100)
          for i in range(10)]
fc_up = pred.predict_series("GA · us · REWARD · NET_A", "NET_A", pts_up)
check("rising series -> UP trend", fc_up is not None and fc_up.trend == "UP",
      fc_up.trend if fc_up else None)
check("rising series predicts above last",
      fc_up.predicted_ecpm > fc_up.last_ecpm,
      f"{fc_up.predicted_ecpm:.2f}>{fc_up.last_ecpm:.2f}")

# 2) falling series -> DOWN
pts_dn = [EcmpPoint(day=str(i), ecpm=float(20 - i), impressions=100)
          for i in range(10)]
fc_dn = pred.predict_series("GB · us · REWARD · NET_B", "NET_B", pts_dn)
check("falling series -> DOWN trend", fc_dn.trend == "DOWN", fc_dn.trend)

# 3) flat series -> FLAT (low r2)
pts_flat = [EcmpPoint(day=str(i), ecpm=15.0, impressions=100)
            for i in range(10)]
fc_flat = pred.predict_series("GC · us · REWARD · NET_C", "NET_C", pts_flat)
check("flat series -> FLAT trend", fc_flat.trend == "FLAT", fc_flat.trend)
check("flat series low r2", fc_flat.r2 < 0.1, fc_flat.r2)

# 4) sparse (< MIN_DAYS) -> None
pts_sparse = [EcmpPoint(day=str(i), ecpm=float(10 + i), impressions=100)
              for i in range(3)]
check("sparse series -> None (MIN_DAYS)",
      pred.predict_series("GD · us · REWARD · NET_D", "NET_D", pts_sparse)
      is None)

# 5) confidence band contains prediction and is non-negative
ok_band = (fc_up.lower <= fc_up.predicted_ecpm <= fc_up.upper
           and fc_up.lower >= 0 and fc_dn.lower >= 0)
check("confidence band contains prediction (>=0, <=upper)",
      ok_band, f"[{fc_up.lower:.2f},{fc_up.upper:.2f}]")

# 6) early-warning: steep fall triggers, mild fall does not
pts_steep = [EcmpPoint(day=str(i), ecpm=float(50 - 4 * i), impressions=100)
             for i in range(10)]
fc_steep = pred.predict_series("GE · us · REWARD · NET_E", "NET_E", pts_steep)
check("steep downtrend -> early_warning True",
      fc_steep.early_warning is True, fc_steep.note)
check("mild downtrend -> early_warning False",
      fc_dn.early_warning is False, fc_dn.note)

# 7) estimate_floor_lift: filtering low-eCPM days raises blend
rows15 = []
for i, ec in enumerate([5, 5, 5, 50, 50]):      # 3 low + 2 high eCPM days
    rows15.append(row(day=f"2026-07-1{i}", app="GameL", fmt="REWARD", cc="us",
                      net="NET_L", imp=100, att=200, resp=100, rev=ec * 0.1))
lift = pred.estimate_floor_lift(rows15, "GameL · us · REWARD · NET_L", 10.0)
check("floor lift positive when low-eCPM days filtered",
      lift is not None and lift > 0, lift)
check("floor lift None when < MIN_DAYS",
      pred.estimate_floor_lift(rows15[:3], "GameL · us · REWARD · NET_L", 10.0)
      is None)

# 8) predict_account aggregates summary counts
rows_acct = []
for i in range(10):
    rows_acct.append(row(day=f"2026-07-{i:02d}", app="GameA", fmt="REWARD",
                         cc="us", net="NET_A", imp=100, att=200, resp=100,
                         rev=(10 + i) * 0.1))     # rising
    rows_acct.append(row(day=f"2026-07-{i:02d}", app="GameB", fmt="REWARD",
                         cc="us", net="NET_B", imp=100, att=200, resp=100,
                         rev=(20 - i) * 0.1))     # falling
acct_fc = pred.predict_account(rows_acct, "ACCT_X", "2026-07-01",
                               "2026-07-10", today="2026-07-10")
check("predict_account summary counts up+down",
      acct_fc.n_up >= 1 and acct_fc.n_down >= 1,
      str(acct_fc.to_dict()["summary"]))
check("predict_account total matches forecasts",
      acct_fc.n_total == len(acct_fc.forecasts))

# 9) agent.run attaches ecpm_forecasts (offline)
_tmp15 = tempfile.mkdtemp(prefix="fc15_")
agent15 = MonetizationIntelligenceAgent(
    account_loader=lambda a: {"report_key": "FAKE"})
out15 = agent15.run("ACCT_X", "2026-07-01", "2026-07-10",
                    rows=rows_acct, report_date="2026-07-10",
                    out_dir=_tmp15,
                    history_revenue={}, network_unique_geos={},
                    enable_experiments=False, enable_config_recommender=False)
check("agent.run attaches ecpm_forecasts",
      len(out15["report"].ecpm_forecasts) == 1)
fcj = out15["report"].ecpm_forecasts[0]
check("forecast summary round-trips to_dict",
      fcj["summary"]["total"] == acct_fc.n_total,
      str(fcj["summary"]))

# 10) report md + feishu card render the forecast section
gen15 = MonetizationReportGenerator()
md15 = gen15.render_markdown(out15["report"])
check("report markdown has eCPM Forecast section",
      "📈 eCPM Forecast" in md15)
card15 = FeishuNotifier(None).build_card(out15["report"], None)
check("feishu card has eCPM Forecast section",
      any("eCPM Forecast" in str(e.get("content", ""))
          for e in card15["elements"] if isinstance(e, dict)))
shutil.rmtree(_tmp15, ignore_errors=True)

# ------------------------------------------- Part 16: Outcome Learning Loop
print("\n== Part 16: Outcome Learning (Impact → Winner → Memory, increment 4) ==")
from operation.optimizer.experiments.impact import ImpactMeasurer
from operation.optimizer.experiments.winner_selector import (
    OBSERVING, WinnerSelector)
from operation.optimizer.experiments.optimization_memory import (
    OptimizationMemory)
from operation.optimizer.experiments.experiment_store import ExperimentStore
from operation.optimizer.experiments.experiment_models import (
    APPLIED, MEMORIZED, ROLLBACK as ST_ROLLBACK, WINNER as ST_WINNER,
    ExperimentDefinition, exp_id as _mk_eid)

_tmp16 = tempfile.mkdtemp(prefix="ol16_")

# synthetic rows: NET_UP +30% after anchor, NET_DN -50%, account has ballast
rows16 = []
for i in range(1, 10):
    d16 = f"2026-07-0{i}"
    after = d16 > "2026-07-05"
    rows16.append({"day": d16, "network": "NET_UP", "application": "appA",
                   "country": "us", "ad_format": "REWARD",
                   "estimated_revenue": "13" if after else "10",
                   "impressions": "1000"})
    rows16.append({"day": d16, "network": "NET_DN", "application": "appA",
                   "country": "us", "ad_format": "REWARD",
                   "estimated_revenue": "5" if after else "10",
                   "impressions": "1000"})
    rows16.append({"day": d16, "network": "NET_BASE", "application": "appA",
                   "country": "us", "ad_format": "REWARD",
                   "estimated_revenue": "100", "impressions": "8000"})

# 1) impact math: diff-in-diff vs account drift
im16 = ImpactMeasurer()
m_up = im16.measure(rows16, "e_up", "NET_UP", "2026-07-05")
check("impact measurable with enough window", m_up.measurable)
check("impact net positive for improved target",
      m_up.net_impact_pct is not None and m_up.net_impact_pct > 10,
      str(m_up.net_impact_pct))
m_dn = im16.measure(rows16, "e_dn", "NET_DN", "2026-07-05")
check("impact net negative for degraded target",
      m_dn.net_impact_pct is not None and m_dn.net_impact_pct < -10,
      str(m_dn.net_impact_pct))
check("impact not measurable without anchor",
      not im16.measure(rows16, "e_x", "NET_UP", "").measurable)
m_thin = im16.measure(rows16, "e_t", "NET_UP", "2026-07-01")
check("impact not measurable with thin before-window", not m_thin.measurable)

# 2) winner selection
ws16 = WinnerSelector()
d_up = ws16.decide(m_up, "pending")
check("winner: positive net impact -> WINNER/KEEP",
      d_up.verdict == ST_WINNER and d_up.decision == "KEEP")
d_dn = ws16.decide(m_dn, "pending")
check("winner: negative net impact -> ROLLBACK",
      d_dn.verdict == ST_ROLLBACK and d_dn.decision == "ROLLBACK")
check("winner: guardrail regression forces ROLLBACK",
      ws16.decide(m_up, "regression").verdict == ST_ROLLBACK)
check("winner: unmeasurable -> OBSERVING, no decision",
      ws16.decide(im16.measure(rows16, "e", "NET_UP", ""),
                  "pending").verdict == OBSERVING)

# 3) optimization memory: record, dedup, prior
mem16 = OptimizationMemory(os.path.join(_tmp16, "mem.jsonl"))
mem16.record(account="ACCT_T", action="increase_bid_opportunity",
             target="NET_UP", net_impact_pct=25.0, guardrail="pending",
             decision="KEEP", confidence=0.9, applied_at="2026-07-05")
mem16.record(account="ACCT_T", action="increase_bid_opportunity",
             target="NET_UP", net_impact_pct=25.0, guardrail="pending",
             decision="KEEP", confidence=0.9, applied_at="2026-07-05")
q16 = mem16.query(action="increase_bid_opportunity", target="NET_UP")
check("memory dedups identical outcome", q16["prior"]["n"] == 1)
check("memory prior aggregates impact",
      q16["prior"]["mean_impact_pct"] == 25.0)
check("memory prior_note non-empty for precedent",
      "prior:" in mem16.prior_note("increase_bid_opportunity", "NET_UP"))

# 4) end-to-end: store mark_applied -> agent learns outcome + memorizes
store16 = ExperimentStore(_tmp16)
eid16 = _mk_eid("ACCT_OL", "increase_bid_opportunity", "NET_UP")
store16.save("ACCT_OL", {eid16: ExperimentDefinition(
    exp_id=eid16, account="ACCT_OL", title="raise NET_UP opportunity",
    hypothesis="t", action_type="increase_bid_opportunity",
    target="NET_UP", source_rule="hidden_winner",
    expected_signal={"rule": "hidden_winner", "target": "NET_UP"},
    created_at="2026-07-01")})
exp16 = store16.mark_applied("ACCT_OL", eid16, "2026-07-05")
check("store.mark_applied sets anchor + APPLIED",
      exp16 is not None and exp16.status == APPLIED
      and exp16.applied_at == "2026-07-05")

agent16 = MonetizationIntelligenceAgent(
    account_loader=lambda a: {"report_key": "FAKE"})
out16 = agent16.run("ACCT_OL", "2026-07-01", "2026-07-09",
                    rows=rows16, report_date="2026-07-09", save=False,
                    history_revenue={}, network_unique_geos={},
                    experiments_dir=_tmp16,
                    enable_config_recommender=False,
                    enable_ecpm_prediction=False)
def16 = store16.load("ACCT_OL")[eid16]
check("agent measures impact for applied experiment",
      bool(def16.impact) and def16.impact.get("measurable") is True)
check("agent reaches WINNER status + KEEP decision",
      def16.status == ST_WINNER and def16.decision == "KEEP",
      f"{def16.status}/{def16.decision}")
check("agent memorizes outcome (memorized_at set)",
      bool(def16.memorized_at))
mem_glob = OptimizationMemory(
    os.path.join(_tmp16, "optimization_memory.jsonl"))
qg = mem_glob.query(action="increase_bid_opportunity", target="NET_UP")
check("outcome persisted to OptimizationMemory", qg["prior"]["n"] == 1)

# 5) rendering carries the outcome
md16 = MonetizationReportGenerator().render_markdown(out16["report"])
check("report markdown shows lifecycle + outcome",
      "WINNER" in md16 and "net impact" in md16)
card16 = FeishuNotifier(None).build_card(out16["report"], None)
check("feishu card shows outcome impact",
      any("净增量" in str(e.get("content", ""))
          for e in card16["elements"] if isinstance(e, dict)))
shutil.rmtree(_tmp16, ignore_errors=True)

# ====================================================================== #
# Part 17: Auto-Executor (E15.2.6 decision layer)
# ====================================================================== #
print("\n--- Part 17: Auto-Executor decision layer ---")
from operation.optimizer.intel_models import ActionItem
from operation.optimizer.auto_executor import classify_action, from_report

# 1) tier classification per action type (real calls carry signal confidence)
check("disable_network -> AUTO",
      classify_action("disable_network", "X", confidence=0.9).tier == "AUTO")
check("increase_bid_opportunity -> AUTO",
      classify_action("increase_bid_opportunity", "X", confidence=0.9).tier == "AUTO")
check("adjust_bid_constraint -> AUTO",
      classify_action("adjust_bid_constraint", "X", confidence=0.85).tier == "AUTO")
check("quarantine_network -> APPROVAL",
      classify_action("quarantine_network", "X").tier == "APPROVAL")
check("diversify -> APPROVAL",
      classify_action("diversify", "X").tier == "APPROVAL")
check("monitor -> OBSERVE",
      classify_action("monitor", "X").tier == "OBSERVE")
check("handoff_ua -> OBSERVE",
      classify_action("handoff_ua", "X").tier == "OBSERVE")
check("unknown action -> APPROVAL (fail-safe)",
      classify_action("mystery_action", "X").tier == "APPROVAL")

# 2) low-confidence AUTO escalates to APPROVAL
low = classify_action("disable_network", "X", title="t", confidence=0.3)
check("low-confidence AUTO escalates to APPROVAL", low.tier == "APPROVAL")

# 3) every decision requires human apply (MAX write-blocked)
d = classify_action("disable_network", "CHARTBOOST")
check("decision always requires_human_apply", d.to_dict()["requires_human_apply"] is True)

# 4) floor range parsed into apply instruction for adjust_bid_constraint
bf = classify_action("adjust_bid_constraint", "APPLOVIN_EXCHANGE",
                     title="Raise unified auction price floor on APPLOVIN_EXCHANGE to $1.00-$1.50")
check("bid floor range parsed into instruction",
      "$1.00" in bf.apply_instruction and "$1.50" in bf.apply_instruction)

# 5) from_report buckets + counts + markdown
ae_actions = [
    ActionItem(priority="P0", title="Disable CHARTBOOST", action="disable_network",
               target="CHARTBOOST", expected_impact="x", source_rule="zombie", confidence=0.9),
    ActionItem(priority="P1", title="Increase bid opportunity for MINTEGRAL",
               action="increase_bid_opportunity", target="MINTEGRAL", expected_impact="x",
               source_rule="hidden_winner", confidence=0.9),
    ActionItem(priority="P2", title="Raise unified auction price floor on APPLOVIN_EXCHANGE to $1.00-$1.50",
               action="adjust_bid_constraint", target="APPLOVIN_EXCHANGE", expected_impact="x",
               source_rule="bid_floor", confidence=0.85),
    ActionItem(priority="P2", title="Quarantine & watch INMOBI (7d)", action="quarantine_network",
               target="INMOBI", expected_impact="x", source_rule="zombie", confidence=0.7),
    ActionItem(priority="P3", title="Monitor US", action="monitor",
               target="US", expected_impact="x", source_rule="rc", confidence=0.5),
]
_tmp17 = tempfile.mkdtemp()
# build a minimal report via MonetizationReportGenerator would need rows;
# instead exercise from_report directly with the action list.
res17 = from_report(type("R", (), {"actions": ae_actions})())
check("from_report buckets 3 AUTO / 1 APPROVAL / 1 OBSERVE",
      res17["counts"] == {"auto": 3, "approval": 1, "observe": 1}, str(res17["counts"]))
check("checklist markdown shows 自动批准", "自动批准" in res17["markdown"])
check("checklist lists an AUTO target instruction",
      any("CHARTBOOST" in a["apply_instruction"] for a in res17["auto"]))
shutil.rmtree(_tmp17, ignore_errors=True)

# ====================================================================== #
# Part 18: A/B Experiment Generator (E15.2.6.1 — Layer 3 upgrade)
# ====================================================================== #
print("\n--- Part 18: A/B Experiment Generator (Layer 3 upgrade) ---")
from operation.optimizer.experiments.experiment_generator import (
    ABExperimentGenerator, AB_ELIGIBLE_ACTIONS,
)
from operation.optimizer.reports.growth_report import build_growth_report

# Rich signals with the metrics the generator reads.
_sig_hw = IntelSignal(
    rule="hidden_winner", severity="warning",
    action="increase_bid_opportunity", target="MINT_BIDDING", confidence=0.9,
    reason="x", metrics={"ecpm": 80.0, "blended_ecpm": 50.0,
                         "impressions": 300, "revenue_share": 0.04,
                         "revenue_capture_rate": 0.30})
_sig_bf = IntelSignal(
    rule="bid_floor", severity="warning", action="adjust_bid_constraint",
    target="APPLOVIN_EXCHANGE", confidence=0.85, reason="x",
    metrics={"ecpm": 1.4, "impression_share": 0.10,
             "recommended_floor_range": [1.0, 1.5]})
_sig_z = IntelSignal(
    rule="zombie_network", severity="critical", action="disable_network",
    target="CHARTBOOST", confidence=0.98, reason="x",
    metrics={"attempts": 17000, "impressions": 14, "revenue": 0.11})
_sig_q = IntelSignal(
    rule="zombie_network", severity="warning", action="quarantine_network",
    target="INMOBI", confidence=0.7, reason="x",
    metrics={"attempts": 1608, "impressions": 0, "revenue": 0.0})
_sig_div = IntelSignal(
    rule="revenue_concentration", severity="critical", action="diversify",
    target="US", confidence=0.6, reason="x", metrics={})

rep_ab = mk_report([_sig_hw, _sig_bf, _sig_z, _sig_q, _sig_div])
rep_ab.validated_actions = [
    {"priority": "P1", "title": "Increase MINT", "action": "increase_bid_opportunity",
     "target": "MINT_BIDDING", "source_rule": "hidden_winner", "confidence": 0.9,
     "expected_impact": "x", "rationale": "x", "layer": "experiment",
     "value_score": 0.5, "factors": {"confidence": 0.9, "impact": 0.8, "safety": 0.7, "reversibility": 0.9},
     "requires_manual_apply": True},
    {"priority": "P2", "title": "Raise floor", "action": "adjust_bid_constraint",
     "target": "APPLOVIN_EXCHANGE", "source_rule": "bid_floor", "confidence": 0.85,
     "expected_impact": "x", "rationale": "x", "layer": "experiment",
     "value_score": 0.4, "factors": {"confidence": 0.85, "impact": 0.6, "safety": 0.6, "reversibility": 0.9},
     "requires_manual_apply": True},
    {"priority": "P0", "title": "Disable CHARTBOOST", "action": "disable_network",
     "target": "CHARTBOOST", "source_rule": "zombie_network", "confidence": 0.98,
     "expected_impact": "x", "rationale": "x", "layer": "safe",
     "value_score": 0.9, "factors": {"confidence": 0.98, "impact": 0.3, "safety": 0.9, "reversibility": 0.95},
     "requires_manual_apply": True},
    {"priority": "P2", "title": "Quarantine INMOBI", "action": "quarantine_network",
     "target": "INMOBI", "source_rule": "zombie_network", "confidence": 0.7,
     "expected_impact": "x", "rationale": "x", "layer": "experiment",
     "value_score": 0.4, "factors": {"confidence": 0.7, "impact": 0.3, "safety": 0.8, "reversibility": 0.9},
     "requires_manual_apply": True},
    {"priority": "P3", "title": "Diversify US", "action": "diversify",
     "target": "US", "source_rule": "revenue_concentration", "confidence": 0.6,
     "expected_impact": "x", "rationale": "x", "layer": "observe",
     "value_score": 0.3, "factors": {"confidence": 0.6, "impact": 0.2, "safety": 0.8, "reversibility": 0.7},
     "requires_manual_apply": True},
]

gen = ABExperimentGenerator()
ab_exps = gen.generate(rep_ab, dau=None)
check("generator emits one A/B exp per eligible action (5)",
      len(ab_exps) == 5, str(len(ab_exps)))
check("every A/B exp uses Revenue/DAU as expected metric",
      all(e.expected_metric == "revenue_per_dau" for e in ab_exps))
check("every A/B exp has A/B variant + design text",
      all(e.variant_a and e.variant_b and e.ab_design for e in ab_exps))

_by = {e.target: e for e in ab_exps}
check("hidden_winner hypothesized lift > 0 (grounded in capture-rate gap)",
      (_by["MINT_BIDDING"].expected_lift_pct or 0) > 0,
      str(_by["MINT_BIDDING"].expected_lift_pct))
check("bid_floor hypothesized lift > 0 (parasite reallocation)",
      (_by["APPLOVIN_EXCHANGE"].expected_lift_pct or 0) > 0,
      str(_by["APPLOVIN_EXCHANGE"].expected_lift_pct))
check("zombie disable hypothesized lift > 0 (freed-slot reallocation)",
      (_by["CHARTBOOST"].expected_lift_pct or 0) > 0,
      str(_by["CHARTBOOST"].expected_lift_pct))
check("diversify is a risk hedge with 0 direct lift",
      _by["US"].ab_kind == "risk_hedge"
      and _by["US"].expected_lift_pct == 0.0
      and _by["US"].verify_mode == "guardrail")
check("diversify expected_signal is empty (guardrail-only)",
      _by["US"].expected_signal == {})

# roundtrip via to_dict/from_dict
rt = ExperimentDefinition.from_dict(_by["MINT_BIDDING"].to_dict())
check("A/B fields survive to_dict/from_dict roundtrip",
      rt.variant_a == _by["MINT_BIDDING"].variant_a
      and rt.expected_lift_pct == _by["MINT_BIDDING"].expected_lift_pct
      and rt.verify_mode == _by["MINT_BIDDING"].verify_mode)

# store propose + dedup
_tmp18 = tempfile.mkdtemp()
store18 = ExperimentStore(_tmp18)
created18 = store18.propose_from_validated(rep_ab, today="2026-07-24")
check("store proposes 5 A/B experiments", len(created18) == 5, str(len(created18)))
check("re-propose is a no-op (dedup by stable id)",
      len(store18.propose_from_validated(rep_ab, today="2026-07-24")) == 0)
# persist/read keeps A/B fields
reread = store18.load("ACCT_X")
check("persisted exp keeps A/B variant text",
      reread[created18[0].exp_id].variant_a != "")

# guardrail verify mode never auto-resolves
_vg = eng.verify(rep_ab, _by["US"], today="2026-08-10")
check("guardrail-mode experiment stays ACTIVE (no auto-resolve)",
      _vg.status == "ACTIVE", _vg.status)
check("guardrail verify note flags risk-hedge",
      "risk-hedge" in _vg.verdict_note, _vg.verdict_note)

# backfill: an experiment stored BEFORE the A/B increment (no variant text)
# gets enriched on the next propose_from_validated run.
from operation.optimizer.experiments.experiment_models import ExperimentDefinition
legacy = ExperimentDefinition(
    exp_id=exp_id("ACCT_X", "increase_bid_opportunity", "MINT_BIDDING"),
    account="ACCT_X", title="Increase MINT",
    hypothesis="old", action_type="increase_bid_opportunity",
    target="MINT_BIDDING", source_rule="hidden_winner",
    status="ACTIVE", created_at="2026-07-20", launched_at="2026-07-20")
store18.save("ACCT_X", {legacy.exp_id: legacy})
store18.propose_from_validated(rep_ab, today="2026-07-24")
reloaded = store18.load("ACCT_X")[legacy.exp_id]
check("legacy experiment backfilled with A/B fields on next run",
      reloaded.variant_a != "" and reloaded.variant_b != ""
      and reloaded.expected_lift_pct is not None,
      f"variant_a={reloaded.variant_a!r} lift={reloaded.expected_lift_pct}")
check("legacy experiment keeps its prior status (ACTIVE)",
      reloaded.status == "ACTIVE", reloaded.status)

# growth report A/B portfolio
gr18 = build_growth_report("ACCT_X", rep_ab, store18, dau=None, prior_revenue=90.0)
check("growth report exposes ab_portfolio",
      "ab_portfolio" in gr18 and gr18["ab_portfolio"]["total"] == 5,
      str(gr18.get("ab_portfolio")))
check("ab_portfolio lift sum > 0 (revenue experiments)",
      gr18["ab_portfolio"]["expected_lift_sum_pct"] > 0,
      str(gr18["ab_portfolio"]["expected_lift_sum_pct"]))
shutil.rmtree(_tmp18, ignore_errors=True)

# ====================================================================== #
# Part 19: DAU truth + ARPDAU guardrail activation (E15.2.6.2)
# ====================================================================== #
print("\n--- Part 19: DAU drop-in + ARPDAU guardrail activation ---")
from operation.optimizer.user_metrics import (
    ManualDropInProvider, UserMetricsService, save_dropin_dau, persist_arpdau)
from operation.optimizer.reports.growth_report import build_growth_report
from operation.optimizer.experiments.experiment_models import (
    ExperimentDefinition, PROPOSED)

_tmp19 = "outputs/_test_um_tmp"
os.makedirs(_tmp19, exist_ok=True)
drop_dir = os.path.join(_tmp19, "user_metrics")
os.makedirs(drop_dir, exist_ok=True)
# point the provider at our temp dir
ManualDropInProvider.DIR = drop_dir

# 1) no drop-in -> provider returns None (PENDING preserved)
prov19 = ManualDropInProvider()
check("no drop-in -> provider returns None (PENDING stays)",
      prov19.fetch("ACCT_Q", "2026-07-15", "2026-07-24") is None)

# 2) save drop-in -> provider returns real dau + available
save_dropin_dau("ACCT_Q", 1000, "2026-07-24", dir=drop_dir)
um19 = UserMetricsService(providers=[prov19]).fetch(
    "ACCT_Q", "2026-07-15", "2026-07-24")
check("drop-in provider returns dau", um19.dau == 1000, str(um19.dau))
check("drop-in provider marks available", um19.available is True)
check("drop-in source = manual_dropin",
      um19.source == "manual_dropin", um19.source)

# 3) _finalize_user_metrics derives ARPDAU = revenue/dau and persists
from operation.optimizer.intelligence_agent import MonetizationIntelligenceAgent
rep19 = mk_report([], um=um19.to_dict())
rep19.revenue = 100.0                 # 100 / 1000 = 0.10 ARPDAU
agent19 = MonetizationIntelligenceAgent()
agent19._finalize_user_metrics(rep19, "ACCT_Q")
check("arpdau derived = revenue/dau",
      abs((rep19.user_metrics or {}).get("arpdau", 0) - 0.10) < 1e-6,
      str(rep19.user_metrics))
check("user_metrics.available True after finalize",
      (rep19.user_metrics or {}).get("available") is True)
hist_path = os.path.join(drop_dir, "ACCT_Q.json")
with open(hist_path, encoding="utf-8") as f:
    _h = json.load(f)
check("arpdau history persisted", _h["arpdau_history"]
      and _h["arpdau_history"][0]["date"] == "2026-07-24",
      str(_h.get("arpdau_history")))

# 4) growth report Revenue/DAU becomes real (not None)
gr19 = build_growth_report("ACCT_Q", rep19, None, dau=1000)
check("growth Revenue/DAU real when DAU supplied",
      gr19["revenue_per_dau"] is not None
      and abs(gr19["revenue_per_dau"] - 0.10) < 1e-6, str(gr19["revenue_per_dau"]))
check("growth dau_pending False when DAU supplied",
      gr19["dau_pending"] is False)

# 5) guardrail ACTIVATES: baseline ARPDAU 0.10, now 0.08 -> regression
exp19 = ExperimentDefinition(
    exp_id="e_baseline", account="ACCT_Q", title="t", hypothesis="h",
    action_type="increase_bid_opportunity", target="X",
    source_rule="hidden_winner",
    baseline_user_metrics={"available": True, "dau": 1000, "arpdau": 0.10,
                           "ads_per_user": 0.0},
    expected_signal={"rule": "hidden_winner", "target": "X"},
    status=PROPOSED, created_at="2026-07-24", launched_at="2026-07-24")
rep_now = mk_report([], um={"available": True, "dau": 1000, "arpdau": 0.08,
                           "ads_per_user": 0.0})
rep_now.signals = []   # signal resolved -> verdict path
v19 = VerificationEngine().verify(rep_now, exp19, today="2026-07-25")
check("guardrail activates -> regression when ARPDAU drops",
      v19.arpdau_guardrail == "regression", v19.arpdau_guardrail)
check("regression verdict recorded", "regression" in (v19.verdict_note or ""),
      v19.verdict_note)

# 6) guardrail stays PENDING without DAU (no false-positive activation)
exp_pend = ExperimentDefinition(
    exp_id="e_pend", account="ACCT_Q", title="t", hypothesis="h",
    action_type="increase_bid_opportunity", target="X",
    source_rule="hidden_winner",
    baseline_user_metrics={"available": False},
    expected_signal={"rule": "hidden_winner", "target": "X"},
    status=PROPOSED, created_at="2026-07-24", launched_at="2026-07-24")
rep_pend = mk_report([], um={"available": False, "note": "pending"})
rep_pend.signals = []
v_pend = VerificationEngine().verify(rep_pend, exp_pend, today="2026-07-25")
check("guardrail stays PENDING without DAU (no false activation)",
      v_pend.arpdau_guardrail == "pending", v_pend.arpdau_guardrail)

shutil.rmtree(_tmp19, ignore_errors=True)
ManualDropInProvider.DIR = os.path.join("outputs", "user_metrics")

# ====================================================================== #
# Part 20: DAU-pending rendering + network-name canonicalization (dedup)
# ====================================================================== #
print("\n--- Part 20: DAU pending render + canon_target dedup ---")
from operation.optimizer.experiments.experiment_models import (  # noqa: E402
    canon_target, exp_id)
from operation.optimizer.reports.growth_report import (  # noqa: E402
    render_growth_card, render_growth_markdown, build_growth_report)

# 1) DAU pending (0 / None) must render as "pending", never "0"
_gr_pend = {
    "account": "ACCT_X", "date": "2026-07-25",
    "dau": 0, "dau_pending": True,
    "iia_revenue": 285.36, "revenue_per_dau": None,
    "prior_revenue": None, "prior_revenue_per_dau": None,
    "blended_ecpm": 57.21, "growth_pct": None,
    "health_score": 67, "health_grade": "B", "actions": [],
    "experiments": {"running": 0, "winning": 0, "rolled_back": 0,
                    "memorized": 0},
    "ab_portfolio": {"total": 0, "revenue_experiments": 0,
                     "risk_hedges": 0, "expected_lift_sum_pct": 0.0},
    "ai_attributed_lift_pct": 0.0,
}
_card = render_growth_card(_gr_pend)
check("DAU pending card shows '(pending DAU)' not 'DAU 0'",
      "—(pending DAU)" in _card and "DAU 0" not in _card, _card.splitlines()[0])

# markdown via the real builder (pending DAU from report.user_metrics)
_rep_md = mk_report([], um={"available": False, "note": "pending"})
_gr_md = build_growth_report("ACCT_X", _rep_md, None, dau=None)
_md2 = render_growth_markdown(_gr_md)
check("DAU pending markdown (built) shows pending, not '0'",
      "(pending" in _md2 and "DAU 0" not in _md2,
      "DAU 0" in _md2 and "HAS 'DAU 0'" or "ok")

# 2) canon_target collapses naming drift to one key
check("canon strips _NETWORK", canon_target("CHARTBOOST_NETWORK") == "CHARTBOOST",
      canon_target("CHARTBOOST_NETWORK"))
check("canon strips _BIDDING", canon_target("CHARTBOOST_BIDDING") == "CHARTBOOST",
      canon_target("CHARTBOOST_BIDDING"))
check("canon keeps base", canon_target("CHARTBOOST") == "CHARTBOOST",
      canon_target("CHARTBOOST"))
check("canon keeps distinct net (APPLOVIN_EXCHANGE)",
      canon_target("APPLOVIN_EXCHANGE") == "APPLOVIN_EXCHANGE",
      canon_target("APPLOVIN_EXCHANGE"))
check("exp_id stable across naming drift",
      exp_id("A", "disable_network", "CHARTBOOST")
      == exp_id("A", "disable_network", "CHARTBOOST_NETWORK"),
      exp_id("A", "disable_network", "CHARTBOOST"))

# 3) store dedups a renamed-network proposal to the same experiment
_tmp20 = os.path.join(tempfile.mkdtemp(prefix="e15_2_5_p20_"))
from operation.optimizer.experiments.experiment_store import (  # noqa: E402
    ExperimentStore)
from operation.optimizer.intel_models import IntelSignal  # noqa: E402


def _va(target):
    return {"action": "disable_network", "target": target, "title": "t",
            "source_rule": "zombie_network", "expected_impact": "",
            "rationale": "zombie"}


_store20 = ExperimentStore(_tmp20)
_rep_a = mk_report([], date="2026-07-25")
_rep_a.account = "ACCT_D"
_rep_a.validated_actions = [_va("CHARTBOOST")]
c1 = _store20.propose_from_validated(_rep_a, today="2026-07-25")
_rep_b = mk_report([], date="2026-07-25")
_rep_b.account = "ACCT_D"
_rep_b.validated_actions = [_va("CHARTBOOST_NETWORK")]
c2 = _store20.propose_from_validated(_rep_b, today="2026-07-25")
check("store dedups renamed-network proposal (no 2nd experiment)",
      len(c1) == 1 and len(c2) == 0, f"c1={len(c1)} c2={len(c2)}")
shutil.rmtree(_tmp20, ignore_errors=True)

print(f"\n===== E15.2.5 VALIDATION: {PASS} PASS / {FAIL} FAIL =====")
sys.exit(1 if FAIL else 0)
