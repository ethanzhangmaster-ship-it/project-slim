"""E9.3: IAP Creative DNA Fusion Engine — player-value-centric DNA.

Upgrades the IAA-focused DNA (CTR, ROAS, ad clicks) into IAP-focused DNA
that measures which creatives attract high-value PAYING players.

For Merge Witch (IAP product), the core question is NOT:
  "Which creative gets cheaper installs?"
But:
  "Which creative attracts users who will play for 30+ days and pay?"

IAP DNA Categories:
  - Fantasy Drive: WHY the player wants to play (rescue, collect, build, discover)
  - Progression Loop: WHAT keeps the player engaged (merge, unlock, level, collect)
  - Payment Trigger: WHY the player pays (blocked, missing piece, exclusive, time gate)
  - Retention Hook: WHY the player returns (daily reward, collection, story, event)

IAP Genome Fitness (replaces ROAS-only scoring):
  - D1/D7/D30 retention (when available)
  - Payer rate (when available)
  - D30/D90 LTV (when available)
  - ROAS as fallback proxy

Input:
  - creative_mapping_adjust_merged_v2.csv (1315 creatives with spend/revenue)
  - Merge Witch IAP keyword vocabulary

Output:
  - creative_dna_master.json (all 1315 creatives with IAP-enriched DNA)
  - IAP Genome Fitness scores
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════
# CreativeDNAV2 Vocabulary — expanded keyword sets
# ═══════════════════════════════════════════════════════════

# Mechanism types (what the player DOES)
MECHANISM_KEYWORDS: dict[str, list[str]] = {
    "merge": ["merge", "合成", "combine", "mermaid", "witch", "vampire", "dragon",
              "merging", "merged", "合并", "融合"],
    "evolution": ["evolution", "进化", "evolve", "upgrade", "升级", "transform"],
    "collection": ["collection", "收集", "collect", "gather", "album", "图鉴"],
    "progression_chain": ["progression", "chain", "连锁", "level", "关卡", "progress"],
    "transformation": ["transformation", "变形", "change", "morph", "before_after"],
    "comparison": ["comparison", "对比", "compare", "vs", "difference"],
    "sort": ["sort", "整理", "排序", "organize", "goods", "shelf", "货架", "分类"],
    "build": ["build", "home", "装修", "建造", "design", "decorate", "布置", "花园"],
    "puzzle": ["puzzle", "解谜", "escape", "谜题", "solve", "解密"],
    "rescue": ["rescue", "save", "救", "help", "rescue", "拯救", "aid"],
}

# Reward types (what the player GETS)
REWARD_KEYWORDS: dict[str, list[str]] = {
    "transformation": ["transformation", "变形", "change", "evolve", "进化", "变身"],
    "collection": ["collection", "collect", "收集", "gather", "unlock", "解锁"],
    "unlock": ["unlock", "new", "解锁", "reveal", "discover", "发现"],
    "upgrade": ["upgrade", "level up", "升级", "增强", "boost", "强化"],
    "discovery": ["discovery", "find", "找到", "探索", "adventure", "冒险"],
    "power_up": ["power", "strength", "力量", "能力", "skill", "技能"],
    "legendary_item": ["legendary", "rare", "传说", "稀有", "mythic", "神话"],
    "completion": ["complete", "finish", "完成", "clear", "通关", "win"],
    "satisfaction": ["satisfy", "爽", "satisfaction", "clean", "整齐", "neat"],
}

# Hook types (WHY user stops scrolling)
HOOK_KEYWORDS: dict[str, list[str]] = {
    "collection": ["collection", "collect", "收集", "gather", "all", "全部"],
    "transformation": ["transformation", "变形", "change", "before_after", "变身"],
    "challenge": ["challenge", "挑战", "can you", "你能", "try", "test"],
    "secret": ["secret", "秘密", "mystery", "hidden", "隐藏", "discover"],
    "curiosity": ["curiosity", "what if", "如果", "curious", "好奇", "wonder"],
    "progression": ["progression", "进度", "progress", "next", "level", "下一关"],
    "achievement": ["achievement", "成就", "achieve", "success", "win", "成功"],
    "rescue": ["rescue", "save", "救", "help", "crisis", "危机", "danger"],
    "emotional": ["magical", "adventure", "story", "journey", "魔幻", "奇幻", "故事"],
    "comparison": ["vs", "对比", "compare", "before_after", "前后", "difference"],
}

# Visual styles (the AESTHETIC)
VISUAL_KEYWORDS: dict[str, list[str]] = {
    "3d_cartoon": ["3d", "cartoon", "animated", "卡通", "blender", "c4d", "maya"],
    "2d_flat": ["2d", "flat", "vector", "平面", "illustration", "插画"],
    "realistic": ["realistic", "真实", "photo", "写实", "real", "hyper"],
    "pixel": ["pixel", "像素", "retro", "8bit", "复古"],
    "dark_fantasy": ["dark", "fantasy", "魔幻", "gothic", "暗黑", "shadow", "night"],
    "bright_casual": ["bright", "casual", "colorful", "明亮", "休闲", "fun", "happy"],
    "minimal": ["minimal", "clean", "简洁", "simple", "white", "干净"],
    "saturated": ["saturated", "vibrant", "鲜艳", "bold", "colorful", "rich"],
}

# Psychology drives (WHY user engages)
PSYCHOLOGY_KEYWORDS: dict[str, list[str]] = {
    "collection_motivation": ["collection", "collect", "收集", "gather", "complete"],
    "completion_bias": ["complete", "finish", "完成", "clear", "fill", "填满"],
    "reward_anticipation": ["reward", "anticipation", "期待", "prize", "奖励"],
    "curiosity_gap": ["curiosity", "what", "好奇", "mystery", "secret", "wonder"],
    "fantasy_appeal": ["fantasy", "magic", "魔法", "magical", "enchanted", "魔幻"],
    "self_projection": ["self", "you", "你", "your", "yourself", "自己"],
    "progress_satisfaction": ["progress", "advance", "进度", "成长", "growth", "level"],
    "rescue_motivation": ["rescue", "save", "救", "help", "rescue", "aid", "拯救"],
    "order_restoration": ["order", "clean", "organize", "tidy", "整理", "恢复"],
}


# ═══════════════════════════════════════════════════════════
# IAP-Specific Keywords — Merge Witch Game
# ═══════════════════════════════════════════════════════════

# Fantasy drives: WHY the player wants to play
FANTASY_KEYWORDS: dict[str, list[str]] = {
    "rescue_kingdom": ["rescue", "save", "拯救", "restore", "恢复", "heal", "cure",
                       "fix", "repair", "dark", "crisis", "rebuild", "重建"],
    "collect_dragons": ["collect", "收集", "dragon", "creature", "monster", "pet",
                        "animal", "magical", "mythical", "rare", "all", "全部"],
    "become_powerful": ["power", "powerful", "强大", "strength", "master", "wizard",
                        "witch", "mage", "magic", "level up", "进化", "evolve"],
    "build_empire": ["build", "empire", "kingdom", "建造", "帝国", "王国", "castle",
                     "领地", "territory", "expand", "扩张", "grow", "develop"],
    "discovery_world": ["discover", "adventure", "explore", "journey", "探索", "冒险",
                        "world", "map", "area", "new", "secret", "mystery", "hidden"],
    "restore_order": ["order", "clean", "tidy", "organize", "整理", "restore",
                      "fix", "repair", "mess", "chaos", "混乱", "恢复秩序"],
}

# Progression loops: WHAT keeps the player engaged
PROGRESSION_KEYWORDS: dict[str, list[str]] = {
    "merge_items": ["merge", "合成", "combine", "融合", "merging", "merged",
                    "triple", "match", "配对"],
    "unlock_area": ["unlock", "解锁", "open", "reveal", "new area", "new zone",
                    "expand", "discover", "探索", "开放"],
    "level_up": ["level", "关卡", "stage", "progress", "advance", "进度",
                 "next", "下一关", "upgrade", "升级", "rank"],
    "complete_collection": ["collection", "complete", "collect all", "全部收集",
                            "gather", "set", "系列", "finish", "完成"],
    "restore_world": ["restore", "rebuild", "重建", "恢复", "revive", "bring back",
                      "life", "生机", "bloom", "flourish", "green"],
    "chain_reaction": ["chain", "连锁", "combo", "multiply", "cascade", "连击",
                       "burst", "explosion"],
}

# Payment triggers: WHY the player pays
PAYMENT_TRIGGER_KEYWORDS: dict[str, list[str]] = {
    "blocked_progress": ["stuck", "blocked", "卡住", "can't", "cannot", "need",
                         "require", "缺少", "not enough", "insufficient"],
    "missing_piece": ["missing", "need one", "差一个", "almost", "就差", "last one",
                      "last piece", "final", "complete", "就差一点"],
    "time_gate": ["wait", "等待", "timer", "time", "speed up", "加速", "skip",
                  "instant", "立即", "now", "马上"],
    "exclusive_item": ["exclusive", "rare", "限定", "special", "unique", "独家",
                       "legendary", "mythic", "传说", "稀有", "only"],
    "energy_depleted": ["energy", "精力", "体力", "depleted", "empty", "refill",
                        "recharge", "恢复", "补充"],
    "collection_completion": ["collection", "complete set", "全套", "收集齐全",
                              "finish collecting", "final item", "最后一件"],
}

# Retention hooks: WHY the player returns
RETENTION_KEYWORDS: dict[str, list[str]] = {
    "daily_reward": ["daily", "每日", "every day", "login", "登录", "reward",
                     "bonus", "签到", "gift", "free"],
    "merge_progress": ["merge", "合成", "progress", "ongoing", "continue", "继续",
                       "in progress", "进行中", "pending"],
    "area_unlock": ["unlock", "解锁", "new area", "open soon", "即将开放",
                    "coming soon", "next zone", "next area"],
    "collection_progress": ["collection", "collect", "收集", "gather", "more",
                            "more items", "更多", "album", "图鉴"],
    "story_continuation": ["story", "剧情", "chapter", "continue", "what happens",
                           "next", "后续", "结局", "ending"],
    "event_timer": ["event", "活动", "limited", "限时", "time limited", "special",
                    "deadline", "ending soon", "即将结束"],
    "social_competition": ["leaderboard", "排行", "rank", "compete", "friend",
                           "好友", "share", "compare", "VS"],
}


# ═══════════════════════════════════════════════════════════
# IAP Genome Fitness Calculator
# ═══════════════════════════════════════════════════════════

def compute_iap_fitness(spend: float, revenue: float, installs: int,
                        d1_retention: float = 0.0, d7_retention: float = 0.0,
                        payer_rate: float = 0.0, ltv_d30: float = 0.0
                        ) -> dict[str, Any]:
    """Compute IAP-focused Genome Fitness.

    IAP formula (when data available):
      Fitness = 0.20×D1_retention + 0.20×D7_retention + 0.20×payer_rate
              + 0.20×LTV_D30 + 0.20×ROAS

    Fallback (when only spend/revenue available):
      Fitness = ROAS_scaled + spend_confidence

    Returns: {score, components, confidence, player_value_score}
    """
    roas = revenue / spend if spend > 0 else 0.0
    cpi = spend / installs if installs > 0 else 999.0

    # Check if we have real retention/payer data
    has_iap_data = d1_retention > 0 or d7_retention > 0 or payer_rate > 0

    if has_iap_data:
        components = {
            "d1_retention": min(d1_retention, 1.0),
            "d7_retention": min(d7_retention, 1.0),
            "payer_rate": min(payer_rate / 0.15, 1.0),  # 15% payer rate = perfect
            "ltv_d30": min(ltv_d30 / (cpi * 5), 1.0) if cpi > 0 else 0.0,
            "roas_proxy": min(roas / 2.0, 1.0),
        }
        score = (
            components["d1_retention"] * 0.20
            + components["d7_retention"] * 0.20
            + components["payer_rate"] * 0.20
            + components["ltv_d30"] * 0.20
            + components["roas_proxy"] * 0.20
        )
    else:
        # Fallback: ROAS-based with spend confidence
        roas_score = min(roas / 2.0, 1.0)
        spend_factor = min(spend / 500.0, 1.0)  # Confidence grows with spend
        components = {
            "roas_scaled": roas_score,
            "spend_confidence": spend_factor,
            "cpi": cpi,
        }
        score = roas_score * 0.7 + spend_factor * 0.3

    # Player Value Score: separate metric for "attracts high-value players"
    pv_score = 0.0
    if has_iap_data:
        pv_score = (
            d7_retention * 0.4 + payer_rate * 0.3 + min(ltv_d30 / 10.0, 1.0) * 0.3
        )
    else:
        # Proxy: high ROAS with low CPI suggests high-value players
        if roas > 0.5 and cpi < 20:
            pv_score = min(roas / 2.0, 1.0)

    confidence = min(spend / 1000.0, 1.0)

    return {
        "score": round(score, 3),
        "components": {k: round(v, 3) for k, v in components.items()},
        "confidence": round(confidence, 3),
        "player_value_score": round(pv_score, 3),
        "sample_size": installs,
        "total_spend": round(spend, 2),
    }


# ═══════════════════════════════════════════════════════════
# Fused DNA Record
# ═══════════════════════════════════════════════════════════

@dataclass
class FusedDNA:
    """Enriched creative DNA with IAP-specific fields + confidence scores.

    Core DNA (from CreativeDNAV2):
      mechanism_type, reward_type, hook_type, visual_style, psychology_drives

    IAP DNA (E9.3):
      fantasy_drives, progression_loops, payment_triggers, retention_hooks
      iap_fitness, player_value_score
    """
    creative_id: str = ""
    creative_name: str = ""
    eagle_filename: str = ""

    # ── Core DNA ──
    mechanism_type: str = ""
    mechanism_confidence: float = 0.0
    mechanism_keywords: list[str] = field(default_factory=list)

    reward_type: str = ""
    reward_confidence: float = 0.0
    reward_keywords: list[str] = field(default_factory=list)

    hook_type: str = ""
    hook_confidence: float = 0.0
    hook_keywords: list[str] = field(default_factory=list)

    visual_style: str = ""
    visual_confidence: float = 0.0
    visual_keywords: list[str] = field(default_factory=list)

    psychology_drives: list[str] = field(default_factory=list)
    psychology_confidence: float = 0.0

    # ── IAP DNA (E9.3) ──
    fantasy_drives: list[str] = field(default_factory=list)
    fantasy_confidence: float = 0.0

    progression_loops: list[str] = field(default_factory=list)
    progression_confidence: float = 0.0

    payment_triggers: list[str] = field(default_factory=list)
    payment_trigger_confidence: float = 0.0

    retention_hooks: list[str] = field(default_factory=list)
    retention_confidence: float = 0.0

    # ── IAP Fitness ──
    iap_fitness_score: float = 0.0
    player_value_score: float = 0.0
    iap_fitness_components: dict[str, float] = field(default_factory=dict)

    # ── Performance (from CSV) ──
    spend: float = 0.0
    revenue: float = 0.0
    installs: int = 0
    roas: float = 0.0

    # ── Metadata ──
    fusion_version: str = "2.0"  # 2.0 = IAP upgrade
    total_confidence: float = 0.0

    @property
    def is_winner(self) -> bool:
        return self.roas >= 1.0 and self.spend >= 100

    @property
    def is_iap_winner(self) -> bool:
        """IAP winner: high player value OR high ROAS."""
        return self.player_value_score > 0.3 or self.is_winner

    @property
    def has_meaningful_dna(self) -> bool:
        return self.total_confidence > 0.1

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "eagle_filename": self.eagle_filename,
            # Core DNA
            "mechanism": {
                "type": self.mechanism_type,
                "confidence": self.mechanism_confidence,
                "keywords": self.mechanism_keywords,
            },
            "reward": {
                "type": self.reward_type,
                "confidence": self.reward_confidence,
                "keywords": self.reward_keywords,
            },
            "hook": {
                "type": self.hook_type,
                "confidence": self.hook_confidence,
                "keywords": self.hook_keywords,
            },
            "visual": {
                "style": self.visual_style,
                "confidence": self.visual_confidence,
                "keywords": self.visual_keywords,
            },
            "psychology": {
                "drives": self.psychology_drives,
                "confidence": self.psychology_confidence,
            },
            # IAP DNA
            "fantasy": {
                "drives": self.fantasy_drives,
                "confidence": self.fantasy_confidence,
            },
            "progression": {
                "loops": self.progression_loops,
                "confidence": self.progression_confidence,
            },
            "payment_trigger": {
                "triggers": self.payment_triggers,
                "confidence": self.payment_trigger_confidence,
            },
            "retention": {
                "hooks": self.retention_hooks,
                "confidence": self.retention_confidence,
            },
            # IAP Fitness
            "iap_fitness": {
                "score": self.iap_fitness_score,
                "player_value_score": self.player_value_score,
                "components": self.iap_fitness_components,
            },
            # Performance
            "performance": {
                "spend": self.spend,
                "revenue": self.revenue,
                "installs": self.installs,
                "roas": self.roas,
                "is_winner": self.is_winner,
                "is_iap_winner": self.is_iap_winner,
            },
            "fusion_version": self.fusion_version,
            "total_confidence": self.total_confidence,
        }


# ═══════════════════════════════════════════════════════════
# Matcher — keyword matching with confidence
# ═══════════════════════════════════════════════════════════

def _match_keywords(text: str, keyword_dict: dict[str, list[str]]
                    ) -> tuple[str, float, list[str]]:
    """Match text against a keyword dictionary, return best match + confidence.

    Confidence = (keyword_length / total_keywords) * specificity_bonus
    Specificity: longer keywords are more specific.
    """
    normalized = (text or "").lower()
    best_type = ""
    best_score = 0.0
    best_keywords: list[str] = []

    total_keywords = sum(len(v) for v in keyword_dict.values())

    for type_name, keywords in keyword_dict.items():
        hits = [kw for kw in keywords if kw.lower() in normalized]
        if not hits:
            continue

        # Score: hit count weighted by keyword specificity
        keyword_bonus = sum(len(kw) for kw in hits) / max(1, len(keywords))
        hit_ratio = len(hits) / len(keywords)
        score = hit_ratio * 0.5 + keyword_bonus * 0.5

        if score > best_score:
            best_score = score
            best_type = type_name
            best_keywords = hits

    return best_type, min(best_score, 1.0), best_keywords


def _match_multi(text: str, keyword_dict: dict[str, list[str]]
                 ) -> tuple[list[str], float]:
    """Match text against multiple keywords (psychology drives)."""
    normalized = (text or "").lower()
    found: list[str] = []
    for type_name, keywords in keyword_dict.items():
        if any(kw.lower() in normalized for kw in keywords):
            found.append(type_name)
    confidence = min(len(found) / max(1, len(keyword_dict)), 1.0)
    return found, confidence


# ═══════════════════════════════════════════════════════════
# Creative DNA Fusion Engine
# ═══════════════════════════════════════════════════════════

class CreativeDNAFusionEngine:
    """Fuses multiple DNA sources into high-confidence CreativeDNA records.

    Sources:
      1. Name-based keyword matching (creative_name + eagle_filename)
      2. CreativeDNAV2 vocabulary (mechanism, reward, hook, visual, psychology)
      3. Performance data from CSV

    Output: creative_dna_master.json — all 1315 creatives with enriched DNA.
    """

    def __init__(self) -> None:
        self._records: list[FusedDNA] = []
        self._csv_path = Path("output/video_intelligence/p04/creative_mapping_adjust_merged_v2.csv")
        self._output_path = Path("output/active/creative_dna_master.json")

    # ── Loading ──────────────────────────────────────────────

    def load_from_csv(self) -> int:
        """Load all creatives from CSV and fuse DNA.

        Returns: number of records processed.
        """
        if not self._csv_path.exists():
            return 0

        self._records = []
        with open(self._csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                creative_id = row.get("creative_id", "").strip()
                if not creative_id:
                    continue

                creative_name = row.get("creative_name", "").strip()
                eagle_filename = row.get("eagle_filename", "").strip()

                # Performance
                adj_cost = float(row.get("adjust_cost", 0) or 0)
                adj_revenue = float(row.get("adjust_revenue", 0) or 0)
                adj_installs = int(float(row.get("adjust_installs", 0) or 0))
                fb_spend = float(row.get("fb_spend", 0) or 0)
                fb_revenue = float(row.get("fb_revenue", 0) or 0)
                fb_installs = int(float(row.get("fb_installs", 0) or 0))

                spend = adj_cost if adj_cost > 0 else fb_spend
                revenue = adj_revenue if adj_revenue > 0 else fb_revenue
                installs = adj_installs if adj_installs > 0 else fb_installs
                roas = revenue / spend if spend > 0 else 0

                # Fuse DNA from all text sources
                text = f"{creative_name} {eagle_filename}"

                mechanism, mech_conf, mech_kw = _match_keywords(text, MECHANISM_KEYWORDS)
                reward, rew_conf, rew_kw = _match_keywords(text, REWARD_KEYWORDS)
                hook, hook_conf, hook_kw = _match_keywords(text, HOOK_KEYWORDS)
                visual, vis_conf, vis_kw = _match_keywords(text, VISUAL_KEYWORDS)
                psy_drives, psy_conf = _match_multi(text, PSYCHOLOGY_KEYWORDS)

                # E9.3: IAP-specific DNA
                fantasy_drives, fantasy_conf = _match_multi(text, FANTASY_KEYWORDS)
                progression_loops, prog_conf = _match_multi(text, PROGRESSION_KEYWORDS)
                payment_triggers, pay_conf = _match_multi(text, PAYMENT_TRIGGER_KEYWORDS)
                retention_hooks, ret_conf = _match_multi(text, RETENTION_KEYWORDS)

                # E9.3: IAP Fitness
                iap_fit = compute_iap_fitness(spend, revenue, installs)

                total_conf = (
                    mech_conf * 0.15
                    + rew_conf * 0.10
                    + hook_conf * 0.15
                    + vis_conf * 0.10
                    + psy_conf * 0.10
                    + fantasy_conf * 0.15
                    + prog_conf * 0.10
                    + pay_conf * 0.05
                    + ret_conf * 0.10
                )

                record = FusedDNA(
                    creative_id=creative_id,
                    creative_name=creative_name,
                    eagle_filename=eagle_filename,
                    # Core DNA
                    mechanism_type=mechanism,
                    mechanism_confidence=round(mech_conf, 3),
                    mechanism_keywords=mech_kw,
                    reward_type=reward,
                    reward_confidence=round(rew_conf, 3),
                    reward_keywords=rew_kw,
                    hook_type=hook,
                    hook_confidence=round(hook_conf, 3),
                    hook_keywords=hook_kw,
                    visual_style=visual,
                    visual_confidence=round(vis_conf, 3),
                    visual_keywords=vis_kw,
                    psychology_drives=psy_drives,
                    psychology_confidence=round(psy_conf, 3),
                    # IAP DNA
                    fantasy_drives=fantasy_drives,
                    fantasy_confidence=round(fantasy_conf, 3),
                    progression_loops=progression_loops,
                    progression_confidence=round(prog_conf, 3),
                    payment_triggers=payment_triggers,
                    payment_trigger_confidence=round(pay_conf, 3),
                    retention_hooks=retention_hooks,
                    retention_confidence=round(ret_conf, 3),
                    # IAP Fitness
                    iap_fitness_score=iap_fit["score"],
                    player_value_score=iap_fit["player_value_score"],
                    iap_fitness_components=iap_fit["components"],
                    # Performance
                    spend=spend,
                    revenue=revenue,
                    installs=installs,
                    roas=roas,
                    total_confidence=round(total_conf, 3),
                )
                self._records.append(record)

        return len(self._records)

    # ── Export ───────────────────────────────────────────────

    def export_master_json(self) -> str:
        """Export all fused DNA records to creative_dna_master.json."""
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.to_dict() for r in self._records]
        with open(self._output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(self._output_path)

    # ── Statistics ───────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get fusion statistics."""
        if not self._records:
            return {"status": "empty"}

        total = len(self._records)
        with_dna = sum(1 for r in self._records if r.has_meaningful_dna)
        winners = sum(1 for r in self._records if r.is_winner)

        # Mechanism distribution
        mech_dist: dict[str, int] = {}
        for r in self._records:
            if r.mechanism_type:
                mech_dist[r.mechanism_type] = mech_dist.get(r.mechanism_type, 0) + 1

        # Hook distribution
        hook_dist: dict[str, int] = {}
        for r in self._records:
            if r.hook_type:
                hook_dist[r.hook_type] = hook_dist.get(r.hook_type, 0) + 1

        # Confidence distribution
        conf_buckets = {"high (>0.5)": 0, "medium (0.2-0.5)": 0, "low (<0.2)": 0}
        for r in self._records:
            if r.total_confidence > 0.5:
                conf_buckets["high (>0.5)"] += 1
            elif r.total_confidence > 0.2:
                conf_buckets["medium (0.2-0.5)"] += 1
            else:
                conf_buckets["low (<0.2)"] += 1

        return {
            "total_records": total,
            "with_meaningful_dna": with_dna,
            "winners": winners,
            "winner_rate": round(winners / max(1, total), 3),
            "confidence_distribution": conf_buckets,
            "mechanism_distribution": dict(sorted(mech_dist.items(), key=lambda x: -x[1])),
            "hook_distribution": dict(sorted(hook_dist.items(), key=lambda x: -x[1])),
            "avg_confidence": round(
                sum(r.total_confidence for r in self._records) / max(1, total), 3
            ),
        }

    def get_gene_performance(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Get gene-level performance from fused DNA.

        Returns: {gene_type: {value: {count, avg_roas, winner_rate}}}
        """
        gene_map = {
            "mechanism": ("mechanism_type", "gameplay"),
            "reward": ("reward_type", "reward"),
            "hook": ("hook_type", "hook"),
            "visual": ("visual_style", "visual"),
        }

        stats: dict[str, dict[str, dict[str, Any]]] = {}
        for attr_name, gene_name in gene_map.values():
            if gene_name not in stats:
                stats[gene_name] = {}

            for r in self._records:
                value = getattr(r, attr_name, "")
                if not value:
                    continue
                if value not in stats[gene_name]:
                    stats[gene_name][value] = {"count": 0, "total_roas": 0.0, "winners": 0,
                                                "total_spend": 0.0, "total_revenue": 0.0}
                s = stats[gene_name][value]
                s["count"] += 1
                s["total_roas"] += r.roas
                s["total_spend"] += r.spend
                s["total_revenue"] += r.revenue
                if r.is_winner:
                    s["winners"] += 1

            for value, s in stats[gene_name].items():
                n = s["count"]
                s["avg_roas"] = round(s["total_roas"] / n, 3) if n > 0 else 0
                s["winner_rate"] = round(s["winners"] / n, 3) if n > 0 else 0

        return stats

    def get_top_genomes(self, top_n: int = 20) -> list[FusedDNA]:
        """Get top-performing creatives as genome templates."""
        candidates = [r for r in self._records if r.has_meaningful_dna and r.spend >= 50]
        candidates.sort(key=lambda r: (r.roas, r.spend), reverse=True)
        return candidates[:top_n]

    def get_genome_combinations(self, min_occurrence: int = 3
                                ) -> list[dict[str, Any]]:
        """E9.2: Discover winning genome combinations (gene pairs).

        Returns: list of {genes, count, avg_roas, winner_rate} sorted by winner_rate.
        """
        from collections import defaultdict

        combo_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "total_roas": 0.0, "winners": 0, "total_spend": 0.0}
        )

        for r in self._records:
            if not r.has_meaningful_dna:
                continue
            # Build combo key from meaningful genes
            parts = []
            if r.mechanism_type:
                parts.append(f"mechanism={r.mechanism_type}")
            if r.hook_type:
                parts.append(f"hook={r.hook_type}")
            if r.reward_type:
                parts.append(f"reward={r.reward_type}")
            if r.visual_style:
                parts.append(f"visual={r.visual_style}")
            if len(parts) < 2:
                continue

            key = " + ".join(sorted(parts))
            s = combo_stats[key]
            s["count"] += 1
            s["total_roas"] += r.roas
            s["total_spend"] += r.spend
            if r.is_winner:
                s["winners"] += 1

        results = []
        for key, s in combo_stats.items():
            n = s["count"]
            if n < min_occurrence:
                continue
            results.append({
                "genes": key,
                "count": n,
                "avg_roas": round(s["total_roas"] / n, 3),
                "winner_rate": round(s["winners"] / n, 3),
                "total_spend": round(s["total_spend"], 2),
            })

        results.sort(key=lambda x: (x["winner_rate"], x["avg_roas"]), reverse=True)
        return results