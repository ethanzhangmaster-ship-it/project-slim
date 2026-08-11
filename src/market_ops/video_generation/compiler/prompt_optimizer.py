"""Prompt Optimizer - 提示词优化器"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from ..models.master_prompt import PromptAST, PromptToken


class PromptOptimizer:
    """提示词优化器"""

    MERGE_GROUPS = [
        (["cinematic", "film", "movie"], "cinematic film look"),
        (["beautiful", "gorgeous", "stunning"], "beautiful cinematic"),
        (["high quality", "ultra detailed", "8k"], "high quality ultra detailed 8k"),
        (["realistic", "photorealistic", "hyperrealistic"], "photorealistic"),
        (["dark", "night", "dim"], "dark cinematic"),
        (["bright", "sunny", "light"], "bright lighting"),
    ]

    CONFLICT_PAIRS = [
        ("dark", "bright"),
        ("slow", "fast"),
        ("close", "wide"),
        ("shallow", "deep"),
        ("smooth", "rough"),
    ]

    TYPE_ORDER = [
        "scene",
        "character",
        "camera",
        "lighting",
        "motion",
        "fx",
        "negative",
    ]

    def optimize(self, ast: PromptAST) -> PromptAST:
        """执行完整优化流程"""
        optimized = PromptAST(scene_id=ast.scene_id)

        tokens = ast.tokens.copy()

        tokens = self._deduplicate(tokens)

        tokens = self._merge_similar(tokens)

        tokens = self._resolve_conflicts(tokens)

        tokens = self._sort(tokens)

        optimized.tokens = tokens
        return optimized

    def _deduplicate(self, tokens: List[PromptToken]) -> List[PromptToken]:
        """去重 - 保留最高权重"""
        seen = {}
        for token in tokens:
            key = token.content.lower().strip()
            if key:
                if key not in seen or token.weight > seen[key].weight:
                    seen[key] = token
        return list(seen.values())

    def _merge_similar(self, tokens: List[PromptToken]) -> List[PromptToken]:
        """合并相似词"""
        merged = []
        merged_content = set()

        for token in tokens:
            matched = False
            for keywords, replacement in self.MERGE_GROUPS:
                if any(kw in token.content.lower() for kw in keywords):
                    if replacement not in merged_content:
                        new_token = PromptToken(
                            content=replacement,
                            type=token.type,
                            weight=token.weight,
                            tags=token.tags,
                        )
                        merged.append(new_token)
                        merged_content.add(replacement)
                    matched = True
                    break
            if not matched and token.content.lower().strip() not in merged_content:
                merged.append(token)

        return merged

    def _resolve_conflicts(self, tokens: List[PromptToken]) -> List[PromptToken]:
        """解决冲突 - 保留最高权重"""
        content_map = {t.content.lower().strip(): t for t in tokens if t.content.strip()}

        for word1, word2 in self.CONFLICT_PAIRS:
            if word1 in content_map and word2 in content_map:
                t1 = content_map[word1]
                t2 = content_map[word2]
                if t1.weight >= t2.weight:
                    tokens.remove(t2)
                else:
                    tokens.remove(t1)

        return tokens

    def _sort(self, tokens: List[PromptToken]) -> List[PromptToken]:
        """按类型排序"""
        type_index = {t: i for i, t in enumerate(self.TYPE_ORDER)}

        def sort_key(token: PromptToken) -> int:
            if token.type in type_index:
                return type_index[token.type]
            return len(self.TYPE_ORDER)

        return sorted(tokens, key=sort_key)

    def calculate_compression_rate(self, original: List[PromptToken], optimized: List[PromptToken]) -> float:
        """计算压缩率"""
        original_len = sum(len(t.content.split()) for t in original)
        optimized_len = sum(len(t.content.split()) for t in optimized)
        if original_len == 0:
            return 0.0
        return 1.0 - (optimized_len / original_len)

    def calculate_duplicate_rate(self, tokens: List[PromptToken]) -> float:
        """计算重复率"""
        if not tokens:
            return 0.0
        contents = [t.content.lower().strip() for t in tokens if t.content.strip()]
        counter = Counter(contents)
        duplicates = sum(c - 1 for c in counter.values())
        return duplicates / len(contents)