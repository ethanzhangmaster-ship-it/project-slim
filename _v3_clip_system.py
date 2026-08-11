"""Creative Intelligence V3 — CLIP Embedding Attribution System.
纯 numpy 实现，CLIP via transformers，完整 7 步流水线。

Flow:
  Step 1: CLIP feature extraction (FB thumbnail + FB text + Eagle text)
  Step 2: Embedding unification → shared 512-d space
  Step 3: Vector index (numpy FAISS FlatIP)
  Step 4: Clustering (Eagle side only)
  Step 5: Attribution (FB → cluster via top-K)
  Step 6: Performance aggregation
  Step 7: Archetype mining

Output: output/video_intelligence/p04/v3/
"""
import json, re, os, sys, io, time, subprocess, warnings
import numpy as np
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

# Fix Windows symlink issue for HuggingFace hub
if os.name == 'nt':
    import shutil
    _real_symlink = os.symlink
    def _symlink_safe(src, dst, target_is_directory=False):
        try:
            _real_symlink(src, dst, target_is_directory)
        except OSError:
            dst_p = Path(dst)
            # Resolve relative src path from dst's parent directory
            src_p = (dst_p.parent / src).resolve()
            dst_p.parent.mkdir(parents=True, exist_ok=True)
            if src_p.is_dir():
                shutil.copytree(src_p, dst_p, dirs_exist_ok=True)
            else:
                shutil.copy2(src_p, dst_p)
    os.symlink = _symlink_safe
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

warnings.filterwarnings("ignore")
SEED = 42; np.random.seed(SEED); torch.manual_seed(SEED)

OUT = Path(__file__).resolve().parent / "output" / "video_intelligence" / "p04" / "v3"
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parent
CACHE_DIR = OUT / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── CLIP Model (lazy load) ──
_model = None; _processor = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def get_clip():
    global _model, _processor
    if _model is None:
        print(f"  Loading CLIP (ViT-B/32) on {DEVICE}...")
        _model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(DEVICE)
        _processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        _model.eval()
    return _model, _processor

# ── FAISS-compatible numpy index ──
class NumpyIndexFlatIP:
    """Flat inner-product (cosine) index using numpy. FAISS-compatible API."""
    def __init__(self, dim):
        self.dim = dim
        self.vectors = None
        self.ids = None
    def add(self, vectors, ids=None):
        # Normalize for cosine
        norms = np.linalg.norm(vectors, axis=1, keepdims=True).clip(1e-10)
        self.vectors = vectors / norms
        self.ids = ids if ids is not None else np.arange(len(vectors))
    def search(self, query, k):
        q_norm = query / np.linalg.norm(query, axis=1, keepdims=True).clip(1e-10)
        sim = q_norm @ self.vectors.T
        top_k = np.argsort(-sim, axis=1)[:, :k]
        scores = np.take_along_axis(sim, top_k, axis=1)
        return scores, np.array([self.ids[t] for t in top_k])
    def save(self, path):
        np.savez(path, vectors=self.vectors, ids=self.ids, dim=self.dim)
    @classmethod
    def load(cls, path):
        data = np.load(path)
        idx = cls(int(data["dim"]))
        idx.vectors = data["vectors"]
        idx.ids = data["ids"]
        return idx

# ═══════════════════════════════════════════════════
# Step 1: CLIP Feature Extraction
# ═══════════════════════════════════════════════════

def clip_image_embed(path_or_pil) -> np.ndarray:
    """Single image → 512-d CLIP embedding."""
    model, proc = get_clip()
    if isinstance(path_or_pil, (str, Path)):
        img = Image.open(path_or_pil).convert("RGB")
    else:
        img = path_or_pil
    inputs = proc(images=img, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        emb = model.get_image_features(**inputs)
    return emb.cpu().numpy().flatten().astype(np.float32)


def clip_text_embed(text: str) -> np.ndarray:
    """Single text string → 512-d CLIP embedding."""
    model, proc = get_clip()
    inputs = proc(text=[text], return_tensors="pt", padding=True, truncation=True).to(DEVICE)
    with torch.no_grad():
        emb = model.get_text_features(**inputs)
    return emb.cpu().numpy().flatten().astype(np.float32)


def download_thumbnail(url, vid):
    """Download FB thumbnail. Returns PIL Image or None."""
    cache_path = CACHE_DIR / f"thumb_{vid}.jpg"
    if cache_path.exists():
        return Image.open(cache_path)
    try:
        import requests
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            img.save(cache_path)
            return img
    except:
        pass
    return None


def extract_eagle_first_frame(filepath, vid):
    """Extract first frame of video via ffmpeg. Returns PIL Image or None."""
    cache_path = CACHE_DIR / f"eagle_frame_{vid}.jpg"
    if cache_path.exists():
        return Image.open(cache_path)
    try:
        subprocess.run(
            ["ffmpeg", "-i", filepath, "-vframes", "1", "-f", "image2",
             str(cache_path)],
            capture_output=True, timeout=30
        )
        if cache_path.exists():
            return Image.open(cache_path)
    except:
        pass
    return None


# ═══════════════════════════════════════════════════
# Data Loaders
# ═══════════════════════════════════════════════════

def load_eagle_data():
    """Load and parse Eagle assets."""
    eagle = json.loads((ROOT / "output/video_intelligence/p04/eagle_assets_full_scan.json").read_text(encoding="utf-8"))
    items = []
    for e in eagle:
        meta = e.get("metadata") or {}
        name = meta.get("name", "")
        if not name: continue
        content_types = []
        for t in ["wanfashipin","wanfazhanshi","kaitou","bianshen","fudan",
                   "juesezhanshi","chongwuzhanshi","juqing","wenzigundong",
                   "hechengwanfa","changjingzhanshi"]:
            if t in name: content_types.append(t)
        ratio = None
        for r in ["1X1","9X16","16X9"]:
            if r in name: ratio = r
        items.append({
            "asset_id": name,
            "source": "eagle",
            "file_name": e["file_name"],
            "file_path": e.get("file_path",""),
            "eagle_name": name,
            "duration": e.get("duration") or 0,
            "resolution": e.get("resolution") or "",
            "ratio": ratio,
            "content_types": content_types,
            "tags": meta.get("tags", []),
            "annotation": meta.get("annotation", ""),
            "text_for_clip": name.replace("-"," ").replace("_"," "),
        })
    # Deduplicate
    seen = set(); unique = []
    for item in items:
        if item["eagle_name"] not in seen:
            seen.add(item["eagle_name"]); unique.append(item)
    return unique


def load_fb_data():
    """Load Facebook video data + thumbnails."""
    fb_data = json.loads((ROOT / "output/video_intelligence/p04/p4_full_export_all_accounts.json").read_text(encoding="utf-8"))
    fb_creatives = json.loads((ROOT / "output/video_intelligence/p04/facebook_creatives_full.json").read_text(encoding="utf-8"))
    
    # Build thumbnail map
    thumb_map = {}
    for cr in fb_creatives:
        vid = cr.get("video_id","")
        url = cr.get("thumbnail_url","")
        if vid and url: thumb_map[vid] = url
    
    items = []
    for v in fb_data["videos"]:
        vid = v.get("video_id","")
        cn_list = v.get("creative_names", []) or []
        an_list = v.get("ad_names", []) or []
        cn = cn_list[0] if cn_list else ""
        
        # Clean text for CLIP
        text = re.sub(r'\s*\d{4}-\d{2}-\d{2}-[a-f0-9]+.*$', '', cn).strip() if cn else ""
        
        items.append({
            "asset_id": vid,
            "source": "facebook",
            "video_id": vid,
            "creative_name": cn,
            "ad_name": an_list[0] if an_list else "",
            "text_for_clip": text,
            "thumbnail_url": thumb_map.get(vid, ""),
            "duration": v.get("video_length") or 0,
            "platforms": v.get("platforms", []),
            "total_spend": v.get("total_spend", 0),
            "total_impressions": v.get("total_impressions", 0),
            "total_clicks": v.get("total_clicks", 0),
            "total_installs": v.get("total_installs", 0),
            "total_revenue": v.get("total_revenue", 0),
        })
    return items


# ═══════════════════════════════════════════════════
# Main Pipeline
# ═══════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("🧠 CREATIVE INTELLIGENCE V3 — CLIP ATTRIBUTION SYSTEM")
    print("=" * 70)
    
    # ── Load data ──
    print("\n[0] Loading data...")
    eagle_items = load_eagle_data()
    fb_items = load_fb_data()
    print(f"  Eagle: {len(eagle_items)} assets")
    print(f"  Facebook: {len(fb_items)} videos")
    
    # ── Step 1: CLIP Feature Extraction ──
    print("\n[1] CLIP Feature Extraction...")
    get_clip()
    
    # FB: thumbnail → visual embedding
    fb_visual_embs = []
    for i, item in enumerate(fb_items):
        vid = item["video_id"]
        url = item.get("thumbnail_url","")
        img = download_thumbnail(url, vid) if url else None
        if img:
            emb = clip_image_embed(img)
        else:
            emb = np.zeros(512, dtype=np.float32)
        fb_visual_embs.append(emb)
        if (i+1) % 100 == 0: print(f"  FB thumbnails [{i+1}/{len(fb_items)}]")
    fb_visual = np.array(fb_visual_embs)
    print(f"  FB visual embedding: {fb_visual.shape}")
    
    # Eagle: try first frame, fallback to zeros
    eagle_visual_embs = []
    for i, item in enumerate(eagle_items):
        fp = item.get("file_path","")
        if fp:
            img = extract_eagle_first_frame(fp, item["asset_id"])
            if img:
                emb = clip_image_embed(img)
                eagle_visual_embs.append(emb)
                continue
        eagle_visual_embs.append(np.zeros(512, dtype=np.float32))
        if (i+1) % 100 == 0: print(f"  Eagle frames [{i+1}/{len(eagle_items)}]")
    eagle_visual = np.array(eagle_visual_embs)
    print(f"  Eagle visual embedding: {eagle_visual.shape}")
    
    # CLIP text embeddings (for both)
    print("  CLIP text embeddings...")
    eagle_texts = []
    for item in eagle_items:
        name = item.get("eagle_name","")
        # Build descriptive text for CLIP
        parts = name.replace("-"," ").split()
        parts = [p for p in parts if not re.match(r'^v?\d+$', p)]
        content = " ".join(item.get("content_types",[]))
        desc = f"mobile game ad video {content} {' '.join(parts)}"
        eagle_texts.append(desc)
    
    fb_texts = []
    for item in fb_items:
        t = item.get("text_for_clip","") or item.get("creative_name","")[:100]
        fb_texts.append(t if t else "mobile game ad")
    
    all_texts = eagle_texts + fb_texts
    batch_size = 64
    all_text_embs = []
    for i in range(0, len(all_texts), batch_size):
        batch = all_texts[i:i+batch_size]
        model, proc = get_clip()
        inputs = proc(text=batch, return_tensors="pt", padding=True, truncation=True).to(DEVICE)
        with torch.no_grad():
            embs = model.get_text_features(**inputs)
        all_text_embs.append(embs.cpu().numpy())
    all_text_embs = np.concatenate(all_text_embs, axis=0).astype(np.float32)
    
    eagle_text = all_text_embs[:len(eagle_items)]
    fb_text = all_text_embs[len(eagle_items):]
    print(f"  Text embedding dim: {eagle_text.shape[1]}")
    
    # Structural features (duration bucket one-hot)
    def dur_onehot(d):
        arr = np.zeros(8)
        if d <= 5: arr[0] = 1
        elif d <= 10: arr[1] = 1
        elif d <= 15: arr[2] = 1
        elif d <= 20: arr[3] = 1
        elif d <= 30: arr[4] = 1
        elif d <= 40: arr[5] = 1
        elif d <= 50: arr[6] = 1
        else: arr[7] = 1
        return arr
    
    eagle_struct = np.array([np.concatenate([
        dur_onehot(item["duration"]),
        np.ones(1) * (item["duration"] / 60.0),
        np.ones(1) * (1 if item.get("ratio") == "1X1" else 0),
        np.ones(1) * (1 if item.get("ratio") == "9X16" else 0),
        np.ones(1) * (1 if item.get("ratio") == "16X9" else 0),
    ]) for item in eagle_items]).astype(np.float32)
    
    fb_struct = np.array([np.concatenate([
        dur_onehot(item["duration"]),
        np.ones(1) * (item["duration"] / 60.0),
        np.zeros(3),  # no ratio info for FB
    ]) for item in fb_items]).astype(np.float32)
    
    # ── Step 2: Embedding Unification ──
    print("\n[2] Unifying embeddings...")
    
    # Normalize each modality
    def normalize(X):
        n = np.linalg.norm(X, axis=1, keepdims=True).clip(1e-10)
        return X / n
    
    W_V = 0.7; W_T = 0.2; W_S = 0.1
    
    eagle_emb = np.concatenate([
        normalize(eagle_visual) * W_V,
        normalize(eagle_text) * W_T,
        normalize(eagle_struct) * W_S,
    ], axis=1).astype(np.float32)
    
    fb_emb = np.concatenate([
        normalize(fb_visual) * W_V,
        normalize(fb_text) * W_T,
        normalize(fb_struct) * W_S,
    ], axis=1).astype(np.float32)
    
    # Final L2 normalize
    eagle_emb = normalize(eagle_emb)
    fb_emb = normalize(fb_emb)
    print(f"  Final embedding dim: {eagle_emb.shape[1]}")
    
    # Save embeddings
    emb_data = {
        "dim": eagle_emb.shape[1],
        "eagle": [{"asset_id": item["asset_id"], "embedding": eagle_emb[i].tolist(),
                    "metadata": {"source":"eagle","name":item["eagle_name"],"duration":item["duration"]}}
                   for i, item in enumerate(eagle_items)],
        "fb": [{"asset_id": item["asset_id"], "embedding": fb_emb[i].tolist(),
                "metadata": {"source":"facebook","creative_name":item.get("creative_name","")[:80],
                             "spend":item["total_spend"],"revenue":item["total_revenue"]}}
               for i, item in enumerate(fb_items)],
    }
    (OUT / "embeddings.json").write_text(json.dumps(emb_data, ensure_ascii=False), encoding="utf-8")
    
    # ── Step 3: Vector Index ──
    print("\n[3] Building FAISS index (numpy)...")
    eagle_ids = [item["asset_id"] for item in eagle_items]
    index = NumpyIndexFlatIP(eagle_emb.shape[1])
    index.add(eagle_emb, np.array(eagle_ids))
    index.save(str(OUT / "faiss_index.npz"))
    
    # Search: FB → top-5 Eagle
    fb_ids = [item["asset_id"] for item in fb_items]
    K = 5
    scores, top_indices = index.search(fb_emb, K)
    
    sim_results = []
    for i, item in enumerate(fb_items):
        matches = []
        for j in range(K):
            idx = top_indices[i][j]
            matches.append({
                "eagle_asset_id": str(idx),
                "similarity": float(scores[i][j]),
            })
        sim_results.append({
            "facebook_video_id": item["video_id"],
            "top_k_matches": matches,
        })
    (OUT / "similarity_results.json").write_text(
        json.dumps(sim_results, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  Similarity results saved ({len(sim_results)} FB videos × K={K})")
    
    # ── Step 4: Clustering (Eagle side) ──
    print("\n[4] Clustering Eagle assets...")
    
    n_clusters = min(20, len(eagle_items) // 10)
    
    try:
        from sklearn.cluster import KMeans as _KMeans
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(eagle_emb)
        km = _KMeans(n_clusters=n_clusters, random_state=SEED, n_init=10)
        eagle_labels = km.fit_predict(X_scaled)
        print("  Using sklearn KMeans")
    except:
        # Pure numpy fallback
        print("  Using numpy KMeans (sklearn unavailable)")
        from numpy import random as npr
        npr.seed(SEED)
        n = eagle_emb.shape[0]; k = n_clusters
        centroids = eagle_emb[npr.randint(n, size=k)]
        for _ in range(100):
            dists = np.array([np.linalg.norm(eagle_emb - c, axis=1) for c in centroids]).T
            labels = np.argmin(dists, axis=1)
            new_c = np.array([eagle_emb[labels == j].mean(axis=0) if np.sum(labels == j) > 0 else centroids[j] for j in range(k)])
            centroids = new_c
        eagle_labels = labels
    
    clusters = {}
    for i, label in enumerate(eagle_labels):
        cid = f"C{label:02d}"
        if cid not in clusters:
            clusters[cid] = {"members": [], "name_tokens": Counter(), "content_types": Counter(),
                             "ratios": Counter(), "mean_dur": 0, "durations": []}
        c = clusters[cid]; item = eagle_items[i]
        c["members"].append(item["eagle_name"])
        c["name_tokens"].update(re.findall(r'[a-z]{3,}', item["eagle_name"].lower()))
        for ct in item.get("content_types",[]): c["content_types"][ct] += 1
        if item.get("ratio"): c["ratios"][item["ratio"]] += 1
        c["durations"].append(item["duration"])
        c["mean_dur"] += item["duration"]
    
    for cid, c in clusters.items():
        c["size"] = len(c["members"])
        c["mean_dur"] /= max(c["size"], 1)
        top = [t for t,_ in c["name_tokens"].most_common(5) if len(t)>3][:3]
        c["cluster_name"] = " ".join(top) if top else "Misc"
        main_ct = c["content_types"].most_common(1)
        c["main_content_type"] = main_ct[0][0] if main_ct else "unknown"
    
    cluster_out = {}
    for cid, c in clusters.items():
        cluster_out[cid] = {
            "cluster_id": cid,
            "archetype_name": c.get("cluster_name",""),
            "size": c["size"],
            "members": c["members"],
            "content_types": dict(c["content_types"].most_common()),
            "mean_duration": round(c["mean_dur"],1),
            "durations": [round(d,1) for d in sorted(c["durations"])[:10]],
        }
    (OUT / "cluster_results.json").write_text(json.dumps(cluster_out, ensure_ascii=False), encoding="utf-8")
    
    print(f"  Clusters: {len(clusters)}")
    for cid, c in sorted(clusters.items(), key=lambda x: len(x[1]["members"]), reverse=True)[:10]:
        ct = dict(c["content_types"].most_common(2))
        print(f"    {cid}: {c['cluster_name'][:25]:<25} ({c['size']} assets) type={ct}")
    
    # ── Step 5: Attribution ──
    print("\n[5] Attributing FB videos to clusters...")
    
    # For each FB video → vote by top-K Eagle matches
    fb_attribution = []
    for i, item in enumerate(fb_items):
        top_eagle_ids = top_indices[i]
        votes = Counter()
        for j, eid in enumerate(top_eagle_ids):
            label = int(np.where(np.array(eagle_ids) == eid)[0][0]) if eid in eagle_ids else -1
            if label >= 0:
                votes[f"C{eagle_labels[label]:02d}"] += 1
        
        if votes:
            best_cid, best_votes = votes.most_common(1)[0]
            confidence = best_votes / K
        else:
            best_cid = "C00"; confidence = 0
        
        fb_attribution.append({
            "video_id": item["video_id"],
            "creative_name": item.get("creative_name","")[:80],
            "assigned_cluster": best_cid,
            "confidence": round(confidence, 4),
            "top_k_clusters": [c for c,_ in votes.most_common(5)],
            "total_spend": item.get("total_spend", 0),
            "total_revenue": item.get("total_revenue", 0),
        })
    
    (OUT / "attribution_results.json").write_text(json.dumps(fb_attribution, ensure_ascii=False), encoding="utf-8")
    
    high_conf = sum(1 for a in fb_attribution if a["confidence"] >= 0.4)
    coverage = high_conf / max(len(fb_items), 1) * 100
    print(f"  Attributed (>=0.4): {high_conf}/{len(fb_items)} ({coverage:.0f}%)")
    
    # ── Step 6: Performance Aggregation ──
    print("\n[6] Aggregating performance by cluster...")
    
    cluster_perf = defaultdict(lambda: {"fb_videos":[],"eagle_assets":[],"total_spend":0,
        "total_revenue":0,"total_installs":0,"total_impressions":0,"total_clicks":0,"fb_count":0})
    
    for attr in fb_attribution:
        cid = attr["assigned_cluster"]
        cp = cluster_perf[cid]
        cp["fb_videos"].append(attr["video_id"])
        cp["total_spend"] += attr["total_spend"]
        cp["total_revenue"] += attr["total_revenue"]
        cp["fb_count"] += 1
    
    for cid, c in clusters.items():
        if cid in cluster_perf:
            cluster_perf[cid]["eagle_assets"] = c["members"]
    
    total_spend_all = sum(v["total_spend"] for v in fb_items)
    
    # ── Step 7: Archetype Mining ──
    print("\n[7] Mining creative archetypes...")
    
    archetypes = []
    for cid, p in sorted(cluster_perf.items(), key=lambda x: x[1]["total_spend"], reverse=True):
        c = clusters.get(cid, {})
        roas = p["total_revenue"] / max(p["total_spend"], 1)
        spend_share = p["total_spend"] / max(total_spend_all, 1) * 100
        
        # Generate archetype name
        arch_name = c.get("cluster_name", "Unknown")
        ct = c.get("main_content_type", "")
        mean_dur = c.get("mean_dur", 0)
        if ct:
            ct_map = {
                "juesezhanshi": "Character Reveal", "juqing": "Narrative",
                "kaitou": "Hook Opener", "wanfashipin": "Gameplay Loop",
                "wanfazhanshi": "Game Showcase", "changjingzhanshi": "Scene Display",
                "wenzigundong": "Text Scroll", "chongwuzhanshi": "Pet Showcase",
                "hechengwanfa": "Crafting System", "bianshen": "Transformation",
                "fudan": "Plot Twist",
            }
            arch_name = ct_map.get(ct, arch_name)
        
        archetypes.append({
            "cluster_id": cid,
            "archetype_name": f"{arch_name} ({mean_dur:.0f}s)",
            "eagle_asset_count": c.get("size", 0),
            "fb_video_count": p["fb_count"],
            "total_spend": round(p["total_spend"], 2),
            "total_revenue": round(p["total_revenue"], 2),
            "roas": round(roas, 4),
            "spend_share_pct": round(spend_share, 1),
            "main_content_type": ct,
            "mean_duration": round(mean_dur, 1),
        })
    
    archetype_report = {
        "total_fb_videos": len(fb_items),
        "total_eagle_assets": len(eagle_items),
        "total_clusters": len(clusters),
        "coverage_pct": round(coverage, 1),
        "overall_spend": round(total_spend_all, 2),
        "overall_revenue": round(sum(v["total_revenue"] for v in fb_items), 2),
        "overall_roas": round(sum(v["total_revenue"] for v in fb_items) / max(total_spend_all, 1), 4),
        "archetypes": archetypes,
    }
    (OUT / "archetype_report.json").write_text(json.dumps(archetype_report, ensure_ascii=False), encoding="utf-8")
    
    # ── Winner Insights Report ──
    winner_md = """# Creative Intelligence V3 — Winner Insights Report

## Overview
- FB videos analyzed: {fb_count}
- Eagle assets: {eagle_count}
- Clusters: {cluster_count}
- Attribution coverage: {coverage}%
- Total spend: ${total_spend:,.0f}
- Overall ROAS: {roas:.2f}

## Top Winner Archetypes

""".format(
        fb_count=len(fb_items), eagle_count=len(eagle_items),
        cluster_count=len(clusters), coverage=round(coverage,1),
        total_spend=total_spend_all, roas=archetype_report["overall_roas"],
    )
    
    for i, a in enumerate(archetypes[:10]):
        winner_md += f"""### {i+1}. {a['archetype_name']} (Cluster {a['cluster_id']})
| Metric | Value |
|--------|-------|
| Eagle assets | {a['eagle_asset_count']} |
| FB videos | {a['fb_video_count']} |
| Total spend | ${a['total_spend']:,.0f} |
| Total revenue | ${a['total_revenue']:,.0f} |
| ROAS | {a['roas']:.2f} |
| Spend share | {a['spend_share_pct']}% |
| Content type | {a['main_content_type']} |
| Mean duration | {a['mean_duration']:.0f}s |

"""
    
    # Winner vs loser analysis
    winners = [a for a in archetypes if a["total_spend"] > 100 and a["roas"] >= 0.5]
    losers = [a for a in archetypes if a["total_spend"] > 100 and a["roas"] < 0.3]
    
    winner_md += f"""## Winner vs Loser Archetypes

### 🔥 High-Performance ({len(winners)} archetypes)
"""
    for a in winners:
        winner_md += f"- **{a['archetype_name']}**: ${a['total_spend']:,.0f} spend, ROAS {a['roas']:.2f}\n"
    
    winner_md += f"""
### 💤 Low-Performance ({len(losers)} archetypes)
"""
    for a in losers:
        winner_md += f"- **{a['archetype_name']}**: ${a['total_spend']:,.0f} spend, ROAS {a['roas']:.2f}\n"
    
    # Duration insight
    winner_md += f"""\n## Duration Insights
"""
    dur_buckets = defaultdict(lambda: {"spend":0,"rev":0})
    for v in fb_items:
        d = v.get("duration",0)
        b = f"{int(d//10*10)}-{int(d//10*10+9)}s" if d > 0 else "0s"
        dur_buckets[b]["spend"] += v.get("total_spend",0)
        dur_buckets[b]["rev"] += v.get("total_revenue",0)
    
    for b in sorted(dur_buckets.keys()):
        d = dur_buckets[b]
        roas = d["rev"]/max(d["spend"],1)
        winner_md += f"- {b}: ${d['spend']:,.0f} spend, ROAS {roas:.2f}\n"
    
    (OUT / "winner_insights.md").write_text(winner_md, encoding="utf-8")
    
    # ── Print Final Report ──
    print(f"\n{'='*70}")
    print("📊 FINAL REPORT: CREATIVE ARCHETYPE RANKING")
    print(f"{'='*70}")
    print(f"  Coverage: {archetype_report['coverage_pct']}%")
    print(f"  Overall: ${archetype_report['overall_spend']:,.0f} spend, ROAS {archetype_report['overall_roas']:.2f}")
    print()
    print(f"{'Rank':>4} | {'Archetype':<35} | {'Eagle':>5} | {'FB':>5} | {'Spend':>10} | {'Revenue':>10} | {'ROAS':>5} | {'Share':>6}")
    print(f"{'-'*4}-+-{'-'*35}-+-{'-'*5}-+-{'-'*5}-+-{'-'*10}-+-{'-'*10}-+-{'-'*5}-+-{'-'*6}")
    for a in archetypes[:15]:
        print(f"{a['cluster_id']:>4} | {a['archetype_name'][:35]:<35} | {a['eagle_asset_count']:>5} | {a['fb_video_count']:>5} | ${a['total_spend']:>8,.0f} | ${a['total_revenue']:>8,.0f} | {a['roas']:>5.2f} | {a['spend_share_pct']:>5.1f}%")
    
    print(f"\n🔥 TOP 5 WINNER ARCHETYPES (by score = spend*roas):")
    scored = sorted(archetypes, key=lambda a: a["total_spend"] * a["roas"], reverse=True)[:5]
    for i, a in enumerate(scored, 1):
        score = a["total_spend"] * a["roas"]
        print(f"  {i}. {a['archetype_name']}: ${a['total_spend']:,.0f} spend × ROAS {a['roas']:.2f} = score {score:,.0f}")
    
    print(f"\n💤 LOWEST PERFORMANCE (ROAS < 0.3):")
    for a in losers[:5]:
        print(f"  {a['archetype_name']}: ${a['total_spend']:,.0f} spend, ROAS {a['roas']:.2f}")
    
    print(f"\n✅ Output files ({OUT}):")
    for f in ["embeddings.json","faiss_index.npz","similarity_results.json",
              "cluster_results.json","attribution_results.json","archetype_report.json",
              "winner_insights.md"]:
        p = OUT / f
        print(f"  {f} ({p.stat().st_size/1024:.0f} KB)" if p.exists() else f"  {f} (missing)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
