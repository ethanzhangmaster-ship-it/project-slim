"""M1: Feature Intelligence Engine

将每张广告图片转换为可分析的 CreativeFeature 数据。

架构:
- Lovart describe_image 提取语义特征 (主体/情绪/Hook/游戏元素/文案)
- 本地 Pillow 提取客观视觉特征 (颜色/构图/亮度/饱和度)
- 两者融合输出完整 CreativeFeature

复用现有:
- market_ops.clients.lovart.LovartClient.describe_image
- 市场会议/src/market_ops/creative_winner_reader.py 的缓存思路

Usage:
    from market_ops.creative_intelligence.feature_engine import FeatureIntelligenceEngine

    engine = FeatureIntelligenceEngine(use_lovart=True, use_local=True)
    feature = engine.extract_features(
        image_path="output/facebook_top_creatives/P04/xxx.png",
        creative_id="123456",
        project="P04",
    )
    print(feature.to_json())
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# 本地视觉分析
try:
    from PIL import Image
    import numpy as np
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Lovart
try:
    from market_ops.clients.lovart import LovartClient
    HAS_LOVART = True
except ImportError:
    HAS_LOVART = False

from market_ops.creative_intelligence.models import (
    ColorFeatures,
    CompositionFeatures,
    CopyFeatures,
    CreativeFeature,
    GameElements,
    PsychologicalFeatures,
    SubjectFeatures,
    VisualFlags,
)

# Load .env
_ROOT = Path(__file__).resolve().parents[3]
_ENV = _ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


CACHE_DIR = _ROOT / "output" / "creative_intelligence" / "feature_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class FeatureIntelligenceEngine:
    """图片 → CreativeFeature 转换引擎

    hybrid 模式(默认): Lovart提取语义 + Pillow提取客观视觉
    lovart 模式: 仅Lovart(需API)
    local 模式: 仅Pillow+规则(零API成本,特征较浅)
    """

    VERSION = "1.0"

    def __init__(
        self,
        use_lovart: bool = True,
        use_local: bool = True,
        cache_enabled: bool = True,
    ) -> None:
        self._use_lovart = use_lovart and HAS_LOVART
        self._use_local = use_local and HAS_PIL
        self._cache_enabled = cache_enabled
        self._lovart: LovartClient | None = None

        if self._use_lovart:
            try:
                self._lovart = LovartClient(mode="fast")
            except Exception as e:
                print(f"[FeatureEngine] Lovart初始化失败,降级到local: {e}")
                self._use_lovart = False

        mode = "hybrid" if (self._use_lovart and self._use_local) else \
               ("lovart" if self._use_lovart else "local")
        print(f"[FeatureEngine] 模式: {mode} | Lovart={self._use_lovart} | Local={self._use_local}")

    # ==================== 公开接口 ====================

    def extract_features(
        self,
        image_path: str | Path,
        creative_id: str = "",
        project: str = "",
        campaign: str = "",
        adset: str = "",
        force_refresh: bool = False,
    ) -> CreativeFeature:
        """提取单张图片的完整特征"""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")

        # 缓存检查
        cache_key = self._cache_key(image_path, creative_id)
        if self._cache_enabled and not force_refresh:
            cached = self._load_cache(cache_key)
            if cached:
                return cached

        t0 = time.time()
        feature = CreativeFeature(
            creative_id=creative_id,
            project=project,
            campaign=campaign,
            adset=adset,
            image_path=str(image_path),
            analyzed_at=datetime.now().isoformat(),
            analyzer_version=self.VERSION,
        )

        # 1. 本地视觉分析(颜色/构图/亮度)
        if self._use_local:
            local_data = self._extract_local(str(image_path))
            feature.color = ColorFeatures(**local_data["color"])
            feature.composition = CompositionFeatures(**local_data["composition"])
            feature.source = "local"

        # 2. Lovart语义分析(主体/情绪/Hook/游戏元素/文案)
        if self._use_lovart and self._lovart:
            lovart_data = self._extract_lovart(str(image_path), project)
            if lovart_data and "error" not in lovart_data:
                self._merge_lovart_data(feature, lovart_data)
                feature.source = "hybrid" if self._use_local else "lovart"

        # 3. 从Lovart描述推断视觉标记和游戏元素
        self._infer_flags_from_description(feature)

        elapsed = time.time() - t0

        # 保存缓存
        if self._cache_enabled:
            self._save_cache(cache_key, feature)

        return feature

    def extract_batch(
        self,
        creatives: list[dict[str, str]],
        force_refresh: bool = False,
        delay_sec: float = 1.0,
    ) -> list[CreativeFeature]:
        """批量提取特征

        Args:
            creatives: [{"image_path":..., "creative_id":..., "project":..., ...}]
            delay_sec: Lovart API调用间隔(避免限流)
        """
        results: list[CreativeFeature] = []
        total = len(creatives)

        for i, c in enumerate(creatives, 1):
            print(f"[{i}/{total}] {c.get('creative_id', '?')} | {c.get('project', '?')}")
            try:
                f = self.extract_features(
                    image_path=c["image_path"],
                    creative_id=c.get("creative_id", ""),
                    project=c.get("project", ""),
                    campaign=c.get("campaign", ""),
                    adset=c.get("adset", ""),
                    force_refresh=force_refresh,
                )
                results.append(f)
            except Exception as e:
                print(f"  [ERR] {e}")
                # 仍然记录失败项
                results.append(CreativeFeature(
                    creative_id=c.get("creative_id", ""),
                    project=c.get("project", ""),
                    image_path=c.get("image_path", ""),
                    analyzed_at=datetime.now().isoformat(),
                    source="error",
                ))

            if self._use_lovart and i < total:
                time.sleep(delay_sec)

        print(f"\n[FeatureEngine] 完成: {len(results)}/{total}")
        return results

    # ==================== Lovart 语义提取 ====================

    def _extract_lovart(self, image_path: str, project: str) -> dict[str, Any]:
        """调用Lovart describe_image提取语义特征

        直接复用 LovartClient.describe_image (已验证可用,16s返回),
        然后在 _merge_lovart_data 中映射到 Feature 字段。
        """
        if not self._lovart:
            return {"error": "Lovart not initialized"}

        try:
            result = self._lovart.describe_image(image_path, project=project)
            return result
        except Exception as e:
            print(f"  [Lovart] 提取失败: {e}")
            return {"error": str(e)}

    def _build_feature_prompt(self, project: str) -> str:
        """构建Feature提取prompt - 按用户规格要求全部字段"""
        return (
            "You are analyzing a mobile game advertisement image for Facebook Ads. "
            "Extract ALL creative features for data analysis. "
            "Respond ONLY with a single JSON object, no markdown fences, in this exact schema:\n"
            "{\n"
            '  "subject_type": "character|creature|scene|object|ui",\n'
            '  "subject_count": <int>,\n'
            '  "character_count": <int>,\n'
            '  "subject_description": "<one phrase>",\n'
            '  "has_female": <bool>,\n'
            '  "has_monster": <bool>,\n'
            '  "has_ui": <bool>,\n'
            '  "has_reward": <bool>,\n'
            '  "has_coins": <bool>,\n'
            '  "has_chest": <bool>,\n'
            '  "has_arrow": <bool>,\n'
            '  "has_before_after": <bool>,\n'
            '  "has_explosion": <bool>,\n'
            '  "has_highlight": <bool>,\n'
            '  "has_finger_guide": <bool>,\n'
            '  "has_number": <bool>,\n'
            '  "has_text": <bool>,\n'
            '  "has_cta": <bool>,\n'
            '  "primary_color": "<main color>",\n'
            '  "secondary_color": "<accent color>",\n'
            '  "warm_cool": "warm|cool|neutral",\n'
            '  "symmetry": <bool>,\n'
            '  "golden_ratio": <bool>,\n'
            '  "left_right_layout": <bool>,\n'
            '  "top_bottom_layout": <bool>,\n'
            '  "center_layout": <bool>,\n'
            '  "has_merge": <bool>,\n'
            '  "has_level": <bool>,\n'
            '  "has_inventory": <bool>,\n'
            '  "has_collection": <bool>,\n'
            '  "has_progress": <bool>,\n'
            '  "overlay_text": "<exact text overlay, empty if none>",\n'
            '  "ocr_title": "<main title text>",\n'
            '  "ocr_numbers": ["<numbers visible>"],\n'
            '  "ocr_cta": "<CTA button text>",\n'
            '  "ocr_keywords": ["<key phrases>"],\n'
            '  "hook_type": "crisis|reward|twist|comparison|curiosity|collection|progress|mystery|other",\n'
            '  "emotion_surprise": <bool>,\n'
            '  "emotion_failure": <bool>,\n'
            '  "emotion_success": <bool>,\n'
            '  "emotion_reward": <bool>,\n'
            '  "emotion_tension": <bool>,\n'
            '  "emotion_satisfaction": <bool>,\n'
            '  "mood": "<emotional tone>"\n'
            "}\n"
        ) + (f"Project context: {project}.\n" if project else "")

    # ==================== 本地视觉分析 ====================

    def _extract_local(self, image_path: str) -> dict[str, Any]:
        """用Pillow+NumPy提取客观视觉特征"""
        img = Image.open(image_path).convert("RGB")
        img_small = img.resize((100, 100))
        pixels = np.array(img_small).reshape(-1, 3).astype(float)

        # --- 颜色分析 ---
        color_data = self._analyze_colors(pixels)

        # --- 构图分析 ---
        comp_data = self._analyze_composition(img)

        return {
            "color": color_data,
            "composition": comp_data,
        }

    def _analyze_colors(self, pixels: np.ndarray) -> dict[str, Any]:
        """颜色分布分析"""
        colors = []
        for r, g, b in pixels:
            if r > 150 and g > 150 and b > 150:
                colors.append("white")
            elif r < 60 and g < 60 and b < 60:
                colors.append("black")
            elif r > 150 and g < 100 and b < 100:
                colors.append("red")
            elif r > 150 and g > 150 and b < 100:
                colors.append("yellow")
            elif r < 100 and g > 150 and b < 100:
                colors.append("green")
            elif r < 100 and g < 100 and b > 150:
                colors.append("blue")
            elif r > 100 and g < 150 and b > 150:
                colors.append("purple")
            elif r > 200 and g > 150 and b > 150:
                colors.append("pink")
            elif r > 150 and g > 100 and b < 100:
                colors.append("orange")
            elif r > 100 and g > 80 and b < 80:
                colors.append("brown")
            else:
                colors.append("gray")

        from collections import Counter
        counter = Counter(colors)
        total = len(colors)
        distribution = {k: round(v / total * 100, 1) for k, v in counter.most_common(5)}

        primary = counter.most_common(1)[0][0] if counter else "gray"
        secondary = counter.most_common(2)[1][0] if len(counter) > 1 else primary

        # 冷暖色判断
        r_mean = pixels[:, 0].mean()
        b_mean = pixels[:, 2].mean()
        if r_mean > b_mean + 15:
            warm_cool = "warm"
        elif b_mean > r_mean + 15:
            warm_cool = "cool"
        else:
            warm_cool = "neutral"

        # 亮度
        brightness = float(pixels.mean(axis=1).mean()) / 255

        # 饱和度
        max_rgb = pixels.max(axis=1)
        min_rgb = pixels.min(axis=1)
        saturation = float(np.where(max_rgb > 0, (max_rgb - min_rgb) / max_rgb, 0).mean())

        return {
            "primary_color": primary,
            "secondary_color": secondary,
            "warm_cool": warm_cool,
            "saturation": round(saturation, 2),
            "brightness": round(brightness, 2),
            "color_distribution": distribution,
        }

    def _analyze_composition(self, img: Image.Image) -> dict[str, Any]:
        """9宫格构图分析"""
        w, h = img.size
        img_small = img.resize((90, 90))
        arr = np.array(img_small).astype(float)

        # 9宫格对比度
        grid_scores = []
        for i in range(3):
            for j in range(3):
                block = arr[i*30:(i+1)*30, j*30:(j+1)*30]
                contrast = float(block.std())
                grid_scores.append({"grid": f"{i+1}{j+1}", "contrast": round(contrast, 1)})

        top = max(grid_scores, key=lambda x: x["contrast"])

        # 对称性检测(左右翻转差异)
        left = arr[:, :45]
        right = arr[:, 45:]
        right_flip = right[:, ::-1]
        symmetry_diff = float(np.abs(left - right_flip).mean())
        symmetry = symmetry_diff < 20

        # 中心布局(中心区域亮度高于边缘)
        center = arr[30:60, 30:60]
        edge = np.concatenate([arr[:30].flatten(), arr[60:].flatten()])
        center_layout = float(center.mean()) > float(edge.mean()) + 5

        # 左右布局(左右两半差异大)
        left_half = arr[:, :45]
        right_half = arr[:, 45:]
        lr_diff = float(np.abs(left_half.mean() - right_half.mean()))
        left_right_layout = lr_diff > 20

        return {
            "symmetry": symmetry,
            "golden_ratio": False,  # 需要更复杂的分析,暂不实现
            "left_right_layout": left_right_layout,
            "top_bottom_layout": False,  # 同上
            "center_layout": center_layout,
            "focus_grid": top["grid"],
            "focus_contrast": top["contrast"],
        }

    # ==================== 数据融合 ====================

    def _merge_lovart_data(self, feature: CreativeFeature, data: dict[str, Any]) -> None:
        """将Lovart describe_image返回的visual DNA映射到CreativeFeature

        describe_image返回字段: subject, composition, palette, lighting,
        ui_elements, overlay_text, cta_style, character_pose, mood,
        hook_type, standout_features, overall_summary
        """
        # 主体 - 从subject字段推断
        subject_text = data.get("subject", "")
        feature.subject = SubjectFeatures(
            subject_type=self._infer_subject_type(subject_text, data),
            subject_count=self._count_subjects(subject_text, data),
            character_count=1 if "witch" in subject_text.lower() or "character" in subject_text.lower() else 0,
            subject_description=subject_text,
        )

        # 视觉标记 - 从描述和ui_elements推断
        ui_elements = data.get("ui_elements", [])
        ui_text = " ".join(str(e) for e in ui_elements).lower() if ui_elements else ""
        all_text = f"{subject_text} {data.get('composition','')} {data.get('standout_features','')} {ui_text}".lower()

        feature.visual_flags = VisualFlags(
            has_female=any(k in all_text for k in ["witch", "woman", "female", "girl", "queen", "princess"]),
            has_monster=any(k in all_text for k in ["monster", "dragon", "creature", "beast", "demon"]),
            has_ui=bool(ui_elements),
            has_reward=any(k in all_text for k in ["reward", "bonus", "prize"]),
            has_coins=any(k in all_text for k in ["coin", "gold", "money", "currency"]),
            has_chest=any(k in all_text for k in ["chest", "box", "treasure"]),
            has_arrow=any(k in all_text for k in ["arrow", "→", "pointer"]),
            has_before_after=any(k in all_text for k in ["before", "after", "vs", "comparison"]),
            has_explosion=any(k in all_text for k in ["explosion", "burst", "blast", "boom"]),
            has_highlight=any(k in all_text for k in ["highlight", "glow", "shine", "glowing"]),
            has_finger_guide=any(k in all_text for k in ["finger", "hand", "pointing"]),
            has_number=any(c.isdigit() for c in all_text),
            has_text=bool(data.get("overlay_text", "")),
            has_cta=bool(data.get("cta_style", "")),
        )

        # 颜色 - Lovart的palette是描述性文本,保留作为补充
        if not feature.color.primary_color:
            palette = data.get("palette", "")
            feature.color = ColorFeatures(
                primary_color=self._extract_color_from_palette(palette),
                secondary_color="",
                warm_cool=self._infer_warm_cool(palette),
            )

        # 构图 - 从composition字段推断
        comp_text = data.get("composition", "").lower()
        feature.composition.symmetry = "symmetric" in comp_text or "symmetry" in comp_text
        feature.composition.left_right_layout = any(k in comp_text for k in ["split", "left", "right", "side"])
        feature.composition.top_bottom_layout = any(k in comp_text for k in ["top", "bottom", "vertical"])
        feature.composition.center_layout = any(k in comp_text for k in ["centered", "center", "hero"])

        # 游戏元素 - 从ui_elements和subject推断
        feature.game_elements = GameElements(
            has_merge=any("merge" in str(e).lower() for e in ui_elements) or "merge" in all_text,
            has_level=any(k in all_text for k in ["level", "lv", "tier", "progression"]),
            has_reward=any(k in all_text for k in ["reward", "bonus", "prize"]),
            has_inventory=any(k in all_text for k in ["inventory", "collection", "slot"]),
            has_collection=any(k in all_text for k in ["collect", "collection"]),
            has_progress=any(k in all_text for k in ["progress", "evolution", "upgrade", "growth"]),
        )

        # 文案
        feature.copy = CopyFeatures(
            ocr_title="",
            ocr_numbers=[],
            ocr_cta=data.get("cta_style", ""),
            ocr_keywords=data.get("standout_features", []) if isinstance(data.get("standout_features"), list) else [],
            overlay_text=data.get("overlay_text", ""),
        )

        # 心理
        mood_text = data.get("mood", "").lower()
        feature.psychology = PsychologicalFeatures(
            hook_type=data.get("hook_type", ""),
            emotion_surprise=any(k in mood_text for k in ["surprise", "shock", "wow"]),
            emotion_failure=any(k in mood_text for k in ["fail", "loss", "defeat"]),
            emotion_success=any(k in mood_text for k in ["success", "win", "victory", "empowering"]),
            emotion_reward=any(k in mood_text for k in ["reward", "satisfying", "satisfaction"]),
            emotion_tension=any(k in mood_text for k in ["tension", "urgent", "crisis", "intense"]),
            emotion_satisfaction=any(k in mood_text for k in ["satisfying", "satisfaction", "fulfill"]),
            mood=data.get("mood", ""),
        )

    def _infer_subject_type(self, subject: str, data: dict) -> str:
        """从subject描述推断主体类型"""
        s = subject.lower()
        if any(k in s for k in ["witch", "character", "girl", "woman", "queen", "hero"]):
            return "character"
        if any(k in s for k in ["dragon", "monster", "creature", "beast"]):
            return "creature"
        if any(k in s for k in ["scene", "landscape", "environment", "castle", "building"]):
            return "scene"
        if any(k in s for k in ["ui", "menu", "board", "gameplay"]):
            return "ui"
        return "object"

    def _count_subjects(self, subject: str, data: dict) -> int:
        """估算主体数量"""
        ui = data.get("ui_elements", [])
        count = 1
        if isinstance(ui, list):
            count = max(count, len(ui))
        return count

    def _extract_color_from_palette(self, palette: str) -> str:
        """从palette描述提取主色"""
        p = palette.lower()
        if "purple" in p or "violet" in p: return "purple"
        if "blue" in p: return "blue"
        if "black" in p or "dark" in p: return "black"
        if "white" in p or "light" in p: return "white"
        if "red" in p: return "red"
        if "yellow" in p or "gold" in p: return "yellow"
        if "green" in p: return "green"
        if "pink" in p or "magenta" in p: return "pink"
        return "gray"

    def _infer_warm_cool(self, palette: str) -> str:
        """从palette推断冷暖色"""
        p = palette.lower()
        warm = any(k in p for k in ["red", "orange", "yellow", "gold", "amber", "warm"])
        cool = any(k in p for k in ["blue", "purple", "violet", "cool", "dark"])
        if warm and not cool: return "warm"
        if cool and not warm: return "cool"
        return "neutral"

    def _infer_flags_from_description(self, feature: CreativeFeature) -> None:
        """从Lovart的subject_description/mood推断额外标记"""
        text = f"{feature.subject.subject_description} {feature.psychology.mood} {feature.copy.overlay_text}".lower()

        # 如果Lovart没返回has_coins但描述提到coin/gold
        if not feature.visual_flags.has_coins and any(k in text for k in ["coin", "gold", "money"]):
            feature.visual_flags.has_coins = True
        if not feature.visual_flags.has_chest and "chest" in text:
            feature.visual_flags.has_chest = True
        if not feature.visual_flags.has_arrow and "arrow" in text:
            feature.visual_flags.has_arrow = True
        if not feature.game_elements.has_merge and "merge" in text:
            feature.game_elements.has_merge = True
        if not feature.game_elements.has_level and any(k in text for k in ["level", "lv", "tier"]):
            feature.game_elements.has_level = True

    # ==================== 缓存 ====================

    def _cache_key(self, image_path: Path, creative_id: str) -> str:
        """基于文件内容+creative_id生成缓存key"""
        stat = image_path.stat()
        raw = f"{creative_id}_{image_path.name}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def _load_cache(self, cache_key: str) -> CreativeFeature | None:
        cache_file = CACHE_DIR / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return self._dict_to_feature(data)
        except Exception:
            return None

    def _save_cache(self, cache_key: str, feature: CreativeFeature) -> None:
        cache_file = CACHE_DIR / f"{cache_key}.json"
        cache_file.write_text(
            json.dumps(feature.to_json(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _dict_to_feature(self, data: dict[str, Any]) -> CreativeFeature:
        """从dict重建CreativeFeature"""
        f = CreativeFeature(
            creative_id=data.get("creative_id", ""),
            project=data.get("project", ""),
            campaign=data.get("campaign", ""),
            adset=data.get("adset", ""),
            image_path=data.get("image_path", ""),
            analyzed_at=data.get("analyzed_at", ""),
            analyzer_version=data.get("analyzer_version", ""),
            source=data.get("source", ""),
        )
        f.subject = SubjectFeatures(**data.get("subject", {}))
        f.visual_flags = VisualFlags(**data.get("visual_flags", {}))
        if "color" in data:
            cd = data["color"]
            cd.pop("color_distribution", None)  # 可能不是简单类型
            f.color = ColorFeatures(**cd)
        f.composition = CompositionFeatures(**data.get("composition", {}))
        f.game_elements = GameElements(**data.get("game_elements", {}))
        f.copy = CopyFeatures(**data.get("copy", {}))
        f.psychology = PsychologicalFeatures(**data.get("psychology", {}))
        return f
