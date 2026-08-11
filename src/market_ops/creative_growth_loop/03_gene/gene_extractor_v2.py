"""Gene Extractor V2 - Inference-centric DNA Extraction

从图片中提取 Creative DNA V2，包含：
  - mechanism_type（机制类型）
  - reward_type（奖励类型）
  - hook_type（钩子类型）
  - layout_template（布局模板）
  - visual_hierarchy（视觉层级）
  - psychology_drive（心理驱动）

不再是元素清单，而是结构化的创意决策模型。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from market_ops.clients.lovart import LovartClient

from .creative_dna_v2 import (
    CreativeDNAV2,
    VisualHierarchySpec,
    MECHANISM_TYPES,
    REWARD_TYPES,
    HOOK_TYPES,
    LAYOUT_TEMPLATES,
)
from .template_library import TemplateLibrary


MECHANISM_KEYWORDS = {
    "merge": ["merge", "combine", "fuse", "blend", "合成", "合并", "融合", "+ =", "A + B", "formula"],
    "evolution": ["evolution", "evolve", "upgrade", "level up", "进化", "升级", "等级", "lv.", "stage", "tier"],
    "collection": ["collect", "collection", "gather", "收集", "收藏", "图鉴", "all", "complete set"],
    "progression_chain": ["chain", "progression", "path", "journey", "链条", "路径", "成长线", "1→2→3", "to max"],
    "transformation": ["transform", "transformation", "before after", "change", "变形", "变身", "前后对比", "before/after"],
    "comparison": ["compare", "comparison", "vs", "versus", "对比", "比较"],
}

REWARD_KEYWORDS = {
    "transformation": ["transform", "new form", "evolve", "变形", "变身", "新形态", "进化体"],
    "collection": ["complete", "full set", "all", "收集完成", "全套", "图鉴满"],
    "unlock": ["unlock", "secret", "hidden", "reveal", "解锁", "秘密", "隐藏", "揭开"],
    "upgrade": ["upgrade", "enhance", "power up", "升级", "强化", "加成", "boost"],
    "discovery": ["discover", "find", "mystery", "发现", "探索", "神秘"],
    "power_up": ["power", "stronger", "powerful", "boost", "能量", "强力", "爆发"],
    "legendary_item": ["legendary", "mythic", "epic", "rare", "传奇", "神话", "史诗", "稀有"],
}

HOOK_KEYWORDS = {
    "collection": ["collect", "all", "complete", "收集", "全部", "集齐"],
    "transformation": ["transform", "before after", "change", "变形", "变身", "前后"],
    "challenge": ["challenge", "can you", "test", "挑战", "你能", "试试"],
    "secret": ["secret", "hidden", "mystery", "秘密", "隐藏", "神秘"],
    "curiosity": ["curious", "wonder", "what if", "好奇", "猜猜", "如果"],
    "progression": ["level up", "upgrade", "grow", "升级", "成长", "进步"],
    "achievement": ["achievement", "unlock", "complete", "成就", "达成", "完成"],
}

TEMPLATE_DETECTION_RULES = [
    {
        "template_id": "merge_formula",
        "indicators": ["A + B", "plus sign", "equals", "formula", "merge two", "合成公式", "加号", "等于"],
        "mechanism": "merge",
    },
    {
        "template_id": "evolution_chain",
        "indicators": ["evolution", "stage 1", "stage 2", "chain", "progression", "进化链", "阶段", "成长", "1→2→3"],
        "mechanism": "evolution",
    },
    {
        "template_id": "before_after",
        "indicators": ["before after", "before/after", "split screen", "transformation", "前后对比", "分屏", "左右对比"],
        "mechanism": "transformation",
    },
]


@dataclass
class ExtractionResult:
    dna: CreativeDNAV2
    raw_analysis: Dict[str, Any]
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dna": self.dna.to_dict(),
            "raw_analysis": self.raw_analysis,
            "confidence": self.confidence,
        }


class GeneExtractorV2:
    def __init__(self, output_dir: str = "memory/creative_dna_v2"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lovart_client = LovartClient()
    
    def extract_dna(self, image_path: str, creative_id: str = None) -> ExtractionResult:
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        creative_id = creative_id or image_path.stem
        
        try:
            visual_analysis = self._analyze_image(str(image_path))
            dna = self._build_dna_from_analysis(visual_analysis, creative_id)
            confidence = self._calculate_confidence(visual_analysis, dna)
        except Exception as e:
            print(f"V2 extraction failed, using fallback: {e}")
            dna = self._fallback_dna(creative_id)
            visual_analysis = {"error": str(e), "fallback": True}
            confidence = 0.3
        
        self._save_dna(dna, visual_analysis, confidence)
        return ExtractionResult(dna=dna, raw_analysis=visual_analysis, confidence=confidence)
    
    def _analyze_image(self, image_path: str) -> Dict[str, Any]:
        result = self.lovart_client.describe_image(image_path)
        return result if isinstance(result, dict) else {"visual_dna": result}
    
    def _build_dna_from_analysis(self, analysis: Dict[str, Any], creative_id: str) -> CreativeDNAV2:
        dna = CreativeDNAV2(dna_id=f"dna_v2_{creative_id}_{uuid.uuid4().hex[:8]}")
        
        description = self._get_full_description(analysis)
        
        dna.mechanism_type = self._detect_mechanism_type(description, analysis)
        dna.reward_type = self._detect_reward_type(description, analysis)
        dna.hook_type = self._detect_hook_type(description, analysis)
        dna.layout_template = self._detect_template(description, analysis)
        dna.visual_hierarchy = self._extract_visual_hierarchy(description, analysis, dna.layout_template)
        dna.psychology_drive = self._detect_psychology_drives(dna, description)
        dna.user_role_mapping = self._detect_user_role(dna, description)
        
        template = TemplateLibrary.get(dna.layout_template)
        if template:
            if not dna.mechanism_type:
                dna.mechanism_type = template.mechanism_type
            if not dna.attention_goal:
                dna.attention_goal = template.attention_goal
            if not dna.psychology_drive:
                dna.psychology_drive = template.psychology_drives.copy()
        
        dna.source_creative_id = creative_id
        
        return dna
    
    def _get_full_description(self, analysis: Dict[str, Any]) -> str:
        parts = []
        
        if "visual_dna" in analysis:
            vd = analysis["visual_dna"]
            if isinstance(vd, dict):
                for key in ["subject", "composition", "style", "mood", "overlay_text", "description"]:
                    if key in vd:
                        parts.append(str(vd[key]))
            elif isinstance(vd, str):
                parts.append(vd)
        
        for key in ["description", "caption", "detailed_description", "analysis"]:
            if key in analysis:
                parts.append(str(analysis[key]))
        
        return " ".join(parts).lower()
    
    def _detect_mechanism_type(self, description: str, analysis: Dict[str, Any]) -> str:
        scores = {}
        
        for mech_type, keywords in MECHANISM_KEYWORDS.items():
            score = 0
            for kw in keywords:
                if kw.lower() in description:
                    score += 1
            scores[mech_type] = score
        
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]
        
        if "mechanism_type" in analysis:
            mech = analysis["mechanism_type"]
            if mech in MECHANISM_TYPES:
                return mech
        
        return "merge"
    
    def _detect_reward_type(self, description: str, analysis: Dict[str, Any]) -> str:
        scores = {}
        
        for reward_type, keywords in REWARD_KEYWORDS.items():
            score = 0
            for kw in keywords:
                if kw.lower() in description:
                    score += 1
            scores[reward_type] = score
        
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]
        
        if "reward_type" in analysis:
            rt = analysis["reward_type"]
            if rt in REWARD_TYPES:
                return rt
        
        return "transformation"
    
    def _detect_hook_type(self, description: str, analysis: Dict[str, Any]) -> str:
        scores = {}
        
        for hook_type, keywords in HOOK_KEYWORDS.items():
            score = 0
            for kw in keywords:
                if kw.lower() in description:
                    score += 1
            scores[hook_type] = score
        
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]
        
        if "hook_type" in analysis:
            ht = analysis["hook_type"]
            if ht in HOOK_TYPES:
                return ht
        
        return "curiosity"
    
    def _detect_template(self, description: str, analysis: Dict[str, Any]) -> str:
        scores = {}
        
        for rule in TEMPLATE_DETECTION_RULES:
            score = 0
            for indicator in rule["indicators"]:
                if indicator.lower() in description:
                    score += 1
            scores[rule["template_id"]] = score
        
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]
        
        if "layout_template" in analysis:
            lt = analysis["layout_template"]
            if lt in LAYOUT_TEMPLATES:
                return lt
        
        return "merge_formula"
    
    def _extract_visual_hierarchy(self, description: str, analysis: Dict[str, Any],
                                   template_id: str) -> VisualHierarchySpec:
        template = TemplateLibrary.get(template_id)
        if template:
            return VisualHierarchySpec(**template.visual_hierarchy.to_dict())
        
        hierarchy = VisualHierarchySpec()
        
        if "visual_hierarchy" in analysis:
            vh = analysis["visual_hierarchy"]
            if isinstance(vh, dict):
                hierarchy.level1 = vh.get("level1", "reward")
                hierarchy.level2 = vh.get("level2", "mechanism")
                hierarchy.level3 = vh.get("level3", "character")
                hierarchy.level4 = vh.get("level4", "ui_cta")
                return hierarchy
        
        hierarchy.level1 = "reward"
        hierarchy.level2 = "mechanism"
        hierarchy.level3 = "brand_character"
        hierarchy.level4 = "ui_cta"
        
        return hierarchy
    
    def _detect_psychology_drives(self, dna: CreativeDNAV2, description: str) -> List[str]:
        drives = []
        
        if dna.reward_type in ["transformation", "upgrade", "power_up"]:
            drives.append("reward_anticipation")
        if dna.mechanism_type in ["collection", "progression_chain"]:
            drives.append("collection_motivation")
            drives.append("completion_bias")
        if dna.hook_type in ["secret", "curiosity"]:
            drives.append("curiosity_gap")
        if dna.mechanism_type in ["merge", "evolution"]:
            drives.append("self_projection")
            drives.append("progress_satisfaction")
        if dna.reward_type == "legendary_item":
            drives.append("fantasy_appeal")
        
        if not drives:
            drives = ["reward_anticipation", "curiosity_gap"]
        
        return list(set(drives))
    
    def _detect_user_role(self, dna: CreativeDNAV2, description: str) -> str:
        if dna.mechanism_type == "merge":
            return "player_who_merges"
        elif dna.mechanism_type == "evolution":
            return "player_who_evolves"
        elif dna.mechanism_type == "collection":
            return "collector"
        elif dna.mechanism_type == "transformation":
            return "transformer"
        else:
            return "player_who_merges"
    
    def _calculate_confidence(self, analysis: Dict[str, Any], dna: CreativeDNAV2) -> float:
        score = 0.5
        
        if dna.mechanism_type and dna.mechanism_type != "unknown":
            score += 0.1
        if dna.reward_type and dna.reward_type != "unknown":
            score += 0.1
        if dna.layout_template and dna.layout_template != "unknown":
            score += 0.15
        if dna.psychology_drive:
            score += 0.05
        if "visual_dna" in analysis and isinstance(analysis["visual_dna"], dict):
            score += 0.1
        
        return min(1.0, score)
    
    def _fallback_dna(self, creative_id: str) -> CreativeDNAV2:
        dna = CreativeDNAV2(
            dna_id=f"dna_v2_{creative_id}_fallback",
            mechanism_type="merge",
            reward_type="transformation",
            hook_type="curiosity",
            layout_template="merge_formula",
            attention_goal="reward_first",
            psychology_drive=["reward_anticipation", "curiosity_gap"],
            user_role_mapping="player_who_merges",
            source_creative_id=creative_id,
        )
        dna.visual_hierarchy = VisualHierarchySpec(
            level1="result_c",
            level2="merge_process",
            level3="character_hands",
            level4="cta_banner",
        )
        return dna
    
    def _save_dna(self, dna: CreativeDNAV2, analysis: Dict[str, Any], confidence: float) -> Path:
        output_path = self.output_dir / f"{dna.source_creative_id}_dna_v2.json"
        
        data = {
            "dna": dna.to_dict(),
            "raw_analysis": analysis,
            "confidence": confidence,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def load_dna(self, creative_id: str) -> Optional[CreativeDNAV2]:
        dna_path = self.output_dir / f"{creative_id}_dna_v2.json"
        
        if dna_path.exists():
            with open(dna_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                dna_data = data.get("dna", data)
                dna = CreativeDNAV2(
                    dna_id=dna_data.get("dna_id", ""),
                    mechanism_type=dna_data.get("mechanism_type", ""),
                    reward_type=dna_data.get("reward_type", ""),
                    hook_type=dna_data.get("hook_type", ""),
                    layout_template=dna_data.get("layout_template", ""),
                    attention_goal=dna_data.get("attention_goal", "reward_first"),
                    psychology_drive=dna_data.get("psychology_drive", []),
                    mechanism_visibility_score=dna_data.get("mechanism_visibility_score", 0.0),
                    reward_salience_score=dna_data.get("reward_salience_score", 0.0),
                    identity_projection_score=dna_data.get("identity_projection_score", 0.0),
                    visual_hierarchy_match=dna_data.get("visual_hierarchy_match", 0.0),
                    scroll_stop_score=dna_data.get("scroll_stop_score", 0.0),
                    total_score=dna_data.get("total_score", 0.0),
                    is_rejected=dna_data.get("is_rejected", False),
                    reject_reasons=dna_data.get("reject_reasons", []),
                    user_role_mapping=dna_data.get("user_role_mapping", "player_who_merges"),
                    source_creative_id=dna_data.get("source_creative_id", ""),
                )
                vh = dna_data.get("visual_hierarchy", {})
                dna.visual_hierarchy = VisualHierarchySpec(
                    level1=vh.get("level1", ""),
                    level2=vh.get("level2", ""),
                    level3=vh.get("level3", ""),
                    level4=vh.get("level4", ""),
                )
                return dna
        
        return None
    
    def extract_batch(self, image_paths: List[str]) -> List[ExtractionResult]:
        results = []
        
        for path in image_paths:
            try:
                result = self.extract_dna(path)
                results.append(result)
            except Exception as e:
                print(f"Failed to extract DNA from {path}: {e}")
        
        return results
