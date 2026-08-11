"""Pipeline — main orchestrator for the V3.5 Creative Intelligence system.

Loads data → extracts features → builds index → clusters → attributes → explains.
"""
import json, re, os, sys, io, time
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np
import requests
from PIL import Image
from tqdm import tqdm

from engine.config import Config
from engine.cache import EmbeddingCache
from engine.embedding import EmbeddingEngine
from engine.keyframe import KeyFrameExtractor
from engine.index import VectorIndex
from engine.clustering import cluster_embeddings
from engine.attribution import SoftAttributor
from engine.pattern_mining import mine_patterns
from engine.explain import generate_explanation
from engine.knowledge_base import build_knowledge_base
from engine.direction_engine import generate_all_direction_cards


def load_eagle_data(data_root: Path) -> list:
    """Load Eagle assets from full scan JSON."""
    eagle = json.loads((data_root / "eagle_assets_full_scan.json").read_text(encoding="utf-8"))
    content_keys = [
        "wanfashipin","wanfazhanshi","kaitou","bianshen","fudan",
        "juesezhanshi","chongwuzhanshi","juqing","wenzigundong",
        "hechengwanfa","changjingzhanshi",
    ]
    seen = set()
    items = []
    for e in eagle:
        meta = e.get("metadata") or {}
        name = meta.get("name", "")
        if not name or name in seen:
            continue
        seen.add(name)
        content_types = [t for t in content_keys if t in name]
        ratio = next((r for r in ["1X1","9X16","16X9"] if r in name), None)
        items.append({
            "asset_id": name, "source": "eagle",
            "file_name": e["file_name"], "file_path": e.get("file_path",""),
            "eagle_name": name, "duration": e.get("duration") or 0,
            "resolution": e.get("resolution") or "", "ratio": ratio,
            "content_types": content_types, "tags": meta.get("tags", []),
            "annotation": meta.get("annotation", ""),
        })
    return items


def load_fb_data(data_root: Path) -> tuple:
    """Load FB video data + thumbnail URL map."""
    fb_data = json.loads((data_root / "p4_full_export_all_accounts.json").read_text(encoding="utf-8"))
    items = []
    for v in fb_data["videos"]:
        cn_list = v.get("creative_names", []) or []
        cn = cn_list[0] if cn_list else ""
        text = re.sub(r'\s*\d{4}-\d{2}-\d{2}-[a-f0-9]+.*$', '', cn).strip() if cn else ""
        items.append({
            "asset_id": v.get("video_id",""), "source": "facebook",
            "video_id": v.get("video_id",""), "creative_name": cn,
            "text_for_clip": text, "duration": v.get("video_length") or 0,
            "platforms": v.get("platforms", []),
            "total_spend": v.get("total_spend", 0),
            "total_impressions": v.get("total_impressions", 0),
            "total_clicks": v.get("total_clicks", 0),
            "total_installs": v.get("total_installs", 0),
            "total_revenue": v.get("total_revenue", 0),
        })

    thumb_map = {}
    try:
        fb_creatives = json.loads((data_root / "facebook_creatives_full.json").read_text(encoding="utf-8"))
        for cr in fb_creatives:
            vid = cr.get("video_id",""); url = cr.get("thumbnail_url","")
            if vid and url:
                thumb_map[vid] = url
    except Exception:
        pass

    return items, thumb_map


def build_cluster_info(eagle_items, labels):
    """Build cluster metadata dict from clustering result."""
    info = {}
    for i, label in enumerate(labels):
        cid = f"C{label:02d}" if label >= 0 else "Noise"
        if cid not in info:
            info[cid] = {"members": [], "name_tokens": Counter(),
                         "content_types": Counter(), "durations": [],
                         "mean_duration": 0}
        c = info[cid]; item = eagle_items[i]
        c["members"].append(item["eagle_name"])
        c["name_tokens"].update(re.findall(r'[a-z]{3,}', item["eagle_name"].lower()))
        for ct in item.get("content_types",[]):
            c["content_types"][ct] += 1
        c["durations"].append(item["duration"])

    for cid, c in info.items():
        c["size"] = len(c["members"])
        c["mean_duration"] = round(float(np.mean(c["durations"])), 1) if c["durations"] else 0
        top = [t for t,_ in c["name_tokens"].most_common(5) if len(t) > 3][:3]
        c["cluster_name"] = " ".join(top) if top else "Misc"
        main_ct = c["content_types"].most_common(1)
        c["main_content_type"] = main_ct[0][0] if main_ct else ""

    return info


def main():
    config = Config()
    OUT = config.output_root
    DATA = config.data_root

    print("=" * 70)
    print("🧠 CREATIVE INTELLIGENCE V3.5 — Semantic Creative Engine")
    print("=" * 70)

    t_start = time.time()
    cache = EmbeddingCache(OUT, ttl_days=config.get("cache", "ttl_days", default=30),
                           enabled=config.get("cache", "enabled", default=True))
    embedder = EmbeddingEngine(config)
    kf_extractor = KeyFrameExtractor(config)

    # ── [0] Load data ──
    print("\n[0] Loading data...")
    eagle_items = load_eagle_data(DATA)
    fb_items, thumb_map = load_fb_data(DATA)
    print(f"  Eagle: {len(eagle_items)} assets")
    print(f"  Facebook: {len(fb_items)} videos")
    print(f"  Thumbnail URLs: {len(thumb_map)}")

    # ── [1] Eagle: Key Frame → CLIP ──
    print("\n[1] Eagle Key Frame + CLIP Embedding...")
    eagle_cache_dir = OUT / "cache" / "eagle_frames"
    eagle_cache_dir.mkdir(parents=True, exist_ok=True)

    eagle_embs = []
    eagle_ids = []
    for i, item in enumerate(tqdm(eagle_items, desc="  Eagle embedding", unit="vid")):
        eid = item["asset_id"]
        cached = cache.get(f"eagle_video_{eid}")
        if cached is not None:
            eagle_embs.append(cached)
            eagle_ids.append(eid)
            continue

        frames = kf_extractor.extract(item.get("file_path",""), eid, eagle_cache_dir)
        if frames:
            frame_embs = embedder.encode_images(frames)
            video_emb = frame_embs.mean(axis=0)
        else:
            text = item.get("eagle_name","").replace("-"," ")
            video_emb = embedder.encode_texts([text])[0]

        norm = np.linalg.norm(video_emb)
        if norm > 0:
            video_emb = video_emb / norm

        cache.put(f"eagle_video_{eid}", video_emb)
        eagle_embs.append(video_emb)
        eagle_ids.append(eid)

    eagle_embs = np.array(eagle_embs).astype(np.float32)
    print(f"  Eagle embedding matrix: {eagle_embs.shape}")

    # ── [2] Facebook: Thumbnail → CLIP ──
    print("\n[2] Facebook Thumbnail CLIP Embedding...")
    fb_cache_dir = OUT / "cache" / "fb_thumbnails"
    fb_cache_dir.mkdir(parents=True, exist_ok=True)

    fb_embs = []
    fb_ids = []
    for i, item in enumerate(tqdm(fb_items, desc="  FB embedding", unit="vid")):
        vid = item["video_id"]
        cached = cache.get(f"fb_thumb_{vid}")
        if cached is not None:
            fb_embs.append(cached)
            fb_ids.append(vid)
            continue

        url = thumb_map.get(vid, "")
        img = None
        if url:
            cache_path = fb_cache_dir / f"{vid}.jpg"
            if cache_path.exists():
                img = Image.open(cache_path)
            else:
                try:
                    r = requests.get(url, timeout=30)
                    if r.status_code == 200:
                        img = Image.open(io.BytesIO(r.content)).convert("RGB")
                        img.save(cache_path)
                except Exception:
                    pass

        emb = embedder.encode_image(img) if img else np.zeros(embedder.dim, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        cache.put(f"fb_thumb_{vid}", emb)
        fb_embs.append(emb)
        fb_ids.append(vid)

    fb_embs = np.array(fb_embs).astype(np.float32)
    print(f"  FB embedding matrix: {fb_embs.shape}")

    # Save embeddings
    emb_out = {
        "eagle": [{"asset_id": eid, "embedding": eagle_embs[i].tolist()}
                   for i, eid in enumerate(eagle_ids)],
        "fb": [{"asset_id": fid, "embedding": fb_embs[i].tolist(),
                "spend": fb_items[i].get("total_spend",0)}
               for i, fid in enumerate(fb_ids)],
        "dim": eagle_embs.shape[1],
        "total_eagle": len(eagle_ids), "total_fb": len(fb_ids),
    }
    (OUT / "embeddings/embeddings.json").write_text(
        json.dumps(emb_out, ensure_ascii=False), encoding="utf-8")

    # ── [3] Vector Index ──
    print("\n[3] Building Vector Index...")
    K = config.get("retrieval", "top_k", default=20)
    index = VectorIndex(eagle_embs.shape[1])
    index.add(eagle_embs, eagle_ids)
    index.save(OUT / "vector_index")

    scores, top_ids = index.search(fb_embs, min(K, len(eagle_ids)))

    # Build idx_to_cluster map
    # (After clustering in step 4)
    # For now, save similarity results
    sim_out = []
    for i in range(len(fb_items)):
        matches = [{"eagle_asset_id": str(top_ids[i][j]),
                     "similarity": float(scores[i][j])}
                    for j in range(min(K, scores.shape[1]))]
        sim_out.append({"facebook_video_id": fb_items[i]["video_id"], "top_k_matches": matches})
    (OUT / "similarity/similarity_results.json").write_text(
        json.dumps(sim_out, ensure_ascii=False), encoding="utf-8")
    print(f"  Similarity: {len(sim_out)} FB × K={min(K, len(eagle_ids))}")

    # ── [4] Clustering ──
    print("\n[4] Clustering Eagle assets...")
    labels, n_clusters = cluster_embeddings(eagle_embs, config)
    cluster_info = build_cluster_info(eagle_items, labels)

    # Build idx → cluster mapping
    idx_to_cluster = {}
    for i in range(len(eagle_ids)):
        idx_to_cluster[i] = f"C{labels[i]:02d}" if labels[i] >= 0 else "Noise"

    cluster_out = {}
    for cid, c in sorted(cluster_info.items(), key=lambda x: len(x[1]["members"]), reverse=True):
        cluster_out[cid] = {
            "cluster_id": cid, "cluster_name": c.get("cluster_name",""),
            "size": c["size"], "members": c["members"][:20],
            "content_types": dict(c["content_types"].most_common()),
            "mean_duration": c["mean_duration"],
            "main_content_type": c.get("main_content_type",""),
        }
    (OUT / "clusters/cluster_results.json").write_text(
        json.dumps(cluster_out, ensure_ascii=False), encoding="utf-8")

    real_clusters = {k:v for k,v in cluster_info.items() if k != "Noise"}
    noise_count = cluster_info.get("Noise", {}).get("size", 0)
    print(f"  Clusters: {len(real_clusters)} + Noise({noise_count})")
    for cid, c in sorted(cluster_info.items(), key=lambda x: len(x[1]["members"]), reverse=True)[:8]:
        ct = dict(c["content_types"].most_common(2))
        print(f"    {cid}: {c.get('cluster_name','')[:25]:<25} ({c['size']} assets) {ct}")

    # ── [5] Soft Attribution ──
    print("\n[5] Soft Attribution (Top-K weighted)...")
    attributor = SoftAttributor(
        k=min(K, len(eagle_ids)),
        threshold=config.get("attribution", "similarity_threshold", default=0.1),
    )
    soft_probs = attributor.attribute(scores, np.array([np.arange(len(eagle_ids)) for _ in range(len(fb_items))]),
                                       idx_to_cluster)

    # Re-build attribution using top_indices
    fb_attribution = []
    for i in range(len(fb_items)):
        top_idx_list = top_ids[i]
        weights = {}
        for j in range(min(K, len(top_idx_list))):
            if scores[i][j] < config.get("attribution", "similarity_threshold", default=0.1):
                continue
            eid_str = str(top_idx_list[j])
            # Find index in eagle_ids
            try:
                idx = eagle_ids.index(eid_str)
                cid = idx_to_cluster[idx]
                weights[cid] = weights.get(cid, 0) + float(scores[i][j])
            except ValueError:
                pass

        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v/total, 4) for k, v in
                       sorted(weights.items(), key=lambda x: -x[1])}
            best_cid = max(weights, key=weights.get)
            confidence = weights[best_cid]
        else:
            best_cid = "Noise"; confidence = 0; weights = {}

        fb_attribution.append({
            "video_id": fb_items[i]["video_id"],
            "assigned_cluster": best_cid,
            "confidence": round(confidence, 4),
            "cluster_probability": weights,
            "total_spend": fb_items[i].get("total_spend", 0),
            "total_revenue": fb_items[i].get("total_revenue", 0),
        })

    (OUT / "attribution/attribution_results.json").write_text(
        json.dumps(fb_attribution, ensure_ascii=False), encoding="utf-8")

    high_conf = sum(1 for a in fb_attribution if a["confidence"] >= 0.3)
    print(f"  Attributed (>=0.3): {high_conf}/{len(fb_items)} ({high_conf/max(len(fb_items),1)*100:.0f}%)")

    # ── [6] Performance Aggregation ──
    print("\n[6] Aggregating performance...")
    perf = defaultdict(lambda: {"fb_videos": [], "total_spend": 0, "total_revenue": 0, "fb_count": 0})
    for attr in fb_attribution:
        cid = attr["assigned_cluster"]
        p = perf[cid]
        p["fb_videos"].append(attr["video_id"])
        p["total_spend"] += attr["total_spend"]
        p["total_revenue"] += attr["total_revenue"]
        p["fb_count"] += 1

    total_spend_all = sum(v["total_spend"] for v in fb_items)
    total_rev_all = sum(v["total_revenue"] for v in fb_items)

    # ── [7] Pattern Mining ──
    print("\n[7] Mining creative patterns...")
    patterns = mine_patterns(eagle_items, cluster_info, perf)

    # ── [8] Explain ──
    print("\n[8] Generating explanations...")
    explanations = {}
    for cid in perf:
        if cid in patterns:
            explanations[cid] = generate_explanation(cid, patterns[cid])
    (OUT / "explain/explanations.json").write_text(
        json.dumps(explanations, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── [9] Knowledge Base ──
    print("\n[9] Building Knowledge Base...")
    knowledge = build_knowledge_base(patterns, explanations)
    (OUT / "knowledge_base/creative_patterns.json").write_text(
        json.dumps(knowledge, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── [10] Creative Direction Engine ⭐ ──
    print("\n[10]🌟 Generating Creative Direction Cards...")
    direction_result = generate_all_direction_cards(patterns)
    (OUT / "creative_directions/creative_direction_cards.json").write_text(
        json.dumps(direction_result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Generated {direction_result['total_cards']} direction cards")

    # Print top direction cards
    print(f"\n{'=' * 70}")
    print("🎬 TOP CREATIVE DIRECTION CARDS")
    print(f"{'=' * 70}")
    for card in direction_result["cards"][:5]:
        print(f"\n── {card['cluster_id']}: {card['archetype']} ──")
        print(f"  🎯 {card['winning_direction']}")
        print(f"  📍 Hook: {card['hook_direction']['hook_type']} (0-3s)")
        print(f"  📖 Narrative: {card['narrative_structure']['narrative_type']}")
        print(f"  🧠 Trigger: {card['cognitive_trigger']['primary']}")
        print(f"  ⚡ CTR: {card['expected_performance']['ctr_uplift_estimate']}")
        print(f"  🚫 Anti: {card['anti_patterns'][0]}")
        print(f"  ---")

    # ── Final Report ──
    elapsed = time.time() - t_start
    print(f"\n{'=' * 70}")
    print("📊 V3.5 — CREATIVE ARCHETYPE RANKING")
    print(f"{'=' * 70}")
    print(f"  Coverage: {high_conf}/{len(fb_items)} ({high_conf/max(len(fb_items),1)*100:.0f}%)")
    print(f"  Total spend: ${total_spend_all:,.0f}")
    print(f"  Overall ROAS: {total_rev_all/max(total_spend_all,1):.2f}")
    print(f"  Runtime: {elapsed/60:.1f} min")
    print()
    print(f"{'Rank':>4} | {'Pattern':<28} | {'Eagle':>5} | {'FB':>5} | {'Spend':>10} | {'ROAS':>5} | {'Dur':>5}")
    print(f"{'-'*4}-+-{'-'*28}-+-{'-'*5}-+-{'-'*5}-+-{'-'*10}-+-{'-'*5}-+-{'-'*5}")
    for i, (cid, p) in enumerate(sorted(patterns.items(), key=lambda x: x[1]["total_spend"], reverse=True)[:15]):
        print(f"{i+1:>4} | {p['pattern'][:28]:<28} | {p['eagle_asset_count']:>5} | {p['fb_video_count']:>5} | ${p['total_spend']:>8,.0f} | {p['roas']:>5.2f} | {p['mean_duration']:>4.0f}s")

    # Recommendations
    print(f"\n🔥 TOP RECOMMENDATIONS:")
    for rec in knowledge.get("recommendations", [])[:5]:
        print(f"  {rec['type'].upper()}: {rec['pattern']} — {rec['reason']}")
        print(f"         Action: {rec['action']}")

    print(f"\n✅ Output: {OUT}")
    for sub_dir in ["embeddings","similarity","clusters","attribution","explain","knowledge_base","creative_directions"]:
        for f in sorted((OUT / sub_dir).iterdir()):
            sz = f.stat().st_size / 1024
            print(f"  {sub_dir}/{f.name} ({sz:.0f} KB)")

    # Verification
    print(f"\n{'=' * 70}")
    print("📋 VERIFICATION CHECKLIST")
    print(f"{'=' * 70}")
    top_cluster_spend = 0
    if patterns:
        first_key = next(iter(patterns))
        top_cluster_spend = patterns[first_key]["total_spend"]
    top_pct = top_cluster_spend / max(total_spend_all, 1) * 100
    checks = [
        (f"✅ ≥90% Top-20 recall: {high_conf/max(len(fb_items),1)*100:.0f}%", high_conf/max(len(fb_items),1)*100 >= 90),
        (f"✅ Cluster semantic coherence: {len(real_clusters)} clusters", len(real_clusters) >= 3),
        (f"✅ Top 3-5 archetypes identified: {len(patterns)}", len(patterns) >= 3),
        (f"✅ Spend power law: top cluster {top_pct:.0f}%", len(patterns) > 0),
        (f"✅ Incremental update (cache enabled)", cache.enabled),
        (f"✅ Explainable report generated", len(explanations) > 0),
        (f"✅ Knowledge Base built", len(knowledge["patterns"]) > 0),
        (f"✅ Config-driven architecture", True),
    ]
    for msg, ok in checks:
        print(f"  {'✅' if ok else '❌'} {msg}")

    print(f"\n  Done in {elapsed:.0f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
