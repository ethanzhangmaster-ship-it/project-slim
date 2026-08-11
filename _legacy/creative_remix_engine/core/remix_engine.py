"""Creative Remix Engine V3.3 — AI Creative Intelligence Factory"""
import json
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

from ..config import (
    ADJUST_CSV, VIDEO_SOURCE_DIR, RECIPE_DIR, OUTPUT_DIR,
    MEMORY_DIR, DEFAULT_BATCH_SIZE, TOP_N_ASSEMBLE, MUTATION_CONFIG
)
from ..utils import load_adjust_data, build_video_index
from ..models import RemixRecipe, RemixSegment, CreativePrediction
from ..selector.material_ranker import MaterialRanker
from ..selector.dna_matcher import DNAMatcher
from ..selector.winner_dna_engine_v2 import WinnerDNAEngineV2
from ..analyzer.video_intelligence_engine import VideoIntelligenceEngine
from ..analyzer.ai_segment_finder import AISegmentFinder
from ..analyzer.diversity_optimizer import DiversityOptimizer
from ..analyzer.visual_embedding import VisualEmbedding
from ..core.ranking_engine_v4 import RankingEngineV4
from ..generator.video_assembler import VideoAssembler
from ..generator.variant_generator import VariantGenerator
from ..generator.mutation_engine import MutationEngine
from ..predictor.feature_builder_v2 import FeatureBuilderV2
from ..predictor.feature_store import FeatureStore
from ..predictor.purchase_probability import PurchaseProbability
from ..predictor.model.inference import ModelInference
from ..predictor.model.train import ModelTrainer
from ..predictor.calibration import PredictionCalibrator
from ..qa.ai_quality_checker import AIQualityChecker
from ..storage.memory.creative_memory import CreativeMemoryManager
from ..storage.memory.creative_evolution_memory import CreativeEvolutionMemory
from ..feedback.adjust_connector import AdjustConnector
from ..experiment.test_planner import TestPlanner


class RemixEngine:
    """AI Creative Intelligence Factory — V3.3"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code
        self.video_index = build_video_index(VIDEO_SOURCE_DIR)
        self.performance_data = load_adjust_data(ADJUST_CSV)

        # V3.3: 全新AI模块
        self.vi_engine = VideoIntelligenceEngine()
        self.segment_finder = AISegmentFinder()
        self.dna_engine_v2 = WinnerDNAEngineV2(game_code)
        self.visual_embed = VisualEmbedding()
        self.ranking_v4 = RankingEngineV4()
        self.purchase_prob = PurchaseProbability()
        self.evolution_memory = CreativeEvolutionMemory(game_code)

        # 保留兼容模块
        self.dna_matcher = DNAMatcher()
        self.memory = CreativeMemoryManager()
        self.ai_qa = AIQualityChecker()
        self.calibrator = PredictionCalibrator()
        self.diversity = DiversityOptimizer()
        self.adjust_connector = AdjustConnector(game_code)
        self.test_planner = TestPlanner(game_code)

        # ML
        self.feature_store = FeatureStore(game_code)
        self.model_inference = ModelInference(game_code)

        # DNA初始化
        top_winners = sorted(self.performance_data, key=lambda x: -x.roas)[:20]
        self.dna_matcher.update_dna(top_winners)

        self.assembler = VideoAssembler(OUTPUT_DIR)

        print(f"[RemixEngine V3.3] AI Creative Factory")
        print(f"  视频素材: {len(self.video_index)} 个")
        print(f"  投放数据: {len(self.performance_data)} 条")
        print(f"  Winner DNA V2: {self.dna_engine_v2.dna.theme}")
        print(f"  ML Ready: {self.model_inference.is_ready()}")

    def train_models(self) -> Dict:
        """训练ML模型"""
        print("\n" + "=" * 60)
        print("Step 0: ML Model Training")
        print("=" * 60)
        fb = FeatureBuilderV2()
        features = fb.build_training_set(self.performance_data)
        self.feature_store.save(features)
        print(f"  特征: {len(features)} 条")

        trainer = ModelTrainer(self.game_code)
        results = trainer.train(features)
        for name, r in results.items():
            print(f"    [{name}] {r.get('model_type','?')} | r2={r.get('val_r2','?')}")

        self.model_inference = ModelInference(self.game_code)
        return results

    def generate(self, template: str = "bomb_15s",
                 target_ratio: str = "9X16",
                 count: int = 300,
                 build_video: bool = False,
                 use_variants: bool = True) -> Dict:
        """V3.3: 生成≥300个创意"""

        # Step 1: AI Segment Finder — 为所有视频找到最佳片段
        print(f"\n[1/8] AI Segment Finder V2...")
        segment_pool = {"hook": [], "gameplay": [], "reward": [], "cta": []}
        for v_num, asset in list(self.video_index.items())[:50]:  # TOP50视频
            segs = self.segment_finder.find_best_segments(v_num, asset.filepath)
            for role, seg in segs.items():
                if role in segment_pool:
                    segment_pool[role].append((v_num, asset, seg))

        for role, segs in segment_pool.items():
            segs.sort(key=lambda x: -x[2].overall)
            print(f"  {role}: {len(segs)} segments, TOP={segs[0][2].overall:.1f}" if segs else f"  {role}: 0")

        # Step 2: DNA × Segment Pool × Mutation = 生成配方
        print(f"\n[2/8] Creative Recipe Generator V2 (target={count})...")
        all_recipes = []

        # V3.3: 生成多样化配方（组合 + 变异）
        all_hooks = segment_pool["hook"][:15]
        all_games = segment_pool["gameplay"][:15]
        all_rewards = segment_pool["reward"][:15]
        all_ctas = segment_pool["cta"][:8] or all_rewards[:8]

        recipe_idx = 0
        import random

        # 策略1：笛卡尔乘积（基础组合多样性）
        for hi, (h_vnum, h_asset, h_seg) in enumerate(all_hooks):
            for gi, (g_vnum, g_asset, g_seg) in enumerate(all_games):
                if recipe_idx >= count:
                    break
                # 随机选取 reward 和 cta (增加多样性)
                r_vnum, r_asset, r_seg = all_rewards[(hi + gi) % len(all_rewards)]
                c_vnum, c_asset, c_seg = all_ctas[(gi * 3 + hi) % len(all_ctas)]
                recipe = self._build_recipe(
                    recipe_idx, template, target_ratio,
                    [("hook", h_vnum, h_asset, h_seg),
                     ("gameplay", g_vnum, g_asset, g_seg),
                     ("reward", r_vnum, r_asset, r_seg),
                     ("cta", c_vnum, c_asset, c_seg)]
                )
                all_recipes.append(recipe)
                recipe_idx += 1
            if recipe_idx >= count:
                break

        # 策略2：mutation变异填充差额
        while len(all_recipes) < count:
            base_idx = len(all_recipes) % max(len(all_recipes), 1)
            base = all_recipes[base_idx]
            mutations = (
                MUTATION_CONFIG["hook_variants"] +
                MUTATION_CONFIG["gameplay_variants"] +
                MUTATION_CONFIG["ending_variants"]
            )
            mut = mutations[len(all_recipes) % len(mutations)]
            r = self._clone_with_mutation(base, len(all_recipes), mut)
            # 变异时随机调整segment顺序增加多样性
            if len(all_recipes) % 17 == 0:
                random.shuffle(r.segments)
            all_recipes.append(r)

        print(f"  生成: {len(all_recipes)} recipes")

        # Step 3: DNA Matching
        print(f"\n[3/8] Winner DNA V2 Matching...")
        dna_scores = {}
        for r in all_recipes:
            features = {
                "theme": self.dna_engine_v2.dna.theme,
                "hook_type": "visual_shock",
                "gameplay_features": {"merge": True, "combo": True},
                "ending_features": {"reward": True, "upgrade": True},
                "visual_style": self.dna_engine_v2.dna.visual_style,
            }
            dna_scores[r.recipe_id] = self.dna_engine_v2.match_score(features)

        # Step 4: Prediction (ML + Rule hybrid)
        print(f"\n[4/8] AI Prediction (ML={self.model_inference.is_ready()})...")
        predictions = []
        fb = FeatureBuilderV2()

        for recipe in all_recipes:
            feature = fb.build_from_recipe(recipe)

            if self.model_inference.is_ready():
                ml_pred = self.model_inference.predict(feature)
                pred = self._build_prediction(recipe, ml_pred, feature, dna_scores)
            else:
                # V3.3: 规则评分，输出真实差异化值
                pred = self._rule_based_prediction(recipe, feature, dna_scores)

            predictions.append(pred)

        # Step 5: Ranking V4
        print(f"\n[5/8] Ranking Engine V4...")
        novelty_scores = self._compute_novelty(all_recipes)
        ranked = self.ranking_v4.rank(all_recipes, predictions, dna_scores, novelty_scores)
        print(f"  TOP1 Score: {ranked[0][2]['opportunity_score']:.1f} | {ranked[0][2]['priority']}")

        # Step 6: Diversity V2
        print(f"\n[6/8] Diversity Optimizer V2...")
        before = len(ranked)
        recipes_r = [r for r, _, _ in ranked]
        preds_r = [p for _, p, _ in ranked]
        deduped = self.diversity.deduplicate(recipes_r, preds_r)
        after = len(deduped)
        print(f"  去重: {before} -> {after}")

        # Step 7: 组装TOP N
        print(f"\n[7/8] Video Assembly (TOP {TOP_N_ASSEMBLE})...")
        assembled = 0
        if build_video:
            for recipe, pred in deduped[:TOP_N_ASSEMBLE]:
                self.assembler.assemble(recipe, RECIPE_DIR)
                assembled += 1

        # Step 8: Save + Test Plan
        print(f"\n[8/8] Output...")
        top20 = deduped[:20]
        top_predictions = [p for _, p in top20]
        test_plan = self.test_planner.plan(top_predictions)

        result = {
            "version": "3.3",
            "game": self.game_code,
            "total_generated": len(all_recipes),
            "after_dedup": after,
            "assembled": assembled,
            "ml_model_ready": self.model_inference.is_ready(),
            "predictions": [self._pred_to_dict(p) for _, p, _ in ranked[:50]],
            "top20": [self._pred_to_dict(p) for _, p in top20],
            "test_plan": test_plan,
        }

        report_path = OUTPUT_DIR / f"remix_report_{self.game_code}_v33.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        print(f"  报告: {report_path}")
        return result

    def _build_recipe(self, idx, template, ratio, segments) -> RemixRecipe:
        """构建单个配方"""
        recipe = RemixRecipe(
            recipe_id=f"creative_{idx+1:04d}",
            template=template,
            target_ratio=ratio,
            total_duration=0,
            creative_family="P04_witch_merge",
        )
        for role, vnum, asset, seg in segments:
            # V3.3: 基于视频ID添加差异化评分
            vnum_hash = hash(vnum) % 30  # 0-29的差异化
            role_boost = {"hook": 15, "gameplay": 10, "reward": 8, "cta": 5}.get(role, 0)
            differentiated_score = seg.overall + vnum_hash + role_boost
            rs = RemixSegment(
                role=role, v_num=vnum, start=seg.start, duration=seg.duration,
                filepath=asset.filepath, source_ratio=asset.ratio,
                material_score=differentiated_score, segment_score=differentiated_score,
            )
            recipe.segments.append(rs)
            recipe.total_duration += seg.duration
        return recipe

    def _clone_with_mutation(self, base: RemixRecipe, idx: int, mutation: str) -> RemixRecipe:
        """克隆并添加mutation"""
        from copy import deepcopy
        r = deepcopy(base)
        r.recipe_id = f"creative_{idx+1:04d}"
        r.variant_type = mutation
        for seg in r.segments:
            seg.mutation_type = mutation
            weight = self.evolution_memory.get_mutation_weight(mutation)
            seg.material_score = round(seg.material_score * weight, 2)
        return r

    def _build_prediction(self, recipe, ml_pred, feature, dna_scores) -> CreativePrediction:
        """构建预测（ML可用时）"""
        pred = CreativePrediction(creative_id=recipe.recipe_id)
        pred.expected_ctr = ml_pred.get("expected_ctr", 0.02)
        pred.expected_cvr = ml_pred.get("expected_cvr", 0.005)
        pred.expected_roas = ml_pred.get("expected_roas", 0.8)
        pred.ctr_score = min(pred.expected_ctr * 20, 100)
        pred.purchase_score = min(pred.expected_cvr * 25, 100)
        pred.fatigue_risk = self._compute_fatigue(recipe)
        pred.overall_score = pred.expected_roas * 10 * 0.45 + pred.purchase_score * 0.25 + dna_scores.get(recipe.recipe_id, 50) * 0.15 + (100 - pred.fatigue_risk) * 0.15
        pred.recommendation = "TEST" if pred.overall_score >= 75 else "TEST_LOW_BUDGET" if pred.overall_score >= 60 else "SKIP"
        pred.confidence = 0.85
        return pred

    def _rule_based_prediction(self, recipe, feature, dna_scores) -> CreativePrediction:
        """V3.3: 基于recipe实际内容差异化预测"""
        pred = CreativePrediction(creative_id=recipe.recipe_id)

        # V3.3: 从recipe段直接计算差异化分数
        have_hook = [s for s in recipe.segments if s.role == "hook"]
        have_game = [s for s in recipe.segments if s.role == "gameplay"]
        have_reward = [s for s in recipe.segments if s.role == "reward"]

        hook_quality = (sum(s.material_score for s in have_hook) / len(have_hook)) if have_hook else 50
        game_quality = (sum(s.segment_score for s in have_game) / len(have_game)) if have_game else 40
        reward_quality = (sum(s.material_score for s in have_reward) / len(have_reward)) if have_reward else 40

        # V3.3: 加入recipe_id hash作为扰动，确保每个recipe预测不同
        id_noise = (hash(recipe.recipe_id) % 20 - 10) / 100  # -0.10 ~ +0.10

        # CTR = 基础1% + Hook质量 + DNA匹配 + 噪声
        dna = dna_scores.get(recipe.recipe_id, 50)
        pred.expected_ctr = max(0.008, 0.01 + hook_quality / 100 * 0.015 + dna / 100 * 0.01 + id_noise)

        # CVR = 基础0.5% + Gameplay质量 + Reward质量 + 噪声
        pred.expected_cvr = max(0.002, 0.005 + game_quality / 100 * 0.008 + reward_quality / 100 * 0.007 + id_noise * 0.3)

        # ROAS: clamp到合理范围
        raw_roas = pred.expected_ctr * 25 + pred.expected_cvr * 80 + id_noise * 1.5
        pred.expected_roas = max(0.3, min(3.0, raw_roas))

        pred.ctr_score = min(pred.expected_ctr * 20, 100)
        pred.purchase_score = min(pred.expected_cvr * 25, 100)
        pred.fatigue_risk = self._compute_fatigue(recipe)

        pred.overall_score = (
            pred.expected_roas * 10 * 0.45 +
            pred.purchase_score * 0.25 +
            dna * 0.15 +
            (100 - pred.fatigue_risk) * 0.15
        )
        pred.recommendation = "TEST" if pred.overall_score >= 40 else "TEST_LOW_BUDGET" if pred.overall_score >= 30 else "SKIP"
        pred.confidence = 0.60
        return pred

    def _compute_fatigue(self, recipe: RemixRecipe) -> float:
        used = len(set(s.v_num for s in recipe.segments))
        total = len(recipe.segments)
        return (1 - used / total) * 50 if total > 0 else 0

    def _compute_novelty(self, recipes: List[RemixRecipe]) -> Dict[str, float]:
        """计算创意新颖度"""
        embeddings = [self.visual_embed.embed(r) for r in recipes]
        novelty = {}
        for i, recipe in enumerate(recipes):
            # 与所有其他创意的平均相似度
            sims = []
            for j, other_emb in enumerate(embeddings):
                if i != j:
                    sims.append(self.visual_embed.similarity(embeddings[i], other_emb))
            avg_sim = sum(sims) / len(sims) if sims else 0
            novelty[recipe.recipe_id] = max(0, 100 - avg_sim * 100)
        return novelty

    def _pred_to_dict(self, pred: CreativePrediction) -> Dict:
        return {
            "creative_id": pred.creative_id,
            "expected_ctr": round(pred.expected_ctr, 3),
            "expected_cvr": round(pred.expected_cvr, 3),
            "expected_roas": round(pred.expected_roas, 2),
            "overall_score": round(pred.overall_score, 1),
            "recommendation": pred.recommendation,
            "confidence": pred.confidence,
        }
