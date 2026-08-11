"""M6: Creative Planner

基于知识库生成创意Prompt - 不能随机,必须读取Knowledge。

流程:
  读取 Top Feature → 组合 Feature → 预测CTR → 生成Prompt → 调用Creative Factory

复用现有:
- CreativeKnowledgeBase (M5) 提供规则
- CreativeImageGenerator (现有) 生成图片
- FinalBandit (Spec §13 封版) 探索/利用决策

Usage:
    from market_ops.creative_intelligence.creative_planner import CreativePlanner

    planner = CreativePlanner()
    prompts = planner.plan(project="P04", count=6)
    # → 调用 CreativeImageGenerator.generate(prompts)
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.creative_intelligence.knowledge_base import CreativeKnowledgeBase

_ROOT = Path(__file__).resolve().parents[3]


class CreativePlanner:
    """基于知识库的创意规划器

    策略 (按project_memory预算分配):
    - 70% Winner Mutation: 读取top rules → 组合已知winner features
    - 20% New Hook: 读取untested feature组合
    - 10% Explore: 随机探索 Bandit Engine推荐的arm
    """

    # Feature → Prompt描述映射
    FEATURE_PROMPT_MAP = {
        "has_female": "female witch character with white hair",
        "has_monster": "cute magical creature companion",
        "has_ui": "merge board gameplay UI element",
        "has_coins": "gold coins reward display",
        "has_chest": "treasure chest with glowing light",
        "has_cta": "call-to-action button overlay",
        "has_arrow": "progression arrow indicators",
        "has_highlight": "glowing highlight effects on key elements",
        "left_right_layout": "left-right split layout composition",
        "center_layout": "centered hero composition",
        "symmetry": "symmetrical composition",
        "game_has_merge": "merge game mechanic visualization",
        "game_has_level": "level progression display",
        "game_has_progress": "evolution progression chain",
        "game_has_collection": "creature collection display",
    }

    # 颜色 → Prompt
    COLOR_PROMPT_MAP = {
        "purple": "deep purples and royal violet",
        "blue": "midnight blues and deep navy",
        "black": "dark black silhouettes with shadows",
        "gray": "neutral gray tones",
        "white": "bright white highlights",
        "gold": "warm golden yellow accents",
        "red": "crimson red energy",
        "pink": "soft pink and magenta",
    }

    def __init__(self) -> None:
        self._kb = CreativeKnowledgeBase()

    def plan(
        self,
        project: str = "P04",
        count: int = 6,
        strategy: str = "balanced",
    ) -> list[dict[str, Any]]:
        """生成创意Prompt

        Args:
            count: 生成多少个prompt
            strategy: balanced / exploit / explore
        """
        print(f"[Planner] 规划 {count} 个prompt | project={project} | strategy={strategy}")

        # 读取知识库规则
        positive_rules = self._kb.get_top_rules(project=project, effect="positive", limit=20)
        negative_rules = self._kb.get_top_rules(project=project, effect="negative", limit=10)
        avoid_features = self._extract_avoid_features(negative_rules)

        print(f"[Planner] 知识库: {len(positive_rules)}条正向规则, 避免{n_features(avoid_features)}个负面特征")

        # 按预算分配
        if strategy == "balanced":
            n_winner = max(1, int(count * 0.7))
            n_new = max(1, int(count * 0.2))
            n_explore = count - n_winner - n_new
        elif strategy == "exploit":
            n_winner, n_new, n_explore = count, 0, 0
        else:
            n_winner, n_new, n_explore = 0, 0, count

        prompts = []

        # 1. Winner Mutation (70%)
        for i in range(n_winner):
            prompt = self._gen_winner_mutation(project, positive_rules, avoid_features, i)
            prompts.append(prompt)

        # 2. New Hook (20%)
        for i in range(n_new):
            prompt = self._gen_new_hook(project, positive_rules, avoid_features, i)
            prompts.append(prompt)

        # 3. Explore (10%)
        for i in range(n_explore):
            prompt = self._gen_explore(project, avoid_features, i)
            prompts.append(prompt)

        # 打印规划
        for p in prompts:
            print(f"  [{p['type']}] {p['prompt_id']}: {p['prompt_text'][:80]}...")

        # 保存规划
        plan_file = _ROOT / "output" / "creative_intelligence" / f"plan_{project}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.write_text(json.dumps(prompts, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[Planner] 规划已保存: {plan_file}")

        return prompts

    def _gen_winner_mutation(
        self,
        project: str,
        rules: list[dict],
        avoid: set[str],
        idx: int,
    ) -> dict[str, Any]:
        """Winner Mutation: 组合top features"""
        # 从规则中提取可用features
        available = [r for r in rules if r["pattern"].split("=")[0] not in avoid]
        selected = random.sample(available, min(3, len(available))) if available else []

        # 构建prompt
        feature_descs = []
        for rule in selected:
            feat = rule["pattern"].split("=")[0]
            if feat in self.FEATURE_PROMPT_MAP:
                feature_descs.append(self.FEATURE_PROMPT_MAP[feat])

        # 颜色
        color_rule = next((r for r in rules if "warm_cool=warm" in r["pattern"]), None)
        if color_rule:
            feature_descs.append("warm color palette with golden accents")
        elif "warm_cool=cool" in avoid:
            feature_descs.append("warm color palette (avoid cool tones)")

        prompt_text = self._build_prompt_text(feature_descs, project, "winner_mutation")

        return {
            "prompt_id": f"winner_{idx:02d}",
            "prompt_text": prompt_text,
            "negative_prompt": "blurry, low quality, watermark, realistic photo, NSFW",
            "hook_type": "mystery",
            "project": project,
            "type": "winner_mutation",
            "based_on_rules": [r["rule_id"] for r in selected],
            "predicted_features": [r["pattern"] for r in selected],
        }

    def _gen_new_hook(
        self,
        project: str,
        rules: list[dict],
        avoid: set[str],
        idx: int,
    ) -> dict[str, Any]:
        """New Hook: 未测试的feature组合"""
        all_features = set(self.FEATURE_PROMPT_MAP.keys())
        tested = {r["pattern"].split("=")[0] for r in rules}
        untested = list(all_features - tested - avoid)
        selected = random.sample(untested, min(3, len(untested))) if untested else list(all_features)[:3]

        feature_descs = [self.FEATURE_PROMPT_MAP[f] for f in selected if f in self.FEATURE_PROMPT_MAP]
        prompt_text = self._build_prompt_text(feature_descs, project, "new_hook")

        return {
            "prompt_id": f"new_{idx:02d}",
            "prompt_text": prompt_text,
            "negative_prompt": "blurry, low quality, watermark",
            "hook_type": "collection",
            "project": project,
            "type": "new_hook",
            "based_on_rules": [],
            "predicted_features": selected,
        }

    def _gen_explore(self, project: str, avoid: set[str], idx: int) -> dict[str, Any]:
        """Explore: 随机组合"""
        all_features = [f for f in self.FEATURE_PROMPT_MAP if f not in avoid]
        selected = random.sample(all_features, min(4, len(all_features)))
        feature_descs = [self.FEATURE_PROMPT_MAP[f] for f in selected]
        prompt_text = self._build_prompt_text(feature_descs, project, "explore")

        return {
            "prompt_id": f"explore_{idx:02d}",
            "prompt_text": prompt_text,
            "negative_prompt": "blurry, low quality, watermark",
            "hook_type": "other",
            "project": project,
            "type": "explore",
            "based_on_rules": [],
            "predicted_features": selected,
        }

    def _build_prompt_text(self, features: list[str], project: str, gen_type: str) -> str:
        """构建完整prompt"""
        project_context = {
            "P04": "dark fantasy witch merge game",
            "P02": "ocean mermaid merge game",
            "P07": "vampire dark empire merge game",
        }.get(project, "mobile merge game")

        feature_str = ", ".join(features) if features else "professional game ad creative"

        return (
            f"3D cartoon style mobile game advertisement for {project_context}. "
            f"Key visual elements: {feature_str}. "
            f"Mysterious and magical atmosphere, medium brightness, professional Facebook ad quality. "
            f"1:1 square aspect ratio, 1080x1080 pixels, no text overlay, no watermark."
        )

    def _extract_avoid_features(self, negative_rules: list[dict]) -> set[str]:
        """从负面规则提取应避免的feature"""
        avoid = set()
        for rule in negative_rules:
            pattern = rule.get("pattern", "")
            feat = pattern.split("=")[0]
            avoid.add(feat)
        return avoid


def n_features(s: set) -> int:
    return len(s)
