"""Phase 2.1 视觉验证报告生成。

生成自包含的 HTML（图片以 base64 内嵌），展示 Winner 与 TOP10 候选的
缩略图、相似度、突变说明，用于人工快速审视 CLIP 排序质量。
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


def _b64(path: str | Path) -> str:
    try:
        data = Path(path).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    except Exception:
        return ""


def build_clip_report_html(
    winner_img_path: str | Path | None,
    winner_id: str,
    candidates: list[dict[str, Any]],
    ranking_mode: str,
    sim_stats: dict[str, float] | None = None,
    comparison: dict[str, Any] | None = None,
) -> str:
    """candidates: [{rank, creative_id, image_path, clip_similarity, final_score,
    mutation_reason, dna}]"""
    winner_b64 = _b64(winner_img_path) if winner_img_path else ""
    stats = sim_stats or {}
    cards = []
    for c in candidates:
        img = _b64(c.get("image_path", ""))
        cards.append(
            f"""
      <div class="card">
        <div class="rank">#{c.get('rank', '?')}</div>
        <img src="{img}" alt="{c.get('creative_id','')}" />
        <div class="meta">
          <div class="cid">{c.get('creative_id','')}</div>
          <div class="sim">similarity <b>{c.get('clip_similarity', 0):.3f}</b></div>
          <div class="fin">final <b>{c.get('final_score', 0):.3f}</b></div>
          <div class="mut">{c.get('mutation_reason', '')}</div>
        </div>
      </div>"""
        )
    cards_html = "\n".join(cards)

    compare_html = ""
    if comparison:
        overlap = comparison.get("overlap", 0)
        mode_a = comparison.get("mode_a", "openclip")
        mode_b = comparison.get("mode_b", "heuristic")
        compare_html = f"""
      <div class="compare">
        TOP10 重合度（{mode_a} vs {mode_b}）：<b>{overlap}/10</b>
      </div>"""

    stats_html = ""
    if stats:
        stats_html = (
            f"<div class='stats'>similarity min={stats.get('min',0):.3f} "
            f"max={stats.get('max',0):.3f} mean={stats.get('mean',0):.3f} "
            f"std={stats.get('std',0):.4f}</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8" />
<title>Phase 2.1 CLIP Ranking Report — {winner_id}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
         background: #0f1115; color: #e6e6e6; padding: 24px; }}
  h1 {{ font-size: 20px; }}
  .sub {{ color: #9aa; font-size: 13px; margin-bottom: 16px; }}
  .winner {{ display: flex; gap: 16px; align-items: center; background: #1a1d24;
            padding: 16px; border-radius: 12px; margin-bottom: 20px; }}
  .winner img {{ width: 160px; height: 160px; object-fit: cover; border-radius: 8px; }}
  .grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; }}
  .card {{ background: #1a1d24; border-radius: 10px; overflow: hidden; position: relative; }}
  .card img {{ width: 100%; aspect-ratio: 1/1; object-fit: cover; display: block; }}
  .rank {{ position: absolute; top: 6px; left: 6px; background: #ff4d6d; color: #fff;
          font-weight: 700; border-radius: 6px; padding: 2px 8px; font-size: 12px; }}
  .meta {{ padding: 8px 10px; font-size: 12px; }}
  .cid {{ font-weight: 600; margin-bottom: 2px; }}
  .sim b, .fin b {{ color: #6cf; }}
  .mut {{ color: #9aa; margin-top: 4px; line-height: 1.35; }}
  .stats {{ color: #9aa; font-size: 13px; margin: 10px 0; }}
  .compare {{ color: #fd6; font-size: 14px; margin: 10px 0; }}
</style>
</head>
<body>
  <h1>Phase 2.1 — Real CLIP Ranking Validation</h1>
  <div class="sub">winner={winner_id} · ranking_mode={ranking_mode}</div>
  {stats_html}
  {compare_html}
  <div class="winner">
    <img src="{winner_b64}" alt="winner" />
    <div>
      <div style="font-size:16px;font-weight:700;">Winner Reference</div>
      <div class="sub">{winner_id}</div>
    </div>
  </div>
  <div class="grid">
    {cards_html}
  </div>
</body>
</html>"""
