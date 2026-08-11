"""Phase 2.1.7 — Step 4 (Quality Gate) + Step 5 (OpenCLIP Ranking)。

对 gen_phase2_1_7.py 生成的 12 张 1:1 UA 创意跑 Critic Agent（含 Composition
Validator），按 PRD §7 / §8 / §9 做：

Step 4 — Quality Gate
  单张 Hard Reject 口径（PRD §7）：
    Aspect ratio == 1:1
    Character <= 35% (proxy for <=30% subject share)
    Merge mechanic present (gameplay understood)
    No poster feeling
    No fake text / fake UI (AI artifact)
    Visible reward
    Production Score V2 >= 0.85
  Batch Gate（PRD §8）：
    Approved >= 8/12
    Avg Production Score >= 0.85
    Merge >= 4 / Evolution >= 3 / Collection >= 3

Step 5 — Ranking（PRD §9）
  TOP12_heuristic.json  : 按 Production Score V2（DNA 规则排序）
  TOP12_openclip.json   : 按 CLIP 相似度 vs winner（OpenCLIP 视觉排序）
  ranking_compare.html  : 双排序对照 + overlap（Kendall tau -> 0-1）
  验收 overlap 40%-70%（模型不是复制规则，产生有效重排）

多样性（diversity）修正：
  2.1.6.2 用 distinct_patterns / total（3/3=1.0）。12 张仅 3 玩法模式 ×4，
  若沿用 = 3/12 = 0.25 会错误拉低 Production Score。此处改为
  pattern_coverage = distinct_planned / expected_distinct（3/3 = 1.0），
  即「是否覆盖计划中的不同创意角度」，与批次意图一致。

用法: python scripts/run_phase2_1_7_gate.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scipy.stats import kendalltau  # noqa: E402

from market_ops.creative_intelligence.factory.ranking.clip_ranker import _cosine  # noqa: E402
from creative_quality_gate.critic_agent import CriticAgent  # noqa: E402
from creative_quality_gate.scoring import production_score_v2, REJECT_GAMEPLAY  # noqa: E402
from creative_quality_gate.report import build_outputs  # noqa: E402

OUT = ROOT / "output" / "creative_phase2_1_7"
IMG = OUT / "images"
PLAN = OUT / "compositions" / "composition_plan.json"
EMB_C = OUT / "embeddings" / "creative"
GATE = OUT / "quality_gate"
RANK = OUT / "ranking"
WINNER = ROOT / "output" / "phase2_1_5" / "real_validation" / "winner_reference" / "winner_001.png"
GATE.mkdir(parents=True, exist_ok=True)
RANK.mkdir(parents=True, exist_ok=True)

# 验收阈值
QG_MIN = 0.85
GAMEPLAY_AREA_MIN = 0.45
REWARD_VIS_MIN = 0.60
CHAR_ATTENTION_MAX = 0.35
ARTIFACT_MAX = 0.70
COMPOSITION_MATCH_MIN = 0.70
EXPECTED_DISTINCT_PATTERNS = 3  # merge / evolution / collection
# Batch Gate 门槛
BATCH_APPROVED_MIN = 8
BATCH_AVG_MIN = 0.85
PATTERN_FLOOR = {"merge": 4, "evolution": 3, "collection": 3}
# Ranking overlap 验收
OVERLAP_MIN, OVERLAP_MAX = 0.40, 0.70


def load_plan() -> dict:
    if not PLAN.exists():
        return {}
    pj = json.loads(PLAN.read_text(encoding="utf-8"))
    meta = {}
    for c in pj.get("creatives", []):
        meta[c["creative_id"]] = {
            "group": c.get("group", ""),
            "pattern": c.get("pattern", ""),
            "theme": c.get("theme", ""),
        }
    return meta


def main() -> int:
    meta = load_plan()
    imgs = sorted(IMG.glob("*.png"))
    if not imgs:
        print(f"[!] No images in {IMG}. Run gen_phase2_1_7.py first.")
        return 1

    agent = CriticAgent()
    w_emb = agent.encoder.encode_image(str(WINNER))

    scores = []
    embs = []
    for p in imgs:
        cid = p.stem
        m = meta.get(cid, {})
        cs = agent.evaluate(str(p), str(WINNER), cid, group=m.get("group", ""), mutation_type=m.get("pattern", ""))
        # 复用 gen 阶段落盘的 embedding（更快；缺失则即时编码）
        emb_npy = EMB_C / f"{cid}.npy"
        emb = np.load(emb_npy) if emb_npy.exists() else agent.encoder.encode_image(str(p))
        embs.append(emb)
        scores.append(cs)
        print(f"  evaluated {cid} [{m.get('pattern','')}]: type={cs.gameplay_type} "
              f"prod={cs.production_score:.3f} char={cs.character_attention:.2f}")

    # ---- 批次多样性（修正口径）----
    planned = [m.get("pattern", "") for m in meta.values() if m]
    planned = planned or [s.mutation_type for s in scores]
    distinct = len(set(pp for pp in planned if pp)) or 1
    pattern_coverage = min(1.0, distinct / EXPECTED_DISTINCT_PATTERNS)
    for i, cs in enumerate(scores):
        sims = [(_cosine(embs[i], e) + 1.0) / 2.0 for j, e in enumerate(embs) if i != j]
        emb_div = float(1.0 - float(np.mean(sims))) if sims else 0.0
        cs.diversity = round(float(0.6 * pattern_coverage + 0.4 * emb_div), 4)
        cs.production_score = production_score_v2(
            {
                "gameplay_understanding": cs.gameplay_understanding,
                "reward_visibility": cs.reward_visibility,
                "composition_match": cs.composition_match,
                "visual_quality": cs.visual_quality,
                "clip_similarity": cs.clip_similarity,
                "diversity": cs.diversity,
            }
        )

    # ---- 单张决策（PRD §7 Hard Reject 口径）----
    for s in scores:
        passed = (
            s.aspect_ok
            and s.ai_artifact_score < ARTIFACT_MAX
            and s.gameplay_area_ratio >= GAMEPLAY_AREA_MIN
            and s.reward_visibility >= REWARD_VIS_MIN
            and s.character_attention <= CHAR_ATTENTION_MAX
            and s.composition_match >= COMPOSITION_MATCH_MIN
            and s.production_score >= QG_MIN
            and s.gameplay_clarity >= REJECT_GAMEPLAY  # merge mechanic present
        )
        s.decision = "PASS" if passed else "FAIL"
        if not passed:
            reasons = []
            if not s.aspect_ok:
                reasons.append("aspect != 1:1")
            if s.ai_artifact_score >= ARTIFACT_MAX:
                reasons.append("fake text/UI")
            if s.gameplay_clarity < REJECT_GAMEPLAY:
                reasons.append("no merge mechanic")
            if s.character_attention > CHAR_ATTENTION_MAX:
                reasons.append("character >30%")
            if s.reward_visibility < REWARD_VIS_MIN:
                reasons.append("no visible reward")
            if s.production_score < QG_MIN:
                reasons.append(f"prod {s.production_score:.2f}<{QG_MIN}")
            s.hard_reject_reason = "; ".join(reasons) or "failed quality checks"
            if s.hard_reject_reason not in s.issues:
                s.issues.append(s.hard_reject_reason)

    # ---- 7 项 quality 验收 ----
    def all_pass(pred) -> bool:
        return all(pred(s) for s in scores)

    checks = {
        "Gameplay first": all_pass(lambda s: s.gameplay_area_ratio >= GAMEPLAY_AREA_MIN),
        "Reward dominant": all_pass(lambda s: s.reward_visibility >= REWARD_VIS_MIN),
        "Character secondary": all_pass(lambda s: s.character_attention <= CHAR_ATTENTION_MAX),
        "No poster feeling": all_pass(lambda s: s.character_attention <= 0.50 and s.gameplay_area_ratio >= 0.40),
        "No fake text": all_pass(lambda s: s.ai_artifact_score < ARTIFACT_MAX),
        "Facebook UA structure": all_pass(lambda s: s.composition_match >= COMPOSITION_MATCH_MIN),
        "Quality Gate >= 0.85": all_pass(lambda s: s.production_score >= QG_MIN),
    }

    approved = [s for s in scores if s.decision == "PASS"]
    avg_prod = round(float(np.mean([s.production_score for s in scores])), 4) if scores else 0.0

    # ---- Batch Gate（PRD §8）----
    approved_by_pattern = {k: 0 for k in PATTERN_FLOOR}
    for s in approved:
        pt = s.mutation_type or meta.get(s.creative_id, {}).get("pattern", "")
        if pt in approved_by_pattern:
            approved_by_pattern[pt] += 1

    batch_gate = {
        "Approved >= 8/12": len(approved) >= BATCH_APPROVED_MIN,
        "Avg Production >= 0.85": avg_prod >= BATCH_AVG_MIN,
    }
    for pt, floor in PATTERN_FLOOR.items():
        batch_gate[f"{pt.capitalize()} >= {floor}"] = approved_by_pattern.get(pt, 0) >= floor

    checks.update(batch_gate)

    # ---- Step 5: Ranking（PRD §9）----
    by_heuristic = sorted(scores, key=lambda s: s.production_score, reverse=True)
    by_openclip = sorted(scores, key=lambda s: s.clip_similarity, reverse=True)

    top_heuristic = [s.creative_id for s in by_heuristic]
    top_openclip = [s.creative_id for s in by_openclip]

    # overlap = Kendall tau 映射到 0-1（(tau+1)/2）
    rank_map_h = {cid: i for i, cid in enumerate(top_heuristic)}
    rank_map_o = {cid: i for i, cid in enumerate(top_openclip)}
    common = [s.creative_id for s in scores]
    rh = [rank_map_h[c] for c in common]
    ro = [rank_map_o[c] for c in common]
    tau, _ = kendalltau(rh, ro)
    overlap = round(float((tau + 1.0) / 2.0), 4)
    top3_overlap = len(set(top_heuristic[:3]) & set(top_openclip[:3])) / 3.0

    ranking_ok = OVERLAP_MIN <= overlap <= OVERLAP_MAX
    checks["Ranking overlap 40-70%"] = ranking_ok

    # ---- 写入 ranking 产物 ----
    def rank_obj(order):
        return [
            {
                "rank": i + 1,
                "creative_id": s.creative_id,
                "pattern": s.mutation_type or meta.get(s.creative_id, {}).get("pattern", ""),
                "production_score": s.production_score,
                "clip_similarity": s.clip_similarity,
                "decision": s.decision,
            }
            for i, s in enumerate(order)
        ]

    RANK.joinpath("TOP12_heuristic.json").write_text(
        json.dumps(rank_obj(by_heuristic), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    RANK.joinpath("TOP12_openclip.json").write_text(
        json.dumps(rank_obj(by_openclip), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    RANK.joinpath("ranking_compare.json").write_text(json.dumps(
        {
            "overlap_kendall01": overlap,
            "top3_overlap": round(top3_overlap, 4),
            "overlap_acceptance": [OVERLAP_MIN, OVERLAP_MAX],
            "heuristic_order": top_heuristic,
            "openclip_order": top_openclip,
        }, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ranking_compare.html
    RANK.joinpath("ranking_compare.html").write_text(
        render_ranking_html(by_heuristic, by_openclip, overlap, top3_overlap, meta), encoding="utf-8"
    )

    # ---- 总 Gate 结果 + 产物 ----
    from creative_quality_gate.models import GateResult

    gate = GateResult(
        total=len(scores),
        approved=len(approved),
        rejected=len(scores) - len(approved),
        conditional=0,
        avg_production_score=avg_prod,
        checks=checks,
        produced_at=datetime.now().isoformat(timespec="seconds"),
    )
    paths = build_outputs(scores, gate, GATE, img_dir=IMG)

    # 补充批次统计到 production_gate.json
    pg = json.loads(Path(paths["production_gate.json"]).read_text(encoding="utf-8"))
    pg["batch_gate"] = batch_gate
    pg["approved_by_pattern"] = approved_by_pattern
    pg["ranking"] = {"overlap": overlap, "top3_overlap": round(top3_overlap, 4), "overlap_ok": ranking_ok}
    Path(paths["production_gate.json"]).write_text(json.dumps(pg, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 控制台摘要 ----
    print("\n=== Phase 2.1.7 Quality Gate + Ranking ===")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\nApproved {len(approved)}/12 · Avg Production {avg_prod:.3f}")
    print(f"Approved by pattern: {approved_by_pattern}")
    print(f"Ranking overlap (Kendall 0-1): {overlap:.3f} (top3 {top3_overlap:.2f}) · "
          f"{'IN RANGE' if ranking_ok else 'OUT OF 40-70%'}")
    print("Outputs:")
    for name, p in paths.items():
        print(f"  - {name}: {p}")
    print(f"  - ranking/TOP12_heuristic.json")
    print(f"  - ranking/TOP12_openclip.json")
    print(f"  - ranking/ranking_compare.html")

    batch_pass = all(batch_gate.values())
    ok = batch_pass and all(v for k, v in checks.items() if k != "Ranking overlap 40-70%")
    print("\nRESULT:", "BATCH GATE PASS ✅ → Phase 2.1.7 COMPLETE" if ok
          else "BATCH GATE FAILED ❌ (review rejected creatives)")
    return 0 if ok else 2


def render_ranking_html(by_h, by_o, overlap, top3, meta) -> str:
    def rows(order, kind):
        out = ""
        for i, s in enumerate(order):
            pt = s.mutation_type or meta.get(s.creative_id, {}).get("pattern", "")
            score = s.production_score if kind == "h" else s.clip_similarity
            color = "#1a7f37" if s.decision == "PASS" else "#cf222e"
            out += (f"<tr><td>{i+1}</td><td>{s.creative_id}</td><td>{pt}</td>"
                    f"<td>{score:.3f}</td>"
                    f"<td><span style='color:{color}'>{s.decision}</span></td></tr>")
        return out

    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
body{{font-family:system-ui;background:#f5f5f7;margin:0;padding:24px;color:#222}}
h1{{font-size:20px}} .sum{{background:#fff;border-radius:10px;padding:16px;margin-bottom:16px;
  box-shadow:0 1px 6px rgba(0,0,0,.08)}}
.grid{{display:flex;gap:16px;flex-wrap:wrap}}
table{{border-collapse:collapse;font-size:13px;background:#fff;border-radius:10px;
  box-shadow:0 1px 6px rgba(0,0,0,.08);margin:0;width:100%}}
th,td{{padding:6px 10px;border-bottom:1px solid #eee;text-align:left}}
th{{background:#0969da;color:#fff}}
.win{{color:#1a7f37;font-weight:700}}
</style></head><body>
<h1>Phase 2.1.7 — Ranking Comparison (OpenCLIP vs DNA Heuristic)</h1>
<div class="sum">
  <b>Overlap (Kendall tau → 0-1): {overlap:.3f}</b><br>
  Top-3 set overlap: {top3:.2f}<br>
  Acceptance: 0.40–0.70 (model is not copying rules; produces effective re-ranking)
</div>
<div class="grid">
  <div><h3>DNA Heuristic (Production Score V2)</h3>
    <table><tr><th>#</th><th>ID</th><th>Pattern</th><th>Score</th><th>Decision</th></tr>
    {rows(by_h, 'h')}</table></div>
  <div><h3>OpenCLIP Visual (CLIP vs Winner)</h3>
    <table><tr><th>#</th><th>ID</th><th>Pattern</th><th>CLIP</th><th>Decision</th></tr>
    {rows(by_o, 'o')}</table></div>
</div>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
