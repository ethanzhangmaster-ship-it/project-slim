"""Creative Loop - 7步编排器 (DEPRECATED)
Use market_ops.creative_growth_loop.13_scheduler.daily_runner instead.
"""
from __future__ import annotations

from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop.13_scheduler.daily_runner")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from .pattern_engine import PatternEngine, ImagePattern
from .mutation_engine import MutationEngine, Mutation
from .prompt_builder import PromptBuilder, VariantPrompt
from .image_generator import ImageGenerator, GeneratedImage
from .image_validator import ImageValidator, ValidationResult
from .scoring_engine import ScoringEngine, ImageScore
from .library_manager import LibraryManager, WinnerRecord


@dataclass
class LoopResult:
    run_id: str
    generation_round: int
    total_mutations: int
    total_images: int
    valid_images: int
    scored_images: int
    promoted_winners: int
    avg_score: float
    top_score: float
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generation_round": self.generation_round,
            "total_mutations": self.total_mutations,
            "total_images": self.total_images,
            "valid_images": self.valid_images,
            "scored_images": self.scored_images,
            "promoted_winners": self.promoted_winners,
            "avg_score": self.avg_score,
            "top_score": self.top_score,
            "errors": self.errors,
        }


class CreativeLoop:
    CLIP_SIMILARITY_RANGE = (0.6, 0.85)
    
    def __init__(self, output_dir: str = "output/creative_loop_v2", max_generations: int = 5):
        self.output_dir = Path(output_dir)
        self.max_generations = max_generations
        
        self.pattern_engine = PatternEngine(str(self.output_dir / "patterns"))
        self.mutation_engine = MutationEngine(num_mutations=8)
        self.prompt_builder = PromptBuilder(str(self.output_dir / "prompts"))
        self.image_generator = ImageGenerator(str(self.output_dir / "images"))
        self.scoring_engine = ScoringEngine(str(self.output_dir / "scores"))
        self.library_manager = LibraryManager(str(output_dir))
        
        self.reports_dir = self.output_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def run(self, winner_image_path: str, generations: int = 1) -> List[LoopResult]:
        results: List[LoopResult] = []
        
        current_winner_path = Path(winner_image_path)
        if not current_winner_path.exists():
            raise FileNotFoundError(f"Winner image not found: {winner_image_path}")
        
        print(f"\n{'='*70}")
        print(f"  Creative Loop V2: Real Creative Fission Engine")
        print(f"{'='*70}\n")
        
        for gen in range(1, generations + 1):
            print(f"\n--- Generation {gen} / {generations} ---")
            print(f"  Starting with: {current_winner_path.name}")
            
            result = self._run_single_generation(current_winner_path, gen)
            results.append(result)
            
            if result.promoted_winners > 0:
                winners = self.library_manager.get_latest_winners(1)
                if winners:
                    current_winner_path = Path(winners[0]["image_path"])
                    print(f"  Promoted {result.promoted_winners} winner(s)")
            else:
                print(f"  No winners promoted this generation")
                break
        
        self._save_summary_report(results)
        return results

    def _run_single_generation(self, winner_path: Path, generation: int) -> LoopResult:
        from datetime import datetime
        
        run_id = f"gen_{generation}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        errors: List[str] = []
        
        try:
            print(f"  [1/7] Pattern Engine: Extracting visual DNA...")
            pattern = self.pattern_engine.extract_pattern(winner_path, name=f"winner_gen{generation}")
            print(f"    Subject: {pattern.subject}")
            print(f"    Style: {pattern.style}")
            print(f"    Emotion: {pattern.emotion}")
            
        except Exception as e:
            errors.append(f"Pattern Engine failed: {str(e)}")
            return LoopResult(
                run_id=run_id,
                generation_round=generation,
                total_mutations=0,
                total_images=0,
                valid_images=0,
                scored_images=0,
                promoted_winners=0,
                avg_score=0.0,
                top_score=0.0,
                errors=errors,
            )
        
        try:
            print(f"  [2/7] Mutation Engine: Generating variations...")
            mutations = self.mutation_engine.generate_mutations(pattern)
            print(f"    Generated {len(mutations)} mutations")
            for m in mutations:
                print(f"      - {m.mutation_type.value}: {m.description}")
            
        except Exception as e:
            errors.append(f"Mutation Engine failed: {str(e)}")
            return LoopResult(
                run_id=run_id,
                generation_round=generation,
                total_mutations=0,
                total_images=0,
                valid_images=0,
                scored_images=0,
                promoted_winners=0,
                avg_score=0.0,
                top_score=0.0,
                errors=errors,
            )
        
        try:
            print(f"  [3/7] Prompt Builder: Constructing prompts...")
            prompts = self.prompt_builder.build_prompts(pattern, mutations)
            print(f"    Built {len(prompts)} prompts")
            
        except Exception as e:
            errors.append(f"Prompt Builder failed: {str(e)}")
            return LoopResult(
                run_id=run_id,
                generation_round=generation,
                total_mutations=len(mutations),
                total_images=0,
                valid_images=0,
                scored_images=0,
                promoted_winners=0,
                avg_score=0.0,
                top_score=0.0,
                errors=errors,
            )
        
        try:
            print(f"  [4/7] Image Generator: Creating images...")
            prompts_dict = [p.to_dict() for p in prompts]
            images = self.image_generator.generate_images(prompts_dict, run_id)
            print(f"    Generated {len(images)} images")
            
        except Exception as e:
            errors.append(f"Image Generator failed: {str(e)}")
            return LoopResult(
                run_id=run_id,
                generation_round=generation,
                total_mutations=len(mutations),
                total_images=0,
                valid_images=0,
                scored_images=0,
                promoted_winners=0,
                avg_score=0.0,
                top_score=0.0,
                errors=errors,
            )
        
        try:
            print(f"  [5/7] Image Validator: Filtering invalid images...")
            validator = ImageValidator(str(winner_path))
            image_paths = [img.file_path for img in images]
            validation_results = validator.validate_images(image_paths)
            
            valid_images = [img for img, res in zip(images, validation_results) if res.is_valid]
            invalid_count = len(validation_results) - len(valid_images)
            
            print(f"    Valid: {len(valid_images)}, Invalid: {invalid_count}")
            
            if invalid_count > 0:
                for res in validation_results:
                    if not res.is_valid:
                        print(f"      Rejected: {res.image_path.name} - {res.reason}")
            
        except Exception as e:
            errors.append(f"Image Validator failed: {str(e)}")
            valid_images = images
        
        try:
            print(f"  [6/7] Scoring Engine: Evaluating images...")
            previous_winners = self.library_manager.get_previous_winners()
            images_dict = [img.to_dict() for img in valid_images]
            scores = self.scoring_engine.score_images(images_dict, previous_winners)
            
            avg_score = sum(s.final_score for s in scores) / len(scores) if scores else 0.0
            top_score = max(s.final_score for s in scores) if scores else 0.0
            
            print(f"    Average score: {avg_score:.2f}")
            print(f"    Top score: {top_score:.2f}")
            
            for score in sorted(scores, key=lambda x: x.final_score, reverse=True):
                print(f"      {score.final_score:.2f} - {score.image_path.name}")
            
        except Exception as e:
            errors.append(f"Scoring Engine failed: {str(e)}")
            return LoopResult(
                run_id=run_id,
                generation_round=generation,
                total_mutations=len(mutations),
                total_images=len(images),
                valid_images=len(valid_images),
                scored_images=0,
                promoted_winners=0,
                avg_score=0.0,
                top_score=0.0,
                errors=errors,
            )
        
        try:
            print(f"  [7/7] Library Manager: Promoting winners...")
            winners = self.library_manager.promote_winners(scores, generation)
            print(f"    Promoted {len(winners)} winners (score >= 8.0)")
            
        except Exception as e:
            errors.append(f"Library Manager failed: {str(e)}")
            winners = []
        
        return LoopResult(
            run_id=run_id,
            generation_round=generation,
            total_mutations=len(mutations),
            total_images=len(images),
            valid_images=len(valid_images),
            scored_images=len(scores),
            promoted_winners=len(winners),
            avg_score=avg_score,
            top_score=top_score,
            errors=errors,
        )

    def _save_summary_report(self, results: List[LoopResult]) -> Path:
        from datetime import datetime
        
        summary = {
            "loop_version": "V2 - Real Creative Fission",
            "total_generations": len(results),
            "total_mutations": sum(r.total_mutations for r in results),
            "total_images": sum(r.total_images for r in results),
            "total_valid_images": sum(r.valid_images for r in results),
            "total_winners": sum(r.promoted_winners for r in results),
            "avg_score_across_runs": sum(r.avg_score for r in results) / len(results) if results else 0.0,
            "top_score_across_runs": max(r.top_score for r in results) if results else 0.0,
            "generation_results": [r.to_dict() for r in results],
            "generated_at": datetime.now().isoformat(),
        }
        
        report_path = self.reports_dir / f"loop_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\nSummary report saved to: {report_path}")
        return report_path

    def validate_clip_range(self, generated_path: str) -> bool:
        validator = ImageValidator()
        return validator.validate_clip_similarity(Path(generated_path), self.CLIP_SIMILARITY_RANGE)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Creative Loop V2 - Real Creative Fission Engine")
    parser.add_argument("--winner", required=True, help="Path to the winner image")
    parser.add_argument("--generations", type=int, default=3, help="Number of generations to run")
    parser.add_argument("--output-dir", default="output/creative_loop_v2", help="Output directory")
    
    args = parser.parse_args()
    
    loop = CreativeLoop(output_dir=args.output_dir, max_generations=args.generations)
    results = loop.run(args.winner, generations=args.generations)
    
    print(f"\n{'='*70}")
    print(f"  Creative Loop V2 Complete")
    print(f"{'='*70}")
    for i, result in enumerate(results):
        print(f"\n  Generation {i+1}:")
        print(f"    Mutations: {result.total_mutations}")
        print(f"    Images: {result.total_images}")
        print(f"    Valid: {result.valid_images}")
        print(f"    Winners: {result.promoted_winners}")
        print(f"    Avg Score: {result.avg_score:.2f}")


if __name__ == "__main__":
    main()