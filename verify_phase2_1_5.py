"""Phase 2.1.5 — Real Creative Validation。

用真实广告图片验证 OpenCLIP 视觉排序 vs 纯 DNA heuristic。

流程：
  Load winner + 12 real creatives
    → OpenCLIP encode (512-d)
    → cosine similarity
    → dual ranking (openclip 视觉 / heuristic DNA)
    → similarity stats + group analysis
    → HTML report + release_gate.json

产物（output/phase2_1_5/）：
  embeddings/{winner,creative}/*.npy
  ranking_openclip.json / ranking_heuristic.json
  TOP5_openclip.json / TOP5_heuristic.json
  similarity_stats.json / validation_report.html / release_gate.json

用法：
  python verify_phase2_1_5.py                # 自动：有 torch+open_clip 走真实，否则回退
  python verify_phase2_1_5.py --mode openclip
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

VAL = ROOT / "output" / "phase2_1_5" / "real_validation"
OUT = ROOT / "output" / "phase2_1_5"
EMB = OUT / "embeddings"

WINNER_DNA = {"character": "witch", "reward": "baby dragon", "environment": "castle"}
_DIM_W = {"character": 3.0, "reward": 1.0, "environment": 1.0}


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, np.float32); b = np.asarray(b, np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na == 0 or nb == 0 else float(np.dot(a, b) / (na * nb))


def _dna_vec(dna: dict, vocab: dict) -> np.ndarray:
    vec = []
    for dim, terms in vocab.items():
        w = _DIM_W.get(dim, 1.0)
        val = str(dna.get(dim, "")).strip().lower()
        for t in terms:
            vec.append(w if t == val else 0.0)
    return np.array(vec, np.float32)


def _img_stats(path: Path) -> tuple[float, float]:
    """返回 (contrast_norm, mean_luma_norm)，真实图像测量。"""
    from PIL import Image
    img = Image.open(path).convert("L")
    arr = np.asarray(img, np.float32) / 255.0
    return float(arr.std()), float(arr.mean())


def _b64(path: Path, max_px: int = 300) -> str:
    from PIL import Image
    import io
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_px, max_px))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="auto", choices=["auto", "openclip", "heuristic"])
    args = ap.parse_args()

    ok = True
    def check(name, cond):
        nonlocal ok
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond: ok = False
        return cond

    # 依赖探测
    try:
        import torch, open_clip  # noqa: F401
        real_ok = True
    except Exception as e:
        real_ok = False
        print(f"== real CLIP deps MISSING ({type(e).__name__}) ==")
    mode = "openclip" if (args.mode in ("auto", "openclip") and real_ok) else "heuristic"
    print(f"== Phase 2.1.5 Real Validation | mode={mode} ==\n")

    # 1) 加载真实图片
    print("== Load real images ==")
    meta = json.loads((VAL / "metadata.json").read_text(encoding="utf-8"))
    winner_path = VAL / "winner_reference" / "winner_001.png"
    creatives = meta["creatives"]
    check("winner image exists", winner_path.exists())
    check(f"winner is real (>{20}KB)", winner_path.exists() and winner_path.stat().st_size > 20000)
    files_ok = all((Path(c["file"]).exists() and Path(c["file"]).stat().st_size > 20000) for c in creatives)
    check(f"12 real creatives loaded (got {len(creatives)})", len(creatives) == 12 and files_ok)

    # 2) OpenCLIP 编码
    print("\n== OpenCLIP encode ==")
    EMB.mkdir(parents=True, exist_ok=True)
    (EMB / "winner").mkdir(exist_ok=True); (EMB / "creative").mkdir(exist_ok=True)

    encoder = None
    if mode == "openclip":
        from market_ops.creative_intelligence.factory.ranking.clip_ranker import OpenCLIPEncoder
        encoder = OpenCLIPEncoder(device="cpu")

    def encode(path: Path) -> np.ndarray:
        if encoder is not None:
            return encoder.encode_image(path)
        # heuristic 回退：像素向量
        from PIL import Image
        a = np.asarray(Image.open(path).convert("RGB").resize((32, 32)), np.float32).flatten()
        return (a - a.mean()) / (a.std() + 1e-6)

    wvec = encode(winner_path)
    np.save(EMB / "winner" / "winner_001.npy", wvec.astype(np.float32))
    cvecs = {}
    for c in creatives:
        v = encode(Path(c["file"]))
        np.save(EMB / "creative" / f"{c['creative_id']}.npy", v.astype(np.float32))
        cvecs[c["creative_id"]] = v
    check("winner embedding generated", (EMB / "winner" / "winner_001.npy").exists())
    n_emb = len(list((EMB / "creative").glob("*.npy")))
    check(f"12 creative embeddings (got {n_emb})", n_emb == 12)
    shape_ok = wvec.shape == (512,) if mode == "openclip" else True
    print(f"  winner shape={wvec.shape} | mode={mode}")
    if mode == "openclip":
        check("embedding shape == (512,)", shape_ok)

    # 3) 视觉相似度
    print("\n== Similarity distribution ==")
    sims = {cid: _cosine(wvec, v) for cid, v in cvecs.items()}
    svals = np.array(list(sims.values()))
    std = float(svals.std()); rng = float(svals.max() - svals.min())
    stats = {"min": float(svals.min()), "max": float(svals.max()),
             "mean": float(svals.mean()), "std": std, "range": rng}
    print(f"  {stats}")
    check(f"std > 0.03 (got {std:.4f})", std > 0.03)
    check(f"max-min > 0.08 (got {rng:.4f})", rng > 0.08)

    # heuristic DNA 相似度
    dims = {"character": set(), "reward": set(), "environment": set()}
    for c in creatives:
        for d in dims:
            dims[d].add(str(c["dna"].get(d, "")).strip().lower())
    for d in dims:
        dims[d].add(str(WINNER_DNA[d]).lower())
    vocab = {d: sorted(v) for d, v in dims.items()}
    wdna = _dna_vec(WINNER_DNA, vocab)
    dna_sims = {c["creative_id"]: _cosine(wdna, _dna_vec(c["dna"], vocab)) for c in creatives}

    # visual quality（对比度真实测量）+ gameplay clarity（CLIP 文图相似度）
    # 这是从"视觉检索"升级到"广告智能系统"的关键补层：
    # 一个漂亮但无 merge mechanic 的图，不应因 CLIP 像 winner 就排名高。
    contrasts = {}
    for c in creatives:
        con, _ = _img_stats(Path(c["file"]))
        contrasts[c["creative_id"]] = con
    cmax = max(contrasts.values()) or 1.0
    contrast_norm = {k: v / cmax for k, v in contrasts.items()}

    GAMEPLAY_PROMPT = ("mobile game advertisement showing a visible merge board, "
                       "two identical items combining into a higher-level reward, "
                       "clear before and after progression, gameplay mechanic visible")
    QUALITY_PROMPT = ("high-end premium 3D mobile game advertisement, polished colorful "
                      "App Store quality, professional game art")
    if mode == "openclip" and encoder is not None and hasattr(encoder, "encode_text"):
        gp_emb = encoder.encode_text(GAMEPLAY_PROMPT)
        q_emb = encoder.encode_text(QUALITY_PROMPT)
        raw_gp = {cid: _cosine(v, gp_emb) for cid, v in cvecs.items()}
        raw_q = {cid: _cosine(v, q_emb) for cid, v in cvecs.items()}
        def _norm(d):
            vals = list(d.values()); lo, hi = min(vals), max(vals)
            return {k: (v - lo) / (hi - lo + 1e-9) for k, v in d.items()}
        gameplay_clarity = _norm(raw_gp)
        visual_quality = _norm(raw_q)
    else:
        # heuristic 回退：metadata merge_board 标志 + 对比度归一
        gameplay_clarity = {c["creative_id"]: (1.0 if c.get("merge_board") else 0.2) for c in creatives}
        visual_quality = {k: v / cmax for k, v in contrast_norm.items()}

    # 4) 双模式 ranking（新权重：0.35 CLIP + 0.30 DNA + 0.20 Gameplay + 0.15 Visual）
    grp = {c["creative_id"]: c["group"] for c in creatives}
    dna_of = {c["creative_id"]: c["dna"] for c in creatives}
    mut_of = {c["creative_id"]: c.get("mutation_type", "") for c in creatives}
    ids = list(cvecs.keys())

    def build(sim_map, rmode):
        rows = []
        for cid in ids:
            clip_s = sim_map[cid]
            final = (0.35 * clip_s + 0.30 * dna_sims[cid]
                     + 0.20 * gameplay_clarity[cid] + 0.15 * visual_quality[cid])
            rows.append({
                "creative_id": cid, "group": grp[cid], "ranking_mode": rmode,
                "clip_similarity": round(clip_s, 4), "dna_score": round(dna_sims[cid], 4),
                "gameplay_clarity": round(gameplay_clarity[cid], 4),
                "visual_quality": round(visual_quality[cid], 4),
                "final_score": round(final, 4), "mutation_type": mut_of[cid], "dna": dna_of[cid],
            })
        rows.sort(key=lambda r: -r["final_score"])
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return rows

    rank_oc = build(sims, "openclip")           # 视觉排序（final 以 CLIP 视觉相似度为主）
    rank_he = build(dna_sims, "heuristic")       # DNA 排序（final 以 DNA 相似度为主）

    (OUT / "ranking_openclip.json").write_text(json.dumps(rank_oc, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "ranking_heuristic.json").write_text(json.dumps(rank_he, indent=2, ensure_ascii=False), encoding="utf-8")
    top5_oc = rank_oc[:5]; top5_he = rank_he[:5]
    (OUT / "TOP5_openclip.json").write_text(json.dumps(top5_oc, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "TOP5_heuristic.json").write_text(json.dumps(top5_he, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "similarity_stats.json").write_text(json.dumps({
        "clip_similarity": stats,
        "per_creative": {cid: {"clip": round(sims[cid], 4), "dna": round(dna_sims[cid], 4)} for cid in ids},
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # 5) TOP5 group 组成 + negative control 分离
    print("\n== Ranking validation (TOP5 openclip) ==")
    ga = sum(1 for r in top5_oc if r["group"] == "A")
    gc = sum(1 for r in top5_oc if r["group"] == "C")
    print(f"  TOP5 openclip groups: {[r['group'] for r in top5_oc]}")
    check(f"Group A in TOP5 >= 3 (got {ga})", ga >= 3)
    check(f"Group C in TOP5 <= 1 (got {gc})", gc <= 1)

    # 6) 双模式重合度
    print("\n== Dual mode comparison ==")
    s_oc = {r["creative_id"] for r in top5_oc}; s_he = {r["creative_id"] for r in top5_he}
    inter = len(s_oc & s_he); pct = inter / 5 * 100
    print(f"  TOP5 intersection = {inter}/5 ({pct:.0f}%)")
    check("both rankings generated", (OUT / "TOP5_openclip.json").exists() and (OUT / "TOP5_heuristic.json").exists())

    # group averages
    def gavg(g): 
        vv = [sims[c["creative_id"]] for c in creatives if c["group"] == g]
        return sum(vv) / len(vv) if vv else 0.0
    grp_avg = {g: round(gavg(g), 4) for g in ("A", "B", "C")}
    print(f"  group avg clip sim: {grp_avg}")

    # 7) HTML report
    print("\n== HTML report ==")
    html = _render_html(winner_path, rank_oc, grp_avg, stats, mode, inter, pct)
    (OUT / "validation_report.html").write_text(html, encoding="utf-8")
    rep_ok = (OUT / "validation_report.html").exists() and (OUT / "validation_report.html").stat().st_size > 1024
    check("validation_report.html generated", rep_ok)

    # 8) release gate
    gate = {
        "Real Images Loaded": bool(winner_path.exists() and files_ok and len(creatives) == 12),
        "12 Embeddings Generated": n_emb == 12,
        "OpenCLIP Active": mode == "openclip" and shape_ok,
        "Similarity Distribution": std > 0.03 and rng > 0.08,
        "Negative Control Separation": ga >= 3 and gc <= 1,
        "Dual Ranking Generated": (OUT / "TOP5_openclip.json").exists() and (OUT / "TOP5_heuristic.json").exists(),
        "HTML Report": rep_ok,
    }
    gate["scoring_weights"] = {"clip_similarity": 0.35, "dna_match": 0.30,
                               "gameplay_clarity": 0.20, "visual_quality": 0.15}
    gate["intersection_pct"] = round(pct, 1)
    gate["group_avg_clip"] = grp_avg
    gate["similarity_stats"] = stats
    gate["result"] = "Phase 2.1.5 COMPLETE" if all(v for k, v in gate.items() if isinstance(v, bool)) else "Phase 2.1.5 FAIL"
    (OUT / "release_gate.json").write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n== Release Gate ==")
    for k, v in gate.items():
        if isinstance(v, bool):
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\n{gate['result']}")
    print("\nRESULT:", "ALL PASS" if ok and gate["result"].endswith("COMPLETE") else "HAS FAILURES")
    return 0 if ok else 1


def _render_html(winner_path, rank_oc, grp_avg, stats, mode, inter, pct):
    wimg = _b64(winner_path, 360)
    rows = ""
    for r in rank_oc[:10]:
        cf = _find_file(r["creative_id"])
        cimg = _b64(cf, 200) if cf else ""
        gcolor = {"A": "#c0392b", "B": "#2980b9", "C": "#7f8c8d"}.get(r["group"], "#555")
        rows += f"""<tr>
<td class="rk">{r['rank']}</td>
<td><img src="data:image/jpeg;base64,{cimg}" class="thumb"/></td>
<td>{r['creative_id']}</td>
<td><span class="badge" style="background:{gcolor}">{r['group']}</span></td>
<td>{r['clip_similarity']:.3f}</td>
<td>{r['dna_score']:.3f}</td>
<td>{r['gameplay_clarity']:.3f}</td>
<td>{r['visual_quality']:.3f}</td>
<td class="final">{r['final_score']:.3f}</td>
</tr>"""
    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>Phase 2.1.5 CLIP Validation Report</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#f7f8fa;color:#1a1a1a;margin:0;padding:32px}}
.wrap{{max-width:1000px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#888;font-size:13px;margin-bottom:24px}}
.card{{background:#fff;border:1px solid #e6e8eb;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.winner{{display:flex;gap:20px;align-items:center}}
.winner img{{width:200px;border-radius:8px}}
.dna span{{display:inline-block;background:#f0eefb;color:#5b4bbd;border-radius:6px;padding:3px 10px;margin:3px 4px 0 0;font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid #eee}}
th{{color:#888;font-weight:600;font-size:12px;text-transform:uppercase}}
.thumb{{width:56px;height:100px;object-fit:cover;border-radius:6px}}
.rk{{font-weight:700;color:#5b4bbd;font-size:16px}}
.final{{font-weight:700;color:#c0392b}}
.badge{{color:#fff;border-radius:5px;padding:2px 9px;font-size:12px;font-weight:600}}
.stats{{display:flex;gap:24px;flex-wrap:wrap}}
.stat b{{display:block;font-size:20px;color:#5b4bbd}} .stat span{{font-size:12px;color:#888}}
.ga{{display:flex;gap:20px}} .ga div{{flex:1;text-align:center;padding:14px;border-radius:8px}}
.gaA{{background:#fdecea}} .gaB{{background:#eaf2fb}} .gaC{{background:#f0f1f2}}
.ga b{{display:block;font-size:22px}}
</style></head><body><div class="wrap">
<h1>Phase 2.1.5 — Real Creative Validation</h1>
<div class="sub">mode = {mode} · OpenCLIP ViT-B-32 / laion2b · 真实广告图片视觉相似度排序</div>

<div class="card"><h3 style="margin-top:0">Winner Reference</h3>
<div class="winner"><img src="data:image/jpeg;base64,{wimg}"/>
<div><b>winner_001</b><div class="dna" style="margin-top:8px">
<span>character: witch</span><span>reward: baby dragon</span><span>environment: castle</span>
<span>hook: collection</span></div>
<p style="color:#666;font-size:13px;margin-top:12px">elegant witch tending a magical garden, centered hero shot with castle background, deep purple/blue palette.</p>
</div></div></div>

<div class="card"><h3 style="margin-top:0">Similarity Distribution</h3>
<div class="stats">
<div class="stat"><b>{stats['min']:.3f}</b><span>min</span></div>
<div class="stat"><b>{stats['max']:.3f}</b><span>max</span></div>
<div class="stat"><b>{stats['mean']:.3f}</b><span>mean</span></div>
<div class="stat"><b>{stats['std']:.4f}</b><span>std</span></div>
<div class="stat"><b>{stats['range']:.3f}</b><span>range</span></div>
<div class="stat"><b>{inter}/5 ({pct:.0f}%)</b><span>openclip∩heuristic</span></div>
</div></div>

<div class="card"><h3 style="margin-top:0">Group Analysis (avg CLIP similarity)</h3>
<div class="ga">
<div class="gaA"><span>Group A · DNA 保持</span><b style="color:#c0392b">{grp_avg['A']:.3f}</b></div>
<div class="gaB"><span>Group B · Mutation</span><b style="color:#2980b9">{grp_avg['B']:.3f}</b></div>
<div class="gaC"><span>Group C · Negative</span><b style="color:#7f8c8d">{grp_avg['C']:.3f}</b></div>
</div></div>

<div class="card"><h3 style="margin-top:0">Ranking (OpenCLIP, TOP10)</h3>
<table><thead><tr><th>Rank</th><th>Image</th><th>Creative</th><th>Group</th>
<th>CLIP</th><th>DNA</th><th>Gameplay</th><th>Visual</th><th>Final</th></tr></thead>
<tbody>{rows}</tbody></table></div>

</div></body></html>"""


def _find_file(cid: str):
    p = VAL / "creatives" / f"{cid}.png"
    return p if p.exists() else None


if __name__ == "__main__":
    raise SystemExit(main())
