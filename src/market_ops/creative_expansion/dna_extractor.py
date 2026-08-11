"""Creative DNA 提取器 - 从 Winning Facebook 素材中提取创意 DNA 图谱

将 Lovart 分析结果 + video_feature_analysis 数据融合为结构化 Creative DNA Graph。
用于 Merge Witches (P04) 项目的素材扩量：识别 winning 素材的核心创意基因，
支撑后续 DNA 交叉、变异和批量生成。

输入:
  - lovart_results: Lovart AI 分析结果列表，每条包含 subject, composition,
    palette, lighting, character_pose, mood, hook_type, standout_features 等字段
  - video_analysis: video_feature_analysis 汇总数据，含 saturation, brightness,
    edge_density, motion_magnitude 等视频特征

输出:
  - list[CreativeDNA]: 结构化创意 DNA 列表
  - to_graph(): 将扁平 DNA 转为树状图谱（用于可视化和 DNA 组合）
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Merge Witches 世界的生物类型映射
# ---------------------------------------------------------------------------
_CREATURE_KEYWORDS: dict[str, list[str]] = {
    "dragon": ["dragon", "dracon", "drake", "飞龙", "龙"],
    "cat": ["cat", "kitten", "feline", "猫", "小猫"],
    "fox": ["fox", "vulpine", "狐狸"],
    "owl": ["owl", "鸟类", "猫头鹰"],
    "squirrel": ["squirrel", "chipmunk", "松鼠"],
    "fairy": ["fairy", "pixie", "sprite", "仙女", "精灵"],
    "unicorn": ["unicorn", "独角兽"],
    "phoenix": ["phoenix", "火鸟", "凤凰"],
    "wolf": ["wolf", "wolverine", "狼"],
    "spider": ["spider", "arachnid", "蜘蛛"],
    "snake": ["snake", "serpent", "蛇"],
    "bat": ["bat", "蝙蝠"],
    "frog": ["frog", "toad", "青蛙", "蟾蜍"],
    "raven": ["raven", "crow", "乌鸦"],
    "troll": ["troll", "ogre", "巨魔"],
    "golem": ["golem", "construct", "魔像"],
    "spirit": ["spirit", "ghost", "wraith", "幽灵", "魂"],
    "butterfly": ["butterfly", "moth", "蝴蝶"],
    "rabbit": ["rabbit", "bunny", "兔子"],
}

# 生物颜色映射（从描述推断）
_CREATURE_COLOR_MAP: dict[str, str] = {
    "ice": "cyan", "ice_blue": "cyan", "frost": "cyan",
    "fire": "orange", "flame": "orange", "lava": "red",
    "shadow": "dark_purple", "dark": "dark_purple", "void": "dark_purple",
    "nature": "green", "forest": "green", "leaf": "green",
    "holy": "gold", "divine": "gold", "sacred": "gold",
    "water": "blue", "ocean": "blue", "sea": "blue",
}

# 环境类型映射
_ENV_SCENE_MAP: dict[str, str] = {
    "forest": "magic_forest", "woods": "magic_forest", "tree": "magic_forest",
    "cave": "crystal_cave", "dungeon": "crystal_cave", "underground": "crystal_cave",
    "castle": "enchanted_castle", "tower": "enchanted_castle", "palace": "enchanted_castle",
    "village": "witch_village", "town": "witch_village", "cottage": "witch_village",
    "lake": "mystic_lake", "pond": "mystic_lake", "water": "mystic_lake",
    "mountain": "dragon_peak", "peak": "dragon_peak", "cliff": "dragon_peak",
    "garden": "magic_garden", "meadow": "magic_garden",
    "night_sky": "starry_night", "sky": "starry_night", "stars": "starry_night",
    "swamp": "dark_swamp", "bog": "dark_swamp", "marsh": "dark_swamp",
}

# 魔法元素关键词
_MAGIC_KEYWORDS: list[str] = [
    "particle", "sparkle", "glow", "magic", "spell", "enchant",
    "aura", "rune", "portal", "mystic", "shimmer",
    "粒子", "火花", "发光", "魔法", "符文", "传送门",
]

# Hook 类型到心理驱动的映射
_HOOK_TYPE_TO_TRIGGER: dict[str, str] = {
    "chest": "reward_anticipation",
    "number": "progress_curiosity",
    "beauty": "aesthetic_attraction",
    "boss": "challenge_thrill",
    "gold_coin": "greed_trigger",
    "giant_reward": "reward_anticipation",
    "danger": "fear_urgency",
    "countdown": "scarcity_urgency",
    "failure": "empathy_rescue",
    "mystery": "curiosity_gap",
    "comparison": "superiority_drive",
    "collection": "completion_drive",
}

# Hook 类型到情感 hook 的映射
_HOOK_TYPE_TO_EMOTION: dict[str, str] = {
    "chest": "惊喜期待",
    "number": "成长满足",
    "beauty": "视觉愉悦",
    "boss": "战斗兴奋",
    "gold_coin": "获得欲望",
    "giant_reward": "丰收喜悦",
    "danger": "紧张担忧",
    "countdown": "时间紧迫",
    "failure": "同情救援",
    "mystery": "好奇探索",
    "comparison": "优劣对比",
    "collection": "收集成就",
}

# Hook 类型到视觉 hook 的映射
_HOOK_TYPE_TO_VISUAL: dict[str, str] = {
    "chest": "宝箱/礼盒特写",
    "number": "大数字/进度条",
    "beauty": "角色/场景美图",
    "boss": "Boss 威压镜头",
    "gold_coin": "金币喷涌",
    "giant_reward": "满屏奖励",
    "danger": "危机场景",
    "countdown": "倒计时UI",
    "failure": "失败/低级状态",
    "mystery": "未知/问号元素",
    "comparison": "左右/上下对比",
    "collection": "收集图鉴展示",
}

# 合图法则关键词
_COMPOSITION_RULES: list[tuple[str, list[str]]] = [
    ("rule_of_thirds", ["thirds", "off-center", "三分"]),
    ("center_symmetry", ["centered", "symmetric", "居中", "对称"]),
    ("golden_ratio", ["golden", "spiral", "黄金比例"]),
    ("diagonal", ["diagonal", "对角线"]),
    ("frame_in_frame", ["framed", "border", "画中画"]),
    ("leading_lines", ["leading", "guiding", "引导线"]),
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CreativeDNA:
    """单个素材的创意 DNA 图谱"""

    variant_id: str  # 素材变体ID, 如 "434"

    # 角色 DNA
    character: dict  # {type, hair, hat, clothes, face, eyes, pose, gesture, emotion, age, accessories}

    # 生物 DNA (可多只)
    creatures: list[dict]  # [{type, color, glow, action, size, position}]

    # 环境 DNA
    environment: dict  # {type, time, weather, elements:[], lighting_source, magic_elements:[]}

    # 灯光 DNA
    lighting: dict  # {type, color_temperature, direction, intensity, special_effects:[]}

    # 镜头 DNA
    camera: dict  # {shot_type, angle, movement, composition_rule}

    # 构图 DNA
    composition: dict  # {layout, subject_position, depth_layers, foreground, midground, background}

    # Hook DNA
    hook: dict  # {type, trigger, emotional_hook, visual_hook}

    # 色彩 DNA
    colors: dict  # {dominant:[], accent:[], background:[], mood_palette:[]}

    # 动态 DNA
    motion: dict  # {camera_movement, character_action, creature_actions:[], particle_effects:[], transition_style}

    # Facebook 元数据
    fb_meta: dict  # {duration, resolution, headline, cta, placement, aspect_ratio}

    # 投放效果
    performance: dict  # {roas, spend, ctr, cpa, hook_rate, hold_rate, ipm}


# ---------------------------------------------------------------------------
# 主提取器
# ---------------------------------------------------------------------------

class CreativeDNAExtractor:
    """从 Lovart 分析 + 视频特征数据中提取 Creative DNA

    用法:
        extractor = CreativeDNAExtractor()
        dna_list = extractor.extract(lovart_results, video_analysis)
        graph = extractor.to_graph(dna_list[0])
    """

    def extract(self, lovart_results: list[dict], video_analysis: dict) -> list[CreativeDNA]:
        """提取 Creative DNA 列表

        Args:
            lovart_results: Lovart AI 分析结果列表, 每条包含:
                - creative_id / variant_id / video_number
                - subject: 主体描述
                - composition: 构图描述
                - palette: 色板
                - lighting: 灯光描述
                - character_pose: 角色姿态
                - mood: 情绪/氛围
                - hook_type: Hook 类型
                - standout_features: 亮点特征列表
                - (可选) character, environment, camera, motion, cta 等 Lovart 结构化字段
                - (可选) frame_analysis.hook.analysis / frame_analysis.mid.analysis 嵌套结构
            video_analysis: 视频特征分析汇总, 含:
                - creative_id -> {saturation, brightness, edge_density, motion_magnitude, ...}
                - high_roas_videos / all_videos 数组
                - 或全局特征: avg_saturation, avg_brightness 等

        Returns:
            结构化 Creative DNA 列表
        """
        # 构建 video_analysis 查找索引: creative_id -> features
        video_feat_map = self._build_video_feat_map(video_analysis)

        dna_list: list[CreativeDNA] = []
        for lovart in lovart_results:
            # 展平嵌套的 frame_analysis 结构，将 hook.analysis / mid.analysis
            # 中的字段合并到顶层，使后续提取方法可以直接访问
            flat = self._flatten_lovart(lovart)

            variant_id = str(
                flat.get("creative_id")
                or flat.get("variant_id")
                or flat.get("video_id")
                or flat.get("video_number")
                or ""
            )
            vid_feat = video_feat_map.get(variant_id, {})

            character = self._extract_character(flat, vid_feat)
            creatures = self._extract_creatures(flat)
            environment = self._extract_environment(flat, vid_feat)
            lighting = self._extract_lighting(flat, vid_feat)
            camera = self._extract_camera(flat)
            composition = self._extract_composition(flat, vid_feat)
            hook = self._extract_hook(flat)
            colors = self._extract_colors(flat, vid_feat)
            motion = self._extract_motion(flat, vid_feat)
            fb_meta = self._extract_fb_meta(flat)
            performance = self._extract_performance(flat)

            dna_list.append(CreativeDNA(
                variant_id=variant_id,
                character=character,
                creatures=creatures,
                environment=environment,
                lighting=lighting,
                camera=camera,
                composition=composition,
                hook=hook,
                colors=colors,
                motion=motion,
                fb_meta=fb_meta,
                performance=performance,
            ))

        return dna_list

    # ------------------------------------------------------------------
    # 角色提取
    # ------------------------------------------------------------------
    def _extract_character(self, lovart: dict, vid_feat: dict) -> dict:
        """从 Lovart 结构化 character 字段 + subject 推断角色 DNA"""
        # 优先使用 Lovart 结构化 character
        lovart_char = lovart.get("character") or {}

        # 如果 Lovart 返回了结构化 character，直接映射
        if lovart_char and isinstance(lovart_char, dict):
            char_type = self._infer_character_type(lovart_char)
            return {
                "type": char_type,
                "hair": lovart_char.get("hairstyle", "") or self._infer_from_text(lovart, "hair"),
                "hat": self._infer_from_text(lovart, "hat"),
                "clothes": lovart_char.get("clothing", "") or self._infer_from_text(lovart, "clothes"),
                "face": self._infer_from_text(lovart, "face"),
                "eyes": self._infer_from_text(lovart, "eyes"),
                "pose": lovart_char.get("action", "") or lovart.get("character_pose", ""),
                "gesture": self._infer_from_text(lovart, "gesture"),
                "emotion": lovart_char.get("expression", "") or lovart.get("mood", ""),
                "age": lovart_char.get("age", "adult"),
                "accessories": self._infer_list_from_text(lovart, ["accessory", "accessories", "wand", "staff", "orb"]),
            }

        # 退化: 从 subject + character_pose 推断
        subject = str(lovart.get("subject", "") or "")
        char_type = self._infer_character_type_from_subject(subject)
        return {
            "type": char_type,
            "hair": self._infer_from_text(lovart, "hair"),
            "hat": self._infer_from_text(lovart, "hat"),
            "clothes": self._infer_from_text(lovart, "clothes"),
            "face": "",
            "eyes": "",
            "pose": str(lovart.get("character_pose", "") or ""),
            "gesture": "",
            "emotion": str(lovart.get("mood", "") or ""),
            "age": "adult",
            "accessories": [],
        }

    def _infer_character_type(self, char: dict) -> str:
        """从 Lovart character 结构推断角色类型"""
        profession = str(char.get("profession", "")).lower()
        clothing = str(char.get("clothing", "")).lower()
        text = f"{profession} {clothing}"

        type_map = [
            ("witch", ["witch", "mage", "sorceress", "女巫", "巫师"]),
            ("wizard", ["wizard", "warlock", "sorcerer"]),
            ("fairy", ["fairy", "pixie", "仙女"]),
            ("queen", ["queen", "princess", "女王", "公主"]),
            ("warrior", ["warrior", "knight", "fighter", "战士"]),
            ("villager", ["villager", "civilian", "peasant", "村民"]),
        ]
        for ctype, keywords in type_map:
            if any(kw in text for kw in keywords):
                return ctype
        return "witch"  # Merge Witches 默认角色类型

    def _infer_character_type_from_subject(self, subject: str) -> str:
        """从 subject 文本推断角色类型"""
        text = subject.lower()
        type_map = [
            ("witch", ["witch", "sorceress", "女巫", "魔女"]),
            ("wizard", ["wizard", "warlock", "巫师"]),
            ("fairy", ["fairy", "仙女", "精灵"]),
            ("queen", ["queen", "princess", "女王", "公主"]),
            ("warrior", ["warrior", "knight", "战士", "骑士"]),
            ("cat", ["cat", "猫"]),
        ]
        for ctype, keywords in type_map:
            if any(kw in text for kw in keywords):
                return ctype
        return "unknown"

    # ------------------------------------------------------------------
    # 生物提取
    # ------------------------------------------------------------------
    def _extract_creatures(self, lovart: dict) -> list[dict]:
        """从 standout_features + subject 推断生物 DNA

        Merge Witches 的核心元素之一是各种伴生生物 (dragon, cat, owl 等)，
        需要从描述中推断生物类型、颜色、动作等。
        """
        # 收集所有可能提及生物的文本
        texts = []
        for key in ("subject", "standout_features", "description"):
            val = lovart.get(key)
            if isinstance(val, str):
                texts.append(val)
            elif isinstance(val, list):
                texts.extend(str(v) for v in val if v)

        # Lovart 结构化数据中也可能直接包含 creature 信息
        lovart_char = lovart.get("character") or {}
        if isinstance(lovart_char, dict):
            for sub_key in ("tags", "features"):
                sub_val = lovart_char.get(sub_key)
                if isinstance(sub_val, list):
                    texts.extend(str(v) for v in sub_val if v)

        combined_text = " ".join(texts).lower()

        creatures: list[dict] = []
        detected_types: set[str] = set()

        for creature_type, keywords in _CREATURE_KEYWORDS.items():
            if any(kw in combined_text for kw in keywords):
                detected_types.add(creature_type)

        for creature_type in detected_types:
            creatures.append({
                "type": creature_type,
                "color": self._infer_creature_color(combined_text, creature_type),
                "glow": self._infer_creature_glow(combined_text, creature_type),
                "action": self._infer_creature_action(combined_text, creature_type),
                "size": self._infer_creature_size(combined_text, creature_type),
                "position": self._infer_creature_position(combined_text, creature_type),
            })

        # 如果没有检测到生物但场景暗示存在（如 magic_forest），添加默认生物
        if not creatures and any(
            kw in combined_text
            for kw in ["creature", "companion", "pet", "petit", "动物", "宠物", "伙伴"]
        ):
            creatures.append({
                "type": "unknown",
                "color": "unknown",
                "glow": "none",
                "action": "nearby",
                "size": "small",
                "position": "beside",
            })

        return creatures

    def _infer_creature_color(self, text: str, creature_type: str) -> str:
        """推断生物颜色"""
        # 检查文本中是否有颜色+生物的组合描述
        color_keywords = [
            ("blue", ["blue", "青", "蓝"]),
            ("red", ["red", "红"]),
            ("green", ["green", "绿"]),
            ("gold", ["gold", "golden", "金"]),
            ("purple", ["purple", "violet", "紫"]),
            ("orange", ["orange", "橙"]),
            ("cyan", ["cyan", "ice", "frost", "冰"]),
            ("pink", ["pink", "粉"]),
            ("white", ["white", "白"]),
            ("black", ["black", "dark", "黑"]),
        ]
        for color, kws in color_keywords:
            # 查找 "颜色+生物" 的模式，如 "blue dragon", "golden cat"
            for kw in kws:
                pattern = rf"{kw}\s+\w*\s*{creature_type}|{creature_type}\s+\w*\s*{kw}"
                if re.search(pattern, text):
                    return color

        # 基于生物类型给默认颜色
        default_colors = {
            "dragon": "blue", "cat": "orange", "owl": "brown",
            "fairy": "gold", "unicorn": "white", "phoenix": "red",
            "wolf": "gray", "spider": "black", "snake": "green",
            "bat": "black", "frog": "green", "raven": "black",
            "troll": "brown", "golem": "gray", "spirit": "cyan",
        }
        return default_colors.get(creature_type, "unknown")

    def _infer_creature_glow(self, text: str, creature_type: str) -> str:
        """推断生物发光效果"""
        glow_patterns = [
            ("cyan", [rf"(cyan|ice|frost|glow|发光|冰).*{creature_type}", rf"{creature_type}.*(cyan|ice|frost|glow|发光|冰)"]),
            ("gold", [rf"(gold|golden|holy|divine|金).*{creature_type}", rf"{creature_type}.*(gold|golden|holy|divine|金)"]),
            ("purple", [rf"(purple|dark|shadow|紫|暗).*{creature_type}", rf"{creature_type}.*(purple|dark|shadow|紫|暗)"]),
            ("green", [rf"(green|nature|nature|绿|自然).*{creature_type}", rf"{creature_type}.*(green|nature|绿|自然)"]),
        ]
        for glow_color, patterns in glow_patterns:
            for pattern in patterns:
                if re.search(pattern, text):
                    return glow_color
        return "none"

    def _infer_creature_action(self, text: str, creature_type: str) -> str:
        """推断生物动作"""
        action_map = [
            ("perched", ["perch", "shoulder", "stand on", "栖息", "站立"]),
            ("flying", ["fly", "soar", "hover", "飞", "翱翔"]),
            ("sitting", ["sit", "rest", "坐", "休息"]),
            ("running", ["run", "chase", "跑", "追"]),
            ("sleeping", ["sleep", "nap", "睡"]),
            ("playing", ["play", "jump", "玩", "跳"]),
            ("attacking", ["attack", "bite", "scratch", "攻击", "咬"]),
            ("glowing", ["glow", "shimmer", "sparkle", "发光"]),
        ]
        for action, keywords in action_map:
            if any(kw in text for kw in keywords):
                return action
        return "nearby"

    def _infer_creature_size(self, text: str, creature_type: str) -> str:
        """推断生物体型"""
        if any(kw in text for kw in ["baby", "tiny", "small", "little", "幼", "小", "mini"]):
            return "baby"
        if any(kw in text for kw in ["huge", "giant", "large", "big", "巨大", "大"]):
            return "large"
        return "small"

    def _infer_creature_position(self, text: str, creature_type: str) -> str:
        """推断生物位置"""
        position_map = [
            ("left_shoulder", ["left shoulder", "左肩"]),
            ("right_shoulder", ["right shoulder", "右肩"]),
            ("on_head", ["on head", "head", "头上"]),
            ("beside", ["beside", "next to", "旁边", "身边"]),
            ("background", ["behind", "background", "后面", "背景"]),
            ("in_hand", ["in hand", "holding", "手拿", "手持"]),
            ("foreground", ["in front", "foreground", "前面", "前景"]),
        ]
        for pos, keywords in position_map:
            if any(kw in text for kw in keywords):
                return pos
        return "nearby"

    # ------------------------------------------------------------------
    # 环境提取
    # ------------------------------------------------------------------
    def _extract_environment(self, lovart: dict, vid_feat: dict) -> dict:
        """提取环境 DNA"""
        lovart_env = lovart.get("environment") or {}
        subject = str(lovart.get("subject", "") or "").lower()
        standout = lovart.get("standout_features") or []
        if isinstance(standout, str):
            standout = [standout]
        standout_text = " ".join(str(s) for s in standout).lower()

        env_text = f"{subject} {standout_text}"

        # 环境类型
        env_type = "unknown"
        if isinstance(lovart_env, dict) and lovart_env.get("scene"):
            scene = str(lovart_env["scene"]).lower()
            for key, mapped in _ENV_SCENE_MAP.items():
                if key in scene:
                    env_type = mapped
                    break
            if env_type == "unknown":
                env_type = scene
        else:
            for key, mapped in _ENV_SCENE_MAP.items():
                if key in env_text:
                    env_type = mapped
                    break

        # 时间
        time_of_day = "unknown"
        if any(kw in env_text for kw in ["night", "dark", "midnight", "夜晚", "黑暗"]):
            time_of_day = "night"
        elif any(kw in env_text for kw in ["sunset", "dusk", "dawn", "黄昏", "黎明"]):
            time_of_day = "twilight"
        elif any(kw in env_text for kw in ["day", "morning", "bright", "白天", "早晨"]):
            time_of_day = "day"

        # 天气
        weather = "clear"
        if any(kw in env_text for kw in ["rain", "storm", "thunder", "雨", "暴风"]):
            weather = "stormy"
        elif any(kw in env_text for kw in ["fog", "mist", "雾", "薄雾"]):
            weather = "foggy"
        elif any(kw in env_text for kw in ["snow", "ice", "frost", "雪", "冰"]):
            weather = "snowy"

        # 环境元素
        elements = self._extract_env_elements(env_text, lovart_env)

        # 灯光来源
        lighting_source = "unknown"
        if any(kw in env_text for kw in ["bioluminescent", "bioluminescence", "生物发光", "萤火"]):
            lighting_source = "bioluminescent"
        elif any(kw in env_text for kw in ["moon", "moonlight", "月光"]):
            lighting_source = "moonlight"
        elif any(kw in env_text for kw in ["candle", "lantern", "torch", "烛光", "火把"]):
            lighting_source = "candlelight"
        elif any(kw in env_text for kw in ["fire", "campfire", "flame", "篝火"]):
            lighting_source = "firelight"
        elif any(kw in env_text for kw in ["magic", "spell", "glow", "魔法"]):
            lighting_source = "magical"

        # 魔法元素
        magic_elements = [
            kw for kw in _MAGIC_KEYWORDS
            if kw in env_text
        ]

        return {
            "type": env_type,
            "time": time_of_day,
            "weather": weather,
            "elements": elements,
            "lighting_source": lighting_source,
            "magic_elements": magic_elements,
        }

    def _extract_env_elements(self, text: str, lovart_env: dict) -> list[str]:
        """提取环境元素列表"""
        # 从 Lovart 结构化数据获取
        if isinstance(lovart_env, dict):
            tags = lovart_env.get("tags") or []
            if tags:
                return [str(t) for t in tags if t]

        # 从文本推断
        element_keywords = [
            "mushroom", "fountain", "tree", "flower", "crystal", "rock",
            "waterfall", "bridge", "ruin", "altar", "cauldron", "bookshelf",
            "potion", "scroll", "chest", "door", "gate", "stair",
            "蘑菇", "喷泉", "树", "花", "水晶", "瀑布", "桥", "废墟",
            "祭坛", "大锅", "书架", "药水", "卷轴", "宝箱", "门", "阶梯",
        ]
        return [kw for kw in element_keywords if kw in text]

    # ------------------------------------------------------------------
    # 灯光提取
    # ------------------------------------------------------------------
    def _extract_lighting(self, lovart: dict, vid_feat: dict) -> dict:
        """提取灯光 DNA"""
        lovart_lighting = str(lovart.get("lighting", "") or "").lower()
        lovart_style = lovart.get("style") or {}
        if isinstance(lovart_style, dict):
            color_tone = str(lovart_style.get("color_tone", "")).lower()
            saturation = str(lovart_style.get("saturation", "")).lower()
        else:
            color_tone = ""
            saturation = ""

        combined = f"{lovart_lighting} {color_tone}"

        # 灯光类型
        light_type = "ambient"
        if any(kw in combined for kw in ["dramatic", "contrast", "high contrast", "戏剧"]):
            light_type = "dramatic"
        elif any(kw in combined for kw in ["soft", "diffused", "柔和", "漫射"]):
            light_type = "soft"
        elif any(kw in combined for kw in ["rim", "backlight", "轮廓光", "逆光"]):
            light_type = "rim"
        elif any(kw in combined for kw in ["spot", "focused", "聚光"]):
            light_type = "spotlight"
        elif any(kw in combined for kw in ["volumetric", "god ray", "体积光", "丁达尔"]):
            light_type = "volumetric"
        elif any(kw in combined for kw in ["bioluminescent", "glow", "生物发光"]):
            light_type = "bioluminescent"

        # 色温
        color_temp = "neutral"
        if any(kw in combined for kw in ["warm", "暖", "orange", "gold"]):
            color_temp = "warm"
        elif any(kw in combined for kw in ["cool", "冷", "blue", "cyan"]):
            color_temp = "cool"

        # 方向
        direction = "front"
        if any(kw in combined for kw in ["back", "behind", "后方", "逆光"]):
            direction = "back"
        elif any(kw in combined for kw in ["side", "侧面"]):
            direction = "side"
        elif any(kw in combined for kw in ["top", "overhead", "顶", "上方"]):
            direction = "top"
        elif any(kw in combined for kw in ["bottom", "under", "底", "下方"]):
            direction = "bottom"

        # 强度 - 融合视频特征 brightness
        brightness = vid_feat.get("brightness")
        if isinstance(brightness, (int, float)):
            intensity = "high" if brightness > 0.65 else ("low" if brightness < 0.35 else "medium")
        elif saturation in ("high",):
            intensity = "high"
        elif saturation in ("low",):
            intensity = "low"
        else:
            intensity = "medium"

        # 特殊效果
        special_effects: list[str] = []
        if any(kw in combined for kw in ["lens flare", "flare", "光晕"]):
            special_effects.append("lens_flare")
        if any(kw in combined for kw in ["bloom", "glow", "泛光"]):
            special_effects.append("bloom")
        if any(kw in combined for kw in ["god ray", "volumetric", "丁达尔", "体积光"]):
            special_effects.append("god_rays")
        if any(kw in combined for kw in ["chromatic", "色散"]):
            special_effects.append("chromatic_aberration")

        return {
            "type": light_type,
            "color_temperature": color_temp,
            "direction": direction,
            "intensity": intensity,
            "special_effects": special_effects,
        }

    # ------------------------------------------------------------------
    # 镜头提取
    # ------------------------------------------------------------------
    def _extract_camera(self, lovart: dict) -> dict:
        """提取镜头 DNA"""
        lovart_camera = lovart.get("camera") or {}
        if isinstance(lovart_camera, str):
            lovart_camera = {}

        shot_type = str(lovart_camera.get("shot_type", "") or "").lower()
        if not shot_type:
            shot_type = "medium"

        movement = str(lovart_camera.get("movement", "") or "").lower()
        if not movement:
            movement = "static"

        # 角度推断
        angle = "eye_level"
        subject = str(lovart.get("subject", "") or "").lower()
        if any(kw in subject for kw in ["overhead", "top-down", "bird", "俯视"]):
            angle = "high_angle"
        elif any(kw in subject for kw in ["low", "ground", "worm", "仰视"]):
            angle = "low_angle"
        elif any(kw in subject for kw in ["dutch", "tilted", "倾斜"]):
            angle = "dutch_angle"

        # 合图法则
        composition_rule = "center_symmetry"
        composition_text = str(lovart.get("composition", "") or "").lower()
        for rule, keywords in _COMPOSITION_RULES:
            if any(kw in composition_text for kw in keywords):
                composition_rule = rule
                break

        return {
            "shot_type": shot_type,
            "angle": angle,
            "movement": movement,
            "composition_rule": composition_rule,
        }

    # ------------------------------------------------------------------
    # 构图提取
    # ------------------------------------------------------------------
    def _extract_composition(self, lovart: dict, vid_feat: dict) -> dict:
        """提取构图 DNA"""
        composition_text = str(lovart.get("composition", "") or "").lower()

        # 布局
        layout = "single_subject"
        if any(kw in composition_text for kw in ["split", "divided", "compare", "对比", "分屏"]):
            layout = "split_screen"
        elif any(kw in composition_text for kw in ["grid", "montage", "网格", "拼图"]):
            layout = "grid"
        elif any(kw in composition_text for kw in ["layered", "depth", "分层", "纵深"]):
            layout = "layered"

        # 主体位置
        subject_position = "center"
        if any(kw in composition_text for kw in ["left", "左"]):
            subject_position = "left_third"
        elif any(kw in composition_text for kw in ["right", "右"]):
            subject_position = "right_third"
        elif any(kw in composition_text for kw in ["top", "上"]):
            subject_position = "top"

        # 深度层次
        depth_layers = 2
        if any(kw in composition_text for kw in ["deep", "3-layer", "多层", "纵深"]):
            depth_layers = 3

        # 前中后景
        foreground = self._infer_layer_content(composition_text, "foreground")
        midground = self._infer_layer_content(composition_text, "midground")
        background = self._infer_layer_content(composition_text, "background")

        return {
            "layout": layout,
            "subject_position": subject_position,
            "depth_layers": depth_layers,
            "foreground": foreground,
            "midground": midground,
            "background": background,
        }

    @staticmethod
    def _infer_layer_content(text: str, layer: str) -> str:
        """推断某一层的内容"""
        layer_keywords = {
            "foreground": ["front", "前景", "近处"],
            "midground": ["mid", "中景", "中间"],
            "background": ["back", "background", "背景", "远处"],
        }
        # 简单推断 - 实际可结合 edge_density 等视频特征细化
        kws = layer_keywords.get(layer, [])
        if any(kw in text for kw in kws):
            return "detailed"
        return "implied"

    # ------------------------------------------------------------------
    # Hook 提取
    # ------------------------------------------------------------------
    def _extract_hook(self, lovart: dict) -> dict:
        """提取 Hook DNA"""
        lovart_hook = lovart.get("hook") or {}
        if isinstance(lovart_hook, str):
            lovart_hook = {"hook_type": lovart_hook}

        hook_type = str(
            lovart_hook.get("hook_type")
            or lovart.get("hook_type", "")
            or "other"
        ).lower()

        # 标准化 hook_type
        hook_type = self._normalize_hook_type(hook_type)

        trigger = _HOOK_TYPE_TO_TRIGGER.get(hook_type, "curiosity_gap")
        emotional_hook = _HOOK_TYPE_TO_EMOTION.get(hook_type, "好奇探索")
        visual_hook = _HOOK_TYPE_TO_VISUAL.get(hook_type, "视觉吸引")

        return {
            "type": hook_type,
            "trigger": trigger,
            "emotional_hook": emotional_hook,
            "visual_hook": visual_hook,
        }

    @staticmethod
    def _normalize_hook_type(raw: str) -> str:
        """标准化 hook 类型名称"""
        aliases: dict[str, str] = {
            "chest_open": "chest", "treasure": "chest",
            "big_number": "number", "number_hook": "number",
            "beautiful": "beauty", "aesthetic": "beauty",
            "boss_fight": "boss", "boss_battle": "boss",
            "coin": "gold_coin", "coins": "gold_coin",
            "mega_reward": "giant_reward", "huge_reward": "giant_reward",
            "peril": "danger", "threat": "danger",
            "timer": "countdown", "urgent": "countdown",
            "fail": "failure", "lose": "failure",
            "mysterious": "mystery", "unknown": "mystery",
            "compare": "comparison", "vs": "comparison",
            "collect": "collection", "gather": "collection",
        }
        return aliases.get(raw, raw)

    # ------------------------------------------------------------------
    # 色彩提取
    # ------------------------------------------------------------------
    def _extract_colors(self, lovart: dict, vid_feat: dict) -> dict:
        """提取色彩 DNA - 融合 Lovart palette + 视频特征数据"""
        # 从 Lovart palette 获取色板信息
        palette = lovart.get("palette") or []
        if isinstance(palette, str):
            palette = [s.strip() for s in palette.split(",") if s.strip()]

        lovart_style = lovart.get("style") or {}
        if isinstance(lovart_style, str):
            lovart_style = {}
        color_tone = str(lovart_style.get("color_tone", "") or "").lower()
        saturation_level = str(lovart_style.get("saturation", "") or "").lower()

        # 主色调
        dominant: list[str] = []
        accent: list[str] = []
        background_colors: list[str] = []

        if palette:
            dominant = palette[:3]
            accent = palette[3:5] if len(palette) > 3 else []
            background_colors = palette[-2:] if len(palette) > 2 else palette[:1]
        else:
            # 从 tone 推断
            if "warm" in color_tone:
                dominant = ["orange", "gold"]
                accent = ["red", "yellow"]
                background_colors = ["dark_brown"]
            elif "cool" in color_tone:
                dominant = ["blue", "cyan"]
                accent = ["purple", "teal"]
                background_colors = ["dark_blue"]
            else:
                dominant = ["purple", "gold"]
                accent = ["blue", "green"]
                background_colors = ["dark_gray"]

        # 氛围色板
        mood_palette: list[str] = []
        if saturation_level == "high":
            mood_palette.append("vivid")
        elif saturation_level == "low":
            mood_palette.append("muted")

        # 融合视频特征 saturation
        vid_saturation = vid_feat.get("saturation")
        if isinstance(vid_saturation, (int, float)):
            if vid_saturation > 0.7 and "vivid" not in mood_palette:
                mood_palette.append("vivid")
            elif vid_saturation < 0.3 and "muted" not in mood_palette:
                mood_palette.append("muted")

        # 融合视频特征 hue 统计
        vid_hue = vid_feat.get("dominant_hue")
        if isinstance(vid_hue, str) and vid_hue and vid_hue not in dominant:
            accent.append(vid_hue)

        # 从 mood 补充
        mood = str(lovart.get("mood", "") or "").lower()
        if any(kw in mood for kw in ["mystery", "神秘", "dark"]):
            mood_palette.append("dark_mysterious")
        elif any(kw in mood for kw in ["warm", "cozy", "温馨"]):
            mood_palette.append("warm_cozy")
        elif any(kw in mood for kw in ["exciting", "thrill", "刺激"]):
            mood_palette.append("high_energy")
        elif any(kw in mood for kw in ["calm", "peaceful", "宁静"]):
            mood_palette.append("serene")

        if not mood_palette:
            mood_palette = ["balanced"]

        return {
            "dominant": dominant,
            "accent": accent,
            "background": background_colors,
            "mood_palette": mood_palette,
        }

    # ------------------------------------------------------------------
    # 动态提取
    # ------------------------------------------------------------------
    def _extract_motion(self, lovart: dict, vid_feat: dict) -> dict:
        """提取动态 DNA"""
        lovart_motion = lovart.get("motion") or {}
        if isinstance(lovart_motion, str):
            lovart_motion = {}

        # 镜头运动
        camera_movement = str(lovart_motion.get("movement") or lovart_motion.get("cut_speed", "") or "").lower()
        if not camera_movement:
            vid_motion = vid_feat.get("motion_magnitude")
            if isinstance(vid_motion, (int, float)):
                camera_movement = "dynamic" if vid_motion > 0.6 else ("subtle" if vid_motion < 0.3 else "moderate")
            else:
                camera_movement = "moderate"

        # 角色动作
        character_action = ""
        lovart_char = lovart.get("character") or {}
        if isinstance(lovart_char, dict):
            character_action = str(lovart_char.get("action", "") or lovart.get("character_pose", "") or "")

        # 生物动作
        creatures = self._extract_creatures(lovart)
        creature_actions = [c.get("action", "") for c in creatures if c.get("action")]

        # 粒子效果
        particle_effects: list[str] = []
        standout = lovart.get("standout_features") or []
        if isinstance(standout, str):
            standout = [standout]
        standout_text = " ".join(str(s) for s in standout).lower()
        if any(kw in standout_text for kw in ["particle", "sparkle", "glitter", "粒子", "火花"]):
            particle_effects.append("sparkles")
        if any(kw in standout_text for kw in ["smoke", "mist", "fog", "烟", "雾"]):
            particle_effects.append("smoke")
        if any(kw in standout_text for kw in ["rain", "raindrop", "雨"]):
            particle_effects.append("rain")
        if any(kw in standout_text for kw in ["snow", "snowflake", "雪"]):
            particle_effects.append("snow")
        if any(kw in standout_text for kw in ["fire", "flame", "ember", "火"]):
            particle_effects.append("fire_particles")
        if any(kw in standout_text for kw in ["magic", "spell", "enchant", "魔法"]):
            particle_effects.append("magic_particles")

        # 转场风格
        transition_style = "cut"
        if any(kw in standout_text for kw in ["fade", "dissolve", "渐变", "溶解"]):
            transition_style = "fade"
        elif any(kw in standout_text for kw in ["zoom", "zoom-in", "zoom-out", "缩放"]):
            transition_style = "zoom"
        elif any(kw in standout_text for kw in ["swipe", "slide", "滑动"]):
            transition_style = "swipe"
        elif any(kw in standout_text for kw in ["morph", "transform", "变形"]):
            transition_style = "morph"

        return {
            "camera_movement": camera_movement,
            "character_action": character_action,
            "creature_actions": creature_actions,
            "particle_effects": particle_effects,
            "transition_style": transition_style,
        }

    # ------------------------------------------------------------------
    # Facebook 元数据提取
    # ------------------------------------------------------------------
    def _extract_fb_meta(self, lovart: dict) -> dict:
        """提取 Facebook 广告元数据"""
        lovart_cta = lovart.get("cta") or {}
        if isinstance(lovart_cta, str):
            lovart_cta = {}

        # 时长
        duration = lovart.get("duration") or lovart.get("asset_duration_seconds") or 0
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = 0.0

        # 分辨率
        resolution = str(lovart.get("resolution", "") or "")

        # 标题
        headline = str(
            lovart.get("headline")
            or lovart.get("title")
            or lovart.get("creative_name", "")
        )

        # CTA
        cta = str(
            lovart_cta.get("cta_type", "")
            or lovart.get("cta_type", "")
            or lovart.get("call_to_action", "")
            or "install"
        )

        # 投放位置
        placement = str(lovart.get("placement", "") or "feed")

        # 宽高比
        aspect_ratio = str(lovart.get("aspect_ratio", "") or "")
        if not aspect_ratio:
            if duration > 0:
                aspect_ratio = "9:16"  # 视频默认竖版
            else:
                aspect_ratio = "1:1"  # 图片默认方形

        return {
            "duration": duration,
            "resolution": resolution,
            "headline": headline,
            "cta": cta,
            "placement": placement,
            "aspect_ratio": aspect_ratio,
        }

    # ------------------------------------------------------------------
    # 投放效果提取
    # ------------------------------------------------------------------
    def _extract_performance(self, lovart: dict) -> dict:
        """提取投放效果指标"""
        spend = float(lovart.get("spend", 0) or lovart.get("total_spend", 0) or 0)
        revenue = float(lovart.get("revenue", 0) or lovart.get("revenue_value", 0) or 0)
        roas = revenue / spend if spend else float(lovart.get("roas", 0) or 0)
        ctr = float(lovart.get("ctr", 0) or 0)
        cpa = float(lovart.get("cpa", 0) or 0)
        ipm = float(lovart.get("ipm", 0) or 0)

        # hook_rate / hold_rate 可从视频分析指标获取，如无则置 0
        hook_rate = float(lovart.get("hook_rate", 0) or 0)
        hold_rate = float(lovart.get("hold_rate", 0) or 0)

        return {
            "roas": round(roas, 4),
            "spend": round(spend, 2),
            "ctr": round(ctr, 4),
            "cpa": round(cpa, 2),
            "hook_rate": round(hook_rate, 4),
            "hold_rate": round(hold_rate, 4),
            "ipm": round(ipm, 2),
        }

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _flatten_lovart(lovart: dict) -> dict:
        """将 Lovart 嵌套 frame_analysis 结构展平为扁平 dict

        Lovart 返回的数据格式为:
        {
            "video_number": "434",
            "roas": 7.0731,
            "total_spend": 30.92,
            "hook_score": 0.4461,
            "resolution": "9:16 竖版",
            "frame_analysis": {
                "hook": {"analysis": {"subject": "...", "palette": "...", ...}},
                "mid":  {"analysis": {"subject": "...", ...}},
            }
        }

        将 hook.analysis 和 mid.analysis 的字段合并到顶层,
        顶层字段优先级最高, hook 优先级高于 mid.
        """
        flat = dict(lovart)  # 浅拷贝，保留顶层字段

        frame_analysis = lovart.get("frame_analysis")
        if not isinstance(frame_analysis, dict):
            return flat

        # 先合并 mid.analysis (低优先级)
        mid = frame_analysis.get("mid")
        if isinstance(mid, dict):
            mid_analysis = mid.get("analysis")
            if isinstance(mid_analysis, dict):
                for key, value in mid_analysis.items():
                    if value and (key not in flat or not flat.get(key)):
                        flat[key] = value

        # 再合并 hook.analysis (高优先级, 覆盖 mid 同名字段)
        hook = frame_analysis.get("hook")
        if isinstance(hook, dict):
            hook_analysis = hook.get("analysis")
            if isinstance(hook_analysis, dict):
                for key, value in hook_analysis.items():
                    if value and (key not in flat or not flat.get(key)):
                        flat[key] = value

        return flat

    def _build_video_feat_map(self, video_analysis: dict) -> dict[str, dict]:
        """构建 video_feature_analysis 查找索引

        支持多种格式:
          1. {creative_id: {saturation, brightness, ...}}  (per-creative)
          2. {avg_saturation, avg_brightness, ...}         (全局聚合)
          3. {high_roas_videos: [...], all_videos: [...]}  (video_feature_analysis.json)
        """
        feat_map: dict[str, dict] = {}

        if not video_analysis:
            return feat_map

        # 检测是否为 per-creative 格式
        per_creative_keys = {"saturation", "brightness", "edge_density", "motion_magnitude", "dominant_hue"}

        # 判断是否包含 per-creative 子项
        for key, value in video_analysis.items():
            if isinstance(value, dict) and per_creative_keys & set(value.keys()):
                # 可能是 creative_id -> features 的映射
                feat_map[key] = value

        # 检查数组类子键: high_roas_videos / all_videos / videos / creatives / features
        for sub_key in ("high_roas_videos", "all_videos", "videos", "creatives", "features"):
            sub_data = video_analysis.get(sub_key)
            if isinstance(sub_data, list):
                for item in sub_data:
                    cid = str(
                        item.get("creative_id")
                        or item.get("video_id")
                        or item.get("video_number")
                        or ""
                    )
                    if cid:
                        if cid in feat_map:
                            feat_map[cid].update(item)
                        else:
                            feat_map[cid] = item
            elif isinstance(sub_data, dict):
                for cid, features in sub_data.items():
                    if isinstance(features, dict):
                        if cid in feat_map:
                            feat_map[cid].update(features)
                        else:
                            feat_map[cid] = features

        return feat_map

    def _infer_from_text(self, lovart: dict, attr: str) -> str:
        """从 Lovart 结果的文本字段中推断属性值"""
        search_texts = [
            str(lovart.get("subject", "") or ""),
            str(lovart.get("description", "") or ""),
        ]
        standout = lovart.get("standout_features") or []
        if isinstance(standout, list):
            search_texts.extend(str(s) for s in standout)
        elif isinstance(standout, str):
            search_texts.append(standout)

        combined = " ".join(search_texts).lower()

        # 属性关键词映射
        attr_keywords: dict[str, list[tuple[str, list[str]]]] = {
            "hair": [
                ("white", ["white hair", "silver hair", "白发", "银发"]),
                ("blonde", ["blonde", "golden hair", "金发"]),
                ("black", ["black hair", "dark hair", "黑发"]),
                ("red", ["red hair", "ginger", "红发"]),
                ("purple", ["purple hair", "violet hair", "紫发"]),
                ("blue", ["blue hair", "蓝发"]),
            ],
            "hat": [
                ("pointed", ["pointed hat", "witch hat", "尖帽", "巫师帽"]),
                ("hood", ["hood", "cowl", "兜帽"]),
                ("crown", ["crown", "tiara", "王冠"]),
                ("none", ["no hat", "bareheaded"]),
            ],
            "clothes": [
                ("dark_cloak", ["dark cloak", "purple cloak", "暗色斗篷", "紫斗篷"]),
                ("robe", ["robe", "gown", "长袍"]),
                ("armor", ["armor", "plate", "铠甲"]),
                ("dress", ["dress", "gown", "裙"]),
            ],
            "face": [
                ("gentle", ["gentle", "soft", "温柔"]),
                ("stern", ["stern", "serious", "严肃"]),
                ("smiling", ["smiling", "grin", "微笑"]),
            ],
            "eyes": [
                ("glowing", ["glowing eyes", "发光的眼睛"]),
                ("bright", ["bright eyes", "明亮的眼睛"]),
                ("mysterious", ["mysterious eyes", "神秘的眼睛"]),
            ],
            "gesture": [
                ("casting", ["casting", "spell", "施法"]),
                ("pointing", ["pointing", "指向"]),
                ("waving", ["waving", "挥手"]),
                ("clasped", ["clasped", "hands together", "合掌"]),
            ],
        }

        for value, keywords in attr_keywords.get(attr, []):
            if any(kw in combined for kw in keywords):
                return value
        return ""

    def _infer_list_from_text(self, lovart: dict, keywords: list[str]) -> list[str]:
        """从文本推断列表属性（如 accessories）"""
        search_texts = [
            str(lovart.get("subject", "") or ""),
            str(lovart.get("standout_features", "") or ""),
        ]
        standout = lovart.get("standout_features") or []
        if isinstance(standout, list):
            search_texts.extend(str(s) for s in standout)

        combined = " ".join(search_texts).lower()
        return [kw for kw in keywords if kw in combined]

    # ------------------------------------------------------------------
    # DNA -> Graph 转换
    # ------------------------------------------------------------------
    def to_graph(self, dna: CreativeDNA) -> dict:
        """将扁平 Creative DNA 转换为树状图谱结构

        用于可视化展示和 DNA 组合分析。图谱从 Collection Hook 出发，
        分支到角色、生物、环境等节点，每个节点再展开细节。

        示例输出::

            Collection Hook
              └── Character
                   └── Witch
                        ├── Hair: white
                        ├── Hat: pointed
                        ├── Clothes: dark purple cloak + gold trim
                        ├── Pose: standing centered, hands clasped
                        └── Expression: gentle smile
              └── Creatures
                   ├── Dragon (blue/cyan, perched on shoulder, baby size)
                   └── Cat (orange, sitting nearby, small)
              └── Environment
                   └── Magic Forest
                        ├── Time: night
                        ├── Lighting: bioluminescent
                        ├── Elements: mushrooms, fountain
                        └── Magic: particles, sparkles

        Returns:
            树状图谱字典，key 为节点名，value 为子树或叶节点值
        """
        # 构建角色子树
        char_type = dna.character.get("type", "unknown")
        char_title = char_type.capitalize()
        char_children: dict[str, str] = {}
        if dna.character.get("hair"):
            char_children["Hair"] = dna.character["hair"]
        if dna.character.get("hat"):
            char_children["Hat"] = dna.character["hat"]
        if dna.character.get("clothes"):
            char_children["Clothes"] = dna.character["clothes"]
        if dna.character.get("pose"):
            char_children["Pose"] = dna.character["pose"]
        if dna.character.get("emotion"):
            char_children["Expression"] = dna.character["emotion"]
        if dna.character.get("age"):
            char_children["Age"] = dna.character["age"]
        if dna.character.get("accessories"):
            acc = dna.character["accessories"]
            if isinstance(acc, list):
                char_children["Accessories"] = ", ".join(str(a) for a in acc)
            else:
                char_children["Accessories"] = str(acc)

        # 构建生物子树
        creature_nodes: list[dict] = []
        for creature in dna.creatures:
            c_type = creature.get("type", "unknown").capitalize()
            color = creature.get("color", "")
            glow = creature.get("glow", "")
            action = creature.get("action", "")
            size = creature.get("size", "")
            position = creature.get("position", "")

            # 格式化: "Dragon (blue/cyan, perched on shoulder, baby size)"
            detail_parts: list[str] = []
            if color:
                color_str = f"{color}/{glow}" if glow and glow != "none" else color
                detail_parts.append(color_str)
            if action:
                detail_parts.append(action.replace("_", " "))
            if size and size != "small":
                detail_parts.append(f"{size} size")

            detail = ", ".join(detail_parts)
            position_info = f" ({position.replace('_', ' ')})" if position and position != "nearby" else ""

            creature_node: dict[str, Any] = {
                "type": c_type,
                "detail": detail + position_info if detail else "",
            }
            if color:
                creature_node["color"] = color
            if glow and glow != "none":
                creature_node["glow"] = glow
            if action:
                creature_node["action"] = action
            if size:
                creature_node["size"] = size
            if position:
                creature_node["position"] = position
            creature_nodes.append(creature_node)

        # 构建环境子树
        env_type = dna.environment.get("type", "unknown")
        env_title = env_type.replace("_", " ").title()
        env_children: dict[str, str] = {}
        if dna.environment.get("time"):
            env_children["Time"] = dna.environment["time"]
        if dna.environment.get("lighting_source"):
            env_children["Lighting"] = dna.environment["lighting_source"]
        if dna.environment.get("elements"):
            elements = dna.environment["elements"]
            if isinstance(elements, list):
                env_children["Elements"] = ", ".join(str(e) for e in elements)
            else:
                env_children["Elements"] = str(elements)
        if dna.environment.get("magic_elements"):
            magic = dna.environment["magic_elements"]
            if isinstance(magic, list):
                env_children["Magic"] = ", ".join(str(m) for m in magic)
            else:
                env_children["Magic"] = str(magic)
        if dna.environment.get("weather") and dna.environment["weather"] != "clear":
            env_children["Weather"] = dna.environment["weather"]

        # 构建灯光子树
        lighting_children: dict[str, str] = {}
        if dna.lighting.get("type"):
            lighting_children["Type"] = dna.lighting["type"]
        if dna.lighting.get("color_temperature"):
            lighting_children["Temperature"] = dna.lighting["color_temperature"]
        if dna.lighting.get("direction"):
            lighting_children["Direction"] = dna.lighting["direction"]
        if dna.lighting.get("intensity"):
            lighting_children["Intensity"] = dna.lighting["intensity"]
        if dna.lighting.get("special_effects"):
            effects = dna.lighting["special_effects"]
            if isinstance(effects, list):
                lighting_children["Effects"] = ", ".join(str(e) for e in effects)
            else:
                lighting_children["Effects"] = str(effects)

        # 构建镜头子树
        camera_children: dict[str, str] = {}
        if dna.camera.get("shot_type"):
            camera_children["Shot"] = dna.camera["shot_type"]
        if dna.camera.get("angle"):
            camera_children["Angle"] = dna.camera["angle"]
        if dna.camera.get("movement"):
            camera_children["Movement"] = dna.camera["movement"]
        if dna.camera.get("composition_rule"):
            camera_children["Rule"] = dna.camera["composition_rule"]

        # 构图子树
        comp_children: dict[str, str] = {}
        if dna.composition.get("layout"):
            comp_children["Layout"] = dna.composition["layout"]
        if dna.composition.get("subject_position"):
            comp_children["Subject"] = dna.composition["subject_position"]
        if dna.composition.get("depth_layers"):
            comp_children["Depth"] = str(dna.composition["depth_layers"]) + " layers"

        # 色彩子树
        color_children: dict[str, str] = {}
        if dna.colors.get("dominant"):
            color_children["Dominant"] = ", ".join(str(c) for c in dna.colors["dominant"])
        if dna.colors.get("accent"):
            color_children["Accent"] = ", ".join(str(c) for c in dna.colors["accent"])
        if dna.colors.get("mood_palette"):
            color_children["Mood"] = ", ".join(str(c) for c in dna.colors["mood_palette"])

        # 动态子树
        motion_children: dict[str, str] = {}
        if dna.motion.get("camera_movement"):
            motion_children["Camera"] = dna.motion["camera_movement"]
        if dna.motion.get("character_action"):
            motion_children["Character"] = dna.motion["character_action"]
        if dna.motion.get("particle_effects"):
            effects = dna.motion["particle_effects"]
            if isinstance(effects, list):
                motion_children["Particles"] = ", ".join(str(e) for e in effects)
            else:
                motion_children["Particles"] = str(effects)
        if dna.motion.get("transition_style"):
            motion_children["Transition"] = dna.motion["transition_style"]

        # 组装完整图谱
        hook_type = dna.hook.get("type", "unknown")
        graph = {
            "root": "Collection Hook",
            "variant_id": dna.variant_id,
            "hook": {
                "type": hook_type,
                "trigger": dna.hook.get("trigger", ""),
                "emotional_hook": dna.hook.get("emotional_hook", ""),
                "visual_hook": dna.hook.get("visual_hook", ""),
            },
            "character": {
                "type": char_title,
                "detail": char_children,
            },
            "creatures": creature_nodes,
            "environment": {
                "type": env_title,
                "detail": env_children,
            },
            "lighting": lighting_children,
            "camera": camera_children,
            "composition": comp_children,
            "colors": color_children,
            "motion": motion_children,
            "fb_meta": dna.fb_meta,
            "performance": dna.performance,
        }
        return graph

    def to_graph_text(self, dna: CreativeDNA) -> str:
        """将 Creative DNA 转换为可读的树状文本格式

        Returns:
            缩进树状文本，适合在终端或文档中展示
        """
        graph = self.to_graph(dna)
        lines: list[str] = []

        hook = graph["hook"]
        lines.append(f"Collection Hook [{hook['type']}]")
        if hook.get("trigger"):
            lines.append(f"  ├── Trigger: {hook['trigger']}")
        if hook.get("emotional_hook"):
            lines.append(f"  ├── Emotional: {hook['emotional_hook']}")
        if hook.get("visual_hook"):
            lines.append(f"  └── Visual: {hook['visual_hook']}")

        # 角色
        char = graph["character"]
        lines.append(f"  └── Character")
        lines.append(f"       └── {char['type']}")
        char_detail = char["detail"]
        char_items = list(char_detail.items())
        for i, (key, val) in enumerate(char_items):
            prefix = "├──" if i < len(char_items) - 1 else "└──"
            lines.append(f"            {prefix} {key}: {val}")

        # 生物
        creatures = graph["creatures"]
        if creatures:
            lines.append(f"  └── Creatures")
            for ci, creature in enumerate(creatures):
                prefix = "├──" if ci < len(creatures) - 1 else "└──"
                detail = creature.get("detail", "")
                if detail:
                    lines.append(f"       {prefix} {creature['type']} ({detail})")
                else:
                    lines.append(f"       {prefix} {creature['type']}")

        # 环境
        env = graph["environment"]
        lines.append(f"  └── Environment")
        lines.append(f"       └── {env['type']}")
        env_detail = env["detail"]
        env_items = list(env_detail.items())
        for i, (key, val) in enumerate(env_items):
            prefix = "├──" if i < len(env_items) - 1 else "└──"
            lines.append(f"            {prefix} {key}: {val}")

        # 灯光
        lighting = graph["lighting"]
        if lighting:
            lines.append(f"  └── Lighting")
            lt_items = list(lighting.items())
            for i, (key, val) in enumerate(lt_items):
                prefix = "├──" if i < len(lt_items) - 1 else "└──"
                lines.append(f"       {prefix} {key}: {val}")

        # 镜头
        camera = graph["camera"]
        if camera:
            lines.append(f"  └── Camera")
            cam_items = list(camera.items())
            for i, (key, val) in enumerate(cam_items):
                prefix = "├──" if i < len(cam_items) - 1 else "└──"
                lines.append(f"       {prefix} {key}: {val}")

        # 色彩
        colors = graph["colors"]
        if colors:
            lines.append(f"  └── Colors")
            clr_items = list(colors.items())
            for i, (key, val) in enumerate(clr_items):
                prefix = "├──" if i < len(clr_items) - 1 else "└──"
                lines.append(f"       {prefix} {key}: {val}")

        return "\n".join(lines)
