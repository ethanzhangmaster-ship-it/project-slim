"""Creative Factory V2 — Phase 1 主入口。

统一串起：Winner DNA -> Reference Image -> Image Generator V2 -> 50 张变体 -> 统一输出。

设计与验收约束：
- 不修改任何现有系统（ua_renderer / hybrid_renderer / golden_sample_verify / creative_image_gen）。
- 参考图校验失败必须抛异常（ReferenceError），绝不回退 text2img。
- 输出结构：output/creative_factory/batch_xxx/creatives/*.png + batch_metadata.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from market_ops.creative_intelligence.factory.dna.winner_dna_loader import (  # noqa: E402
    WinnerDNALoader,
)
from market_ops.creative_intelligence.factory.dna.dna_mutator import (  # noqa: E402
    DNAMutator,
)
from market_ops.creative_intelligence.factory.generation_context import (  # noqa: E402
    GenerationContext,
    find_project_root,
)
from market_ops.creative_intelligence.factory.generation.image_generator_v2 import (  # noqa: E402
    ImageGeneratorV2,
)
from market_ops.creative_intelligence.factory.reference.reference_manager import (  # noqa: E402
    ReferenceManager,
)
from market_ops.creative_intelligence.factory.ranking.creative_ranker import (  # noqa: E402
    CreativeRanker,
)


class CreativeFactory:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        root = find_project_root()
        self.factory_root = Path(output_dir) if output_dir else root / "output" / "creative_factory"
        self.factory_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def generate(
        self,
        winner_id: str,
        count: int = 50,
        dry_run: bool = False,
        model: str | None = None,
        use_mutation: bool = False,
        rank: bool = False,
        top_k: int = 10,
        clip_mode: str = "auto",
    ) -> dict[str, Any]:
        """生成一批基于某 winner 的创意变体。

        Phase 1（默认）: Winner DNA -> Reference -> ImageGeneratorV2 -> count 张
        Phase 2（use_mutation=True）: Winner DNA -> Mutation Engine -> count 个 DNA
            变体 -> ImageGeneratorV2（逐张绑定变异）-> [可选 rank] CLIP 排序 -> TOP-K

        Args:
            use_mutation: 启用 DNA Mutation Engine（Phase 2 核心开关）
            rank: 启用 CLIP 相似度 + 综合排序并产出 production_candidates
            top_k: 排序后保留的候选数（默认 10）
            clip_mode: "auto" | "openclip" | "clip" | "heuristic"
        Returns:
            包含 batch_dir / reference_status / creatives 的结果字典；
            若 rank=True 额外含 ranking 摘要。
        Raises:
            KeyError: winner_id 不存在
            ReferenceError: 参考图不可达 / 损坏（禁止回退）
        """
        loader = WinnerDNALoader()
        winner = loader.load_winner(winner_id)

        context = GenerationContext(
            project_id="P04",
            winner_id=winner_id,
            winner_code=winner["winner_code"],
            winner_dna=winner,
            generation_count=count,
            output_dir=self.factory_root,
            metadata={"dry_run": dry_run, "model": model, "use_mutation": use_mutation},
        )

        # 2) Reference
        if dry_run:
            cache_dir = self.factory_root / "reference_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            placeholder = cache_dir / f"winner_{winner['winner_code']}.png"
            self._write_placeholder_reference(placeholder)
            reference = {
                "path": str(placeholder),
                "url": "dry-run",
                "status": "available (dry-run)",
            }
            reference_status = "available (dry-run)"
        else:
            cache_dir = self.factory_root / "reference_cache"
            manager = ReferenceManager(cache_dir)
            reference = manager.get_reference(winner)  # 失败即抛 ReferenceError
            reference_status = reference["status"]

        # 2.5) Mutation Engine（Phase 2）
        variants: list[dict[str, Any]] | None = None
        if use_mutation:
            mutator = DNAMutator()
            variants = mutator.mutate(winner, count=count)
            generation_mode = "dna_mutation"
        else:
            generation_mode = "reference_mutation"

        # 3) Generate
        generator = ImageGeneratorV2(dry_run=dry_run)
        batch = generator.generate(context, reference, count, dna_variants=variants)

        # 4) Persist batch metadata
        batch_dir = Path(batch["batch_dir"])
        batch_metadata = {
            "batch_id": batch["batch_id"],
            "project_id": context.project_id,
            "winner_id": winner_id,
            "winner_code": winner["winner_code"],
            "generation_mode": generation_mode,
            "reference_image": f"winner_{winner['winner_code']}.png",
            "reference_status": reference_status,
            "reference_url": reference.get("url", ""),
            "generation_count": count,
            "model": batch["model"],
            "dry_run": dry_run,
            "use_mutation": use_mutation,
            "created_at": datetime.now().isoformat(),
            "dna": {
                "subject": winner.get("subject", ""),
                "theme": winner.get("theme", ""),
                "palette": winner.get("palette", ""),
                "composition": winner.get("composition", ""),
                "overlay_text": winner.get("overlay_text", ""),
                "hook_type": winner.get("hook_type", ""),
            },
            "creatives": batch["creatives"],
        }
        if variants is not None:
            batch_metadata["mutations"] = variants
            batch_metadata["mutation_count"] = len(variants)
            batch_metadata["mutations_unique"] = len(
                {tuple(sorted(v["dna"].items())) for v in variants}
            ) == len(variants)
        meta_path = batch_dir / "batch_metadata.json"
        meta_path.write_text(
            json.dumps(batch_metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 5) Ranking + TOP-K 产出（Phase 2）
        ranking_summary: dict[str, Any] | None = None
        if rank and variants is not None:
            ranker = CreativeRanker(
                clip_mode=clip_mode, embeddings_dir=batch_dir / "embeddings"
            )
            ranking = ranker.rank(winner, batch["creatives"], reference, top_k=top_k)
            ranking_summary = self._export_production_candidates(
                batch_dir, ranking, batch["creatives"], winner_id, winner["winner_code"],
                variants, reference=reference, winner=winner,
            )

        return {
            "batch_id": batch["batch_id"],
            "batch_dir": str(batch_dir),
            "reference_status": reference_status,
            "generation_count": count,
            "generation_mode": generation_mode,
            "ready": sum(1 for c in batch["creatives"] if c["status"] == "ready"),
            "creatives": batch["creatives"],
            "ranking": ranking_summary,
        }

    # ------------------------------------------------------------------
    def _export_production_candidates(
        self,
        batch_dir: Path,
        ranking: dict[str, Any],
        creatives: list[dict[str, Any]],
        winner_id: str,
        winner_code: str,
        variants: list[dict[str, Any]],
        reference: dict[str, Any] | None = None,
        winner: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """写入 production_candidates/：TOP0k.png + ranking.json + mutation_report.json
        + TOP10_<mode>.json（双模式对比）+ reports/phase2_clip_report.html。
        """
        import numpy as np
        from shutil import copyfile

        from market_ops.creative_intelligence.factory.ranking.clip_report import (
            build_clip_report_html,
        )
        from market_ops.creative_intelligence.factory.ranking.creative_ranker import (
            CreativeRanker,
        )

        prod_dir = batch_dir / "production_candidates"
        prod_dir.mkdir(parents=True, exist_ok=True)
        reports_dir = batch_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        by_id = {c["creative_id"]: c for c in creatives}
        mode = ranking["clip_mode"]
        top = ranking["candidates"]
        top_ids = [c["creative_id"] for c in top]

        # TOP-K 图片（copy 真实/占位图）
        for rank_pos, cid in enumerate(top_ids, start=1):
            src = by_id[cid].get("file", "")
            dst = prod_dir / f"TOP{rank_pos:02d}.png"
            try:
                if src and Path(src).exists():
                    copyfile(src, dst)
            except Exception:
                pass

        # 候选导出结构（Phase 2.1 字段）
        def _cand(c, i):
            return {
                "rank": i + 1,
                "id": c["creative_id"],
                "mutation_id": c["mutation_id"],
                "score": c["final_score"],
                "ranking_mode": c["ranking_mode"],
                "clip_similarity": c["clip_similarity"],
                "dna_score": c["dna_score"],
                "visual_score": c["visual_score"],
                "diversity_score": c["diversity_score"],
                "final_score": c["final_score"],
                "mutation": c.get("mutation_reason", ""),
                "dna": c["dna"],
            }

        # ranking.json（主模式）
        ranking_json = {
            "winner": winner_id,
            "winner_code": winner_code,
            "clip_mode": mode,
            "top_k": ranking["top_k"],
            "composition_clusters": ranking["composition_clusters"],
            "candidates": [_cand(c, i) for i, c in enumerate(top)],
        }
        (prod_dir / "ranking.json").write_text(
            json.dumps(ranking_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # TOP10_<mode>.json
        (prod_dir / f"TOP10_{mode}.json").write_text(
            json.dumps(ranking_json["candidates"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 双模式对比：真实模式下额外产出 heuristic TOP10
        comparison = None
        if mode != "heuristic" and winner is not None:
            heur = CreativeRanker(
                clip_mode="heuristic", embeddings_dir=batch_dir / "embeddings"
            ).rank(winner, creatives, reference, top_k=ranking["top_k"])
            heur_ids = [c["creative_id"] for c in heur["candidates"]]
            heur_json = {
                "winner": winner_id,
                "winner_code": winner_code,
                "clip_mode": "heuristic",
                "top_k": heur["top_k"],
                "candidates": [_cand(c, i) for i, c in enumerate(heur["candidates"])],
            }
            (prod_dir / "TOP10_heuristic.json").write_text(
                json.dumps(heur_json["candidates"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            overlap = len(set(top_ids) & set(heur_ids))
            comparison = {"mode_a": mode, "mode_b": "heuristic", "overlap": overlap}

        # mutation_report.json
        dim_counter: dict[str, int] = {}
        for v in variants:
            reason = v.get("mutation_reason", "")
            for dim in ("reward", "composition", "background", "color", "hook"):
                if f"{dim}:" in reason:
                    dim_counter[dim] = dim_counter.get(dim, 0) + 1
        mutation_report = {
            "winner": winner_id,
            "winner_code": winner_code,
            "total_variants": len(variants),
            "unique": ranking.get("composition_clusters", 0) >= 1,
            "composition_clusters": ranking["composition_clusters"],
            "mutations_by_dimension": dim_counter,
            "top_mutation_summary": [
                {
                    "rank": i + 1,
                    "mutation_id": c["mutation_id"],
                    "reason": c.get("mutation_reason", ""),
                    "final_score": c["final_score"],
                }
                for i, c in enumerate(top)
            ],
        }
        (prod_dir / "mutation_report.json").write_text(
            json.dumps(mutation_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 相似度统计
        sims = [c["clip_similarity"] for c in ranking.get("all_scores", top)]
        sim_arr = np.array(sims, dtype=np.float32)
        sim_stats = {
            "min": float(sim_arr.min()),
            "max": float(sim_arr.max()),
            "mean": float(sim_arr.mean()),
            "std": float(sim_arr.std()),
        }

        # 视觉验证 HTML 报告
        report_cands = []
        for i, cid in enumerate(top_ids):
            c = by_id[cid]
            src_cand = next(x for x in top if x["creative_id"] == cid)
            report_cands.append(
                {
                    "rank": i + 1,
                    "creative_id": cid,
                    "image_path": c.get("file", ""),
                    "clip_similarity": src_cand["clip_similarity"],
                    "final_score": src_cand["final_score"],
                    "mutation_reason": c.get("mutation_reason", ""),
                }
            )
        winner_img = reference.get("path") if reference else None
        html = build_clip_report_html(
            winner_img, winner_id, report_cands, mode, sim_stats, comparison
        )
        (reports_dir / "phase2_clip_report.html").write_text(html, encoding="utf-8")

        return {
            "clip_mode": mode,
            "top_k": len(top),
            "composition_clusters": ranking["composition_clusters"],
            "similarity_stats": sim_stats,
            "comparison": comparison,
            "production_candidates_dir": str(prod_dir),
            "report_path": str(reports_dir / "phase2_clip_report.html"),
            "top_ids": top_ids,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _write_placeholder_reference(path: Path) -> None:
        from PIL import Image

        if path.exists():
            return
        img = Image.new("RGB", (1080, 1080), (60, 40, 90))
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
