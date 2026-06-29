"""AI 创意闭环: 分析 → 出图 → 评分 → 入库 → 验证

Usage:
    python -m market_ops.creative_closed_loop \\
        --game "P04 Witch" \\
        --max-prompts 6 \\
        --output-dir output/creative_loop

Flow:
    1. 加载 creative_library.csv 中的图片素材数据
    2. CreativeDNA 分析 → 提取赢家模式
    3. PromptForge → 生成 AI 出图提示词
    4. CreativeImageGenerator → 生成图片 (mock / Lovart / DALL-E)
    5. CreativeImageScorer → AI 质量评分 → 淘汰低分 → 重新生成
    6. 输出报告 + 入库清单
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from market_ops.creative_dna import (
    CreativeDnaBuilder,
    CreativeDnaItem,
)
from market_ops.creative_image_gen import (
    CreativeImageGenerator,
    GenerationBatch,
)
from market_ops.creative_image_scorer import (
    CreativeImageScorer,
    ScoreBatch,
    print_score_report,
    save_score_report,
)
from market_ops.creative_prompt_forge import (
    CreativePromptForge,
    ImagePrompt,
    PromptBatch,
    save_prompt_batch,
)
from market_ops.creative_winner_reader import WinnerVisualDnaReader
from market_ops.models import CreativeAssetRow


# ---------------------------------------------------------------------------
# Closed Loop Result
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class LoopResult:
    """Complete output of one creative closed-loop cycle."""

    cycle_id: str
    project: str
    run_at: str

    # Stage outputs
    dna_summary: dict[str, Any]
    prompt_count: int
    image_count: int

    # Paths
    dna_csv_path: str
    prompt_json_path: str
    generation_manifest_path: str
    library_update_path: str

    # Quality gates
    passed_quality_gate: bool
    warnings: list[str]

    # Optional paths
    score_report_path: str = ""

    # Scoring
    score_passed: int = 0
    score_rejected: int = 0
    score_avg: float = 0.0
    regenerate_rounds: int = 0


# ---------------------------------------------------------------------------
# Closed Loop Orchestrator
# ---------------------------------------------------------------------------
class CreativeClosedLoop:
    """Orchestrates the full AI creative generation cycle.

    Cycle:
        CreativeLibrary CSV → DNA Analysis → Prompt Forge → Image Gen → Library Update
    """

    def __init__(
        self,
        game: str = "P04 Witch",
        creative_csv_path: str = "output/normalized/creative_library.csv",
        output_dir: str = "output/creative_loop",
        image_api_key: str | None = None,
        image_model: str = "dall-e-3",
        use_lovart: bool = True,  # default to Lovart
        score_threshold: float = 6.0,
        max_regenerate_rounds: int = 2,
    ) -> None:
        self._game = game
        self._csv_path = Path(creative_csv_path)
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._prompt_forge = CreativePromptForge(game=game)
        self._image_gen = CreativeImageGenerator(
            output_dir=self._output_dir / "images",
            api_key=image_api_key,
            model=image_model,
            use_lovart=use_lovart,
        )
        self._scorer = CreativeImageScorer(
            api_key=image_api_key,  # reuse OpenAI key for vision scoring fallback
            threshold=score_threshold,
            use_lovart=use_lovart,
        )
        self._score_threshold = score_threshold
        self._max_regenerate = max_regenerate_rounds

    # ----- public API -----

    def run(
        self,
        max_prompts: int = 8,
        image_size: str = "1024x1792",
        dry_run: bool = False,
    ) -> LoopResult:
        """Execute one full creative generation cycle with scoring."""
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        warnings: list[str] = []

        print(f"\n{'='*60}")
        print(f"  AI Creative Closed Loop | {self._game}")
        print(f"  Cycle: {cycle_id}")
        print(f"{'='*60}\n")

        # ---- Stage 1: Load creative data ----
        print("[1/5] Loading creative library...")
        creative_rows = self._load_creative_rows()
        image_rows = [r for r in creative_rows if not self._is_video(r)]
        print(f"      Loaded {len(creative_rows)} creatives, {len(image_rows)} images")

        if not image_rows:
            warnings.append("No image creatives found in CSV")
            return self._empty_result(cycle_id, warnings)

        # ---- Stage 2: DNA Analysis ----
        print("[2/5] Analyzing winning patterns (CreativeDNA)...")
        dna_summary = self._analyze_dna(image_rows)
        top_patterns = dna_summary.get("top_patterns", [])
        print(f"      Found {len(top_patterns)} winning patterns")
        for pat in top_patterns[:5]:
            print(f"        {pat.get('hook_type','?')}/{pat.get('emotion','?')} "
                  f"count={pat.get('count',0)} avg_roi={pat.get('avg_roi',0):.3f} "
                  f"score={pat.get('score',0):.3f}")

        # ---- Stage 3: Prompt Forge ----
        print(f"[3/5] Forging AI prompts (max {max_prompts})...")
        prompt_batch = self._prompt_forge.forge_from_csv(image_rows, max_prompts=max_prompts)
        prompt_path = save_prompt_batch(prompt_batch, self._output_dir / "prompts")
        print(f"      Generated {prompt_batch.total_prompts} prompts")
        print(f"      Saved to: {prompt_path}")

        for p in prompt_batch.prompts:
            print(f"        [{p.hook_type}/{p.emotion}] {p.prompt_text[:80]}...")

        if dry_run:
            print("\n      DRY RUN - skipping image generation")
            return LoopResult(
                cycle_id=cycle_id,
                project=self._game,
                run_at=datetime.now().isoformat(),
                dna_summary=dna_summary,
                prompt_count=prompt_batch.total_prompts,
                image_count=0,
                dna_csv_path="",
                prompt_json_path=str(prompt_path),
                generation_manifest_path="",
                library_update_path="",
                passed_quality_gate=True,
                warnings=warnings,
            )

        # ---- Stage 4: Image Generation ----
        print(f"[4/5] Generating images ({self._image_gen.active_backend.upper()})...")
        gen_batch = self._image_gen.generate(
            prompts=[asdict(p) for p in prompt_batch.prompts],
            project=self._game,
            size=image_size,
        )
        print(f"      Generated {gen_batch.total_images} images")
        print(f"      Manifest: {gen_batch.manifest_path}")

        # ---- Stage 4.5: Quality Scoring + Regeneration Loop ----
        print(f"[4.5/5] Scoring images (threshold={self._score_threshold:.1f}, "
              f"backend={self._scorer.active_backend})...")

        all_passed_images = []
        current_prompts = [asdict(p) for p in prompt_batch.prompts]
        current_batch = gen_batch
        score_report_path = ""
        total_regenerate_rounds = 0
        total_score_passed = 0
        total_score_rejected = 0
        total_score_avg = 0.0
        score_count = 0

        for round_num in range(self._max_regenerate + 1):
            # Score current batch
            score_input = []
            for img in current_batch.images:
                score_input.append({
                    "file_path": img.file_path,
                    "prompt_used": img.prompt_used,
                    "model": img.model,
                    "image_id": img.image_id,
                    "hook_type": img.hook_type,
                })

            score_batch = self._scorer.score_batch(score_input, project=self._game)
            print_score_report(score_batch)

            # Save report
            report_path = save_score_report(
                score_batch,
                self._output_dir / f"scores_{cycle_id}_r{round_num}.json",
            )
            if round_num == 0:
                score_report_path = str(report_path)

            # Collect passed images
            for s in score_batch.scores:
                if s.passed:
                    all_passed_images.append(s)

            total_score_passed += score_batch.total_passed
            total_score_rejected += score_batch.total_rejected
            total_score_avg += score_batch.avg_overall
            score_count += 1

            # Check if we should regenerate
            rejected = self._scorer.get_rejected_prompts(score_batch)
            if not rejected or round_num >= self._max_regenerate:
                if rejected and round_num >= self._max_regenerate:
                    print(f"      Max regeneration rounds reached, keeping {len(rejected)} below-threshold images")
                break

            # Build improved prompts from rejection feedback
            total_regenerate_rounds += 1
            print(f"      Round {round_num + 1}: Regenerating {len(rejected)} rejected images...")
            regen_prompts = []
            for rej in rejected:
                improved_prompt = rej["prompt"]
                if rej.get("improvements"):
                    hint = ". ".join(rej["improvements"][:2])
                    improved_prompt = f"{rej['prompt']} -- IMPROVE: {hint}"
                regen_prompts.append({
                    "prompt_id": f"regen_r{round_num+1}_{rej['image_id']}",
                    "prompt_text": improved_prompt,
                    "hook_type": "unknown",
                    "negative_prompt": "",
                    "project": self._game,
                })

            current_batch = self._image_gen.generate(
                prompts=regen_prompts,
                project=self._game,
                size=image_size,
            )
            print(f"      Regenerated {current_batch.total_images} images")

        avg_score = total_score_avg / score_count if score_count else 0.0
        print(f"\n      Score Summary: {total_score_passed} passed, "
              f"{total_score_rejected} rejected, avg={avg_score:.1f}, "
              f"regen_rounds={total_regenerate_rounds}")

        # ---- Stage 5: Library Update ----
        library_path = self._write_library_update(
            cycle_id=cycle_id,
            prompt_batch=prompt_batch,
            gen_batch=gen_batch,
        )
        print(f"      Library update: {library_path}")

        # ---- Quality Gate ----
        passed = self._check_quality(prompt_batch, gen_batch, warnings)

        print(f"\n{'='*60}")
        print(f"  Cycle Complete: {cycle_id}")
        print(f"  Prompts: {prompt_batch.total_prompts}")
        print(f"  Images: {gen_batch.total_images}")
        print(f"  Scored: {total_score_passed} passed / {total_score_rejected} rejected")
        print(f"  Regeneration rounds: {total_regenerate_rounds}")
        print(f"  Quality Gate: {'PASSED' if passed else 'WARNINGS'}")
        if warnings:
            for w in warnings:
                print(f"    \u26a0\ufe0f {w}")
        print(f"{'='*60}\n")

        return LoopResult(
            cycle_id=cycle_id,
            project=self._game,
            run_at=datetime.now().isoformat(),
            dna_summary=dna_summary,
            prompt_count=prompt_batch.total_prompts,
            image_count=gen_batch.total_images,
            dna_csv_path="",
            prompt_json_path=str(prompt_path),
            generation_manifest_path=str(gen_batch.manifest_path),
            library_update_path=str(library_path),
            score_report_path=score_report_path,
            passed_quality_gate=passed,
            warnings=warnings,
            score_passed=total_score_passed,
            score_rejected=total_score_rejected,
            score_avg=round(avg_score, 2),
            regenerate_rounds=total_regenerate_rounds,
        )

    def run_multi_project(
        self,
        projects: list[str],
        max_prompts_per_project: int = 4,
        dry_run: bool = False,
    ) -> dict[str, LoopResult]:
        """Run the loop for multiple projects and return per-project results."""
        results: dict[str, LoopResult] = {}
        for project in projects:
            print(f"\n\u2501\u2501\u2501 {project} \u2501\u2501\u2501")
            self._game = project
            self._prompt_forge.set_game(project)
            results[project] = self.run(
                max_prompts=max_prompts_per_project,
                dry_run=dry_run,
            )
        return results

    def run_winner_fission(
        self,
        max_prompts: int = 6,
        image_size: str = "1024x1792",
        dry_run: bool = False,
    ) -> LoopResult:
        """Run the winner-fission path: real winner images → visual DNA → variation prompts → img2img generation.

        This path replaces the old template-fill-in approach. It reads winner
        images from the local asset folder, uses Lovart to describe their visual
        DNA, then generates variation prompts anchored to each winner's proven
        core features. Generated images use the winner's CDN url as a reference
        attachment for true img2img variation.

        Does NOT read creative_library.csv or run CreativeDNA keyword analysis.
        """
        cycle_id = f"fission_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        warnings: list[str] = []

        print(f"\n{'='*60}")
        print(f"  Winner Fission | {self._game}")
        print(f"  Cycle: {cycle_id}")
        print(f"{'='*60}\n")

        # ---- Stage F1: Load winner visual DNA ----
        print("[F1/4] Reading winner visual DNA...")
        settings = self._load_settings()
        reader = WinnerVisualDnaReader(settings)
        read_result = reader.read(limit=None)

        if read_result.errors:
            for err in read_result.errors[:3]:
                warnings.append(f"Winner reader: {err}")

        if not read_result.items:
            warnings.append(
                "No winner images with valid visual DNA found. "
                "Run scripts/probe_winner_description.py first to populate winner_visual_dna.json."
            )
            return self._empty_result(cycle_id, warnings)

        print(f"      Loaded {len(read_result.items)} winner DNA items "
              f"(cached={read_result.cached}, new={read_result.newly_described})")

        for item in read_result.items:
            dna = item.get("visual_dna") or {}
            print(f"        [{item['creative_name']}] "
                  f"hook={dna.get('hook_type','?')} mood={dna.get('mood','?')} "
                  f"subject={str(dna.get('subject') or '')[:50]}")

        # ---- Stage F2: Forge variation prompts ----
        print(f"[F2/4] Forging variation prompts from real winner DNA (max {max_prompts})...")
        prompt_batch = self._prompt_forge.forge_from_winner_dna(
            winner_items=read_result.items,
            max_prompts=max_prompts,
        )
        prompt_path = save_prompt_batch(prompt_batch, self._output_dir / "prompts")
        print(f"      Generated {prompt_batch.total_prompts} variation prompts")
        print(f"      Saved to: {prompt_path}")

        for p in prompt_batch.prompts:
            has_ref = "📎" if p.reference_image_url else "✗"
            print(f"        {has_ref} [{p.hook_type}] axis={p.variation_axis} | {p.prompt_text[:80]}...")

        if prompt_batch.total_prompts == 0:
            warnings.append("No variation prompts generated from winner DNA")
            return self._empty_result(cycle_id, warnings)

        if dry_run:
            print("\n      DRY RUN - skipping image generation")
            return LoopResult(
                cycle_id=cycle_id,
                project=self._game,
                run_at=datetime.now().isoformat(),
                dna_summary={"winner_count": len(read_result.items)},
                prompt_count=prompt_batch.total_prompts,
                image_count=0,
                dna_csv_path="",
                prompt_json_path=str(prompt_path),
                generation_manifest_path="",
                library_update_path="",
                passed_quality_gate=True,
                warnings=warnings,
            )

        # ---- Stage F3: Image generation with reference images ----
        print(f"[F3/4] Generating variations ({self._image_gen.active_backend.upper()})...")
        gen_batch = self._image_gen.generate(
            prompts=[asdict(p) for p in prompt_batch.prompts],
            project=self._game,
            size=image_size,
        )
        print(f"      Generated {gen_batch.total_images} images")
        print(f"      Manifest: {gen_batch.manifest_path}")

        # ---- Stage F4: Quality scoring ----
        print(f"[F4/4] Scoring images (threshold={self._score_threshold:.1f})...")
        score_input = []
        for img in gen_batch.images:
            score_input.append({
                "file_path": img.file_path,
                "prompt_used": img.prompt_used,
                "model": img.model,
                "image_id": img.image_id,
                "hook_type": img.hook_type,
            })

        score_batch = self._scorer.score_batch(score_input, project=self._game)
        print_score_report(score_batch)
        report_path = save_score_report(
            score_batch,
            self._output_dir / f"scores_{cycle_id}.json",
        )

        # ---- Library update ----
        library_path = self._write_library_update(
            cycle_id=cycle_id,
            prompt_batch=prompt_batch,
            gen_batch=gen_batch,
        )

        # ---- Quality gate ----
        passed = self._check_quality(prompt_batch, gen_batch, warnings, fission=True)

        print(f"\n{'='*60}")
        print(f"  Fission Complete: {cycle_id}")
        print(f"  Source winners: {len(read_result.items)}")
        print(f"  Variation prompts: {prompt_batch.total_prompts}")
        print(f"  Images: {gen_batch.total_images}")
        print(f"  Scored: {score_batch.total_passed} passed / {score_batch.total_rejected} rejected")
        print(f"  Quality Gate: {'PASSED' if passed else 'WARNINGS'}")
        if warnings:
            for w in warnings:
                print(f"    ⚠️ {w}")
        print(f"{'='*60}\n")

        return LoopResult(
            cycle_id=cycle_id,
            project=self._game,
            run_at=datetime.now().isoformat(),
            dna_summary={"winner_count": len(read_result.items)},
            prompt_count=prompt_batch.total_prompts,
            image_count=gen_batch.total_images,
            dna_csv_path="",
            prompt_json_path=str(prompt_path),
            generation_manifest_path=str(gen_batch.manifest_path),
            library_update_path=str(library_path),
            score_report_path=str(report_path),
            passed_quality_gate=passed,
            warnings=warnings,
            score_passed=score_batch.total_passed,
            score_rejected=score_batch.total_rejected,
            score_avg=round(score_batch.avg_overall, 2),
        )

    def _load_settings(self):
        """Lazy-load Settings without importing at module level."""
        from market_ops.config import load_settings
        return load_settings()

    # ----- internal -----

    def _load_creative_rows(self) -> list[CreativeAssetRow]:
        """Load creative rows from CSV."""
        rows: list[CreativeAssetRow] = []
        if not self._csv_path.exists():
            print(f"      WARNING: CSV not found at {self._csv_path}")
            return rows

        with self._csv_path.open("r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                game = (r.get("game") or "").strip()
                if game != self._game:
                    continue
                rows.append(CreativeAssetRow(
                    asset_id=r.get("asset_id", ""),
                    creative_type=r.get("creative_type", ""),
                    video_path=r.get("video_path", ""),
                    game=game,
                    country=r.get("country", "All"),
                    channel=r.get("channel", ""),
                    ctr=float(r.get("ctr") or 0),
                    cvr=float(r.get("cvr") or 0),
                    roas=float(r.get("roas") or 0),
                    spend=float(r.get("spend") or 0),
                    status=r.get("status", ""),
                    hook_type=r.get("hook_type", ""),
                    creative_name=r.get("creative_name", ""),
                    campaign=r.get("campaign", ""),
                    campaign_id=r.get("campaign_id", ""),
                    adgroup=r.get("adgroup", ""),
                    adgroup_id=r.get("adgroup_id", ""),
                    ad_id=r.get("ad_id", ""),
                    ad_name=r.get("ad_name", ""),
                    source_name=r.get("source_name", ""),
                    source_id=r.get("source_id", ""),
                    installs=float(r.get("installs") or 0),
                    conversions=float(r.get("conversions") or 0),
                    revenue_value=float(r.get("revenue_value") or 0),
                ))
        return rows

    @staticmethod
    def _is_video(row: CreativeAssetRow) -> bool:
        text = " ".join([
            row.creative_type or "",
            row.creative_name or "",
            row.hook_type or "",
            row.adgroup or "",
            row.source_name or "",
        ]).lower()
        return "\u89c6\u9891" in text or "video" in text

    def _analyze_dna(self, rows: list[CreativeAssetRow]) -> dict[str, Any]:
        """Run lightweight DNA analysis on image creatives."""
        from collections import defaultdict

        # Aggregate by hook_type + emotion pattern
        pattern_data: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "spend": 0.0, "installs": 0.0, "revenue": 0.0, "ctrs": [], "cvrs": []}
        )

        for row in rows:
            hook = _classify_hook(row)
            emotion = _classify_emotion(row)
            key = (hook, emotion)
            d = pattern_data[key]
            d["count"] += 1
            d["spend"] += row.spend
            d["installs"] += row.installs
            d["revenue"] += row.revenue_value
            if row.ctr > 0:
                d["ctrs"].append(row.ctr)
            if row.cvr > 0:
                d["cvrs"].append(row.cvr)

        # Score each pattern
        patterns = []
        for (hook, emotion), d in pattern_data.items():
            if d["count"] < 2:
                continue
            avg_roi = d["revenue"] / d["spend"] if d["spend"] else 0
            avg_ctr = sum(d["ctrs"]) / len(d["ctrs"]) if d["ctrs"] else 0
            avg_cvr = sum(d["cvrs"]) / len(d["cvrs"]) if d["cvrs"] else 0
            # Score: ROI × 0.5 + CTR × 0.25 + installs_weight × 0.25
            installs_score = min(d["installs"] / 100, 1.0)
            score = avg_roi * 0.5 + avg_ctr * 0.25 * 100 + installs_score * 0.25
            patterns.append({
                "hook_type": hook,
                "emotion": emotion,
                "count": d["count"],
                "total_spend": round(d["spend"], 2),
                "total_installs": round(d["installs"], 2),
                "avg_roi": round(avg_roi, 4),
                "avg_ctr": round(avg_ctr, 4),
                "avg_cvr": round(avg_cvr, 4),
                "score": round(score, 4),
            })

        patterns.sort(key=lambda p: p["score"], reverse=True)

        # Find strongest hook and emotion
        top_hook = patterns[0]["hook_type"] if patterns else "unknown"
        top_emotion = patterns[0]["emotion"] if patterns else "unknown"

        return {
            "total_creatives": len(rows),
            "total_spend": round(sum(r.spend for r in rows), 2),
            "total_installs": round(sum(r.installs for r in rows), 2),
            "pattern_count": len(patterns),
            "top_hook": top_hook,
            "top_emotion": top_emotion,
            "top_patterns": patterns[:10],
        }

    def _check_quality(
        self,
        prompt_batch: PromptBatch,
        gen_batch: GenerationBatch,
        warnings: list[str],
        fission: bool = False,
    ) -> bool:
        """Quality gate checks."""
        if prompt_batch.total_prompts == 0:
            warnings.append("No prompts generated")
            return False

        # Check diversity: at least 2 different hook types (skip for fission —
        # fission varies by visual axis, not hook type, so single-hook is expected)
        if not fission:
            hooks = {p.hook_type for p in prompt_batch.prompts}
            if len(hooks) < 2:
                warnings.append(f"Low hook diversity: only {len(hooks)} types generated")

        # Check generation success
        failed = sum(1 for img in gen_batch.images if not img.ready_for_review)
        if failed > 0:
            warnings.append(f"{failed}/{gen_batch.total_images} images failed generation")

        return len(warnings) == 0

    def _write_library_update(
        self,
        cycle_id: str,
        prompt_batch: PromptBatch,
        gen_batch: GenerationBatch,
    ) -> Path:
        """Write a CSV that can be appended to the creative library."""
        path = self._output_dir / f"library_update_{cycle_id}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "asset_id", "creative_type", "video_path", "game", "country",
                "channel", "ctr", "cvr", "roas", "spend", "status",
                "hook_type", "creative_name", "campaign", "adgroup",
                "ad_id", "ad_name", "source_name", "installs",
                "conversions", "revenue_value",
            ])
            for img in gen_batch.images:
                writer.writerow([
                    img.image_id,
                    "image",
                    img.file_path,
                    self._game,
                    "All",
                    "AI_Generated",
                    0, 0, 0, 0,
                    "PENDING_REVIEW",
                    img.hook_type,
                    f"AI_{img.hook_type}_{img.image_id}",
                    f"AI_Creative_Loop_{cycle_id[:8]}",
                    f"AI_AdGroup_{img.hook_type}",
                    img.image_id,
                    f"AI_Ad_{img.hook_type}",
                    f"AI_Source_{cycle_id[:8]}",
                    0, 0, 0,
                ])
        return path

    def _empty_result(self, cycle_id: str, warnings: list[str]) -> LoopResult:
        return LoopResult(
            cycle_id=cycle_id,
            project=self._game,
            run_at=datetime.now().isoformat(),
            dna_summary={},
            prompt_count=0,
            image_count=0,
            dna_csv_path="",
            prompt_json_path="",
            generation_manifest_path="",
            library_update_path="",
            passed_quality_gate=False,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Hook / Emotion classifiers
# ---------------------------------------------------------------------------
def _classify_hook(row: CreativeAssetRow) -> str:
    text = " ".join([
        row.hook_type or "",
        row.creative_name or "",
        row.adgroup or "",
        row.campaign or "",
    ]).lower()

    if any(w in text for w in ("\u5371\u673a", "rescue", "save", "help", "danger", "fail")):
        return "crisis"
    if any(w in text for w in ("\u723d", "reward", "win", "success", "clear", "level")):
        return "reward"
    if any(w in text for w in ("\u53cd\u8f6c", "twist", "unexpected", "fail")):
        return "twist"
    if any(w in text for w in ("\u5bf9\u6bd4", "before", "after")):
        return "comparison"
    if any(w in text for w in ("\u6536\u96c6", "collect", "collection", "unlock")):
        return "collection"
    if any(w in text for w in ("\u597d\u5947", "mystery", "secret", "hidden")):
        return "curiosity"

    # Default based on creative naming patterns
    if "roas" in text or "purchase" in text:
        return "reward"
    if "re" in text or "t0" in text:
        return "crisis"
    return "reward"


def _classify_emotion(row: CreativeAssetRow) -> str:
    text = " ".join([
        row.hook_type or "",
        row.creative_name or "",
    ]).lower()

    if any(w in text for w in ("anxiety", "\u7126\u8651", "urgent", "danger")):
        return "anxiety"
    if any(w in text for w in ("satisfaction", "\u723d", "win", "reward")):
        return "satisfaction"
    if any(w in text for w in ("healing", "\u6cbb\u6108", "cozy", "relax")):
        return "healing"
    if any(w in text for w in ("curiosity", "\u597d\u5947", "mystery")):
        return "curiosity"
    return "satisfaction"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Creative Closed Loop")
    parser.add_argument("--game", default="P04 Witch", help="Target game project")
    parser.add_argument("--max-prompts", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true", help="Skip image generation")
    parser.add_argument("--api-key", default=None, help="OpenAI API key for DALL-E (legacy)")
    parser.add_argument("--lovart", action="store_true", default=True, help="Use Lovart (nano banana + gpt-2)")
    parser.add_argument("--no-lovart", dest="lovart", action="store_false", help="Disable Lovart, fallback to DALL-E/mock")
    parser.add_argument("--score-threshold", type=float, default=6.0, help="Min score to pass (1-10)")
    parser.add_argument("--max-regen", type=int, default=2, help="Max regeneration rounds for rejected images")
    parser.add_argument("--output-dir", default="output/creative_loop")
    parser.add_argument("--multi", nargs="*", help="Run for multiple projects")
    parser.add_argument("--winner-fission", action="store_true",
                        help="Use winner-fission path: real winner images → visual DNA → img2img variations")

    args = parser.parse_args()

    if args.winner_fission:
        loop = CreativeClosedLoop(
            game=args.game,
            output_dir=args.output_dir,
            image_api_key=args.api_key,
            use_lovart=args.lovart,
            score_threshold=args.score_threshold,
            max_regenerate_rounds=args.max_regen,
        )
        result = loop.run_winner_fission(
            max_prompts=args.max_prompts,
            dry_run=args.dry_run,
        )
        status = "✅" if result.passed_quality_gate else "⚠️"
        print(f"\n  {status} Fission: {result.prompt_count} prompts, "
              f"{result.image_count} images, score={result.score_avg:.1f}")

    elif args.multi:
        loop = CreativeClosedLoop(
            output_dir=args.output_dir,
            image_api_key=args.api_key,
            use_lovart=args.lovart,
            score_threshold=args.score_threshold,
            max_regenerate_rounds=args.max_regen,
        )
        results = loop.run_multi_project(
            projects=args.multi,
            max_prompts_per_project=args.max_prompts,
            dry_run=args.dry_run,
        )
        for proj, result in results.items():
            status = "\u2705" if result.passed_quality_gate else "\u26a0\ufe0f"
            print(f"  {status} {proj}: {result.prompt_count} prompts, {result.image_count} images")
    else:
        loop = CreativeClosedLoop(
            game=args.game,
            output_dir=args.output_dir,
            image_api_key=args.api_key,
            use_lovart=args.lovart,
            score_threshold=args.score_threshold,
            max_regenerate_rounds=args.max_regen,
        )
        result = loop.run(
            max_prompts=args.max_prompts,
            dry_run=args.dry_run,
        )
        status = "\u2705" if result.passed_quality_gate else "\u26a0\ufe0f"
        print(f"\n  {status} {result.project}: {result.prompt_count} prompts, "
              f"{result.image_count} images, score={result.score_avg:.1f}, "
              f"{result.score_passed} passed / {result.score_rejected} rejected")
