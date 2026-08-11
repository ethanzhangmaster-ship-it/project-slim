"""Phase 2.1.6 — 产物输出（JSON + HTML）。

输出目录 output/quality_gate/：
  creative_scores.json   全部创意逐维分数
  approved.json          决策 PASS 的创意
  rejected.json          决策 FAIL 的创意（含原因）
  quality_report.html    可视化报告（预览→分数→问题→决策）
  production_gate.json   总 Gate 结果 + 9 项验收
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from creative_quality_gate.models import CreativeScore, GateResult  # noqa: E402


def _b64_img(path: str) -> str:
    try:
        return base64.b64encode(Path(path).read_bytes()).decode()
    except Exception:
        return ""


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def build_outputs(
    scores: list[CreativeScore],
    gate: GateResult,
    out_dir: Path,
    img_dir: Path | None = None,
) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_scores = [s.to_dict() for s in scores]
    approved = [s.to_dict() for s in scores if s.decision == "PASS"]
    rejected = [s.to_dict() for s in scores if s.decision == "FAIL"]

    write_json(out_dir / "creative_scores.json", all_scores)
    write_json(out_dir / "approved.json", approved)
    write_json(out_dir / "rejected.json", rejected)
    write_json(out_dir / "production_gate.json", gate.to_dict())

    html = render_html(scores, gate, img_dir)
    (out_dir / "quality_report.html").write_text(html, encoding="utf-8")

    return {
        "creative_scores.json": str(out_dir / "creative_scores.json"),
        "approved.json": str(out_dir / "approved.json"),
        "rejected.json": str(out_dir / "rejected.json"),
        "quality_report.html": str(out_dir / "quality_report.html"),
        "production_gate.json": str(out_dir / "production_gate.json"),
    }


def render_html(
    scores: list[CreativeScore],
    gate: GateResult,
    img_dir: Path | None = None,
) -> str:
    rows = ""
    for s in scores:
        color = "#1a7f37" if s.decision == "PASS" else "#cf222e"
        badge = "PASS" if s.decision == "PASS" else "FAIL"
        img_tag = ""
        if img_dir is not None:
            p = Path(img_dir) / f"{s.creative_id}.png"
            if p.exists():
                img_tag = (
                    f'<img src="data:image/png;base64,{_b64_img(p)}" '
                    f'style="width:160px;border-radius:8px"/>'
                )
        issues = "<br>".join(f"• {i}" for i in s.issues) or "—"
        pats = (
            f"M={s.merge_score:.2f} E={s.evolution_score:.2f} "
            f"C={s.collection_score:.2f} R={s.reward_score:.2f}"
        )
        rows += f"""
        <div class="card">
          {img_tag}
          <div class="cid">{s.creative_id} <span class="badge" style="background:{color}">{badge}</span></div>
          <div class="ptype">pattern: <b>{s.gameplay_type or '-'}</b> ({s.gameplay_confidence:.2f})</div>
          <div class="ptype">{pats}</div>
          <table>
            <tr><td>Gameplay Und.</td><td>{s.gameplay_understanding:.2f}</td></tr>
            <tr><td>Reward</td><td>{s.reward_visibility:.2f}</td></tr>
            <tr><td>Composition Match</td><td>{s.composition_match:.2f}</td></tr>
            <tr><td>Gameplay Area</td><td>{s.gameplay_area_ratio:.2f}</td></tr>
            <tr><td>Char Attn</td><td>{s.character_attention:.2f}</td></tr>
            <tr><td>State Trans.</td><td>{s.state_transition_score:.2f}</td></tr>
            <tr><td>Action</td><td>{s.action_visibility:.2f}</td></tr>
            <tr><td>Visual</td><td>{s.visual_quality:.2f}</td></tr>
            <tr><td>CLIP</td><td>{s.clip_similarity:.2f}</td></tr>
            <tr><td>Diversity</td><td>{s.diversity:.2f}</td></tr>
            <tr><td>AI Artifact</td><td>{s.ai_artifact_score:.2f}</td></tr>
            <tr><td><b>Production V2</b></td><td><b>{s.production_score:.2f}</b></td></tr>
          </table>
          <div class="issues">{issues}</div>
        </div>"""

    checks = "".join(
        f"<li class=\"{'ok' if v else 'no'}\">[{'PASS' if v else 'FAIL'}] {k}</li>"
        for k, v in gate.checks.items()
    )

    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
body{{font-family:system-ui;background:#f5f5f7;margin:0;padding:24px;color:#222}}
h1{{font-size:20px}} .summary{{background:#fff;border-radius:10px;padding:16px;margin-bottom:16px;
  box-shadow:0 1px 6px rgba(0,0,0,.08)}}
.checks{{background:#fff;border-radius:10px;padding:16px;margin-bottom:16px}}
.checks li.ok{{color:#1a7f37}} .checks li.no{{color:#cf222e}}
.grid{{display:flex;gap:16px;flex-wrap:wrap}}
.card{{background:#fff;border-radius:10px;padding:12px;width:200px;box-shadow:0 1px 6px rgba(0,0,0,.08)}}
.cid{{font-weight:700;margin:8px 0}} .badge{{color:#fff;padding:2px 8px;border-radius:6px;font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}} td{{padding:2px 4px;border-bottom:1px solid #eee}}
.issues{{font-size:12px;color:#cf222e;margin-top:8px}}
.ptype{{font-size:12px;color:#0969da;margin:4px 0}}
</style></head><body>
<h1>Phase 2.1.6.2 — Creative Composition Planner Gate</h1>
<div class="summary">
  Total <b>{gate.total}</b> · Approved <b style="color:#1a7f37">{gate.approved}</b> ·
  Rejected <b style="color:#cf222e">{gate.rejected}</b> ·
  Avg Production Score <b>{gate.avg_production_score:.3f}</b>
</div>
<div class="checks"><b>9-Point Acceptance</b><ul>{checks}</ul></div>
<div class="grid">{rows}</div>
</body></html>"""
