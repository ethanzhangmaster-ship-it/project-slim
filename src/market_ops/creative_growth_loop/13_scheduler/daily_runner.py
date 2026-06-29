"""Daily Runner - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from ..01_collectors.facebook_ads_collector import FacebookAdsCollector
from ..02_performance.winner_engine import WinnerEngine
from ..02_performance.loser_engine import LoserEngine
from ..03_gene.gene_extractor import GeneExtractor
from ..03_gene.gene_memory import GeneMemory, GeneLock
from ..04_mutation.hook_mutator import (
    HookMutator, RewardMutator, EmotionMutator, ProgressMutator, OverlayMutator,
    SubjectMutator, CompositionMutator, CostumeMutator, PoseMutator,
    CameraMutator, LightingMutator, ColorMutator,
)
from ..05_prompt.prompt_builder import PromptBuilder
from ..06_generation.image_generator import ImageGenerator
from ..06_generation.overlay_engine import OverlayEngine
from ..07_validation.similarity_filter import SimilarityFilter, ImageQualityFilter
from ..08_scoring.creative_score_engine import CreativeScoreEngine
from ..09_family.creative_family_engine import CreativeFamilyEngine
from ..11_memory.winner_memory import WinnerMemory, LoserMemory, FamilyTree


@dataclass
class DailyRunResult:
    run_date: str
    total_winners: int
    total_mutations: int
    total_images: int
    valid_images: int
    top_score: float
    avg_score: float
    promoted_winners: int
    families_created: int
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_date": self.run_date,
            "total_winners": self.total_winners,
            "total_mutations": self.total_mutations,
            "total_images": self.total_images,
            "valid_images": self.valid_images,
            "top_score": self.top_score,
            "avg_score": self.avg_score,
            "promoted_winners": self.promoted_winners,
            "families_created": self.families_created,
            "errors": self.errors,
        }


class DailyRunner:
    VARIANTS_PER_RUN = 20
    GENERATIONS = 3
    
    def __init__(
        self,
        output_dir: str = "output/creative_growth_loop",
        config: dict = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or {}
        
        self.fb_collector = FacebookAdsCollector()
        self.winner_engine = WinnerEngine()
        self.loser_engine = LoserEngine()
        self.gene_extractor = GeneExtractor()
        self.gene_memory = GeneMemory()
        self.gene_lock = GeneLock()
        
        self.hook_mutator = HookMutator()
        self.reward_mutator = RewardMutator()
        self.emotion_mutator = EmotionMutator()
        self.progress_mutator = ProgressMutator()
        self.overlay_mutator = OverlayMutator()
        self.subject_mutator = SubjectMutator()
        self.composition_mutator = CompositionMutator()
        self.costume_mutator = CostumeMutator()
        self.pose_mutator = PoseMutator()
        self.camera_mutator = CameraMutator()
        self.lighting_mutator = LightingMutator()
        self.color_mutator = ColorMutator()
        
        self.prompt_builder = PromptBuilder()
        self.image_generator = ImageGenerator()
        self.overlay_engine = OverlayEngine()
        
        self.similarity_filter = SimilarityFilter()
        self.quality_filter = ImageQualityFilter()
        
        self.score_engine = CreativeScoreEngine()
        self.family_engine = CreativeFamilyEngine()

        self.winner_memory = WinnerMemory()
        self.loser_memory = LoserMemory()
        self.family_tree = FamilyTree()
        
        # Publish integration (lazy init)
        self._publisher = None
    
    def run(self, project: str = None, generations: int = None) -> DailyRunResult:
        """运行每日闭环"""
        run_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        generations = generations or self.GENERATIONS
        errors = []
        
        print(f"\n{'='*70}")
        print(f"  V15 Creative Growth Loop - Daily Runner")
        print(f"  Date: {run_date}")
        print(f"{'='*70}\n")
        
        try:
            print("  [Step 1] Collecting Facebook performance data...")
            performances = self.fb_collector.get_top_performers(metric="ctr", days=7)
            print(f"    Found {len(performances)} top performers")
        except Exception as e:
            errors.append(f"Collector failed: {str(e)}")
            performances = []
        
        try:
            print("  [Step 2] Selecting winners...")
            winners = self.winner_engine.select_winners(performances)
            print(f"    Selected {len(winners)} winners")
        except Exception as e:
            errors.append(f"Winner Engine failed: {str(e)}")
            winners = []
        
        try:
            print("  [Step 3] Extracting genes from winners...")
            genes = []
            for winner in winners[:3]:
                if winner.image_path:
                    gene = self.gene_extractor.extract_gene(winner.image_path, winner.creative_id)
                    genes.append(gene)
                    self.gene_memory.record_win(gene)
            print(f"    Extracted {len(genes)} genes")
        except Exception as e:
            errors.append(f"Gene Extractor failed: {str(e)}")
            genes = []
        
        total_mutations = 0
        total_images = 0
        valid_images = 0
        all_scores = []
        families_created = 0
        
        if genes:
            gene = genes[0]
            self.gene_lock.lock_from_winner(gene)
            
            try:
                print("  [Step 4] Generating mutations...")
                mutations = self._generate_all_mutations(gene)
                total_mutations = len(mutations)
                print(f"    Generated {total_mutations} mutations")
            except Exception as e:
                errors.append(f"Mutation Engine failed: {str(e)}")
                mutations = []
            
            if mutations:
                try:
                    print("  [Step 5] Building prompts...")
                    prompts = self.prompt_builder.build_prompts(gene, mutations, count=self.VARIANTS_PER_RUN)
                    print(f"    Built {len(prompts)} prompts")
                except Exception as e:
                    errors.append(f"Prompt Builder failed: {str(e)}")
                    prompts = []
                
                if prompts:
                    try:
                        print("  [Step 6] Generating images...")
                        prompts_dict = [p.to_dict() for p in prompts]
                        images = self.image_generator.generate_images(prompts_dict, run_date)
                        total_images = len(images)
                        print(f"    Generated {total_images} images")
                    except Exception as e:
                        errors.append(f"Image Generator failed: {str(e)}")
                        images = []
                    
                    if images:
                        try:
                            print("  [Step 7] Filtering images...")
                            image_paths = [img.file_path for img in images]
                            filter_results = self.similarity_filter.filter_images(image_paths)
                            valid_paths = [r.image_path for r in filter_results if r.is_valid]
                            valid_images = len(valid_paths)
                            print(f"    Valid: {valid_images}, Invalid: {total_images - valid_images}")
                        except Exception as e:
                            errors.append(f"Filter failed: {str(e)}")
                            valid_paths = image_paths
                        
                        try:
                            print("  [Step 8] Scoring images...")
                            valid_images_data = [{"file_path": str(p)} for p in valid_paths]
                            scores = self.score_engine.score_images(valid_images_data)
                            all_scores = scores
                            print(f"    Scored {len(scores)} images")
                        except Exception as e:
                            errors.append(f"Score Engine failed: {str(e)}")
                            scores = []
                        
                        if scores:
                            try:
                                print("  [Step 9] Creating creative families...")
                                top_winners = self.score_engine.get_top_winners(scores, top_n=3)
                                
                                if winners:
                                    winner_id = winners[0].creative_id
                                    family = self.family_engine.create_family(
                                        winner_id, valid_paths, scores, generation=1
                                    )
                                    families_created = 1
                                    
                                    self.family_tree.add_family(
                                        winner_id, family.family_id,
                                        family.variants[:3], 1
                                    )
                                    
                                    for score in top_winners:
                                        self.winner_memory.record_win("hook", gene.hook)
                                
                                print(f"    Created {families_created} families")
                            except Exception as e:
                                errors.append(f"Family Engine failed: {str(e)}")
        
        # ---- Step 10: Auto Publish to Facebook Ads (if enabled) ----
        publish_result = None
        if self.config.get('auto_publish', False):
            try:
                print("  [Step 10] Publishing to Facebook Ads...")
                publish_result = self._publish_step(valid_paths, scores)
                if publish_result and publish_result.success:
                    print(f"    Published {publish_result.ad_count} ads, "
                          f"{publish_result.creative_count} creatives, "
                          f"{publish_result.uploaded_count} images")
                else:
                    errors_msg = publish_result.errors if publish_result else ["Unknown error"]
                    print(f"    Publish failed: {'; '.join(errors_msg[:3])}")
            except Exception as e:
                errors.append(f"Publish failed: {str(e)}")
                print(f"    Publish error: {e}")
        
        top_score = max(s.final_score for s in all_scores) if all_scores else 0.0
        avg_score = sum(s.final_score for s in all_scores) / len(all_scores) if all_scores else 0.0
        
        result = DailyRunResult(
            run_date=run_date,
            total_winners=len(winners),
            total_mutations=total_mutations,
            total_images=total_images,
            valid_images=valid_images,
            top_score=top_score,
            avg_score=avg_score,
            promoted_winners=len(top_winners) if 'top_winners' in dir() else 0,
            families_created=families_created,
            errors=errors,
        )
        
        self._save_result(result)
        
        print(f"\n{'='*70}")
        print(f"  Daily Run Complete")
        print(f"{'='*70}")
        print(f"  Winners: {result.total_winners}")
        print(f"  Mutations: {result.total_mutations}")
        print(f"  Images: {result.total_images}")
        print(f"  Valid: {result.valid_images}")
        print(f"  Top Score: {result.top_score:.2f}")
        print(f"  Families: {result.families_created}")
        
        return result
    
    def _generate_all_mutations(self, gene) -> List[Dict[str, Any]]:
        """生成所有突变（含旧版 creative_loop 迁移的 costume/pose/camera/lighting/color）"""
        mutations = []
        
        hook_mutations = self.hook_mutator.generate_from_winner(gene.hook, count=8)
        mutations.extend([m.to_dict() for m in hook_mutations])
        
        reward_mutations = self.reward_mutator.generate_mutations(count=4)
        mutations.extend(reward_mutations)
        
        emotion_mutations = self.emotion_mutator.generate_mutations(count=3)
        mutations.extend(emotion_mutations)
        
        progress_mutations = self.progress_mutator.generate_mutations(count=2)
        mutations.extend(progress_mutations)
        
        overlay_mutations = self.overlay_mutator.generate_mutations(count=2)
        mutations.extend(overlay_mutations)
        
        # From old creative_loop mutation_engine
        subject_mutations = self.subject_mutator.generate_mutations(count=2)
        mutations.extend(subject_mutations)
        
        composition_mutations = self.composition_mutator.generate_mutations(count=2)
        mutations.extend(composition_mutations)
        
        costume_mutations = self.costume_mutator.generate_mutations(count=1)
        mutations.extend(costume_mutations)
        
        pose_mutations = self.pose_mutator.generate_mutations(count=1)
        mutations.extend(pose_mutations)
        
        camera_mutations = self.camera_mutator.generate_mutations(count=1)
        mutations.extend(camera_mutations)
        
        lighting_mutations = self.lighting_mutator.generate_mutations(count=1)
        mutations.extend(lighting_mutations)
        
        color_mutations = self.color_mutator.generate_mutations(count=1)
        mutations.extend(color_mutations)
        
        return mutations
    
    def _save_result(self, result: DailyRunResult) -> Path:
        """保存结果"""
        result_path = self.output_dir / f"daily_run_{result.run_date}.json"
        
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        return result_path
    
    def _init_publisher(self):
        """延迟初始化 FacebookPublisher"""
        if self._publisher is not None:
            return
        campaign_cfg = self.config.get("campaign", {})
        access_token = campaign_cfg.get("access_token", "")
        ad_account_id = campaign_cfg.get("ad_account_id", "")
        api_version = campaign_cfg.get("api_version", "v22.0")
        page_id = campaign_cfg.get("page_id", "")
        
        if not access_token or not ad_account_id:
            raise ValueError(
                "auto_publish enabled but missing access_token or ad_account_id in config.campaign"
            )
        
        from ..14_publish.facebook_publisher import FacebookPublisher
        self._publisher = FacebookPublisher(
            access_token=access_token,
            ad_account_id=ad_account_id,
            api_version=api_version,
            page_id=page_id,
        )
    
    def _publish_step(self, valid_paths: list, scores: list) -> "PublishResult":
        """执行自动发布步骤"""
        self._init_publisher()
        
        # Determine image directory: use the run's image output dir
        image_dir = str(self.image_generator.output_dir)
        
        campaign_config = self.config.get("campaign", {})
        # Generate ad names from top-scored images
        if not campaign_config.get("ad_names"):
            top_scores = sorted(scores, key=lambda s: s.final_score if hasattr(s, 'final_score') else 0, reverse=True)
            campaign_config["ad_names"] = [
                f"AI_Creative_{i+1:02d}" for i in range(len(valid_paths))
            ]
        
        result = self._publisher.publish_and_monitor(
            image_dir=image_dir,
            campaign_config=campaign_config,
        )
        self._log_publish_result(result)
        return result
    
    def _log_publish_result(self, result: "PublishResult") -> None:
        """记录发布结果到 JSON 日志"""
        log_dir = self.output_dir / "publish_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"publish_{result.run_id}.json"
        
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    def run_feedback_loop(self, hours: int = 24) -> Dict[str, Any]:
        """运行反馈闭环"""
        print(f"\n  Running feedback loop (last {hours}h)...")
        
        performances = self.fb_collector.get_top_performers(metric="ctr", days=1)
        
        feedback_result = {
            "new_winners": 0,
            "new_losers": 0,
            "gene_updates": 0,
        }
        
        winners = self.winner_engine.select_winners(performances)
        feedback_result["new_winners"] = len(winners)
        
        losers = self.loser_engine.select_losers(performances)
        feedback_result["new_losers"] = len(losers)
        
        for winner in winners:
            if winner.image_path:
                gene = self.gene_extractor.extract_gene(winner.image_path)
                self.gene_memory.record_win(gene)
                self.winner_memory.record_win("hook", gene.hook)
                feedback_result["gene_updates"] += 1
        
        for loser in losers:
            self.loser_memory.record_loss("hook", "unknown")
        
        return feedback_result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="V15 Creative Growth Loop - Daily Runner")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--generations", type=int, default=3, help="Number of generations")
    
    args = parser.parse_args()
    
    runner = DailyRunner()
    result = runner.run(project=args.project, generations=args.generations)
    
    print(f"\nResult saved to: output/creative_growth_loop/daily_run_{result.run_date}.json")


if __name__ == "__main__":
    main()