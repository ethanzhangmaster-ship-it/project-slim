"""Phase 3.0A: Image Exporter — exports Golden Sample files.

Creates the following output structure:
  output/golden_sample/
    prompt.txt       — human-readable prompt text
    prompt.json      — full prompt data in JSON
    image.png        — the generated image
    report.html      — HTML review report
    quality.json     — quality gate results
    review.json      — human review scores (if provided)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..creative_generation.models.prompt import Prompt, PromptScore
from ..creative_image_pipeline.image_quality_gate import QualityResult


class ImageExporter:
    """Exports Golden Sample files for review and archival."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path("output/golden_sample")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        prompt: Prompt,
        image_path: str,
        quality: QualityResult | None = None,
        review_scores: dict[str, int] | None = None,
        winner_id: str = "",
    ) -> dict[str, str]:
        """Export all Golden Sample files.

        Args:
            prompt: The Prompt object used for generation.
            image_path: Path to the generated image.
            quality: Quality gate result (optional).
            review_scores: Human review scores (optional).
            winner_id: Source winner DNA ID.

        Returns:
            Dict mapping file type to file path.
        """
        files: dict[str, str] = {}

        # prompt.txt
        txt_path = self._output_dir / "prompt.txt"
        self._write_prompt_txt(prompt, txt_path, quality, winner_id)
        files["txt"] = str(txt_path)

        # prompt.json
        json_path = self._output_dir / "prompt.json"
        self._write_prompt_json(prompt, json_path, quality, review_scores, winner_id)
        files["json"] = str(json_path)

        # image.png (copy or link)
        if image_path and Path(image_path).exists():
            import shutil
            img_dest = self._output_dir / "image.png"
            try:
                shutil.copy2(image_path, img_dest)
                files["image"] = str(img_dest)
            except Exception:
                files["image"] = image_path

        # quality.json
        if quality:
            q_path = self._output_dir / "quality.json"
            self._write_quality_json(quality, q_path)
            files["quality"] = str(q_path)

        # report.html
        html_path = self._output_dir / "report.html"
        self._write_report_html(prompt, quality, review_scores, html_path, winner_id, files)
        files["html"] = str(html_path)

        # review.json
        if review_scores:
            r_path = self._output_dir / "review.json"
            self._write_review_json(prompt, review_scores, r_path)
            files["review"] = str(r_path)

        return files

    # ── Writers ──

    def _write_prompt_txt(
        self, prompt: Prompt, path: Path, quality: QualityResult | None, winner_id: str,
    ) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write("========================================\n")
            f.write("  GOLDEN SAMPLE — Prompt\n")
            f.write("========================================\n\n")
            if winner_id:
                f.write(f"Source Winner: {winner_id}\n")
            f.write(f"Prompt ID:     {prompt.prompt_id}\n")
            f.write(f"Model:         {prompt.model}\n")
            f.write(f"Aspect Ratio:  {prompt.aspect_ratio}\n")
            f.write(f"Seed:          {prompt.seed}\n")
            if prompt.score:
                f.write(f"Prompt Score:  {prompt.score.total}\n")
            if quality:
                f.write(f"Quality Gate:  {'PASS' if quality.passed else 'FAIL'}\n")
            f.write("\n--- Positive Prompt ---\n")
            f.write(prompt.positive_prompt)
            f.write("\n\n--- Negative Prompt ---\n")
            f.write(prompt.negative_prompt)
            f.write("\n\n--- Dimensions ---\n")
            f.write(f"Camera:      {prompt.camera}\n")
            f.write(f"Lighting:    {prompt.lighting}\n")
            f.write(f"Composition: {prompt.composition}\n")
            f.write("\n========================================\n")
            f.write(f"Exported: {datetime.now().isoformat()}\n")

    def _write_prompt_json(
        self, prompt: Prompt, path: Path,
        quality: QualityResult | None,
        review_scores: dict[str, int] | None,
        winner_id: str,
    ) -> None:
        data = prompt.to_dict()
        data["winner_id"] = winner_id
        data["exported_at"] = datetime.now().isoformat()

        if quality:
            data["quality_gate"] = {
                "passed": quality.passed,
                "score": quality.score,
                "checks": [
                    {"name": c.name, "passed": c.passed, "detail": c.detail}
                    for c in quality.checks
                ],
            }

        if review_scores:
            data["human_review"] = review_scores

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _write_quality_json(self, quality: QualityResult, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "passed": quality.passed,
                "score": quality.score,
                "image_path": quality.image_path,
                "checks": [
                    {"name": c.name, "passed": c.passed, "detail": c.detail, "weight": c.weight}
                    for c in quality.checks
                ],
                "checked_at": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)

    def _write_review_json(
        self, prompt: Prompt, review_scores: dict[str, int], path: Path,
    ) -> None:
        avg = sum(review_scores.values()) / max(len(review_scores), 1)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "prompt_id": prompt.prompt_id,
                "scores": review_scores,
                "average": round(avg, 1),
                "reviewed_at": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)

    def _write_report_html(
        self, prompt: Prompt, quality: QualityResult | None,
        review_scores: dict[str, int] | None,
        path: Path, winner_id: str, files: dict[str, str],
    ) -> None:
        score_html = ""
        if prompt.score:
            score_html = self._render_score_table(prompt.score)

        quality_html = ""
        if quality:
            quality_html = self._render_quality_table(quality)

        review_html = ""
        if review_scores:
            review_html = self._render_review_table(review_scores)

        image_tag = ""
        if files.get("image"):
            image_tag = f'<img src="image.png" style="max-width:400px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);" alt="Golden Sample">'

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Golden Sample — {winner_id or prompt.prompt_id}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#0f0f1a; color:#e0e0e0; padding:24px; }}
h1 {{ color:#c084fc; font-size:24px; margin-bottom:8px; }}
h2 {{ color:#a78bfa; font-size:18px; margin:24px 0 12px; border-bottom:1px solid #2d2d4a; padding-bottom:6px; }}
.meta {{ color:#888; font-size:13px; margin-bottom:16px; }}
.card {{ background:#1a1a2e; border-radius:12px; padding:20px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.3); }}
.prompt-text {{ background:#0d0d1a; border:1px solid #2d2d4a; border-radius:8px; padding:16px; font-family:monospace; font-size:14px; line-height:1.6; white-space:pre-wrap; color:#c4b5fd; }}
.neg-text {{ background:#1a0d0d; border:1px solid #4a2d2d; border-radius:8px; padding:16px; font-family:monospace; font-size:13px; line-height:1.6; white-space:pre-wrap; color:#fca5a5; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th {{ text-align:left; padding:8px 12px; color:#888; font-weight:600; border-bottom:1px solid #2d2d4a; }}
td {{ padding:8px 12px; border-bottom:1px solid #1a1a2e; }}
.pass {{ color:#4ade80; font-weight:700; }}
.fail {{ color:#f87171; font-weight:700; }}
.score-bar {{ height:8px; border-radius:4px; background:#2d2d4a; overflow:hidden; margin-top:4px; }}
.score-fill {{ height:100%; border-radius:4px; background:linear-gradient(90deg,#c084fc,#818cf8); }}
.review-score {{ text-align:center; font-size:32px; font-weight:800; color:#c084fc; }}
.golden-badge {{ display:inline-block; background:linear-gradient(135deg,#f59e0b,#d97706); color:#000; padding:4px 12px; border-radius:6px; font-size:13px; font-weight:700; margin-left:8px; }}
</style>
</head>
<body>
<h1>Golden Sample <span class="golden-badge">PASS</span></h1>
<div class="meta">Winner: {winner_id} | Prompt: {prompt.prompt_id} | Model: {prompt.model} | {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>

{image_tag}

<h2>Prompt</h2>
<div class="card">
<div class="prompt-text">{prompt.positive_prompt}</div>
</div>

<h2>Negative Prompt</h2>
<div class="card">
<div class="neg-text">{prompt.negative_prompt}</div>
</div>

<h2>Prompt Score</h2>
{score_html}

<h2>Quality Gate</h2>
{quality_html}

<h2>Human Review</h2>
{review_html}
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def _render_score_table(self, score: PromptScore) -> str:
        rows = ""
        for dim in ["gameplay", "composition", "hook", "reward", "brand", "readability", "novelty", "diversity"]:
            val = getattr(score, dim, 0)
            color = "#4ade80" if val >= 80 else ("#fbbf24" if val >= 60 else "#f87171")
            rows += f"""<tr>
<td>{dim.title()}</td>
<td style="color:{color};font-weight:600;">{val}</td>
<td><div class="score-bar"><div class="score-fill" style="width:{val}%"></div></div></td>
</tr>"""
        return f"""<div class="card">
<table>
<tr><th>Dimension</th><th>Score</th><th>Bar</th></tr>
{rows}
<tr><td style="font-weight:700;color:#c084fc;">TOTAL</td><td style="font-weight:700;color:#c084fc;">{score.total}</td><td><div class="score-bar"><div class="score-fill" style="width:{score.total}%"></div></div></td></tr>
</table>
</div>"""

    def _render_quality_table(self, quality: QualityResult) -> str:
        rows = ""
        for c in quality.checks:
            status = '<span class="pass">PASS</span>' if c.passed else '<span class="fail">FAIL</span>'
            rows += f"<tr><td>{c.name}</td><td>{status}</td><td style='color:#888;font-size:13px;'>{c.detail}</td></tr>"
        overall = '<span class="pass">PASS</span>' if quality.passed else '<span class="fail">FAIL</span>'
        return f"""<div class="card">
<table>
<tr><th>Check</th><th>Result</th><th>Detail</th></tr>
{rows}
<tr><td style="font-weight:700;">OVERALL</td><td>{overall}</td><td>Score: {quality.score}</td></tr>
</table>
</div>"""

    def _render_review_table(self, review_scores: dict[str, int]) -> str:
        if not review_scores:
            return '<div class="card"><p style="color:#888;">No review scores yet</p></div>'
        rows = ""
        for dim, score in review_scores.items():
            color = "#4ade80" if score >= 8 else ("#fbbf24" if score >= 5 else "#f87171")
            rows += f"<tr><td>{dim}</td><td style='color:{color};font-weight:600;'>{score}/10</td></tr>"
        avg = sum(review_scores.values()) / max(len(review_scores), 1)
        return f"""<div class="card">
<div class="review-score">{avg:.1f} / 10</div>
<table>
<tr><th>Dimension</th><th>Score</th></tr>
{rows}
</table>
</div>"""