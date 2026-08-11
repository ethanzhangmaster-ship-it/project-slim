from .base_scorer import BaseScorer, ScoreResult
from ..config import RankingConfig


class ReadabilityScorer(BaseScorer):
    """Visual Readability - Facebook Feed中是否容易识别

    逻辑：
    - 主体是否居中
    - 背景是否太复杂（边缘密度）
    - 主体是否突出（对比度）
    - 文字是否过多
    - 颜色是否干净（色彩熵）
    - 是否符合安全区域（CTA不被遮挡）

    评分因素：
    - centered composition: +15
    - simple background: +15
    - high contrast: +15
    - subject 40-70% coverage: +20
    - minimal text: +15
    - clean color palette: +10
    - 9:16 format: +10
    """

    name = "Visual Readability"
    weight_key = "visual_readability"

    def score(
        self,
        variant_dna: dict,
        base_dna: dict | None = None,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        config = RankingConfig()
        constraints = config.fb_constraints

        breakdown = {}
        recommendations = []
        risks = []
        total_score = 0.0

        # 1. 居中构图 (0-15分)
        subject_position = self._safe_get(
            variant_dna, ["composition", "subject_position"], default=""
        )
        composition_layout = self._safe_get(
            variant_dna, ["composition", "layout"], default=""
        )
        camera_composition = self._safe_get(
            variant_dna, ["camera", "composition_rule"], default=""
        )
        pos_str = str(subject_position).lower()
        layout_str = str(composition_layout).lower()
        camera_str = str(camera_composition).lower()

        centered_keywords = ["center", "居中", "central", "middle", "对称", "symmetry"]
        is_centered = any(kw in pos_str for kw in centered_keywords) or \
                      any(kw in layout_str for kw in centered_keywords) or \
                      any(kw in camera_str for kw in centered_keywords)

        if is_centered:
            centered_score = 15.0
            recommendations.append("主体居中构图，在Feed流中易于快速识别")
        elif subject_position or composition_layout:
            centered_score = 8.0
            risks.append("主体未居中，在小屏幕上可能被忽略")
        else:
            centered_score = 5.0
            risks.append("缺少构图位置信息，建议采用居中或对称构图")

        breakdown["centered_composition"] = {
            "score": round(centered_score, 1),
            "subject_position": subject_position,
            "composition_layout": composition_layout,
        }
        total_score += centered_score

        # 2. 背景简洁度 (0-15分)
        edge_density = self._safe_get(
            variant_dna, ["video_analysis", "edge_density"], default=None
        )
        if edge_density is None and fb_meta:
            edge_density = fb_meta.get("edge_density")
        if edge_density is None:
            # 从环境元素数量推断
            env_elements = self._safe_get(
                variant_dna, ["environment", "elements"], default=[]
            )
            bg_elements = self._safe_get(
                variant_dna, ["composition", "background"], default=[]
            )
            total_elements = len(env_elements) + len(bg_elements)
            if total_elements <= 2:
                edge_density = 0.15
            elif total_elements <= 5:
                edge_density = 0.35
            else:
                edge_density = 0.60

        # edge_density 越低背景越简洁
        if edge_density <= 0.20:
            bg_score = 15.0
            recommendations.append("背景简洁干净，主体非常突出")
        elif edge_density <= 0.40:
            bg_score = 15.0 - (edge_density - 0.20) / 0.20 * 5.0
            recommendations.append("背景复杂度适中")
        elif edge_density <= 0.60:
            bg_score = 10.0 - (edge_density - 0.40) / 0.20 * 5.0
            risks.append("背景略显复杂，可能分散对主体的注意力")
        else:
            bg_score = max(0.0, 5.0 - (edge_density - 0.60) / 0.40 * 5.0)
            risks.append("背景过于复杂（边缘密度高），在移动端小屏幕上显得杂乱")

        breakdown["simple_background"] = {
            "score": round(bg_score, 1),
            "edge_density": edge_density,
        }
        total_score += bg_score

        # 3. 高对比度 (0-15分)
        contrast = self._safe_get(variant_dna, ["lighting", "contrast"], default=None)
        if contrast is None and fb_meta:
            contrast = fb_meta.get("contrast")
        if contrast is None:
            contrast = self._safe_get(variant_dna, ["video_analysis", "contrast"], default=3.0)

        min_contrast = constraints.get("min_contrast_ratio", 3.0)
        if contrast >= min_contrast * 1.5:
            contrast_score = 15.0
            recommendations.append("对比度极高，主体与背景分离清晰")
        elif contrast >= min_contrast:
            contrast_score = 12.0
            recommendations.append("对比度满足可读性要求")
        elif contrast >= min_contrast * 0.6:
            contrast_score = max(0.0, contrast / min_contrast * 12.0)
            risks.append("对比度一般，主体边界可能不够清晰")
        else:
            contrast_score = max(0.0, contrast / min_contrast * 12.0)
            risks.append("对比度不足，主体可能融入背景导致识别困难")

        breakdown["high_contrast"] = {
            "score": round(contrast_score, 1),
            "value": contrast,
            "min_required": min_contrast,
        }
        total_score += contrast_score

        # 4. 主体覆盖率 (0-20分)
        subject_coverage = self._safe_get(
            variant_dna, ["composition", "subject_coverage"], default=None
        )
        if subject_coverage is None and fb_meta:
            subject_coverage = fb_meta.get("subject_coverage")
        if subject_coverage is None:
            subject_coverage = 0.55

        min_cov = constraints.get("min_subject_coverage", 0.40)
        max_cov = constraints.get("max_subject_coverage", 0.70)
        ideal_mid = (min_cov + max_cov) / 2  # 0.55

        if min_cov <= subject_coverage <= max_cov:
            # 越接近0.55分数越高
            deviation = abs(subject_coverage - ideal_mid) / (max_cov - ideal_mid)
            coverage_score = 20.0 - deviation * 4.0  # 18-20分
            recommendations.append(f"主体占比{subject_coverage:.0%}，在Feed中识别度最佳")
        elif subject_coverage < min_cov:
            coverage_score = max(0.0, subject_coverage / min_cov * 15.0)
            risks.append(f"主体占比仅{subject_coverage:.0%}，在缩略图中难以辨认")
        else:
            coverage_score = max(0.0, (1.0 - subject_coverage) / (1.0 - max_cov) * 15.0)
            risks.append(f"主体占比高达{subject_coverage:.0%}，画面拥挤缺少呼吸感")

        breakdown["subject_coverage"] = {
            "score": round(coverage_score, 1),
            "value": subject_coverage,
            "ideal_range": f"{min_cov:.0%}-{max_cov:.0%}",
        }
        total_score += coverage_score

        # 5. 文字数量 (0-15分)
        headline = ""
        text_words = 0
        if fb_meta:
            headline = str(fb_meta.get("headline", ""))
            text_words = len(headline.split()) if headline else 0
        if text_words == 0:
            # 从DNA中检查是否有文字叠加
            text_overlay = self._safe_get(variant_dna, ["fb_meta", "headline"], default="")
            if text_overlay:
                text_words = len(str(text_overlay).split())

        max_words = constraints.get("max_text_overlay_words", 5)
        if text_words == 0:
            text_score = 15.0
            recommendations.append("无文字叠加，画面干净纯粹")
        elif text_words <= max_words:
            text_score = 15.0 - (text_words / max_words) * 3.0
            recommendations.append(f"文字数量适中（{text_words}词），不影响视觉识别")
        elif text_words <= max_words * 2:
            text_score = 12.0 - ((text_words - max_words) / max_words) * 6.0
            risks.append(f"文字较多（{text_words}词），可能遮挡主体或显得拥挤")
        else:
            text_score = max(0.0, 6.0 - ((text_words - max_words * 2) / max_words) * 6.0)
            risks.append(f"文字过多（{text_words}词），严重影响Feed中的视觉识别")

        breakdown["minimal_text"] = {
            "score": round(text_score, 1),
            "word_count": text_words,
            "max_recommended": max_words,
            "headline_preview": headline[:30] if headline else "",
        }
        total_score += text_score

        # 6. 干净色板 (0-10分)
        dominant_colors = self._safe_get(variant_dna, ["colors", "dominant"], default=[])
        accent_colors = self._safe_get(variant_dna, ["colors", "accent"], default=[])
        total_color_count = len(dominant_colors) + len(accent_colors)

        if total_color_count == 0:
            # 从 mood_palette 推断
            mood_palette = self._safe_get(variant_dna, ["colors", "mood_palette"], default=[])
            total_color_count = len(mood_palette)

        if total_color_count <= 3:
            palette_score = 10.0
            recommendations.append("色板干净简洁，色彩记忆点清晰")
        elif total_color_count <= 5:
            palette_score = 8.0 - (total_color_count - 3) * 1.0
            recommendations.append("色彩数量适中，保持较好的视觉统一性")
        elif total_color_count <= 8:
            palette_score = 6.0 - (total_color_count - 5) * 1.0
            risks.append("色彩较多，可能削弱品牌色彩记忆点")
        else:
            palette_score = max(0.0, 3.0 - (total_color_count - 8) * 0.5)
            risks.append("色彩过于繁杂，在Feed中显得混乱且难以建立品牌认知")

        breakdown["clean_palette"] = {
            "score": round(palette_score, 1),
            "color_count": total_color_count,
            "dominant": dominant_colors[:5],
            "accent": accent_colors[:5],
        }
        total_score += palette_score

        # 7. 9:16 格式 (0-10分)
        aspect_ratio = ""
        if fb_meta:
            aspect_ratio = str(fb_meta.get("aspect_ratio", ""))
        if not aspect_ratio:
            resolution = ""
            if fb_meta:
                resolution = str(fb_meta.get("resolution", ""))
            if resolution and "x" in resolution:
                try:
                    w, h = resolution.lower().split("x")
                    w_val = int(w.strip())
                    h_val = int(h.strip())
                    ratio = h_val / w_val if w_val > 0 else 0
                    if 1.6 <= ratio <= 2.0:
                        aspect_ratio = "9:16"
                    elif 0.5 <= ratio <= 0.65:
                        aspect_ratio = "16:9"
                    else:
                        aspect_ratio = f"{w_val}:{h_val}"
                except Exception:
                    aspect_ratio = resolution

        preferred = constraints.get("preferred_aspect_ratio", "9:16")
        if aspect_ratio == preferred or aspect_ratio == "9:16":
            format_score = 10.0
            recommendations.append("9:16竖屏格式完美适配Facebook Reels/Stories")
        elif aspect_ratio in ["4:5", "3:4", "2:3"]:
            format_score = 7.0
            recommendations.append("竖屏格式适配移动端，但非最佳9:16")
        elif aspect_ratio in ["16:9", "1:1"]:
            format_score = 4.0
            risks.append("横屏或方形格式在移动端Feed中占用屏幕面积较少")
        else:
            format_score = 5.0
            if aspect_ratio:
                risks.append(f"非标准宽高比({aspect_ratio})，建议统一为9:16以最大化Feed展示面积")
            else:
                risks.append("缺少宽高比信息，建议使用9:16竖屏格式")

        breakdown["format_9_16"] = {
            "score": round(format_score, 1),
            "aspect_ratio": aspect_ratio,
            "preferred": preferred,
        }
        total_score += format_score

        final_score = max(0.0, min(100.0, total_score))

        # 根据总分给出整体建议
        if final_score >= 80:
            recommendations.insert(0, "视觉可读性优秀，在Facebook Feed中极易识别")
        elif final_score >= 60:
            recommendations.insert(0, "视觉可读性良好，基本满足Feed展示要求")
        else:
            risks.insert(0, "视觉可读性不足，在移动端Feed中可能难以被用户识别")

        return ScoreResult(
            score=round(final_score, 1),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features={
                "subject_coverage": subject_coverage,
                "edge_density": edge_density,
                "contrast": contrast,
                "text_word_count": text_words,
                "color_count": total_color_count,
                "aspect_ratio": aspect_ratio,
                "is_centered": is_centered,
            },
        )
