"""DNA Mutator — Winner DNA 变异引擎

输入: Winner DNA (from true_winner_dna.json)
输出: Variant Pool (dna_variants.json)

每个 Winner 按 4 种策略生成变异, 每种策略在保留核心维度的前提下
随机替换可变维度。
"""
import json
import random
import copy
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import (
    OUTPUT_DIR, DNA_EVOLUTION_DIR, PRESERVE_WEIGHTS,
    EVO_TOP_WINNERS, EVO_VARIANTS_PER, ensure_dirs,
)
from .mutation_rules import (
    DNA_DIMENSIONS, MUTATION_POOLS, VARIANT_STRATEGIES,
)


class DNAMutator:
    """Winner DNA 变异引擎"""

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        self.winners: List[dict] = []
        self.variants: List[dict] = []

    def load_winner_dna(self, dna_path: Optional[Path] = None) -> List[dict]:
        """加载 Winner DNA

        Args:
            dna_path: true_winner_dna.json 路径

        Returns:
            Winner 列表
        """
        dna_path = dna_path or (OUTPUT_DIR / "true_winner_dna.json")
        with open(dna_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.winners = data.get("winners", [])
        print(f"[DNAMutator] 加载 {len(self.winners)} 个 Winner DNA")
        return self.winners

    def mutate(self, winner: dict, strategy_key: str) -> Optional[dict]:
        """对单个 Winner DNA 按策略变异

        Args:
            winner: Winner DNA 记录 (含 dna 字段)
            strategy_key: 策略名 (A/B/C/D)

        Returns:
            变异后的 variant dict, 含 winner_reference/mutation_reason/preserve/change
        """
        strategy = VARIANT_STRATEGIES.get(strategy_key)
        if not strategy:
            print(f"[DNAMutator] 未知策略: {strategy_key}")
            return None

        source_dna = winner.get("dna", {})
        if not source_dna:
            return None

        # 深拷贝 DNA, 只变异 mutate 列表中的维度
        mutated_dna = copy.deepcopy(source_dna)

        preserve_list = []
        change_list = []

        # 保留维度: 不做任何修改
        for dim_key in strategy["preserve"]:
            dim_info = DNA_DIMENSIONS.get(dim_key, {})
            dim_name = dim_info.get("path", [dim_key])[-1] if dim_info.get("path") else dim_key
            preserve_list.append(self._describe_dimension(dim_key, mutated_dna))

        # 变异维度: 从候选池随机替换
        for dim_key in strategy["mutate"]:
            changes = self._apply_mutation(dim_key, mutated_dna, source_dna)
            if changes:
                change_list.append(changes)

        # 生成 variant
        winner_id = winner.get("asset_id", "unknown")
        variant_id = f"{winner_id}_mutation_{strategy_key}"

        return {
            "creative_id": variant_id,
            "winner_source": {
                "asset_id": winner_id,
                "ad_names": winner.get("sample_names", []),
                "performance": winner.get("performance", {}),
            },
            "strategy": strategy_key,
            "strategy_label": strategy.get("strategy_label", ""),
            "mutation_reason": strategy["description"],
            "expected_advantage": strategy["expected_advantage"],
            "preserve": preserve_list,
            "change": change_list,
            "mutated_dna": mutated_dna,
            "original_dna": source_dna,
        }

    def generate_pool(self, top_n: Optional[int] = None) -> List[dict]:
        """生成完整 Variant Pool

        Args:
            top_n: 使用 Top N 个 winner (默认 EVO_TOP_WINNERS)

        Returns:
            Variant 列表
        """
        if not self.winners:
            self.load_winner_dna()

        top_n = top_n or EVO_TOP_WINNERS
        top_winners = self.winners[:min(top_n, len(self.winners))]

        self.variants = []
        strategies = list(VARIANT_STRATEGIES.keys())[:EVO_VARIANTS_PER]

        for winner in top_winners:
            for sk in strategies:
                variant = self.mutate(winner, sk)
                if variant:
                    self.variants.append(variant)

        print(f"[DNAMutator] 生成 {len(self.variants)} 个 variants "
              f"({len(top_winners)} winners × {len(strategies)} strategies)")

        # 保存
        self.save()
        return self.variants

    def save(self, output_path: Optional[Path] = None):
        """保存 variants 到 dna_variants.json"""
        ensure_dirs()
        output_path = output_path or (DNA_EVOLUTION_DIR / "dna_variants.json")

        clean = []
        for v in self.variants:
            clean.append({
                "creative_id": v["creative_id"],
                "winner_source": v["winner_source"],
                "strategy": v["strategy"],
                "strategy_label": v["strategy_label"],
                "mutation_reason": v["mutation_reason"],
                "expected_advantage": v["expected_advantage"],
                "preserve": v["preserve"],
                "change": v["change"],
                "mutated_dna": v["mutated_dna"],
            })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "2.1.8-evo",
                "total": len(clean),
                "variants": clean,
            }, f, ensure_ascii=False, indent=2)

        print(f"[DNAMutator] 已保存: {output_path}")

    # --- 内部方法 ---

    def _apply_mutation(self, dim_key: str, dna: dict, original: dict) -> Optional[str]:
        """对单个维度应用变异

        Returns:
            变更描述字符串, 无变更则返回 None
        """
        if dim_key == "style":
            return self._mutate_style(dna, original)
        elif dim_key == "reward":
            return self._mutate_reward(dna, original)
        elif dim_key == "composition":
            return self._mutate_composition(dna, original)
        elif dim_key == "layout":
            return self._mutate_layout(dna, original)
        elif dim_key == "gameplay":
            return self._mutate_gameplay(dna, original)
        return None

    def _mutate_style(self, dna: dict, original: dict) -> Optional[str]:
        """变异 style 维度"""
        style = dna.get("style", {})
        orig_style = original.get("style", {})

        pool = MUTATION_POOLS.get("style", {})
        changes = {}

        for key, candidates in pool.items():
            if not candidates:
                continue
            # 50% 概率变异每个子维度
            if random.random() < 0.5:
                old_val = orig_style.get(key, "")
                new_val = random.choice([c for c in candidates if c != old_val] or candidates)
                style[key] = new_val
                changes[key] = f"{old_val} → {new_val}"

        # 保证至少 1 个变化
        if not changes:
            # 随机选一个子维度强制变异
            key = random.choice(list(pool.keys()))
            candidates = pool[key]
            if candidates:
                old_val = orig_style.get(key, "")
                new_val = random.choice([c for c in candidates if c != old_val] or candidates)
                style[key] = new_val
                changes[key] = f"{old_val} → {new_val}"

        if changes:
            parts = [f"{k}: {v}" for k, v in changes.items()]
            return f"Style 变异: {', '.join(parts)}"
        return None

    def _mutate_reward(self, dna: dict, original: dict) -> Optional[str]:
        """变异 reward 维度"""
        reward = dna.get("reward", {})
        orig_reward = original.get("reward", {})

        pool = MUTATION_POOLS.get("reward", {})
        changes = {}

        # 60% 概率变异 reward type
        type_candidates = pool.get("type", [])
        if type_candidates and random.random() < 0.6:
            old_val = orig_reward.get("type", "")
            new_val = random.choice([c for c in type_candidates if c != old_val] or type_candidates)
            reward["type"] = new_val
            changes["type"] = f"{old_val} → {new_val}"

        # 50% 概率变异 reward elements
        elem_candidates = pool.get("elements", [])
        if elem_candidates and random.random() < 0.5:
            old_val = orig_reward.get("elements", [])
            new_val = random.choice(elem_candidates)
            reward["elements"] = new_val
            changes["elements"] = f"{old_val} → {new_val}"

        # 保证至少 1 个变化
        if not changes:
            if type_candidates:
                old_val = orig_reward.get("type", "")
                new_val = random.choice([c for c in type_candidates if c != old_val] or type_candidates)
                reward["type"] = new_val
                changes["type"] = f"{old_val} → {new_val}"

        if changes:
            parts = [f"{k}: {v}" for k, v in changes.items()]
            return f"Reward 变异: {', '.join(parts)}"
        return None

    def _mutate_composition(self, dna: dict, original: dict) -> Optional[str]:
        """变异 composition 维度 (重排区域比例)"""
        comp = dna.get("composition", {})
        pool = MUTATION_POOLS.get("composition", {})

        # 选择新的 gameplay ratio (必须与原始值不同)
        old_gp = comp.get("gameplay_area", {}).get("ratio", 0.5)
        old_rw = comp.get("reward_area", {}).get("ratio", 0.25)
        gr = pool.get("gameplay_ratio_range", [0.5])
        rr = pool.get("reward_ratio_range", [0.25])

        gr_diff = [r for r in gr if abs(r - old_gp) > 0.01]
        rr_diff = [r for r in rr if abs(r - old_rw) > 0.01]
        new_gp = random.choice(gr_diff) if gr_diff else random.choice(gr)
        new_rw = random.choice(rr_diff) if rr_diff else random.choice(rr)

        # 确保总和不超过 1.0
        if new_gp + new_rw > 0.85:
            new_gp = 0.50
            new_rw = 0.25

        remaining = 1.0 - new_gp - new_rw
        new_ch = round(remaining * 0.6, 2)
        new_bg = round(remaining - new_ch, 2)

        comp["gameplay_area"]["ratio"] = new_gp
        comp["reward_area"]["ratio"] = new_rw
        comp["character_area"]["ratio"] = new_ch
        comp["background_area"]["ratio"] = new_bg

        # 80% 概率变更 position (确保与原始不同)
        rp = pool.get("reward_position", ["top_right"])
        cp = pool.get("character_position", ["bottom_left"])
        old_rp = comp.get("reward_area", {}).get("position", "")
        old_cp = comp.get("character_area", {}).get("position", "")

        if random.random() < 0.8:
            rp_diff = [p for p in rp if p != old_rp]
            comp["reward_area"]["position"] = random.choice(rp_diff) if rp_diff else random.choice(rp)
        if random.random() < 0.8:
            cp_diff = [p for p in cp if p != old_cp]
            comp["character_area"]["position"] = random.choice(cp_diff) if cp_diff else random.choice(cp)

        return (f"Composition 变异: gameplay {old_gp}→{new_gp}, "
                f"reward {old_rw}→{new_rw}")

    def _mutate_layout(self, dna: dict, original: dict) -> Optional[str]:
        """变异 layout"""
        pool = MUTATION_POOLS.get("layout", {}).get("values", [])
        old_val = dna.get("layout", "")
        if pool:
            pool_diff = [v for v in pool if v != old_val]
            new_val = random.choice(pool_diff) if pool_diff else random.choice(pool)
            dna["layout"] = new_val
            return f"Layout 变异: {old_val} → {new_val}"
        return None

    def _mutate_gameplay(self, dna: dict, original: dict) -> Optional[str]:
        """变异 gameplay elements (保留 type, 仅变异 elements)"""
        gameplay = dna.get("gameplay", {})
        # gameplay type 保留, 仅尝试变更 elements
        # 这里保持保守, 不实际改变 type
        return None

    def _describe_dimension(self, dim_key: str, dna: dict) -> str:
        """描述某个维度的当前值"""
        if dim_key == "composition":
            comp = dna.get("composition", {})
            gp = comp.get("gameplay_area", {})
            rw = comp.get("reward_area", {})
            return f"Composition: gameplay={gp.get('ratio', '?')}@{gp.get('position', '?')}, reward={rw.get('ratio', '?')}"
        elif dim_key == "gameplay":
            gp = dna.get("gameplay", {})
            return f"Gameplay: {gp.get('type', '?')} [{', '.join(gp.get('elements', []))}]"
        elif dim_key == "reward":
            rw = dna.get("reward", {})
            return f"Reward: {rw.get('type', '?')} [{', '.join(rw.get('elements', []))}]"
        elif dim_key == "style":
            st = dna.get("style", {})
            return f"Style: {st.get('color_palette', '?')} | {st.get('render_style', '?')}"
        elif dim_key == "hook":
            return f"Hook: {dna.get('hook', '?')}"
        elif dim_key == "layout":
            return f"Layout: {dna.get('layout', '?')}"
        return f"{dim_key}: preserved"
