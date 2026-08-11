from .base_scorer import BaseScorer, ScoreResult


class AIRiskScorer(BaseScorer):
    """AI Generation Risk - AI生成失败概率评估

    注意：这个维度是"风险"，分数越高表示AI生成越容易成功
    （即风险越低 = 分数越高）

    逻辑：
    - P0变化（颜色换换）= 非常容易生成（90+）
    - P1变化（生物换换）= 容易生成（80+）
    - P2变化（角色换换）= 中等难度（60-70）
    - 手部可见 = 难生成（-15）
    - 文字在画面中 = 难生成（-10）
    - 复杂场景 = 难生成（-8）
    - 多只生物 = 稍难（-5）
    - 3D render要求 = 加分（+5，当前AI擅长）
    """

    name = "AI Generation Risk"
    weight_key = "ai_generation_risk"

    # P0 维度路径集合（低风险、高频）
    _P0_PATHS: set[str] = {
        "creatures.0.color",
        "creatures.0.glow",
        "creatures.0.action",
        "particles.0.color",
        "particles.0.type",
        "plants.0.type",
        "plants.0.glow",
        "lighting.color",
        "background.detail",
    }

    # P1 维度路径集合（中等风险）
    _P1_PATHS: set[str] = {
        "character.clothes",
        "character.pose",
        "character.gesture",
        "camera.shot_type",
        "camera.movement",
        "environment.type",
        "environment.time",
    }

    # P2 维度路径集合（高风险、低频）
    _P2_PATHS: set[str] = {
        "character.type",
        "hook.type",
        "composition.layout",
        "style.render",
    }

    # 高风险关键词（会导致AI生成困难）
    _HAND_KEYWORDS: list[str] = [
        "hand", "hands", "finger", "fingers", "palm", "fist", "grasp",
        "手", "手指", "手掌", "握拳",
    ]

    _TEXT_IN_IMAGE_KEYWORDS: list[str] = [
        "text", "word", "letter", "caption", "subtitle", "slogan",
        "文字", "字幕", "标题", "标语", "铭文", "符文"  # rune 属于世界观，不计入
    ]

    _COMPLEX_SCENE_KEYWORDS: list[str] = [
        "crowd", "battlefield", "army", "massive", "chaos", "explosion",
        "人群", "战场", "军队", "大规模", "混乱", "爆炸",
    ]

    def score(
        self,
        variant_dna: dict,
        base_dna: dict,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        """对单个 Variant 进行 AI 生成风险评分"""
        score = 100.0
        breakdown: dict[str, float] = {}
        recommendations: list[str] = []
        risks: list[str] = []

        # 1. 分析变化层级（对比 variant_dna 与 base_dna）
        changed_paths = self._get_changed_paths(variant_dna, base_dna)
        max_risk_level = self._classify_change_level(changed_paths)

        if max_risk_level == "P0":
            score = 92.0
            breakdown["change_level"] = 92.0
            recommendations.append("P0级变化（颜色/装饰等），AI生成成功率极高")
        elif max_risk_level == "P1":
            score = 82.0
            breakdown["change_level"] = 82.0
            recommendations.append("P1级变化（生物/姿态/环境等），AI生成较容易")
        elif max_risk_level == "P2":
            score = 65.0
            breakdown["change_level"] = 65.0
            risks.append("P2级变化（角色/Hook/构图/风格），AI生成难度中等")
        else:
            score = 95.0
            breakdown["change_level"] = 95.0
            recommendations.append("与Winning素材几乎一致，AI生成最稳定")

        # 2. 检查手部可见性
        subject_text = self._extract_subject_text(variant_dna)
        if self._has_any_keyword(subject_text, self._HAND_KEYWORDS):
            score -= 15.0
            breakdown["hand_visible"] = -15.0
            risks.append("画面中出现手部/手指，AI生成失败率显著上升")
        else:
            breakdown["hand_visible"] = 0.0

        # 3. 检查画面中是否有文字
        if self._has_any_keyword(subject_text, self._TEXT_IN_IMAGE_KEYWORDS):
            score -= 10.0
            breakdown["text_in_image"] = -10.0
            risks.append("画面要求包含文字/字幕，当前AI文字渲染能力较弱")
        else:
            breakdown["text_in_image"] = 0.0

        # 4. 检查复杂场景
        if self._has_any_keyword(subject_text, self._COMPLEX_SCENE_KEYWORDS):
            score -= 8.0
            breakdown["complex_scene"] = -8.0
            risks.append("复杂场景（人群/战场/大规模）会增加AI生成难度")
        else:
            breakdown["complex_scene"] = 0.0

        # 5. 检查多只生物
        creatures = variant_dna.get("creatures") or []
        if isinstance(creatures, list) and len(creatures) > 1:
            score -= 5.0
            breakdown["multiple_creatures"] = -5.0
            risks.append(f"画面中包含{len(creatures)}只生物，构图复杂度稍增")
        else:
            breakdown["multiple_creatures"] = 0.0

        # 6. 3D render 加分
        style = self._safe_get(variant_dna, ["style", "render"], "")
        if not style:
            style = self._safe_get(variant_dna, ["style"], "")
        style_str = str(style).lower()
        if "3d" in style_str or "render" in style_str or "三维" in style_str:
            score += 5.0
            breakdown["3d_render_bonus"] = 5.0
            recommendations.append("3D render风格，当前AI模型对此类风格生成效果较好")
        else:
            breakdown["3d_render_bonus"] = 0.0

        # 分数截断到 0-100
        final_score = max(0.0, min(100.0, score))
        breakdown["raw_score"] = round(score, 2)

        return ScoreResult(
            score=round(final_score, 2),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features={
                "changed_paths": changed_paths,
                "max_risk_level": max_risk_level,
                "subject_text": subject_text[:200] if subject_text else "",
            },
        )

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _get_changed_paths(self, variant_dna: dict, base_dna: dict) -> list[str]:
        """递归对比两个字典，返回发生变化的叶子节点路径（点号分隔）"""
        changed: list[str] = []
        self._diff_dict(variant_dna, base_dna, [], changed)
        return changed

    def _diff_dict(self, a: dict, b: dict, path: list[str], changed: list[str]) -> None:
        """递归对比两个字典，收集变化路径"""
        all_keys = set(a.keys()) | set(b.keys())
        for key in all_keys:
            current_path = path + [key]
            val_a = a.get(key)
            val_b = b.get(key)

            if isinstance(val_a, dict) and isinstance(val_b, dict):
                self._diff_dict(val_a, val_b, current_path, changed)
            elif isinstance(val_a, list) and isinstance(val_b, list):
                if val_a != val_b:
                    changed.append(".".join(current_path))
            elif val_a != val_b:
                changed.append(".".join(current_path))

    def _classify_change_level(self, changed_paths: list[str]) -> str:
        """根据变化路径判断最高风险等级"""
        level = "none"
        for p in changed_paths:
            # 尝试匹配已知路径
            if p in self._P2_PATHS or any(p.startswith(prefix) for prefix in self._P2_PATHS):
                return "P2"
            if p in self._P1_PATHS or any(p.startswith(prefix) for prefix in self._P1_PATHS):
                level = "P1"
            elif p in self._P0_PATHS or any(p.startswith(prefix) for prefix in self._P0_PATHS):
                if level not in ("P1", "P2"):
                    level = "P0"
        return level

    def _extract_subject_text(self, dna: dict) -> str:
        """从 DNA 中提取所有可用于关键词匹配的文本"""
        texts: list[str] = []

        for key in ("subject", "description", "standout_features"):
            val = dna.get(key)
            if isinstance(val, str):
                texts.append(val)
            elif isinstance(val, list):
                texts.extend(str(v) for v in val if v)

        # 递归收集所有字符串值
        self._collect_strings(dna, texts)
        return " ".join(texts).lower()

    def _collect_strings(self, obj: object, out: list[str]) -> None:
        """递归收集对象中所有字符串值"""
        if isinstance(obj, str):
            out.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._collect_strings(v, out)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_strings(item, out)

    def _has_any_keyword(self, text: str, keywords: list[str]) -> bool:
        """检查文本中是否包含任一关键词"""
        if not text:
            return False
        return any(kw.lower() in text for kw in keywords)
