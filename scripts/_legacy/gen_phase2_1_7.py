"""Phase 2.1.7 — Step 3: 12 Creative Generation (Lovart) + Step 5 embedding prep.

读取 Step 1 产出的 prompts/creative_prompts.json（人工 review 后可直接改这里），
调用 Lovart 生成 12 张 Facebook UA 创意，并落盘 OpenCLIP embedding 供 Step 5 排序。

关键设计：
  - Winner 参考图先 upload_file 拿到稳定 CDN URL，再作为 attachment 传入（比传本地
    路径更稳；本地路径在 2.1.6.2 实测偶发 "local path cannot be accessed"）。
  - attachment 失败自动回退为无参考生成（flaky 兜底）。
  - 可断点续跑：已存在的 creative_00X.png 跳过，不重复消耗配额。
  - 每张生成后即时保存 embedding（embeddings/creative/creative_00X.npy），
    winner embedding 保存为 embeddings/winner.npy。

用法: python scripts/gen_phase2_1_7.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_ops.clients.lovart import LovartClient, download_image
from market_ops.creative_intelligence.factory.ranking.clip_ranker import OpenCLIPEncoder

OUT = ROOT / "output" / "creative_phase2_1_7"
PROMPTS = OUT / "prompts" / "creative_prompts.json"
IMAGES = OUT / "images"
EMB = OUT / "embeddings"
EMB_C = EMB / "creative"
WINNER = ROOT / "output" / "phase2_1_5" / "real_validation" / "winner_reference" / "winner_001.png"

for d in (IMAGES, EMB, EMB_C):
    d.mkdir(parents=True, exist_ok=True)


def main() -> int:
    if not PROMPTS.exists():
        print(f"[!] {PROMPTS} 不存在。请先运行 gen_phase2_1_7_plans.py (Step 1)。")
        return 1

    prompts = json.loads(PROMPTS.read_text(encoding="utf-8"))

    client = LovartClient()
    if not client.is_configured:
        print("[!] Lovart AK/SK 未配置（LOVART_ACCESS_KEY / LOVART_SECRET_KEY）。")
        return 1

    encoder = OpenCLIPEncoder(device="cpu")

    # Winner embedding（一次编码，供 Step 5 排序复用）
    if WINNER.exists():
        w_emb = encoder.encode_image(str(WINNER))
        np.save(EMB / "winner.npy", w_emb)
        print(f"  [winner] embedding saved -> {EMB / 'winner.npy'}")

    # Winner 参考图上传为 CDN URL（attachment 更稳定）
    winner_cdn = None
    if WINNER.exists():
        try:
            winner_cdn = client.upload_file(WINNER)
            print(f"  [winner] CDN ref ready ({winner_cdn[:60]}...)")
        except Exception as exc:
            print(f"  [winner] upload failed ({exc}); 将以无参考方式生成。")

    order = sorted(prompts.keys())
    done = 0
    skipped = 0
    failed = []

    for cid in order:
        dest = IMAGES / f"{cid}.png"
        emb_dest = EMB_C / f"{cid}.npy"
        if dest.exists() and emb_dest.exists():
            skipped += 1
            print(f"  [skip] {cid} (already generated)")
            continue

        prompt = prompts[cid]["prompt"]
        t0 = time.time()
        result = client.generate_image(prompt, attachments=[winner_cdn] if winner_cdn else None)
        if not result.image_urls and winner_cdn:
            # flaky 兜底：去掉 attachment 重试
            print(f"  [retry] {cid} attachment failed, regenerating without ref...")
            result = client.generate_image(prompt, attachments=None)

        if not result.image_urls:
            print(f"  [FAIL] {cid} no image ({result.status}). {result.assistant_text[:120]}")
            failed.append(cid)
            continue

        download_image(result.image_urls[0], dest)
        emb = encoder.encode_image(str(dest))
        np.save(emb_dest, emb)
        done += 1
        print(f"  [ok] {cid} saved ({time.time() - t0:.0f}s)")

    print("\n=== Step 3 generation summary ===")
    print(f"  generated: {done} | skipped(resume): {skipped} | failed: {len(failed)}")
    if failed:
        print(f"  failed ids: {failed}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
