"""P04 Witch项目 V15创意增长闭环运行脚本 - 独立版本"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from market_ops.clients.lovart import LovartClient, download_image


class P04CreativeLoop:
    """P04 Witch项目专用创意闭环 - 独立版本"""
    
    PROJECT_NAME = "P04 Witch"
    SOURCE_DIR = Path(r"D:\p4素材")
    GOOD_MATERIALS_DIR = Path(r"D:\p4素材\新建文件夹 (3)")
    OUTPUT_DIR = Path("output/P04_Witch_Creative_Growth")
    VARIANTS_PER_VARIANT = 8
    
    WINNER_DNA = [
        {
            "creative_id": "winner_1",
            "subject": "witch queen with white hair holding baby dragon surrounded by magical creatures",
            "style": "3D cartoon",
            "hook": "collection",
            "reward": "baby_dragon",
            "emotion": "whimsical",
            "progress": "lv100",
            "overlay": "arrow",
            "background": "castle silhouette",
            "palette": "deep purple, royal violet, soft lavender",
            "hook_text": "200+ Magical Creatures to Collect!",
            "key_features": ["cute baby dragon", "magical creatures", "collection excitement", "whimsical mood"]
        },
        {
            "creative_id": "winner_2",
            "subject": "witch character with floating castle merge progression",
            "style": "3D cartoon",
            "hook": "collection",
            "reward": "castle",
            "emotion": "mysterious",
            "progress": "merge",
            "overlay": "arrow",
            "background": "dark fantasy",
            "palette": "deep purples, dark blues, glowing magenta",
            "hook_text": "MERGE WITCHES",
            "key_features": ["merge progression", "castle upgrade", "dark fantasy", "mystery box"]
        },
        {
            "creative_id": "winner_3",
            "subject": "witch character nurturing magical plant with glowing hands",
            "style": "3D cartoon",
            "hook": "collection",
            "reward": "magic_garden",
            "emotion": "enchanting",
            "progress": "growth",
            "overlay": "arrow",
            "background": "moonlit forest",
            "palette": "deep purples, electric gold, bioluminescent",
            "hook_text": "Nurture Your Magic Garden",
            "key_features": ["plant nurturing", "merge progression", "golden glow", "fantasy art"]
        },
        {
            "creative_id": "winner_4",
            "subject": "cute witch character with magical creatures collection",
            "style": "3D cartoon",
            "hook": "collection",
            "reward": "creatures",
            "emotion": "enchanting",
            "progress": "hatching",
            "overlay": "text",
            "background": "enchanted forest",
            "palette": "warm golden yellows, soft purples, pastel blues",
            "hook_text": "200+ Creatures to Collect!",
            "key_features": ["adorable chibi", "hatching eggs", "spell book", "warm magical"]
        }
    ]
    
    def __init__(self):
        self.output_dir = self.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "images").mkdir(exist_ok=True)
        (self.output_dir / "prompts").mkdir(exist_ok=True)
        (self.output_dir / "scores").mkdir(exist_ok=True)
        
        self.lovart_client = LovartClient()
    
    def run(self) -> Dict[str, Any]:
        """运行P04创意闭环"""
        run_id = f"P04_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"\n{'='*70}")
        print(f"  P04 Witch V15 Creative Growth Loop")
        print(f"  Run ID: {run_id}")
        print(f"{'='*70}\n")
        
        all_results = []
        all_generated_images = []
        
        for idx, winner in enumerate(self.WINNER_DNA[:2]):
            print(f"\n--- Processing Winner {idx+1}: {winner['creative_id']} ---")
            
            result = self._process_winner(winner, run_id, idx)
            all_results.append(result)
            all_generated_images.extend(result.get("images", []))
        
        summary = self._create_summary(run_id, all_results, all_generated_images)
        self._save_results(run_id, summary)
        
        return summary
    
    def _process_winner(self, winner: Dict[str, Any], run_id: str, idx: int) -> Dict[str, Any]:
        """处理单个赢家"""
        result = {
            "winner_id": winner["creative_id"],
            "images": [],
            "prompts": [],
            "scores": [],
            "top_score": 0.0,
            "avg_score": 0.0,
        }
        
        print(f"  [1/4] Generating mutation prompts...")
        prompts = self._generate_prompts(winner)
        result["prompts"] = prompts
        print(f"      Generated {len(prompts)} prompts")
        
        print(f"  [2/4] Generating images with Lovart...")
        images = self._generate_images(prompts, run_id, idx)
        result["images"] = images
        print(f"      Generated {len(images)} images")
        
        if images:
            print(f"  [3/4] Scoring images with Lovart...")
            scores = self._score_images(images)
            result["scores"] = scores
            
            if scores:
                result["top_score"] = max(scores, key=lambda x: x["overall"])["overall"]
                result["avg_score"] = sum(s["overall"] for s in scores) / len(scores)
                
                print(f"      Top Score: {result['top_score']:.2f}")
                print(f"      Avg Score: {result['avg_score']:.2f}")
        
        print(f"  [4/4] Saving results...")
        self._save_winner_results(winner, result)
        
        return result
    
    def _generate_prompts(self, winner: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成变体提示词"""
        prompts = []
        
        mutation_templates = [
            {
                "prompt_id": f"{winner['creative_id']}_m1",
                "hook_text": "Only 1% Can Reach Lv100",
                "mutation_type": "hook",
                "style": winner["style"],
                "subject": winner["subject"],
                "emotion": winner["emotion"],
                "reward": winner["reward"],
                "background": winner["background"],
                "palette": winner["palette"],
            },
            {
                "prompt_id": f"{winner['creative_id']}_m2",
                "hook_text": "Don't Merge Them!",
                "mutation_type": "hook",
                "style": winner["style"],
                "subject": winner["subject"],
                "emotion": "panic",
                "reward": winner["reward"],
                "background": winner["background"],
                "palette": winner["palette"],
            },
            {
                "prompt_id": f"{winner['creative_id']}_m3",
                "hook_text": "Secret Dragon Inside",
                "mutation_type": "hook",
                "style": winner["style"],
                "subject": winner["subject"],
                "emotion": "surprise",
                "reward": "secret_dragon",
                "background": "mysterious cave",
                "palette": "dark purple, gold accents",
            },
            {
                "prompt_id": f"{winner['creative_id']}_m4",
                "hook_text": "Wait For Final Evolution",
                "mutation_type": "hook",
                "style": winner["style"],
                "subject": winner["subject"],
                "emotion": "excited",
                "reward": "evolution",
                "background": "cosmic space",
                "palette": "deep blue, silver stars",
            },
            {
                "prompt_id": f"{winner['creative_id']}_m5",
                "hook_text": "Merge Witches Build Empire",
                "mutation_type": "hook",
                "style": winner["style"],
                "subject": winner["subject"],
                "emotion": "determined",
                "reward": "castle_empire",
                "background": winner["background"],
                "palette": winner["palette"],
            },
            {
                "prompt_id": f"{winner['creative_id']}_m6",
                "hook_text": "Collect 200+ Magical Creatures",
                "mutation_type": "hook",
                "style": winner["style"],
                "subject": winner["subject"],
                "emotion": "happy",
                "reward": winner["reward"],
                "background": winner["background"],
                "palette": winner["palette"],
            },
            {
                "prompt_id": f"{winner['creative_id']}_m7",
                "hook_text": "Why Is Everyone Stuck At Lv28?",
                "mutation_type": "hook",
                "style": winner["style"],
                "subject": winner["subject"],
                "emotion": "curious",
                "reward": "level_up",
                "background": "mystical forest",
                "palette": "emerald green, gold",
            },
            {
                "prompt_id": f"{winner['creative_id']}_m8",
                "hook_text": "Can You Reach Lv100?",
                "mutation_type": "hook",
                "style": winner["style"],
                "subject": winner["subject"],
                "emotion": "challenging",
                "reward": "golden_dragon",
                "background": "ancient temple",
                "palette": "warm amber, bronze",
            },
        ]
        
        for template in mutation_templates:
            prompt_text = self._build_prompt_text(template)
            template["prompt_text"] = prompt_text
            prompts.append(template)
        
        return prompts
    
    def _build_prompt_text(self, template: Dict[str, Any]) -> str:
        """构建提示词文本"""
        parts = [
            f"{template['style']} style",
            f"{template['subject']}",
            f"{template['emotion']} expression",
            f"holding {template['reward']}",
            f"set in {template['background']}",
            f"color palette: {template['palette']}",
            "high quality",
            "professional advertising",
            "mobile game ad",
            "9:16 aspect ratio",
        ]
        
        return ",\n".join(parts)
    
    def _generate_images(self, prompts: List[Dict[str, Any]], run_id: str, winner_idx: int) -> List[Dict[str, Any]]:
        """使用Lovart生成图片"""
        images = []

        for idx, prompt_data in enumerate(prompts):
            print(f"      Generating image {idx+1}/{len(prompts)}: {prompt_data['hook_text']}")

            try:
                result = self.lovart_client.generate_image(
                    prompt_data["prompt_text"]
                )

                # LovartResult 是 dataclass，属性是 image_urls: list[str]，没有 "image_path" key
                image_urls = getattr(result, "image_urls", None) if result else None
                if image_urls:
                    img_url = image_urls[0]
                    final_path = self.output_dir / "images" / f"{run_id}_w{winner_idx+1}_{idx:02d}_{prompt_data['hook_text'][:20]}.png"
                    download_image(img_url, final_path)

                    images.append({
                        "image_path": str(final_path),
                        "image_url": img_url,
                        "prompt": prompt_data["prompt_text"],
                        "hook_text": prompt_data["hook_text"],
                        "mutation_type": prompt_data["mutation_type"],
                        "model": "lovart",
                    })
                    print(f"        Saved: {final_path.name}")
                else:
                    status = getattr(result, "status", "unknown") if result else "None"
                    text = getattr(result, "assistant_text", "")[:120] if result else ""
                    print(f"        Failed: status={status} text={text}")

            except Exception as e:
                print(f"        Error: {str(e)[:80]}")
                continue

        return images
    
    def _score_images(self, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """使用Lovart评分，保存原始响应以便审计。

        修复点：
        1. 保存 Lovart 原始 assistant_text/summary 到 raw_response
        2. 缺维度时不静默填 0，标记 dimensions_missing
        3. 只对存在的维度求 overall
        """
        scores: List[Dict[str, Any]] = []
        dims = ["visual_quality", "brand_alignment", "hook_clarity",
                "ad_suitability", "originality"]

        for img_data in images:
            try:
                result = self.lovart_client.evaluate_image(
                    image_path=img_data["image_path"],
                    prompt=img_data.get("prompt", ""),
                    project=self.PROJECT_NAME,
                    hook_type=img_data.get("mutation_type", ""),
                )

                if not result or "error" in result:
                    err = result.get("error", "unknown") if result else "None"
                    print(f"        No score returned: {err[:80]}")
                    continue

                # 收集维度值；缺失的不静默填 0
                present: Dict[str, float] = {}
                missing: List[str] = []
                for d in dims:
                    raw = result.get(d)
                    if raw is None:
                        missing.append(d)
                        continue
                    try:
                        present[d] = float(raw)
                    except (TypeError, ValueError):
                        missing.append(d)

                overall = sum(present.values()) / len(present) if present else 0.0

                # 保留原始响应文本，方便审计；优先用 summary，否则序列化整个 result
                raw_text = result.get("summary") or ""
                if not raw_text:
                    raw_text = json.dumps(result, ensure_ascii=False)
                raw_text = raw_text[:2000]

                score_data = {
                    "image_path": img_data["image_path"],
                    "hook_text": img_data.get("hook_text", ""),
                    # 数值维度（缺失的为 None，不静默填 0）
                    "visual_quality": present.get("visual_quality"),
                    "brand_alignment": present.get("brand_alignment"),
                    "hook_clarity": present.get("hook_clarity"),
                    "ad_suitability": present.get("ad_suitability"),
                    "originality": present.get("originality"),
                    "overall": overall,
                    # 审计字段
                    "dimensions_present": len(present),
                    "dimensions_missing": missing,
                    "strengths": list(result.get("strengths", []))[:5],
                    "improvements": list(result.get("improvements", []))[:5],
                    "raw_response": raw_text,
                }
                scores.append(score_data)

                miss_tag = f" missing={missing}" if missing else ""
                print(f"        Score: {overall:.2f} - {img_data.get('hook_text', '')}{miss_tag}")

            except Exception as e:
                print(f"        Score error: {str(e)[:80]}")
                continue

        return scores
    
    def _save_winner_results(self, winner: Dict[str, Any], result: Dict[str, Any]) -> None:
        """保存赢家结果"""
        output_path = self.output_dir / "prompts" / f"{winner['creative_id']}_prompts.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    
    def _create_summary(self, run_id: str, results: List[Dict], images: List[Dict]) -> Dict[str, Any]:
        """创建汇总，含跨图评分合理性校验。"""
        all_scores: List[Dict[str, Any]] = []
        for r in results:
            all_scores.extend(r.get("scores", []))

        top_score = max([s.get("overall", 0) for s in all_scores]) if all_scores else 0.0
        avg_score = sum([s.get("overall", 0) for s in all_scores]) / len(all_scores) if all_scores else 0.0

        # 跨图合理性校验：某维度在 3+ 张图上完全相同 → 可疑（可能是模板化评分或 fallback 抓数字）
        dims = ["visual_quality", "brand_alignment", "hook_clarity",
                "ad_suitability", "originality"]
        suspicious_dims: List[Dict[str, Any]] = []
        for d in dims:
            vals = [s.get(d) for s in all_scores if s.get(d) is not None]
            if len(vals) >= 3 and len(set(vals)) == 1:
                suspicious_dims.append({"dimension": d, "value": vals[0], "count": len(vals)})

        score_suspicious = len(suspicious_dims) > 0
        score_audit = {
            "total_scored": len(all_scores),
            "suspicious": score_suspicious,
            "suspicious_dimensions": suspicious_dims,
            "note": (
                "suspicious=true 表示某维度在 3+ 张图上分数完全一致，"
                "可能是 Lovart 返回了模板化评分，或 _parse_eval_text 走了正则 fallback。"
                "请检查 raw_response 字段确认。"
                if score_suspicious else ""
            ),
        }

        return {
            "run_id": run_id,
            "project": self.PROJECT_NAME,
            "run_date": datetime.now().isoformat(),
            "total_winners_processed": len(results),
            "total_images_generated": len(images),
            "top_score": top_score,
            "avg_score": avg_score,
            "score_audit": score_audit,
            "winners": results,
            "image_paths": [i.get("image_path") for i in images if i.get("image_path")],
        }
    
    def _save_results(self, run_id: str, summary: Dict[str, Any]) -> None:
        """保存结果"""
        output_path = self.output_dir / f"run_{run_id}.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*70}")
        print(f"  Results Summary")
        print(f"{'='*70}")
        print(f"  Run ID: {run_id}")
        print(f"  Winners Processed: {summary['total_winners_processed']}")
        print(f"  Images Generated: {summary['total_images_generated']}")
        print(f"  Top Score: {summary['top_score']:.2f}")
        print(f"  Avg Score: {summary['avg_score']:.2f}")
        print(f"\n  Results saved to: {output_path}")
        print(f"  Images saved to: {self.output_dir / 'images'}")
        print(f"{'='*70}\n")


def main():
    loop = P04CreativeLoop()
    summary = loop.run()
    
    print("\n" + "="*70)
    print("  P04 Witch V15 Creative Growth Loop Complete!")
    print("="*70)
    print("\nGenerated Image Paths:")
    for path in summary.get("image_paths", []):
        print(f"  - {path}")


if __name__ == "__main__":
    main()
