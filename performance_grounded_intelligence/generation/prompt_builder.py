"""Generation Pipeline — Prompt Builder

读取 true_winner_dna.json 和 generation_constraints.json，
构建符合 Winner DNA 约束的生成 Prompt。

输出:
- prompt: 正向描述
- negative_prompt: 负面约束
- reference_image_path: 参考图路径
- constraints: 硬约束参数
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..config import OUTPUT_DIR, WINNERS_DIR, THUMBNAILS_DIR, ensure_dirs


# Prompt 模板
PROMPT_TEMPLATE = """Create a mobile game advertisement image for a merge/puzzle game (similar to Merge Dragons).

## Composition Requirements:
- Gameplay area: {gameplay_ratio}% of the image, positioned at {gameplay_position}
- Reward showcase: {reward_ratio}% of the image, positioned at {reward_position}
- Character area: {character_ratio}% of the image
- Background: {background_ratio}% of the image

## Gameplay Elements:
- Type: {gameplay_type}
- Must include: {gameplay_elements}

## Reward Elements:
- Primary reward: {reward_type}
- Visual elements: {reward_elements}

## Visual Style:
- Color palette: {color_palette}
- Lighting: {lighting}
- Camera angle: {camera}
- Render style: {render_style}

## Layout:
- Overall layout: {layout}
- Hook strategy: {hook}

## Quality Requirements:
- High resolution, professional mobile game ad quality
- Clear visual hierarchy with gameplay as focal point
- Vibrant colors with magical atmosphere
- {additional_requirements}"""

NEGATIVE_PROMPT_TEMPLATE = """blurry, low quality, pixelated, text overlay, watermark,
UI elements, buttons, phone frame, screenshot border,
realistic photo, photograph, {negative_additions}"""

# === Mutation-based Prompt 模板 ===
MUTATION_PROMPT_TEMPLATE = """Create a mobile game advertisement image for a merge/puzzle game (similar to Merge Dragons).

## Winner Reference:
This creative is an evolution variant of a high-performing winner:
- Winner Asset: {winner_asset_id}
- Winner Performance: {winner_performance}

## Mutation Strategy: {strategy_label}
- Reason: {mutation_reason}
- Expected Advantage: {expected_advantage}

## What to PRESERVE (keep identical to winner):
{preserve_items}

## What to CHANGE (mutate from winner):
{change_items}

## Composition Requirements:
- Gameplay area: {gameplay_ratio}% of the image, positioned at {gameplay_position}
- Reward showcase: {reward_ratio}% of the image, positioned at {reward_position}
- Character area: {character_ratio}% of the image
- Background: {background_ratio}% of the image

## Gameplay Elements:
- Type: {gameplay_type}
- Must include: {gameplay_elements}

## Reward Elements:
- Primary reward: {reward_type}
- Visual elements: {reward_elements}

## Visual Style:
- Color palette: {color_palette}
- Lighting: {lighting}
- Camera angle: {camera}
- Render style: {render_style}

## Layout:
- Overall layout: {layout}
- Hook strategy: {hook}

## Quality Requirements:
- High resolution, professional mobile game ad quality
- Clear visual hierarchy with gameplay as focal point
- Vibrant colors with magical atmosphere
- Maintain winner's core appeal while introducing novelty"""

MUTATION_NEGATIVE_TEMPLATE = """blurry, low quality, pixelated, text overlay, watermark,
UI elements, buttons, phone frame, screenshot border,
realistic photo, photograph, distorted proportions,
wrong color scheme, deviating from {color_palette} style"""


class PromptBuilder:
    """Winner DNA 约束的 Prompt 构建器"""

    def __init__(self):
        self.dna_data = None
        self.constraints = None

    def load(self, dna_path: Optional[Path] = None,
             constraints_path: Optional[Path] = None):
        """加载 DNA 和约束数据

        Args:
            dna_path: true_winner_dna.json 路径
            constraints_path: generation_constraints.json 路径
        """
        dna_path = dna_path or (OUTPUT_DIR / "true_winner_dna.json")
        constraints_path = constraints_path or (OUTPUT_DIR / "generation_constraints.json")

        if dna_path.exists():
            with open(dna_path, "r", encoding="utf-8") as f:
                self.dna_data = json.load(f)
            print(f"[PromptBuilder] 加载 DNA: {self.dna_data.get('total', 0)} winners")
        else:
            print(f"[PromptBuilder] DNA 文件不存在: {dna_path}")
            self.dna_data = {"winners": []}

        if constraints_path.exists():
            with open(constraints_path, "r", encoding="utf-8") as f:
                self.constraints = json.load(f)
            print(f"[PromptBuilder] 加载约束: {constraints_path.name}")
        else:
            self.constraints = {}

    def build_prompt(self, winner_index: int = 0,
                     variation: str = "default") -> Dict[str, str]:
        """构建生成 Prompt

        Args:
            winner_index: 使用第几个 winner 的 DNA (0=Top1)
            variation: 变体类型 (default / reward_focus / gameplay_focus)

        Returns:
            {"prompt": str, "negative_prompt": str,
             "reference_image": str, "constraints": dict}
        """
        if not self.dna_data:
            self.load()

        winners = self.dna_data.get("winners", [])
        if not winners:
            return self._default_prompt()

        winner = winners[min(winner_index, len(winners) - 1)]
        dna = winner.get("dna", {})

        # 提取 DNA 各维度
        comp = dna.get("composition", {})
        gameplay = dna.get("gameplay", {})
        reward = dna.get("reward", {})
        style = dna.get("style", {})

        # 构图参数
        gp_area = comp.get("gameplay_area", {})
        rw_area = comp.get("reward_area", {})
        ch_area = comp.get("character_area", {})
        bg_area = comp.get("background_area", {})

        # 变体调整
        additional = ""
        negative_add = ""
        if variation == "reward_focus":
            additional = "Emphasize the reward elements, make them larger and more prominent."
            negative_add = "small rewards, hidden rewards"
        elif variation == "gameplay_focus":
            additional = "Emphasize the gameplay board, show more merge interactions."
            negative_add = "empty board, no game elements"

        # 填充模板
        prompt = PROMPT_TEMPLATE.format(
            gameplay_ratio=int(gp_area.get("ratio", 0.5) * 100),
            gameplay_position=gp_area.get("position", "center"),
            reward_ratio=int(rw_area.get("ratio", 0.25) * 100),
            reward_position=rw_area.get("position", "top_right"),
            character_ratio=int(ch_area.get("ratio", 0.15) * 100),
            background_ratio=int(bg_area.get("ratio", 0.10) * 100),
            gameplay_type=gameplay.get("type", "merge_board"),
            gameplay_elements=", ".join(gameplay.get("elements", ["merge_items"])),
            reward_type=reward.get("type", "mixed"),
            reward_elements=", ".join(reward.get("elements", ["gems"])),
            color_palette=style.get("color_palette", "purple_gold").replace("_", " "),
            lighting=style.get("lighting", "magic_glow").replace("_", " "),
            camera=style.get("camera", "isometric").replace("_", " "),
            render_style=style.get("render_style", "3d_cartoon").replace("_", " "),
            layout=dna.get("layout", "center_merge").replace("_", " "),
            hook=dna.get("hook", "merge_upgrade").replace("_", " "),
            additional_requirements=additional,
        )

        negative = NEGATIVE_PROMPT_TEMPLATE.format(negative_additions=negative_add)

        # 参考图路径
        ref_image = ""
        for ad_id in winner.get("source_ad_ids", [])[:1]:
            p = THUMBNAILS_DIR / f"{ad_id}.jpg"
            if p.exists():
                ref_image = str(p)
                break
        if not ref_image and winner.get("thumbnail_urls"):
            ref_image = winner["thumbnail_urls"][0]

        return {
            "prompt": prompt.strip(),
            "negative_prompt": negative.strip(),
            "reference_image": ref_image,
            "winner_asset_id": winner.get("asset_id", ""),
            "winner_performance": winner.get("performance", {}),
            "variation": variation,
            "constraints": self._extract_hard_constraints(dna),
        }

    def build_batch(self, n_variations: int = 3,
                    top_n_winners: int = 3) -> List[Dict]:
        """批量构建多种变体的 Prompt

        Args:
            n_variations: 每个 winner 生成几种变体
            top_n_winners: 使用 Top N 个 winner

        Returns:
            Prompt 列表
        """
        if not self.dna_data:
            self.load()

        variations = ["default", "reward_focus", "gameplay_focus"]
        results = []

        winners = self.dna_data.get("winners", [])
        for i in range(min(top_n_winners, len(winners))):
            for v in variations[:n_variations]:
                result = self.build_prompt(winner_index=i, variation=v)
                results.append(result)

        return results

    def save_prompts(self, prompts: Optional[List[Dict]] = None):
        """保存 prompt 结果到文件"""
        ensure_dirs()

        if prompts is None:
            prompts = self.build_batch()

        output_path = OUTPUT_DIR / "generation_prompts.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "2.1.8",
                "total": len(prompts),
                "prompts": prompts,
            }, f, ensure_ascii=False, indent=2)

        print(f"[PromptBuilder] 已保存 {len(prompts)} 个 prompts: {output_path}")
        return output_path

    def build_from_mutation(self, mutation_variant: Dict) -> Dict[str, str]:
        """基于变异 DNA 构建 Prompt

        Args:
            mutation_variant: 变异 variant (含 mutated_dna, strategy, change, preserve 等)

        Returns:
            {"prompt": str, "negative_prompt": str, "reference_image": str, ...}
        """
        dna = mutation_variant.get("mutated_dna", {})

        # 提取 DNA 维度
        comp = dna.get("composition", {})
        gameplay = dna.get("gameplay", {})
        reward = dna.get("reward", {})
        style = dna.get("style", {})

        # 构图参数
        gp_area = comp.get("gameplay_area", {})
        rw_area = comp.get("reward_area", {})
        ch_area = comp.get("character_area", {})
        bg_area = comp.get("background_area", {})

        # 格式化 preserve/change 列表
        preserve_items = "\n".join(f"- {item}" for item in mutation_variant.get("preserve", []))
        change_items = "\n".join(f"- {item}" for item in mutation_variant.get("change", []))

        if not preserve_items:
            preserve_items = "- (all dimensions preserved)"
        if not change_items:
            change_items = "- (no changes applied)"

        # Winner 参考
        winner_source = mutation_variant.get("winner_source", {})
        winner_perf = winner_source.get("performance", {})
        perf_str = (
            f"ROAS: {winner_perf.get('roas', 'N/A')}, "
            f"Spend: ${winner_perf.get('spend', 0):,.0f}"
        ) if winner_perf else "N/A"

        color_palette = style.get("color_palette", "purple_gold")

        # 填充模板
        prompt = MUTATION_PROMPT_TEMPLATE.format(
            winner_asset_id=winner_source.get("asset_id", "unknown"),
            winner_performance=perf_str,
            strategy_label=mutation_variant.get("strategy_label", ""),
            mutation_reason=mutation_variant.get("mutation_reason", ""),
            expected_advantage=mutation_variant.get("expected_advantage", ""),
            preserve_items=preserve_items,
            change_items=change_items,
            gameplay_ratio=int(gp_area.get("ratio", 0.5) * 100),
            gameplay_position=gp_area.get("position", "center"),
            reward_ratio=int(rw_area.get("ratio", 0.25) * 100),
            reward_position=rw_area.get("position", "top_right"),
            character_ratio=int(ch_area.get("ratio", 0.15) * 100),
            background_ratio=int(bg_area.get("ratio", 0.10) * 100),
            gameplay_type=gameplay.get("type", "merge_board"),
            gameplay_elements=", ".join(gameplay.get("elements", ["merge_items"])),
            reward_type=reward.get("type", "mixed"),
            reward_elements=", ".join(reward.get("elements", ["gems"])),
            color_palette=color_palette.replace("_", " "),
            lighting=style.get("lighting", "magic_glow").replace("_", " "),
            camera=style.get("camera", "isometric").replace("_", " "),
            render_style=style.get("render_style", "3d_cartoon").replace("_", " "),
            layout=dna.get("layout", "center_merge").replace("_", " "),
            hook=dna.get("hook", "merge_upgrade").replace("_", " "),
        )

        negative = MUTATION_NEGATIVE_TEMPLATE.format(
            color_palette=color_palette.replace("_", " ")
        )

        return {
            "prompt": prompt.strip(),
            "negative_prompt": negative.strip(),
            "reference_image": "",
            "creative_id": mutation_variant.get("creative_id", ""),
            "winner_source": winner_source,
            "strategy": mutation_variant.get("strategy", ""),
            "strategy_label": mutation_variant.get("strategy_label", ""),
            "mutation_reason": mutation_variant.get("mutation_reason", ""),
            "expected_advantage": mutation_variant.get("expected_advantage", ""),
            "evolution_score": mutation_variant.get("_evolution_score", 0.0),
            "constraints": self._extract_hard_constraints(dna),
        }

    def build_batch_from_mutations(self, variants: List[Dict]) -> List[Dict]:
        """批量从变异列表构建 Prompts

        Args:
            variants: variant 列表

        Returns:
            Prompt 列表
        """
        results = []
        for v in variants:
            result = self.build_from_mutation(v)
            results.append(result)

        return results

    def save_mutation_prompts(self, prompts: List[Dict],
                              output_path: Optional[Path] = None):
        """保存 mutation-based prompts"""
        from ..config import DNA_EVOLUTION_DIR

        ensure_dirs()
        output_path = output_path or (DNA_EVOLUTION_DIR / "mutation_prompts.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "2.1.8-evo",
                "total": len(prompts),
                "prompts": prompts,
            }, f, ensure_ascii=False, indent=2)

        print(f"[PromptBuilder] 已保存 {len(prompts)} 个 mutation prompts: {output_path}")
        return output_path

    def _extract_hard_constraints(self, dna: dict) -> dict:
        """从 DNA 提取硬约束"""
        comp = dna.get("composition", {})
        return {
            "min_gameplay_ratio": max(0.3, comp.get("gameplay_area", {}).get("ratio", 0.5) - 0.15),
            "max_gameplay_ratio": min(1.0, comp.get("gameplay_area", {}).get("ratio", 0.5) + 0.15),
            "required_reward_type": dna.get("reward", {}).get("type", ""),
            "required_render_style": dna.get("style", {}).get("render_style", "3d_cartoon"),
            "required_color_palette": dna.get("style", {}).get("color_palette", ""),
        }

    def _default_prompt(self) -> Dict[str, str]:
        """无 DNA 数据时的默认 Prompt"""
        return {
            "prompt": "A professional mobile game advertisement for a merge puzzle game, featuring a colorful game board with merge items, magical creatures, and treasure rewards. Isometric 3D cartoon style with purple and gold color palette, magical glow lighting.",
            "negative_prompt": "blurry, low quality, text, watermark, UI elements",
            "reference_image": "",
            "winner_asset_id": "",
            "winner_performance": {},
            "variation": "default",
            "constraints": {},
        }
