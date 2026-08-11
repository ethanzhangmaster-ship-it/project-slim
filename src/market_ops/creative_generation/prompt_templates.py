"""Prompt Templates - Facebook 创意提示词模板库

提供模块化模板系统，覆盖所有 Hook 类型、版位适配和风格变体。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptSegment:
    """提示词片段"""
    name: str                        # 片段名称
    template: str                    # 模板字符串
    required: bool = True            # 是否必填
    description: str = ""            # 描述
    examples: list[str] = field(default_factory=list)


@dataclass
class HookTemplate:
    """Hook 类型模板"""
    hook_type: str
    opening: PromptSegment           # 开场 / Hook
    subject: PromptSegment           # 主体
    environment: PromptSegment       # 环境
    lighting: PromptSegment          # 光照
    composition: PromptSegment       # 构图
    cta: PromptSegment               # 行动号召
    ending: PromptSegment            # 结尾
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptTemplateLibrary:
    """Facebook 创意提示词模板库

    覆盖:
    - Collection / Reward / Transformation / Fail / Emotion / Puzzle / Merge 等 Hook
    - Feed / Reels / Stories / Audience Network 等版位
    - Pixar / Disney / Dreamworks / Semi-Realistic 等风格
    """

    def __init__(self):
        self._hook_templates: dict[str, HookTemplate] = {}
        self._placement_modifiers: dict[str, list[str]] = {}
        self._style_modifiers: dict[str, list[str]] = {}
        self._init_hook_templates()
        self._init_placement_modifiers()
        self._init_style_modifiers()

    # ------------------------------------------------------------------
    # Hook 模板定义
    # ------------------------------------------------------------------
    def _init_hook_templates(self) -> None:
        # Collection Hook
        self._hook_templates["collection"] = HookTemplate(
            hook_type="collection",
            opening=PromptSegment(
                name="opening",
                template="(open_mouth surprise expression), {subject} discovering a rare glowing {collection_item}, "
                         "magical sparkles flying, eyes wide with excitement, hand reaching out, "
                         "ultra expressive face, adorable chibi style, high energy moment",
                required=True,
                description="收藏类 Hook: 角色发现稀有物品时的惊喜表情",
            ),
            subject=PromptSegment(
                name="subject",
                template="{character} {character_pose}, {creature_description}, "
                         "{character_clothes}, cute chibi proportions, big sparkling eyes",
                required=True,
                description="主体: 角色 + 生物",
            ),
            environment=PromptSegment(
                name="environment",
                template="{environment_type}, {time_of_day}, magical atmosphere, "
                         "floating particles, enchanted forest, mossy stones, glowing mushrooms",
                required=True,
                description="环境: 魔法森林等",
            ),
            lighting=PromptSegment(
                name="lighting",
                template="{lighting_type}, golden rim light on {subject_focus}, soft volumetric fog, "
                         "magical glow from {collection_item}, warm atmosphere",
                required=True,
                description="光照: 黄金轮廓光 + 魔法发光",
            ),
            composition=PromptSegment(
                name="composition",
                template="{camera_shot}, {camera_angle}, {subject} centered, "
                         "{collection_item} in foreground with glow, shallow depth of field",
                required=True,
                description="构图: 中心构图 + 前景发光物品",
            ),
            cta=PromptSegment(
                name="cta",
                template="subtle glowing button texture in lower corner, "
                         "inviting atmosphere, call-to-action ready frame",
                required=False,
                description="CTA: 角落发光按钮质感",
            ),
            ending=PromptSegment(
                name="ending",
                template="{subject} proudly showing collected treasures, satisfaction expression, "
                         "sparkles around, collection glow, happy ending vibe",
                required=False,
                description="结尾: 展示收藏成果",
            ),
        )

        # Reward Hook
        self._hook_templates["reward"] = HookTemplate(
            hook_type="reward",
            opening=PromptSegment(
                name="opening",
                template="massive explosion of gold coins and gems, {subject} celebrating, "
                         "victory pose, arms raised, confetti and sparkles everywhere, "
                         "epic reward moment, ultra satisfying visual",
                required=True,
                description="奖励类 Hook: 金币爆炸 + 庆祝",
            ),
            subject=PromptSegment(
                name="subject",
                template="{character} with huge smile, {creature_description} also celebrating, "
                         "victory outfit, glowing accessories, triumphant expression",
                required=True,
                description="主体: 庆祝中的角色和生物",
            ),
            environment=PromptSegment(
                name="environment",
                template="treasure chamber, piles of gold, gem-encrusted walls, "
                         "magical loot raining down, reward screen atmosphere",
                required=False,
                description="环境: 宝藏室",
            ),
            lighting=PromptSegment(
                name="lighting",
                template="golden god rays, sparkling light from treasure, "
                         "dramatic rim lighting, warm rich tones",
                required=True,
                description="光照: 金色神光 + 宝藏闪光",
            ),
            composition=PromptSegment(
                name="composition",
                template="{camera_shot}, low angle looking up at {subject}, "
                         "treasure filling lower frame, dynamic upward energy",
                required=True,
                description="构图: 仰拍 + 宝藏填充下框",
            ),
            cta=PromptSegment(
                name="cta",
                template="shiny claim button visible, reward UI elements, "
                         "golden frame border",
                required=False,
                description="CTA: 领取按钮",
            ),
            ending=PromptSegment(
                name="ending",
                template="{subject} holding the ultimate reward, glowing crown or trophy, "
                         "pride and joy expression, epic final frame",
                required=False,
                description="结尾: 终极奖励",
            ),
        )

        # Transformation Hook
        self._hook_templates["transformation"] = HookTemplate(
            hook_type="transformation",
            opening=PromptSegment(
                name="opening",
                template="{subject} before transformation, ordinary appearance, "
                         "hesitant but determined expression, holding a glowing orb or scroll",
                required=True,
                description="变身类 Hook: 变身前的普通形象",
            ),
            subject=PromptSegment(
                name="subject",
                template="{character} mid-transformation, magical energy swirling, "
                         "aura burst, clothes changing, hair flowing with power, "
                         "epic upgrade moment, glowing eyes, powerful stance",
                required=True,
                description="主体: 变身中的角色",
            ),
            environment=PromptSegment(
                name="environment",
                template="magical vortex, energy portal, particles spiraling, "
                         "reality bending atmosphere, power-up zone",
                required=False,
                description="环境: 魔法漩涡",
            ),
            lighting=PromptSegment(
                name="lighting",
                template="intense magical backlight, lens flare, chromatic aberration, "
                         "power glow in neon colors, dramatic contrast",
                required=True,
                description="光照: 强烈魔法逆光 + 镜头光晕",
            ),
            composition=PromptSegment(
                name="composition",
                template="split frame showing before/after, or {camera_shot} of full transformation, "
                         "dynamic action lines, energy motion blur",
                required=True,
                description="构图: 分屏对比或全景变身",
            ),
            cta=PromptSegment(
                name="cta",
                template="upgrade arrow, level-up badge, glowing upgrade path visible",
                required=False,
                description="CTA: 升级箭头",
            ),
            ending=PromptSegment(
                name="ending",
                template="fully transformed {character}, confident powerful pose, "
                         "new outfit gleaming, aura settled, ready for battle",
                required=False,
                description="结尾: 完全变身完成",
            ),
        )

        # Fail Hook
        self._hook_templates["fail"] = HookTemplate(
            hook_type="fail",
            opening=PromptSegment(
                name="opening",
                template="{subject} looking confused, wrong choice made, "
                         "something going wrong, comical failure expression, "
                         "sweat drop, question marks floating",
                required=True,
                description="失败类 Hook: 角色犯错",
            ),
            subject=PromptSegment(
                name="subject",
                template="{character} in funny fail pose, {creature_description} also confused, "
                         "cartoonish reaction, exaggerated expression, slapstick humor",
                required=True,
                description="主体: 失败的滑稽角色",
            ),
            environment=PromptSegment(
                name="environment",
                template="slightly chaotic scene, broken potion bottles, "
                         "misfired magic sparks, humorous disaster zone",
                required=False,
                description="环境: 轻微混乱",
            ),
            lighting=PromptSegment(
                name="lighting",
                template="comedy lighting, slightly dim with spotlight on fail moment, "
                         "cartoonish highlights",
                required=True,
                description="光照: 喜剧式聚光灯",
            ),
            composition=PromptSegment(
                name="composition",
                template="{camera_shot}, slightly tilted angle for comedic effect, "
                         "character in center of mild chaos",
                required=True,
                description="构图: 喜剧倾斜角度",
            ),
            cta=PromptSegment(
                name="cta",
                template="help button subtly visible, rescue gesture implied",
                required=False,
                description="CTA: 救援暗示",
            ),
            ending=PromptSegment(
                name="ending",
                template="{subject} looking at viewer with pleading eyes, "
                         "can you do better expression, direct engagement",
                required=False,
                description="结尾: 求救眼神 + 直接互动",
            ),
        )

        # Emotion Hook
        self._hook_templates["emotion"] = HookTemplate(
            hook_type="emotion",
            opening=PromptSegment(
                name="opening",
                template="extreme close-up of {subject}'s face, tears of joy or surprise, "
                         "intense emotional moment, heartwarming or heartbreaking, "
                         "ultra detailed facial expression, cinematic",
                required=True,
                description="情感类 Hook: 极致表情特写",
            ),
            subject=PromptSegment(
                name="subject",
                template="{character} showing deep emotion, hugging {creature_description}, "
                         "tender moment, emotional bond visible, beautiful rendering",
                required=True,
                description="主体: 情感丰富的角色互动",
            ),
            environment=PromptSegment(
                name="environment",
                template="soft dreamy background, bokeh lights, gentle atmosphere, "
                         "sentimental setting, memory lane vibe",
                required=False,
                description="环境: 柔和梦幻背景",
            ),
            lighting=PromptSegment(
                name="lighting",
                template="soft emotional lighting, tear catchlights, "
                         "warm heart glow, gentle rim light, intimate atmosphere",
                required=True,
                description="光照: 柔和情感光 + 泪光",
            ),
            composition=PromptSegment(
                name="composition",
                template="extreme close-up portrait, shallow depth of field, "
                         "eyes in sharp focus, cinematic aspect ratio",
                required=True,
                description="构图: 极近特写 + 浅景深",
            ),
            cta=PromptSegment(
                name="cta",
                template="join us, become part of the story, subtle invitation",
                required=False,
                description="CTA: 加入故事",
            ),
            ending=PromptSegment(
                name="ending",
                template="{subject} smiling through tears, hope and warmth, "
                         "beautiful emotional resolution, satisfying closure",
                required=False,
                description="结尾: 含泪微笑",
            ),
        )

        # Puzzle Hook
        self._hook_templates["puzzle"] = HookTemplate(
            hook_type="puzzle",
            opening=PromptSegment(
                name="opening",
                template="{subject} looking at a complex puzzle or maze, "
                         "finger on chin thinking, puzzle pieces floating, "
                         "mysterious ancient mechanism, can you solve this expression",
                required=True,
                description="解谜类 Hook: 思考中的角色",
            ),
            subject=PromptSegment(
                name="subject",
                template="{character} solving puzzle, {creature_description} helping, "
                         "matching gems or merging items, satisfying merge moment, "
                         "puzzle pieces clicking together",
                required=True,
                description="主体: 解谜中的角色",
            ),
            environment=PromptSegment(
                name="environment",
                template="ancient temple, puzzle chamber, glowing runes, "
                         "mysterious mechanisms, treasure behind locked door",
                required=False,
                description="环境: 古代神殿 + 符文",
            ),
            lighting=PromptSegment(
                name="lighting",
                template="mysterious ambient glow from puzzle, rune illumination, "
                         "spotlight on the solution area, dramatic shadows",
                required=True,
                description="光照: 谜题环境光 + 聚光灯",
            ),
            composition=PromptSegment(
                name="composition",
                template="{camera_shot}, puzzle filling frame, {subject} reacting to solution, "
                         "before/after split implied",
                required=True,
                description="构图: 谜题填满画面",
            ),
            cta=PromptSegment(
                name="cta",
                template="solve button, hint glow, interactive puzzle elements",
                required=False,
                description="CTA: 解谜按钮",
            ),
            ending=PromptSegment(
                name="ending",
                template="puzzle solved, door opening, treasure revealed, "
                         "{subject} triumphant, satisfying completion",
                required=False,
                description="结尾: 谜题解开",
            ),
        )

        # Merge Hook
        self._hook_templates["merge"] = HookTemplate(
            hook_type="merge",
            opening=PromptSegment(
                name="opening",
                template="two glowing items floating, merge animation beginning, "
                         "magical fusion energy, particles swirling between objects, "
                         "satisfying merge anticipation",
                required=True,
                description="合成类 Hook: 物品即将合成",
            ),
            subject=PromptSegment(
                name="subject",
                template="{character} watching merge happen, {creature_description} curious, "
                         "items combining with magical effect, evolution glow, "
                         "transforming into something better",
                required=True,
                description="主体: 角色观看合成过程",
            ),
            environment=PromptSegment(
                name="environment",
                template="merge workshop, alchemy table, magical crafting station, "
                         "floating ingredients, enchanted workspace",
                required=False,
                description="环境: 合成工坊",
            ),
            lighting=PromptSegment(
                name="lighting",
                template="merge glow in center, items emanating light, "
                         "fusion energy illuminating scene, magical sparks",
                required=True,
                description="光照: 合成中心发光",
            ),
            composition=PromptSegment(
                name="composition",
                template="{camera_shot}, merging items center frame, "
                         "before/after comparison visible, satisfying visual flow",
                required=True,
                description="构图: 合成物品居中",
            ),
            cta=PromptSegment(
                name="cta",
                template="merge button glowing, drag gesture implied, "
                         "interactive merge UI",
                required=False,
                description="CTA: 合成按钮",
            ),
            ending=PromptSegment(
                name="ending",
                template="new merged item revealed, superior version glowing, "
                         "{subject} impressed, evolution complete, better than before",
                required=False,
                description="结尾: 合成完成 + 进化成功",
            ),
        )

    # ------------------------------------------------------------------
    # 版位修饰词
    # ------------------------------------------------------------------
    def _init_placement_modifiers(self) -> None:
        self._placement_modifiers = {
            "feed": [
                "Facebook feed optimized, square or 4:5 ratio",
                "thumb-stopping scroll pauser, bold colors",
                "clear subject visible at small size, readable at a glance",
                "first 3 seconds maximum impact",
            ],
            "reels": [
                "vertical 9:16 format, mobile native, full screen",
                "fast-paced, energetic, trend-savvy",
                " looping friendly, seamless repeat",
                "text-safe zones, no critical info at edges",
                "sound-on optimized, audio-visual sync",
            ],
            "stories": [
                "vertical 9:16, quick hook, 15 seconds or less",
                "tap-friendly interactive elements",
                "top and bottom safe zones reserved for UI",
                "immediate payoff, no slow buildup",
                "Instagram Stories and Facebook Stories compatible",
            ],
            "audience_network": [
                "banner and native ad compatible",
                "clean composition, not too busy",
                "clear focal point even at thumbnail size",
                "high contrast for visibility",
            ],
        }

    # ------------------------------------------------------------------
    # 风格修饰词
    # ------------------------------------------------------------------
    def _init_style_modifiers(self) -> None:
        self._style_modifiers = {
            "pixar": [
                "Pixar 3D animation style",
                "soft rounded forms, appealing characters",
                "warm color palette, cinematic lighting",
                "subsurface scattering on skin",
                "expressive exaggerated but believable",
                "Toy Story / Inside Out quality level",
            ],
            "disney": [
                "Disney animation style",
                "classic hand-drawn feel with modern polish",
                "elegant character design, flowing hair",
                "magical sparkle effects, fairy tale atmosphere",
                "Frozen / Moana visual quality",
            ],
            "dreamworks": [
                "DreamWorks animation style",
                "slightly more stylized proportions",
                "bold expressive faces, comedic timing feel",
                "How to Train Your Dragon / Shrek visual style",
            ],
            "semi_realistic": [
                "semi-realistic digital art style",
                "anime-inspired but with realistic proportions",
                "detailed textures, realistic lighting",
                "Genshin Impact / anime game art style",
                "beautiful detailed eyes, soft shading",
            ],
            "chibi": [
                "chibi / super-deformed style",
                "big head small body, extremely cute",
                "rounded features, kawaii aesthetic",
                "simplified but adorable, collectable feel",
            ],
        }

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def get_hook_template(self, hook_type: str) -> HookTemplate | None:
        """获取指定 Hook 类型的模板"""
        return self._hook_templates.get(hook_type.lower())

    def list_hook_types(self) -> list[str]:
        """列出所有支持的 Hook 类型"""
        return list(self._hook_templates.keys())

    def get_placement_modifier(self, placement: str) -> list[str]:
        """获取版位修饰词"""
        return self._placement_modifiers.get(placement.lower(), [])

    def get_style_modifier(self, style: str) -> list[str]:
        """获取风格修饰词"""
        return self._style_modifiers.get(style.lower(), [])

    def build_master_prompt(
        self,
        hook_type: str,
        params: dict[str, Any],
        style: str = "pixar",
        placement: str = "feed",
    ) -> str:
        """根据模板和参数构建 Master Prompt

        Args:
            hook_type: Hook 类型
            params: 参数字典，包含 character, creature, environment 等
            style: 风格 (pixar/disney/dreamworks/semi_realistic/chibi)
            placement: 版位 (feed/reels/stories/audience_network)

        Returns:
            完整的 Master Prompt 字符串
        """
        template = self.get_hook_template(hook_type)
        if not template:
            return ""

        # 渲染每个片段
        segments = [
            template.opening,
            template.subject,
            template.environment,
            template.lighting,
            template.composition,
            template.cta,
            template.ending,
        ]

        parts = []
        for seg in segments:
            if not seg.required and not params.get(f"include_{seg.name}", False):
                continue
            try:
                rendered = seg.template.format(**params)
                parts.append(rendered)
            except KeyError:
                # 缺少参数时跳过
                continue

        # 加入风格修饰
        style_parts = self.get_style_modifier(style)
        if style_parts:
            parts.append(", ".join(style_parts))

        # 加入版位修饰
        placement_parts = self.get_placement_modifier(placement)
        if placement_parts:
            parts.append(", ".join(placement_parts))

        return ", ".join(parts)

    def get_template_metadata(self, hook_type: str) -> dict[str, Any]:
        """获取模板元数据（包含所需参数列表）"""
        template = self.get_hook_template(hook_type)
        if not template:
            return {}

        params: set[str] = set()
        for seg in [template.opening, template.subject, template.environment,
                    template.lighting, template.composition, template.cta, template.ending]:
            import re
            found = re.findall(r"\{(\w+)\}", seg.template)
            params.update(found)

        return {
            "hook_type": hook_type,
            "required_params": sorted(params),
            "has_cta": template.cta.required or bool(template.cta.template),
            "has_ending": template.ending.required or bool(template.ending.template),
        }
