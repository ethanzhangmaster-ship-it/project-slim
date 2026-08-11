"""创意变体扩张引擎 — 受控单变量展开

核心规则：每个变体仅改变一个变量，确保 Facebook A/B 测试归因可追溯。
策略分层：
  P0（安全/高ROI）→ 生成全部可能替换值
  P1（中等风险）  → 生成 top 3-5 替换值
  P2（高风险）    → 生成 top 1-2 替换值
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# 变量矩阵 — 定义 DNA 中哪些维度可以被替换、可选值、风险等级
# ---------------------------------------------------------------------------

@dataclass
class VariableSlot:
    """DNA 中一个可变维度的描述"""
    # 变量在 DNA dict 中的路径，如 ["visual_hierarchy", "level1"] 或 ["hook_type"]
    path: list[str]
    # 风险等级：P0=安全高ROI，P1=中等风险，P2=高风险
    risk_level: str
    # 该维度的可选替换值列表（已排除当前值，按效果降序排列）
    candidate_values: list[str]
    # 维度的人类可读名称，如 "hook_type"、"visual_hierarchy.level1"
    dimension_name: str


class VariableMatrix:
    """变量矩阵：维护 DNA 各维度的可选替换值与风险等级

    维度来源：基于 creative_dna_v2 / creative_dna 的 DNA 字段定义。
    风险等级依据：
      P0 — 已有数据支撑的高 ROI 变量（hook_type / emotion / cta_strength）
      P1 — 有一定效果的变量（color_theme / pace / copy_style / ui_type）
      P2 — 高风险探索变量（video_structure / composition / camera_angle / layout_template）
    """

    # ── 各维度的候选值池（按历史效果降序排列） ──

    HOOK_TYPE_VALUES: list[str] = [
        "collection", "transformation", "challenge", "secret",
        "curiosity", "progression", "achievement",
        "crisis", "reward", "twist", "wrong_choice",
        "before_after",
    ]

    EMOTION_VALUES: list[str] = [
        "excited", "surprise", "curious", "wow",
        "happy", "panic", "mysterious", "determined",
        "angry", "proud", "gentle", "fierce",
        "playful", "serene", "whimsical", "epic",
    ]

    CTA_STRENGTH_VALUES: list[str] = [
        "strong_cta", "soft_cta", "medium_cta",
    ]

    REWARD_TYPE_VALUES: list[str] = [
        "transformation", "collection", "unlock", "upgrade",
        "discovery", "power_up", "legendary_item",
    ]

    COLOR_THEME_VALUES: list[str] = [
        "vibrant", "warm", "cool", "dark", "pastel",
        "purple", "dark_purple", "blue_gold", "warm_gold",
        "lavender", "mysterious_blue", "enchanted", "glowing_gold",
    ]

    PACE_VALUES: list[str] = [
        "fast", "medium", "slow",
    ]

    COPY_STYLE_VALUES: list[str] = [
        "strong_title", "soft_title", "ugc", "native", "story",
    ]

    UI_TYPE_VALUES: list[str] = [
        "merge", "build", "battle", "puzzle", "simulation",
    ]

    VIDEO_STRUCTURE_VALUES: list[str] = [
        "ugc", "gameplay", "image", "playable", "cinematic",
    ]

    COMPOSITION_VALUES: list[str] = [
        "center_focus", "rule_of_thirds", "diagonal",
    ]

    CAMERA_ANGLE_VALUES: list[str] = [
        "front", "low_angle", "overhead", "close_up",
    ]

    LAYOUT_TEMPLATE_VALUES: list[str] = [
        "merge_formula", "evolution_chain", "before_after_transformation",
    ]

    ATTENTION_GOAL_VALUES: list[str] = [
        "reward_first", "mechanism_first",
    ]

    MECHANISM_TYPE_VALUES: list[str] = [
        "merge", "evolution", "collection", "progression_chain",
        "transformation", "comparison",
    ]

    SUBTITLE_STYLE_VALUES: list[str] = [
        "large_subtitle", "suspense_subtitle", "dense_subtitle",
    ]

    FIRST_3S_DENSITY_VALUES: list[str] = [
        "high_density", "low_density", "medium_density",
    ]

    CONFLICT_STRENGTH_VALUES: list[str] = [
        "strong_conflict", "soft_conflict", "medium_conflict",
    ]

    # ── 维度 → (路径, 风险等级) 映射 ──
    # 路径支持嵌套 dict，如 visual_hierarchy.level1 → ["visual_hierarchy", "level1"]
    DIMENSION_REGISTRY: list[tuple[str, list[str], str]] = [
        # ── P0 维度：安全高ROI ──
        # 生物颜色
        ("creature_0_color",       ["creatures", "0", "color"],                 "P0"),
        ("creature_0_glow",        ["creatures", "0", "glow"],                  "P0"),
        ("creature_0_action",      ["creatures", "0", "action"],                "P0"),
        # 粒子/灯光颜色
        ("lighting_effects_0",     ["lighting", "special_effects", "0"],        "P0"),
        ("lighting_temperature",   ["lighting", "color_temperature"],           "P0"),
        # 颜色主题
        ("colors_mood",            ["colors", "mood_palette"],                  "P0"),

        # ── P1 维度：中等风险 ──
        # 生物类型（比颜色风险高）
        ("creature_0_type",        ["creatures", "0", "type"],                  "P1"),
        # 角色
        ("character_clothes",      ["character", "clothes"],                    "P1"),
        ("character_pose",         ["character", "pose"],                       "P1"),
        ("character_gesture",      ["character", "gesture"],                    "P1"),
        # 镜头
        ("camera_shot",            ["camera", "shot_type"],                     "P1"),
        ("camera_movement",        ["camera", "movement"],                      "P1"),
        # 环境
        ("environment_type",       ["environment", "type"],                     "P1"),
        ("environment_time",       ["environment", "time"],                     "P1"),

        # ── P2 维度：高风险 ──
        ("character_type",         ["character", "type"],                       "P2"),
        ("hook_type",              ["hook", "type"],                            "P2"),
        ("composition_layout",     ["composition", "layout"],                   "P2"),
    ]

    # 维度 → 候选值池 映射
    VALUE_POOLS: dict[str, list[str]] = {
        # P0
        "creature_0_color": [
            "blue", "cyan", "pink", "purple", "green", "gold",
            "orange", "white", "rainbow", "silver",
        ],
        "creature_0_glow": [
            "cyan", "pink", "gold", "white", "purple",
            "green", "rainbow", "soft_blue",
        ],
        "creature_0_action": [
            "perched", "flying", "sleeping", "playing", "curious",
            "eating", "hiding", "running", "glowing",
        ],
        "lighting_effects_0": [
            "particles", "bloom", "sparkles", "glow", "rays",
            "fireflies", "snow", "bubbles", "stars",
        ],
        "lighting_temperature": [
            "warm", "cool", "neutral", "golden", "moonlit",
            "sunset", "dawn", "mysterious",
        ],
        "colors_mood": [
            "balanced", "warm", "cool", "vibrant", "dark",
            "pastel", "enchanted", "mysterious", "epic",
        ],
        # P1
        "creature_0_type": [
            "dragon", "cat", "fox", "owl", "unicorn",
            "fairy", "magic_egg", "squirrel", "phoenix", "rabbit",
        ],
        "character_clothes": [
            "dark purple cloak + gold trim", "blue robe + silver trim",
            "red dress + gold accessories", "green cloak + leaf ornaments",
            "black robe + star pattern", "pink dress + flower crown",
        ],
        "character_pose": [
            "standing centered", "sitting on mushroom", "floating midair",
            "walking toward camera", "kneeling by pond", "standing with arms open",
        ],
        "character_gesture": [
            "hands clasped", "pointing forward", "waving", "casting spell",
            "holding creature", "arms open welcome", "hand on hip",
        ],
        "camera_shot": [
            "medium", "close_up", "wide", "full_body", "extreme_close",
        ],
        "camera_movement": [
            "static", "push_in", "orbit", "tilt_up", "pull_back", "slow_zoom",
        ],
        "environment_type": [
            "magic_forest", "crystal_cave", "moon_lake", "magic_garden",
            "star_tower", "sky_island", "vineyard", "mushroom_village",
        ],
        "environment_time": [
            "night", "sunset", "dawn", "dusk", "midnight", "twilight",
        ],
        # P2
        "character_type": [
            "witch", "wizard", "girl", "boy", "fairy_queen", "sorceress",
        ],
        "hook_type": [
            "collection", "curiosity", "crisis", "reward", "comparison",
            "transformation", "challenge",
        ],
        "composition_layout": [
            "centered", "layered", "rule_of_thirds", "split", "diagonal",
        ],
    }

    def get_variable_slots(self, dna: dict) -> list[VariableSlot]:
        """从 DNA 中提取所有可变维度及其候选替换值

        自动排除当前值（避免生成无变化的变体）。
        """
        slots: list[VariableSlot] = []
        for dim_name, path, risk_level in self.DIMENSION_REGISTRY:
            current_value = self._get_value_by_path(dna, path)
            if current_value is None:
                # DNA 中不存在该维度，跳过
                continue
            pool = self.VALUE_POOLS.get(dim_name, [])
            # 排除当前值，避免无变化变体
            candidates = [v for v in pool if v != current_value]
            if not candidates:
                continue
            slots.append(VariableSlot(
                path=path,
                risk_level=risk_level,
                candidate_values=candidates,
                dimension_name=dim_name,
            ))
        return slots

    @staticmethod
    def _get_value_by_path(dna: dict, path: list[str]) -> Any:
        """沿路径取值，如 ["visual_hierarchy", "level1"] → dna["visual_hierarchy"]["level1"]"""
        current = dna
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current


# ---------------------------------------------------------------------------
# 变体数据结构
# ---------------------------------------------------------------------------

@dataclass
class Variant:
    variant_id: str  # "V001"
    parent_dna_id: str  # 来源 winning creative 的 DNA ID
    changed_dimension: str  # 被更改的单一维度名称
    changed_path: list[str]  # DNA 图中的路径
    old_value: str  # 原始值
    new_value: str  # 新值
    risk_level: str  # P0/P1/P2
    modified_dna: dict  # 应用单点变更后的完整 DNA
    generation_priority: int  # 越小优先级越高（P0 最先）


# ---------------------------------------------------------------------------
# 扩张引擎
# ---------------------------------------------------------------------------

class ExpansionEngine:
    """生成单变量变体引擎：每次仅变更一个变量，确保 A/B 归因可追溯"""

    def __init__(self, variable_matrix: VariableMatrix, max_variants: int = 100):
        self.matrix = variable_matrix
        self.max_variants = max_variants

    # ── 主入口 ──

    def expand(self, dna: dict, target_count: int = 100) -> list[Variant]:
        """从 winning creative DNA 生成变体

        策略：
        1. 先生成全部 P0 变体（安全，高 ROI）
        2. 再生成 P1 变体（中等风险）
        3. 最后 P2 变体（高风险，仅在需要时填充）
        每个变体仅改变一个变量。
        """
        # 1. 提取 DNA 中所有可变维度
        slots = self.matrix.get_variable_slots(dna)
        parent_dna_id = str(dna.get("dna_id") or dna.get("creative_id") or "unknown")

        # 2. 按风险等级分组
        p0_slots = [s for s in slots if s.risk_level == "P0"]
        p1_slots = [s for s in slots if s.risk_level == "P1"]
        p2_slots = [s for s in slots if s.risk_level == "P2"]

        # 3. 分层生成变体
        variants: list[Variant] = []
        variant_counter = 0

        # P0：生成全部可能替换值
        for slot in p0_slots:
            for new_value in slot.candidate_values:
                old_value = self._get_current_value(dna, slot.path)
                modified = self._apply_single_change(dna, slot.path, new_value)
                priority = self._calculate_priority("P0") + variant_counter
                variants.append(Variant(
                    variant_id=f"V{variant_counter + 1:03d}",
                    parent_dna_id=parent_dna_id,
                    changed_dimension=slot.dimension_name,
                    changed_path=slot.path,
                    old_value=str(old_value),
                    new_value=new_value,
                    risk_level="P0",
                    modified_dna=modified,
                    generation_priority=priority,
                ))
                variant_counter += 1

        # P1：每个维度取 top 3-5 替换值
        for slot in p1_slots:
            top_values = slot.candidate_values[:5]
            for new_value in top_values:
                old_value = self._get_current_value(dna, slot.path)
                modified = self._apply_single_change(dna, slot.path, new_value)
                priority = self._calculate_priority("P1") + variant_counter
                variants.append(Variant(
                    variant_id=f"V{variant_counter + 1:03d}",
                    parent_dna_id=parent_dna_id,
                    changed_dimension=slot.dimension_name,
                    changed_path=slot.path,
                    old_value=str(old_value),
                    new_value=new_value,
                    risk_level="P1",
                    modified_dna=modified,
                    generation_priority=priority,
                ))
                variant_counter += 1

        # P2：每个维度取 top 1-2 替换值
        for slot in p2_slots:
            top_values = slot.candidate_values[:2]
            for new_value in top_values:
                old_value = self._get_current_value(dna, slot.path)
                modified = self._apply_single_change(dna, slot.path, new_value)
                priority = self._calculate_priority("P2") + variant_counter
                variants.append(Variant(
                    variant_id=f"V{variant_counter + 1:03d}",
                    parent_dna_id=parent_dna_id,
                    changed_dimension=slot.dimension_name,
                    changed_path=slot.path,
                    old_value=str(old_value),
                    new_value=new_value,
                    risk_level="P2",
                    modified_dna=modified,
                    generation_priority=priority,
                ))
                variant_counter += 1

        # 4. 去重：移除产生相同 DNA 状态的变体
        variants = self.deduplicate(variants)

        # 5. 按优先级排序（P0 → P1 → P2，同级别内按序号）
        variants.sort(key=lambda v: v.generation_priority)

        # 6. 截断到 max_variants
        effective_limit = min(target_count, self.max_variants)
        return variants[:effective_limit]

    # ── 内部方法 ──

    def _apply_single_change(self, dna: dict, path: list[str], new_value: str) -> dict:
        """深拷贝 DNA 并在指定路径应用单点变更

        保持其他所有变量不变，确保单变量控制。
        """
        result = copy.deepcopy(dna)
        current = result
        # 沿路径逐层深入，直到倒数第二层
        for key in path[:-1]:
            if key not in current or not isinstance(current[key], dict):
                # 路径不存在则创建嵌套 dict
                current[key] = {}
            current = current[key]
        # 在最终层级设置新值
        current[path[-1]] = new_value
        return result

    def _calculate_priority(self, risk_level: str) -> int:
        """计算生成优先级：P0=0, P1=1000, P2=2000

        越小优先级越高，保证 P0 变体排在最前面。
        """
        mapping = {"P0": 0, "P1": 1000, "P2": 2000}
        return mapping.get(risk_level, 9999)

    def _get_current_value(self, dna: dict, path: list[str]) -> Any:
        """沿路径取 DNA 中的当前值"""
        return VariableMatrix._get_value_by_path(dna, path)

    def deduplicate(self, variants: list[Variant]) -> list[Variant]:
        """去除产生相同 DNA 状态的变体

        两个变体如果最终 DNA 一模一样，则保留优先级更高的那个。
        使用 DNA 的 JSON 序列化作为去重键，忽略 dna_id / creative_id
        等元数据字段（它们是标识符而非 DNA 内容）。
        """
        seen: dict[str, Variant] = {}
        identity_keys = {"dna_id", "creative_id"}

        for variant in variants:
            # 构建去重键：排除标识符字段，只看 DNA 内容
            dna_copy = {
                k: v for k, v in variant.modified_dna.items()
                if k not in identity_keys
            }
            dedup_key = json.dumps(dna_copy, sort_keys=True, ensure_ascii=False)

            if dedup_key not in seen:
                seen[dedup_key] = variant
            else:
                # 保留优先级更高的（generation_priority 更小的）
                existing = seen[dedup_key]
                if variant.generation_priority < existing.generation_priority:
                    seen[dedup_key] = variant

        return list(seen.values())
