"""E12.5.2 — Gene Analyzer。

将 ExperienceRecord 中的 mutation 基因值拆解为结构化特征。

核心流程:
  ExperienceRecord.mutation.gene_after
         │
         ▼
  GeneAnalyzer.extract_genes()
         │
         ▼
  list[ExtractedGene]

基于关键词映射，将原始基因字符串（如 "rescue_puppy"）映射为
结构化特征（如 {emotion: rescue, character: animal}）。
"""

from __future__ import annotations

from ..models import ExperienceRecord, GeneCategory
from .models import ExtractedGene


# ── Keyword Mappings ───────────────────────────────────────


# Hook 情感关键词
HOOK_EMOTION_MAP: dict[str, list[str]] = {
    "rescue": ["rescue", "save", "help", "protect", "aid", "free"],
    "challenge": ["challenge", "fail", "fail", "impossible", "hard", "difficult", "tough"],
    "curiosity": ["curious", "mystery", "secret", "discover", "hidden", "unknown"],
    "transformation": ["transform", "change", "evolve", "upgrade", "before_after"],
    "collection": ["collect", "gather", "merge", "combine", "complete"],
    "progression": ["progress", "level", "grow", "advance", "upgrade"],
    "achievement": ["achieve", "win", "success", "complete", "finish"],
    "competition": ["compete", "vs", "race", "battle", "fight", "contest"],
    "surprise": ["surprise", "wow", "shock", "unexpected", "reveal"],
    "humor": ["funny", "laugh", "joke", "silly", "fun", "cute"],
}

# Hook 冲突类型
HOOK_CONFLICT_MAP: dict[str, list[str]] = {
    "danger": ["danger", "risk", "threat", "attack", "enemy", "monster"],
    "time_pressure": ["timer", "countdown", "hurry", "urgent", "clock", "tick"],
    "scarcity": ["limited", "rare", "only", "last", "few", "scarce"],
    "puzzle": ["puzzle", "solve", "riddle", "maze", "connect"],
    "comparison": ["before", "after", "vs", "compare", "better", "worse"],
    "loss": ["lose", "fail", "drop", "sink", "fall", "destroy"],
}

# Hook 角色类型
HOOK_CHARACTER_MAP: dict[str, list[str]] = {
    "cute_animal": ["puppy", "kitten", "animal", "cute", "pet", "cat", "dog", "bunny"],
    "hero": ["hero", "warrior", "knight", "protagonist", "main"],
    "villain": ["villain", "evil", "dark", "boss", "enemy"],
    "fantasy": ["dragon", "witch", "wizard", "magic", "fairy", "elf", "castle"],
    "everyday": ["person", "human", "girl", "boy", "mom", "dad", "family"],
}

# 视觉风格
VISUAL_STYLE_MAP: dict[str, list[str]] = {
    "bright_colorful": ["bright", "colorful", "vibrant", "saturated", "rainbow"],
    "dark_moody": ["dark", "moody", "shadow", "dim", "night", "black"],
    "minimalist": ["clean", "simple", "minimal", "white", "plain"],
    "cartoon": ["cartoon", "2d", "animated", "toon", "drawn"],
    "realistic": ["realistic", "3d", "render", "photo", "real"],
    "fantasy_art": ["fantasy", "magical", "glow", "sparkle", "enchanted"],
    "ui_overlay": ["ui", "button", "tap", "click", "interface", "hud"],
}

# 玩法展示
GAMEPLAY_MAP: dict[str, list[str]] = {
    "merge": ["merge", "combine", "matching", "pair", "connect"],
    "rescue": ["rescue", "save", "help", "protect"],
    "puzzle": ["puzzle", "solve", "match", "sort", "arrange"],
    "building": ["build", "construct", "decorate", "design", "create"],
    "evolution": ["evolve", "upgrade", "level", "grow", "stage"],
    "collection": ["collect", "gather", "set", "complete", "fill"],
    "transformation": ["transform", "change", "morph", "before_after"],
    "battle": ["battle", "fight", "combat", "shoot", "attack"],
}

# 奖励类型
REWARD_MAP: dict[str, list[str]] = {
    "transformation": ["transform", "change", "new_form", "evolve"],
    "collection": ["collect", "unlock", "get", "receive", "obtain"],
    "power_up": ["power", "boost", "buff", "strength", "speed"],
    "discovery": ["discover", "find", "reveal", "unlock", "new"],
    "currency": ["coin", "gold", "gem", "diamond", "money", "reward"],
    "legendary": ["legendary", "rare", "epic", "special", "unique"],
    "completion": ["complete", "finish", "done", "100", "full"],
}

# 心理学驱动
PSYCHOLOGY_MAP: dict[str, list[str]] = {
    "collection_motivation": ["collect", "complete", "set", "gather", "all"],
    "completion_bias": ["finish", "complete", "done", "full", "missing"],
    "reward_anticipation": ["reward", "prize", "win", "get", "earn"],
    "curiosity_gap": ["curious", "mystery", "what", "how", "reveal"],
    "fantasy_appeal": ["fantasy", "magic", "dream", "wonder", "escape"],
    "self_projection": ["you", "your", "self", "identity", "become"],
    "progress_satisfaction": ["progress", "grow", "level", "advance", "improve"],
    "loss_aversion": ["lose", "miss", "risk", "danger", "save"],
    "social_proof": ["others", "everyone", "popular", "trending", "viral"],
}


# ── GeneAnalyzer ───────────────────────────────────────────


class GeneAnalyzer:
    """基因分析器 —— 将 ExperienceRecord 拆解为结构化基因特征。

    从 mutation.gene_before/gene_after 中提取原始基因值，
    通过关键词映射转换为结构化特征（emotion, conflict, character 等）。

    Usage:
        >>> analyzer = GeneAnalyzer()
        >>> genes = analyzer.extract_genes(experience_record)
        >>> for gene in genes:
        ...     print(gene.gene_category, gene.features)
    """

    def extract_genes(self, experience: ExperienceRecord) -> list[ExtractedGene]:
        """从一条经验记录中提取所有结构化基因。

        Args:
            experience: 经验记录

        Returns:
            ExtractedGene 列表
        """
        genes: list[ExtractedGene] = []

        # 从 gene_after 中提取（突变后的基因值）
        gene_after = experience.mutation.gene_after
        if not gene_after:
            return genes

        for gene_name, gene_value in gene_after.items():
            if not gene_value:
                continue

            extracted = self._extract_gene(gene_name, gene_value)
            if extracted:
                genes.append(extracted)

        return genes

    def extract_genes_batch(
        self, experiences: list[ExperienceRecord],
    ) -> list[list[ExtractedGene]]:
        """批量提取基因。

        Args:
            experiences: 经验记录列表

        Returns:
            list[list[ExtractedGene]]
        """
        return [self.extract_genes(exp) for exp in experiences]

    def _extract_gene(self, gene_name: str, gene_value: str) -> ExtractedGene | None:
        """对单个基因值进行结构化提取。

        Args:
            gene_name:  基因名称（如 hook, visual_style, gameplay）
            gene_value: 基因值（如 rescue_puppy, bright_colorful）

        Returns:
            ExtractedGene 或 None
        """
        value_lower = gene_value.lower()

        # 确定基因类别
        category = self._map_gene_category(gene_name)

        # 根据类别选择对应的分析器
        if category in ("hook", GeneCategory.HOOK.value):
            features, confidence = self._analyze_hook(value_lower)
        elif category in ("visual_style", GeneCategory.VISUAL_STYLE.value):
            features, confidence = self._analyze_visual(value_lower)
        elif category in ("gameplay", GeneCategory.GAMEPLAY.value):
            features, confidence = self._analyze_gameplay(value_lower)
        elif category in ("monetization", GeneCategory.MONETIZATION.value):
            features, confidence = self._analyze_reward(value_lower)
        elif category in ("psychology", GeneCategory.PSYCHOLOGY.value):
            features, confidence = self._analyze_psychology(value_lower)
        elif category in ("audience", GeneCategory.AUDIENCE.value):
            features, confidence = self._analyze_audience(value_lower)
        elif category in ("context", GeneCategory.CONTEXT.value):
            features, confidence = self._analyze_context(value_lower)
        else:
            # 通用分析：尝试所有映射
            features, confidence = self._analyze_universal(value_lower)

        if not features:
            # 无法提取特征时，保留原始值
            features = {"raw": value_lower}
            confidence = 0.3

        return ExtractedGene(
            gene_category=category,
            features=features,
            raw_value=gene_value,
            confidence=confidence,
        )

    # ── Category Mappers ────────────────────────────────────

    @staticmethod
    def _map_gene_category(gene_name: str) -> str:
        """将基因名称映射到标准类别。"""
        mapping = {
            "hook": "hook",
            "hook_type": "hook",
            "visual": "visual",
            "visual_style": "visual",
            "gameplay": "gameplay",
            "mechanism": "gameplay",
            "reward": "reward",
            "monetization": "reward",
            "offer": "reward",
            "audience": "audience",
            "target": "audience",
            "market": "market",
            "context": "context",
            "psychology": "psychology",
            "psychology_drive": "psychology",
        }
        return mapping.get(gene_name.lower(), gene_name.lower())

    # ── Gene Analyzers ──────────────────────────────────────

    def _analyze_hook(self, value: str) -> tuple[dict[str, str], float]:
        """分析 Hook 基因。

        提取: emotion, conflict, character
        """
        features: dict[str, str] = {}
        match_count = 0

        # 情感
        for emotion, keywords in HOOK_EMOTION_MAP.items():
            if any(kw in value for kw in keywords):
                features["emotion"] = emotion
                match_count += 1
                break

        # 冲突
        for conflict, keywords in HOOK_CONFLICT_MAP.items():
            if any(kw in value for kw in keywords):
                features["conflict"] = conflict
                match_count += 1
                break

        # 角色
        for character, keywords in HOOK_CHARACTER_MAP.items():
            if any(kw in value for kw in keywords):
                features["character"] = character
                match_count += 1
                break

        confidence = min(match_count / 3, 0.95) if match_count > 0 else 0.3
        return features, confidence

    def _analyze_visual(self, value: str) -> tuple[dict[str, str], float]:
        """分析视觉基因。

        提取: style, palette
        """
        features: dict[str, str] = {}
        match_count = 0

        for style, keywords in VISUAL_STYLE_MAP.items():
            if any(kw in value for kw in keywords):
                features["style"] = style
                match_count += 1
                break

        confidence = 0.7 if match_count > 0 else 0.3
        return features, confidence

    def _analyze_gameplay(self, value: str) -> tuple[dict[str, str], float]:
        """分析玩法基因。

        提取: mechanism, action
        """
        features: dict[str, str] = {}
        match_count = 0

        for mechanism, keywords in GAMEPLAY_MAP.items():
            if any(kw in value for kw in keywords):
                features["mechanism"] = mechanism
                match_count += 1
                break

        confidence = 0.7 if match_count > 0 else 0.3
        return features, confidence

    def _analyze_reward(self, value: str) -> tuple[dict[str, str], float]:
        """分析奖励/变现基因。

        提取: reward_type
        """
        features: dict[str, str] = {}
        match_count = 0

        for reward, keywords in REWARD_MAP.items():
            if any(kw in value for kw in keywords):
                features["reward_type"] = reward
                match_count += 1
                break

        confidence = 0.7 if match_count > 0 else 0.3
        return features, confidence

    def _analyze_psychology(self, value: str) -> tuple[dict[str, str], float]:
        """分析心理学基因。

        提取: drive
        """
        features: dict[str, str] = {}
        match_count = 0

        for drive, keywords in PSYCHOLOGY_MAP.items():
            if any(kw in value for kw in keywords):
                features["drive"] = drive
                match_count += 1
                break

        confidence = 0.7 if match_count > 0 else 0.3
        return features, confidence

    @staticmethod
    def _analyze_audience(value: str) -> tuple[dict[str, str], float]:
        """分析受众基因。

        提取: demographic, interest
        """
        features: dict[str, str] = {}

        # 性别
        if any(kw in value for kw in ["female", "women", "woman", "girl"]):
            features["gender"] = "female"
        elif any(kw in value for kw in ["male", "men", "man", "boy"]):
            features["gender"] = "male"

        # 年龄
        if "25-45" in value or "25_45" in value:
            features["age_range"] = "25-45"
        elif "18-24" in value or "18_24" in value:
            features["age_range"] = "18-24"
        elif "35+" in value or "35plus" in value:
            features["age_range"] = "35+"

        confidence = 0.6 if features else 0.3
        return features, confidence

    @staticmethod
    def _analyze_context(value: str) -> tuple[dict[str, str], float]:
        """分析情境基因。

        提取: platform, mood, lifecycle
        """
        features: dict[str, str] = {}

        if "facebook" in value or "fb" in value:
            features["platform"] = "facebook"
        elif "google" in value:
            features["platform"] = "google"
        elif "tiktok" in value:
            features["platform"] = "tiktok"

        if "new" in value or "fresh" in value:
            features["lifecycle"] = "new"
        elif "mature" in value or "stable" in value:
            features["lifecycle"] = "mature"
        elif "declining" in value or "old" in value:
            features["lifecycle"] = "declining"

        confidence = 0.6 if features else 0.3
        return features, confidence

    @staticmethod
    def _analyze_universal(value: str) -> tuple[dict[str, str], float]:
        """通用分析：尝试所有映射。"""
        features: dict[str, str] = {}

        # 尝试所有映射表
        all_maps = [
            ("emotion", HOOK_EMOTION_MAP),
            ("conflict", HOOK_CONFLICT_MAP),
            ("character", HOOK_CHARACTER_MAP),
            ("style", VISUAL_STYLE_MAP),
            ("mechanism", GAMEPLAY_MAP),
            ("reward_type", REWARD_MAP),
            ("drive", PSYCHOLOGY_MAP),
        ]

        for feat_name, feat_map in all_maps:
            for key, keywords in feat_map.items():
                if any(kw in value for kw in keywords):
                    features[feat_name] = key
                    break

        confidence = 0.5 if features else 0.2
        return features, confidence

    def __repr__(self) -> str:
        return "GeneAnalyzer()"