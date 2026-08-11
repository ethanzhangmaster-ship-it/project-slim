"""Prompt Generator - Facebook Creative Expansion Agent

为 Facebook 广告渠道的每个 variant 生成全类型 prompt：
  1. Image Prompt    → AI 图片生成 (Lovart/Midjourney/SDXL)
  2. Video Prompt    → AI 视频生成 (Runway/Pika/Kling)
  3. Motion Prompt   → 镜头与运动方向
  4. Storyboard      → 完整分镜含时序
  5. Thumbnail       → Facebook 广告缩略图
  6. Headline        → Facebook 广告标题文案
  7. Primary Text    → Facebook 广告正文文案
  8. CTA             → 行动号召文案
  + Negative Prompt  → 需要避免的元素

游戏上下文：Merge Witches
  - 核心玩法：合并魔法物品、收集生物、建设魔法世界
  - 目标受众：休闲手游玩家，女性 25-45 为主
  - 高 ROAS 视频：可爱 Q 版女巫、魔法生物（龙/猫）、生物发光环境
  - Facebook 投放位：Reels / Stories / Feed / IG Feed
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Merge Witches 游戏专用常量
# ---------------------------------------------------------------------------

MERGE_WITCHES_DNA = {
    "game_name": "Merge Witches",
    "genre": "merge_puzzle",
    "target_audience": "casual_female_25_45",
    "core_loop": "merge magical items → collect creatures → build magical world",
    "top_creatures": [
        "baby dragon",
        "magical cat",
        "phoenix chick",
        "forest fairy",
        "crystal unicorn",
    ],
    "key_items": [
        "magic cauldron",
        "crystal ball",
        "spell book",
        "star wand",
        "dragon egg",
        "moon lantern",
        "mushroom house",
        "potion flask",
    ],
    "environments": [
        "enchanted forest with bioluminescent mushrooms",
        "mystical crystal cavern",
        "floating sky island with rainbow waterfalls",
        "ancient magical garden with glowing flowers",
        "witch's cottage interior with potion shelves",
    ],
    "color_palette": {
        "deep_purple": "#2D1B4E",
        "teal": "#00D4AA",
        "warm_gold": "#FFD700",
        "soft_pink": "#FFB6C1",
        "mystic_blue": "#4A90D9",
        "biolum_green": "#39FF14",
        "sunset_orange": "#FF6B35",
        "shadow_violet": "#7B2D8E",
    },
    "style": "3D cartoon, Pixar quality, chibi proportions, high saturation",
}

# Facebook 最佳实践约束
FB_CONSTRAINTS = {
    "hook_first_3s": "Subject must be prominent in first 3 seconds",
    "subject_coverage": "Subject occupies 40-70% of frame",
    "vertical_first": "Default 9:16, compatible with 4:5 and 1:1",
    "duration": "15-30s default, support 6s hook cut",
    "brand_consistency": "Logo top-left, game name, CTA fixed position",
    "style_consistency": "Must match winning creative visual DNA",
}

# SDXL / Midjourney 质量修饰词
QUALITY_MODIFIERS = [
    "3D render",
    "Pixar-like quality",
    "highly detailed",
    "sharp focus",
    "vibrant saturated colors",
    "professional mobile game advertising",
    "octane render",
    "global illumination",
    "subsurface scattering on skin",
    "volumetric lighting",
]

# Facebook 广告标题模板 (Merge Witches 专用)
HEADLINE_TEMPLATES = {
    "curiosity": [
        "What happens when you merge these?",
        "Can you guess the result?",
        "Something magical is about to happen!",
    ],
    "transformation": [
        "Watch this amazing transformation!",
        "From tiny to LEGENDARY!",
        "The evolution is REAL!",
    ],
    "challenge": [
        "Can you merge them all?",
        "Only 1% can unlock this creature!",
        "Think you can handle the magic?",
    ],
    "secret": [
        "The secret creature nobody knows about",
        "Hidden merge recipe revealed!",
        "Unlock the MYSTICAL dragon!",
    ],
    "collection": [
        "Collect ALL the magical creatures!",
        "Build your dream witch world!",
        "How many can YOU collect?",
    ],
    "reward": [
        "Claim your FREE legendary dragon!",
        "Free rewards waiting inside!",
        "Unlock powerful magic NOW!",
    ],
    "progression": [
        "Level up your magical world!",
        "Grow your witch powers!",
        "Evolve creatures to the MAX!",
    ],
    "urgency": [
        "Limited-time magical event!",
        "Don't miss this legendary creature!",
        "Hurry — the portal is closing!",
    ],
    "social": [
        "10 million witches are playing!",
        "Join the magical community!",
        "Your friends are already merging!",
    ],
    "achievement": [
        "Become the ULTIMATE witch!",
        "Reach the highest level!",
        "Master every merge combo!",
    ],
}

# Facebook 广告正文模板 (Merge Witches 专用)
PRIMARY_TEXT_TEMPLATES = {
    "curiosity": [
        "Discover a world where magic comes alive! Merge mysterious items and watch them transform into something extraordinary. What will YOU create?",
        "Ever wonder what happens when you merge two magic wands? The answer will blow your mind! Start merging and discover secrets today.",
        "Hidden creatures are waiting to be discovered. Merge magical items, unlock secret recipes, and build the most enchanted world ever!",
    ],
    "transformation": [
        "From a tiny egg to a LEGENDARY dragon! Watch your creatures evolve through magical merging. Start your transformation journey now!",
        "Merge, evolve, and transform! Your small magical items can become the most powerful artifacts in the realm. See the magic happen!",
        "The transformation is incredible! Merge items to evolve creatures from cute babies to mythical legends. Your magical world awaits!",
    ],
    "challenge": [
        "Think you have what it takes to merge them all? Challenge yourself with hundreds of magical combinations. Can you unlock every creature?",
        "Only the best witches can complete the ultimate merge. Are you up for the challenge? Test your skills and prove your magic!",
        "Hundreds of merge combos, countless creatures to discover. Can you collect them all? The ultimate magical challenge starts now!",
    ],
    "secret": [
        "There's a secret creature hiding in Merge Witches that most players never find. Merge the right items and unlock the mystery!",
        "Shhh... there's a hidden recipe that creates the rarest creature in the game. Can you figure it out? Start merging to find out!",
        "Secret merge combos exist that create LEGENDARY creatures. Most players don't know about them. Will you be the one to discover them all?",
    ],
    "collection": [
        "Collect adorable magical creatures — from baby dragons to crystal unicorns! Merge items, hatch eggs, and build the cutest magical world ever!",
        "Hundreds of creatures are waiting to join your collection! Merge magical items, unlock new species, and create the most enchanting world!",
        "Every merge brings you closer to completing your collection! Discover rare creatures, unlock secret habitats, and show off your magical zoo!",
    ],
    "reward": [
        "FREE legendary dragon inside! Merge magical items and claim powerful rewards. Your magical adventure starts with one tap!",
        "Unlock FREE magical rewards every day! Merge items, collect creatures, and earn legendary prizes. Start now and claim your first reward!",
        "Powerful rewards await! Merge items to unlock legendary creatures, rare artifacts, and magical treasures. Claim yours today!",
    ],
    "progression": [
        "Start with a tiny cottage and build an entire magical kingdom! Merge items, evolve creatures, and watch your world grow. Your magical empire awaits!",
        "Level up your witch powers with every merge! From beginner to legendary sorceress — the journey is magical. Start evolving now!",
        "Grow from a small enchanted garden to a sprawling magical realm! Merge, evolve, and build your way to the top. Every merge counts!",
    ],
}

# CTA 模板 (Facebook 广告)
CTA_TEMPLATES = {
    "high_urgency": ["Play Now FREE!", "Download NOW!", "Start Merging!"],
    "curiosity": ["Discover the Magic", "See What Happens", "Try It Free"],
    "reward": ["Claim Your Reward", "Get Free Dragon", "Unlock Now"],
    "social": ["Join 10M Players", "Play with Friends", "Join the Magic"],
    "default": ["Install Now", "Play Now", "Download Free"],
}

# 负面提示词 (需要避免的元素)
NEGATIVE_PROMPT_BASE = (
    "blurry, low quality, deformed, ugly, bad anatomy, "
    "extra limbs, missing limbs, disfigured, poorly drawn face, "
    "mutated, extra fingers, watermark, text overlay, "
    "realistic human, photorealistic, horror, gore, "
    "dark scary, weapons, violence, blood, "
    "low resolution, pixelated, jpeg artifacts, "
    "cropped, out of frame, worst quality, "
    "male-oriented, masculine, military, "
    "copyrighted character, brand logo (except game), "
    "horizontal layout, landscape orientation, "
    "small subject, tiny character, far away subject, "
    "boring background, flat lighting, no depth"
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class VariantPrompts:
    """单个 variant 的全类型 prompt 集合"""
    variant_id: str
    image_prompt: str
    video_prompt: str
    motion_prompt: str
    storyboard_prompt: str
    thumbnail_prompt: str
    headline_suggestions: List[str]       # 3 options
    primary_text_suggestions: List[str]   # 3 options
    cta_suggestions: List[str]            # 3 options
    negative_prompt: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "image_prompt": self.image_prompt,
            "video_prompt": self.video_prompt,
            "motion_prompt": self.motion_prompt,
            "storyboard_prompt": self.storyboard_prompt,
            "thumbnail_prompt": self.thumbnail_prompt,
            "headline_suggestions": self.headline_suggestions,
            "primary_text_suggestions": self.primary_text_suggestions,
            "cta_suggestions": self.cta_suggestions,
            "negative_prompt": self.negative_prompt,
        }


# ---------------------------------------------------------------------------
# Prompt Generator
# ---------------------------------------------------------------------------

class PromptGenerator:
    """Generates all prompt types for Facebook creative variants.

    针对每一个 variant（变体），一次性生成全部 8 类 prompt + negative prompt。
    输入是 variant dict 和 base_dna dict（来自 winning creative 分析）。
    """

    # Facebook 投放约束（公开只读引用）
    FB_CONSTRAINTS = FB_CONSTRAINTS

    # 合并特效描述词库
    MERGE_FX = [
        "magical fusion sparkle burst",
        "bioluminescent merge energy swirl",
        "prismatic light beam connecting two items",
        "golden particle trail spiral",
        "crystalline shard explosion with teal glow",
    ]

    # 生物特征描述词库
    CREATURE_DETAILS = {
        "baby dragon": (
            "tiny baby dragon with big round sparkling eyes (#4A90D9), "
            "iridescent teal (#00D4AA) scales with golden (#FFD700) belly, "
            "small translucent wings, cute chibi proportions (head:body = 1:1), "
            "wisps of warm smoke from nostrils, curled tail with glowing tip"
        ),
        "magical cat": (
            "fluffy magical cat with large emerald eyes, "
            "purple (#2D1B4E) and pink (#FFB6C1) gradient fur, "
            "floating sparkles around ears, tiny star-shaped markings on forehead, "
            "cute chibi proportions, long swishing tail with glowing orb at tip"
        ),
        "phoenix chick": (
            "adorable phoenix chick with fluffy sunset-orange (#FF6B35) feathers, "
            "golden (#FFD700) wing tips with ember particles, "
            "bright curious eyes, small flame crown on head, "
            "cute chibi proportions, trailing warm light particles"
        ),
        "forest fairy": (
            "tiny forest fairy with translucent bioluminescent (#39FF14) wings, "
            "soft green and teal (#00D4AA) dress made of leaves, "
            "glowing flower crown, sparkling trail of pollen dust, "
            "cute chibi proportions, gentle floating pose"
        ),
        "crystal unicorn": (
            "small crystal unicorn with translucent mystic-blue (#4A90D9) mane, "
            "body shimmering with prismatic reflections, "
            "golden (#FFD700) twisted horn with glow effect, "
            "cute chibi proportions, sparkly hoof trails"
        ),
    }

    # 环境描述词库
    ENVIRONMENT_DETAILS = {
        "enchanted_forest": (
            "enchanted forest, towering ancient trees with bioluminescent (#39FF14) "
            "mushrooms at base, floating teal (#00D4AA) fireflies, "
            "soft purple (#2D1B4E) mist rolling across ground, "
            "warm golden (#FFD700) light rays filtering through canopy, "
            "magical flowers with soft pink (#FFB6C1) glow"
        ),
        "crystal_cavern": (
            "mystical crystal cavern, massive amethyst crystals emitting purple (#2D1B4E) glow, "
            "reflecting pools of teal (#00D4AA) water, "
            "stalactites dripping golden (#FFD700) light drops, "
            "floor scattered with glowing gems, ambient bioluminescent (#39FF14) moss"
        ),
        "sky_island": (
            "floating sky island, lush green grass with pink (#FFB6C1) flower meadow, "
            "rainbow waterfall cascading off the edge into clouds, "
            "teal (#00D4AA) and purple (#2D1B4E) aurora in background sky, "
            "golden (#FFD700) sunlight, cotton-candy clouds"
        ),
        "magical_garden": (
            "ancient magical garden, oversized flowers with bioluminescent (#39FF14) centers, "
            "stone path with glowing teal (#00D4AA) runes, "
            "hanging fairy lanterns with warm golden (#FFD700) light, "
            "butterflies with prismatic wings, soft purple (#2D1B4E) twilight"
        ),
        "witch_cottage": (
            "cozy witch cottage interior, wooden shelves lined with colorful potion bottles, "
            "bubbling cauldron with teal (#00D4AA) and purple (#2D1B4E) steam, "
            "stacks of spell books with golden (#FFD700) lettering, "
            "window with moonlight and floating magical sparks, "
            "warm amber fireplace glow"
        ),
    }

    # 灯光风格
    LIGHTING_STYLES = {
        "magical_warm": (
            "warm golden (#FFD700) key light from upper right, "
            "soft teal (#00D4AA) rim light from left, "
            "purple (#2D1B4E) ambient fill, "
            "bioluminescent (#39FF14) accent from below, "
            "volumetric god rays through mist"
        ),
        "mystical_twilight": (
            "deep purple (#2D1B4E) ambient light, "
            "teal (#00D4AA) moonlight from upper left, "
            "golden (#FFD700) warm accent on subject, "
            "bioluminescent (#39FF14) under-lighting from ground, "
            "soft pink (#FFB6C1) bounce light"
        ),
        "enchanting_glow": (
            "central magical glow teal (#00D4AA), "
            "warm golden (#FFD700) rim light wrapping subject, "
            "soft purple (#2D1B4E) background gradient, "
            "bioluminescent (#39FF14) particle lighting, "
            "ethereal subsurface scattering on character"
        ),
    }

    # 构图模板
    COMPOSITION_TEMPLATES = {
        "center_hero": (
            "centered subject occupying 60% of frame, "
            "shallow depth of field, "
            "brand logo top-left (10% margin), "
            "game title bottom-center above CTA zone"
        ),
        "rule_of_thirds": (
            "subject on right-third line, facing left, "
            "merge items on left-third creating diagonal flow, "
            "negative space top for logo, "
            "bottom third reserved for CTA overlay"
        ),
        "dynamic_diagonal": (
            "subject bottom-right, merge items top-left, "
            "magical energy diagonal connecting both, "
            "logo top-left corner with subtle drop shadow, "
            "CTA bottom-center with contrasting background"
        ),
    }

    def __init__(self, output_dir: str = "output/creative_expansion/prompts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, variant: dict, base_dna: dict) -> VariantPrompts:
        """为单个 variant 生成全类型 prompt。

        Args:
            variant: 变体描述 dict，需包含:
                - variant_id: str
                - creature: str (如 "baby dragon", "magical cat")
                - creature_changed_part: str (如 "golden scales", "rainbow wings")
                - environment: str (如 "enchanted_forest")
                - hook_type: str (如 "curiosity", "transformation")
                - reward_type: str (如 "transformation", "collection")
                - merge_items: list[str] (参与合并的物品名)
                - lighting: str (可选, 默认 "magical_warm")
                - composition: str (可选, 默认 "center_hero")
            base_dna: Winning creative 的基础 DNA dict，需包含:
                - style: str
                - color_palette: dict
                - proven_elements: list[str] (已验证有效的视觉元素)
        """
        variant_id = variant.get("variant_id", uuid.uuid4().hex[:8])

        # 合并 base_dna 与 variant 特异信息
        variant_dna = self._merge_dna(variant, base_dna)

        return VariantPrompts(
            variant_id=variant_id,
            image_prompt=self._build_image_prompt(variant_dna, base_dna),
            video_prompt=self._build_video_prompt(variant_dna, base_dna),
            motion_prompt=self._build_motion_prompt(variant_dna),
            storyboard_prompt=self._build_storyboard(variant_dna),
            thumbnail_prompt=self._build_thumbnail_prompt(variant_dna),
            headline_suggestions=self._build_headlines(variant_dna),
            primary_text_suggestions=self._build_primary_texts(variant_dna),
            cta_suggestions=self._build_ctas(variant_dna),
            negative_prompt=self._build_negative_prompt(),
        )

    def generate_batch(
        self,
        variants: List[dict],
        base_dna: dict,
    ) -> List[VariantPrompts]:
        """批量为多个 variant 生成 prompt。"""
        return [self.generate(v, base_dna) for v in variants]

    def save(self, prompts: List[VariantPrompts], run_id: str = None) -> Path:
        """保存生成结果到 JSON 文件。"""
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"variant_prompts_{run_id}.json"
        data = [p.to_dict() for p in prompts]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return output_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _merge_dna(self, variant: dict, base_dna: dict) -> dict:
        """将 variant 与 base_dna 合并为完整描述 dict。"""
        palette = base_dna.get("color_palette", MERGE_WITCHES_DNA["color_palette"])
        return {
            "variant_id": variant.get("variant_id", uuid.uuid4().hex[:8]),
            "creature": variant.get("creature", "baby dragon"),
            "creature_changed_part": variant.get("creature_changed_part", ""),
            "environment": variant.get("environment", "enchanted_forest"),
            "hook_type": variant.get("hook_type", "curiosity"),
            "reward_type": variant.get("reward_type", "transformation"),
            "merge_items": variant.get("merge_items", ["magic cauldron", "dragon egg"]),
            "lighting": variant.get("lighting", "magical_warm"),
            "composition": variant.get("composition", "center_hero"),
            "style": base_dna.get("style", MERGE_WITCHES_DNA["style"]),
            "color_palette": palette,
            "proven_elements": base_dna.get("proven_elements", []),
        }

    # ------------------------------------------------------------------
    # 1. Image Prompt
    # ------------------------------------------------------------------

    def _build_image_prompt(self, variant_dna: dict, base_dna: dict) -> str:
        """构建 AI 图片生成 prompt（SDXL / Midjourney / Lovart）。

        遵循 SDXL 最佳实践：
          - 前置主体描述（权重最高）
          - 明确画面格式和风格
          - 包含具体色号
          - 质量修饰词放末尾
        """
        parts: List[str] = []

        # --- 1) 主体 (creature) + 变异部分强调 ---
        creature_key = self._extract_key(variant_dna["creature"])
        creature_desc = self.CREATURE_DETAILS.get(
            creature_key,
            f"cute chibi {creature_key} with big sparkling eyes, "
            f"magical aura, adorable proportions",
        )
        changed_part = variant_dna.get("creature_changed_part", "")
        if changed_part:
            # 用 SDXL 权重语法强调变异部分
            creature_desc += f", EMPHASIS on ({changed_part}) as the visual hook"
        parts.append(creature_desc)

        # --- 2) 合并机制视觉 ---
        merge_items = variant_dna.get("merge_items", [])
        if len(merge_items) >= 2:
            merge_fx = self.MERGE_FX[hash(variant_dna["variant_id"]) % len(self.MERGE_FX)]
            parts.append(
                f"merging {merge_items[0]} and {merge_items[1]}, "
                f"connected by {merge_fx}"
            )
        elif merge_items:
            parts.append(f"holding {merge_items[0]} with magical glow")

        # --- 3) 环境 ---
        env_key = self._extract_key(variant_dna["environment"])
        env_desc = self.ENVIRONMENT_DETAILS.get(env_key, env_key)
        parts.append(f"set in {env_desc}")

        # --- 4) 灯光 ---
        lighting_key = self._extract_key(variant_dna["lighting"])
        lighting_desc = self.LIGHTING_STYLES.get(lighting_key, lighting_key)
        parts.append(lighting_desc)

        # --- 5) 构图 ---
        comp_key = self._extract_key(variant_dna["composition"])
        comp_desc = self.COMPOSITION_TEMPLATES.get(comp_key, comp_key)
        parts.append(comp_desc)

        # --- 6) 色彩方案 ---
        palette = variant_dna.get("color_palette", MERGE_WITCHES_DNA["color_palette"])
        color_desc = self._palette_to_prompt(palette)
        parts.append(color_desc)

        # --- 7) 粒子特效 ---
        parts.append(
            "floating magical particles, sparkle dust, "
            "glowing ember motes, gentle bokeh orbs"
        )

        # --- 8) 品牌元素 ---
        parts.append(
            "game logo positioned top-left with subtle glow, "
            '"Merge Witches" title in whimsical font'
        )

        # --- 9) 风格一致性 ---
        proven = variant_dna.get("proven_elements", [])
        if proven:
            parts.append(f"maintaining visual consistency with {', '.join(proven[:3])}")

        # --- 10) 画面格式 + 风格基底 ---
        parts.append(
            "9:16 vertical mobile game ad format, "
            f"{variant_dna.get('style', MERGE_WITCHES_DNA['style'])}"
        )

        # --- 11) 质量修饰词（放末尾，权重最低但保证质量） ---
        parts.append(", ".join(QUALITY_MODIFIERS))

        return ", ".join(parts)

    # ------------------------------------------------------------------
    # 2. Video Prompt
    # ------------------------------------------------------------------

    def _build_video_prompt(self, variant_dna: dict, base_dna: dict) -> str:
        """构建 AI 视频生成 prompt（Runway / Pika / Kling）。

        视频专用：强调动作、时序、转场、持续效果。
        """
        creature = self._extract_key(variant_dna["creature"])
        creature_desc = self.CREATURE_DETAILS.get(creature, f"cute {creature}")
        changed_part = variant_dna.get("creature_changed_part", "")
        merge_items = variant_dna.get("merge_items", [])
        env_key = self._extract_key(variant_dna["environment"])
        env_desc = self.ENVIRONMENT_DETAILS.get(env_key, env_key)

        # Hook 阶段描述
        hook_type = variant_dna["hook_type"]
        hook_actions = {
            "curiosity": f"cute {creature} looks surprised, eyes widening with curiosity",
            "transformation": f"{creature} begins to glow, magical energy swirling around it",
            "challenge": f"{creature} stands confidently, magical aura intensifying",
            "secret": f"{creature} peeks from behind a glowing object, mysterious sparkle",
            "collection": f"{creature} appears excited, jumping with joy among treasures",
            "reward": f"{creature} reaches eagerly toward a glowing reward",
            "progression": f"{creature} evolves in real-time, growing larger and more powerful",
        }
        hook_action = hook_actions.get(hook_type, hook_actions["curiosity"])

        # 合并动画
        merge_animation = ""
        if len(merge_items) >= 2:
            merge_animation = (
                f"Two items ({merge_items[0]} and {merge_items[1]}) float toward each other, "
                f"spinning with magical particle trails, collide in a burst of teal (#00D4AA) "
                f"and golden (#FFD700) light, transforming into {creature}"
            )

        # 变异部分动画
        change_animation = ""
        if changed_part:
            change_animation = (
                f"Camera zooms into {changed_part} as it glows intensely, "
                f"particles swirl around it, revealing the dramatic change"
            )

        video_parts = [
            f"9:16 vertical mobile game ad video, 15-30 seconds",
            f"Scene: {env_desc}",
            f"Character: {creature_desc}",
            f"[0-3s HOOK] {hook_action}, camera pushes in slowly",
        ]

        if merge_animation:
            video_parts.append(f"[3-8s MERGE] {merge_animation}")
        if change_animation:
            video_parts.append(f"[8-12s REVEAL] {change_animation}")

        video_parts.extend([
            f"[12-15s CELEBRATION] {creature} celebrates with sparkle burst, "
            f"surrounding items glow in sequence",
            f"[15-21s CTA] Logo and game name appear with magical transition, "
            f"download button pulses with golden (#FFD700) glow",
            f"Particle effects: floating sparkles, gentle bokeh, bioluminescent (#39FF14) dust",
            f"Style: {variant_dna.get('style', MERGE_WITCHES_DNA['style'])}, smooth cinematic motion",
        ])

        return ", ".join(video_parts)

    # ------------------------------------------------------------------
    # 3. Motion Prompt
    # ------------------------------------------------------------------

    def _build_motion_prompt(self, variant_dna: dict) -> str:
        """构建镜头与运动方向 prompt。

        适用于 Runway Motion Brush / Kling 运动控制。
        """
        creature = self._extract_key(variant_dna["creature"])
        merge_items = variant_dna.get("merge_items", [])
        changed_part = variant_dna.get("creature_changed_part", "")
        hook_type = variant_dna["hook_type"]

        # 基础镜头运动
        camera_motions = {
            "curiosity": "slow dolly-in toward subject, subtle rack focus",
            "transformation": "slow push-in, then dramatic zoom-out to reveal full transformation",
            "challenge": "quick whip-pan to subject, then stabilize on close-up",
            "secret": "gentle orbit around subject, mystery reveal pan",
            "collection": "sweeping pan across collection, landing on new creature",
            "reward": "crane shot rising to reveal reward, then drop to character reaction",
            "progression": "smooth tracking shot following evolution sequence left to right",
        }
        camera_motion = camera_motions.get(hook_type, camera_motions["curiosity"])

        parts = [
            f"Camera: {camera_motion}",
            f"Subject motion: {creature} — slight idle animation, breathing motion, "
            f"tail/ears subtle movement, head tilt",
        ]

        # 合并物品运动
        if len(merge_items) >= 2:
            parts.append(
                f"Item motion: {merge_items[0]} floats from left, "
                f"{merge_items[1]} floats from right, "
                f"both converge to center with spiral rotation, "
                f"merge point erupts with outward particle burst"
            )

        # 变异部分运动
        if changed_part:
            parts.append(
                f"Highlight motion: {changed_part} pulses with glow (2-beat rhythm), "
                f"surrounded by swirling teal (#00D4AA) energy ring"
            )

        # 背景运动
        parts.append(
            "Background: slow parallax drift left-to-right, "
            "floating particles move gently upward, "
            "light rays shift subtly, "
            "bioluminescent (#39FF14) elements pulse slowly"
        )

        # 环境运动
        parts.append(
            "Environment: ambient floating dust motes, "
            "gentle swaying of magical plants, "
            "cauldron steam rises slowly"
        )

        # CTA 区域运动
        parts.append(
            "CTA zone: download button gentle pulse (1.05x scale cycle, 1.5s), "
            "golden (#FFD700) border glow breathing effect"
        )

        return "; ".join(parts)

    # ------------------------------------------------------------------
    # 4. Storyboard Prompt
    # ------------------------------------------------------------------

    def _build_storyboard(self, variant_dna: dict) -> str:
        """构建完整分镜含时序。

        Facebook Reels 最佳节奏：
          [0-3s]   Hook — 立即抓住注意力
          [3-12s]  Display — 展示机制/奖励
          [12-15s] Transition — 过渡到 CTA
          [15-21s] CTA — 行动号召
        支持 6s hook cut 版本。
        """
        creature = self._extract_key(variant_dna["creature"])
        merge_items = variant_dna.get("merge_items", [])
        changed_part = variant_dna.get("creature_changed_part", "")
        hook_type = variant_dna["hook_type"]
        reward_type = variant_dna["reward_type"]
        env_key = self._extract_key(variant_dna["environment"])
        env_desc = self.ENVIRONMENT_DETAILS.get(env_key, env_key)

        # Hook 画面描述
        hook_frames = {
            "curiosity": (
                f"Close-up of {creature} with surprised wide eyes looking at camera, "
                f"question mark particle effect above head, "
                f"teal (#00D4AA) magical aura intensifying"
            ),
            "transformation": (
                f"{creature} standing in center, starting to glow from within, "
                f"magical energy crackling around body, "
                f"golden (#FFD700) light emanating outward"
            ),
            "challenge": (
                f"{creature} in dynamic confident pose, "
                f"magical power-up aura flaring, "
                f"two merge items floating challengingly nearby"
            ),
            "secret": (
                f"{creature} peeking from behind a large glowing crystal, "
                f"mysterious sparkle trail leading to hidden object, "
                f"deep purple (#2D1B4E) shadow with teal (#00D4AA) light cracks"
            ),
            "collection": (
                f"Multiple creatures gathered together, {creature} front and center, "
                f"all looking at a glowing empty spot (missing creature), "
                f"sparkle trail leading toward it"
            ),
        }
        hook_frame = hook_frames.get(hook_type, hook_frames["curiosity"])

        # Display 阶段描述
        display_parts = []
        if len(merge_items) >= 2:
            display_parts.append(
                f"[3-5s] Two items appear: {merge_items[0]} (left) and {merge_items[1]} (right), "
                f"floating with magical particle trails, plus sign between them"
            )
            display_parts.append(
                f"[5-7s] Items move toward each other, spinning with increasing speed, "
                f"energy field building between them, teal (#00D4AA) and purple (#2D1B4E) swirl"
            )
            display_parts.append(
                f"[7-9s] MERGE IMPACT — burst of golden (#FFD700) and teal (#00D4AA) light, "
                f"particle explosion, camera shakes slightly, {creature} materializes"
            )

        if changed_part:
            display_parts.append(
                f"[9-11s] Camera zooms to {changed_part}, "
                f"bioluminescent (#39FF14) glow intensifies, "
                f"particles orbit around the changed feature"
            )

        reward_frames = {
            "transformation": f"{creature} in full evolved glory, powerful pose, magical aura at maximum",
            "collection": f"Complete set of creatures displayed, {creature} highlighted with star burst",
            "unlock": f"Secret gate opens revealing hidden magical realm, {creature} walking through",
            "upgrade": f"{creature} with upgraded powers, glowing stronger, new abilities visible",
            "legendary_item": f"Legendary item floating above {creature}, radiating golden (#FFD700) light",
        }
        reward_desc = reward_frames.get(reward_type, reward_frames["transformation"])
        display_parts.append(
            f"[11-12s] {reward_desc}, slow-motion hero shot"
        )

        display_section = "\n  ".join(display_parts)

        storyboard = f"""STORYBOARD — {variant_dna.get('variant_id', 'variant')}
Format: 9:16 vertical (1080x1920), Facebook Reels / Stories / Feed
Duration: 21s (with 6s hook-cut support)
Environment: {env_desc}

[0-3s] HOOK — {hook_type.upper()}
  Frame 1: {hook_frame}
  Text overlay: none (pure visual hook)
  Camera: slow dolly-in
  Audio: magical chime, character gasp

[3-12s] DISPLAY — MECHANISM + REWARD
  {display_section}
  Text overlay: subtle "+1" badge on merge impact
  Camera: dynamic tracking, zoom-ins on key moments
  Audio: merge whoosh, impact burst, reward fanfare

[12-15s] TRANSITION
  Magical wipe transition (teal → purple gradient wave)
  Scene zooms out to reveal full {env_key} setting
  Game logo fades in top-left with sparkle
  Camera: gentle pull-back

[15-21s] CTA
  "Merge Witches" title animates in (whimsical font, golden (#FFD700))
  Download / Play Now button appears with pulsing glow
  {creature} waves at camera next to CTA button
  Rating stars and "10M+ downloads" social proof below
  Camera: static, subject in lower-right third
  Audio: cheerful jingle, voiceover "Download now!"

--- 6s HOOK CUT VERSION ---
[0-3s] Same HOOK frame
[3-5s] Condensed MERGE IMPACT + creature reveal
[5-6s] Logo + CTA quick flash with download button
"""

        return storyboard.strip()

    # ------------------------------------------------------------------
    # 5. Thumbnail Prompt
    # ------------------------------------------------------------------

    def _build_thumbnail_prompt(self, variant_dna: dict) -> str:
        """构建 Facebook 广告缩略图 prompt。

        缩略图关键：静态一眼抓人、高对比、大主体。
        """
        creature = self._extract_key(variant_dna["creature"])
        creature_desc = self.CREATURE_DETAILS.get(creature, f"cute chibi {creature}")
        changed_part = variant_dna.get("creature_changed_part", "")
        env_key = self._extract_key(variant_dna["environment"])
        env_desc = self.ENVIRONMENT_DETAILS.get(env_key, env_key)

        parts = [
            "Facebook ad thumbnail, static image, scroll-stopping visual,",
            f"MAIN SUBJECT (occupying 60% of frame): {creature_desc}",
        ]

        if changed_part:
            parts.append(
                f"HIGHLIGHT: {changed_part} glowing prominently as the focal point, "
                f"surrounded by radiating light rays"
            )

        parts.extend([
            f"Background: {env_desc}, slightly blurred (shallow DoF) to make subject pop",
            "Composition: subject centered, face at eye-level for mobile scroll,",
            "Color: high contrast between subject and background, "
            "deep purple (#2D1B4E) background with teal (#00D4AA) rim light on subject, "
            "golden (#FFD700) accent highlights,",
            "Effects: sparkle burst around subject, magical particle aura, "
            "subtle lens flare from top-right,",
            "Branding: game logo top-left corner (small, not distracting), "
            "\"Merge Witches\" watermark bottom-right,",
            "Text hook: bold white text with purple (#2D1B4E) outline, "
            "max 5 words, positioned in top-third",
            "9:16 vertical format, optimized for Facebook Feed and Reels grid,",
            ", ".join(QUALITY_MODIFIERS),
        ])

        return ", ".join(parts)

    # ------------------------------------------------------------------
    # 6. Headline Suggestions
    # ------------------------------------------------------------------

    def _build_headlines(self, variant_dna: dict) -> List[str]:
        """生成 3 个 Facebook 广告标题选项。

        Facebook Headline 限制：40 字符（推荐 25 字符以内最佳）。
        """
        hook_type = variant_dna["hook_type"]
        creature = self._extract_key(variant_dna["creature"])

        # 从模板取基础标题
        base_headlines = HEADLINE_TEMPLATES.get(
            hook_type, HEADLINE_TEMPLATES["curiosity"]
        )

        # 将生物名注入部分标题，增加相关性
        creature_name = creature.replace("_", " ").title()
        headlines: List[str] = []
        for i, h in enumerate(base_headlines[:3]):
            if i == 0:
                # 第 1 条：保留原始模板
                headlines.append(h)
            elif i == 1:
                # 第 2 条：注入生物名
                headlines.append(f"{creature_name} awaits you!")
            else:
                # 第 3 条：调整语气
                headlines.append(h)

        # 确保不超过 40 字符
        headlines = [h[:40] for h in headlines]

        # 保证至少 3 条
        while len(headlines) < 3:
            headlines.append("Play Merge Witches Now!")

        return headlines[:3]

    # ------------------------------------------------------------------
    # 7. Primary Text Suggestions
    # ------------------------------------------------------------------

    def _build_primary_texts(self, variant_dna: dict) -> List[str]:
        """生成 3 个 Facebook 广告正文选项。

        Facebook Primary Text 最佳长度：125 字符（桌面）/ 首行 3 行可见。
        """
        hook_type = variant_dna["hook_type"]
        creature = self._extract_key(variant_dna["creature"])
        changed_part = variant_dna.get("creature_changed_part", "")
        merge_items = variant_dna.get("merge_items", [])

        base_texts = PRIMARY_TEXT_TEMPLATES.get(
            hook_type, PRIMARY_TEXT_TEMPLATES["curiosity"]
        )

        texts: List[str] = []
        for i, t in enumerate(base_texts[:3]):
            if i == 0:
                # 第 1 条：原始模板
                texts.append(t)
            elif i == 1:
                # 第 2 条：注入生物和合并物品
                items_str = " and ".join(merge_items[:2]) if merge_items else "magical items"
                texts.append(
                    f"Merge {items_str} to unlock the {creature}! "
                    f"Build your magical world and discover hundreds of adorable creatures. "
                    f"Free to play — start merging today!"
                )
            else:
                # 第 3 条：变异亮点版
                if changed_part:
                    texts.append(
                        f"Look at that {changed_part}! 🐉 The {creature} just got an amazing upgrade! "
                        f"Merge magical items, evolve your creatures, and build the most enchanting world. "
                        f"Download Merge Witches FREE!"
                    )
                else:
                    texts.append(t)

        # 保证至少 3 条
        while len(texts) < 3:
            texts.append(
                "Discover the magic! Merge items, collect creatures, and build your enchanted world. "
                "Play Merge Witches free today!"
            )

        return texts[:3]

    # ------------------------------------------------------------------
    # 8. CTA Suggestions
    # ------------------------------------------------------------------

    def _build_ctas(self, variant_dna: dict) -> List[str]:
        """生成 3 个 CTA 选项。

        Facebook CTA 按钮：短促有力，6-15 字符。
        """
        hook_type = variant_dna["hook_type"]

        # 根据钩子类型选 CTA 风格
        cta_map = {
            "curiosity": "curiosity",
            "transformation": "high_urgency",
            "challenge": "high_urgency",
            "secret": "curiosity",
            "collection": "reward",
            "reward": "reward",
            "progression": "default",
            "urgency": "high_urgency",
            "social": "social",
            "achievement": "reward",
        }
        cta_style = cta_map.get(hook_type, "default")
        ctas = CTA_TEMPLATES.get(cta_style, CTA_TEMPLATES["default"])

        return ctas[:3]

    # ------------------------------------------------------------------
    # Negative Prompt
    # ------------------------------------------------------------------

    def _build_negative_prompt(self) -> str:
        """构建负面 prompt — 需要避免的元素。

        适用于 SDXL / Midjourney / Lovart 的负面提示词。
        """
        # Merge Witches 专用排除
        merge_witches_exclusions = (
            "masculine aesthetic, war theme, military, FPS shooter elements, "
            "realistic human proportions, adult content, scary imagery, "
            "dark souls aesthetic, anime male protagonist, "
            "low-poly, voxel style, pixel art, 8-bit, "
            "horizontal banner layout, desktop aspect ratio, "
            "cluttered UI, too many text overlays, "
            "competitive PvP imagery, leaderboard screenshots"
        )
        return f"{NEGATIVE_PROMPT_BASE}, {merge_witches_exclusions}"

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_key(value: Any, fallback_key: str = "type") -> str:
        """从可能是 dict 的值中提取字符串 key

        当 DNA 中的字段为嵌套 dict (如 {"type": "magic_forest", "time": "night", ...})
        时，提取其 type 字段作为查找 key；若为字符串则直接返回。
        """
        if isinstance(value, dict):
            return str(value.get(fallback_key, ""))
        return str(value)

    @staticmethod
    def _palette_to_prompt(palette: dict) -> str:
        """将色彩方案 dict 转换为 prompt 描述。"""
        if not palette:
            palette = MERGE_WITCHES_DNA["color_palette"]

        color_roles = {
            "deep_purple": "dominant background",
            "teal": "magical accent and rim light",
            "warm_gold": "highlight and reward glow",
            "soft_pink": "character blush and warmth",
            "mystic_blue": "secondary magical glow",
            "biolum_green": "bioluminescent accent",
            "sunset_orange": "warm transition glow",
            "shadow_violet": "shadow depth and mystery",
        }

        parts = []
        for color_name, hex_code in palette.items():
            role = color_roles.get(color_name, "accent")
            parts.append(f"{hex_code} ({color_name.replace('_', ' ')} for {role})")

        return "color palette: " + ", ".join(parts)
