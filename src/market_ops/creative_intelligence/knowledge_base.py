"""M5: Creative Knowledge Base

统一知识库 - 封装现有4个memory store为统一接口,支持版本管理。

复用现有:
- memory/gene_memory.json (GeneMemory)
- memory/winner_memory.json (WinnerMemory)
- memory/loser_memory.json (LoserMemory)
- memory/family_tree.json (FamilyTree)
- + M4 WinnerPatternDiscovery 的输出

新增:
- 统一 KnowledgeBase 接口
- 版本管理 (每次更新生成版本快照)
- 可追踪/可更新/可失效

Usage:
    from market_ops.creative_intelligence.knowledge_base import CreativeKnowledgeBase

    kb = CreativeKnowledgeBase()
    kb.update_from_analytics(analytics_report)
    kb.update_from_patterns(pattern_report)
    rules = kb.get_top_rules(project="P04", metric="ctr", limit=10)
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
MEMORY_DIR = _ROOT / "memory"
KB_DIR = _ROOT / "output" / "creative_intelligence" / "knowledge_base"
KB_DIR.mkdir(parents=True, exist_ok=True)

KB_FILE = KB_DIR / "knowledge_base.json"
VERSIONS_DIR = KB_DIR / "versions"
VERSIONS_DIR.mkdir(exist_ok=True)


class KnowledgeRule:
    """一条知识规则"""

    def __init__(
        self,
        rule_id: str,
        pattern: str,
        metric: str,
        effect: str,  # positive / negative
        lift_pct: float,
        confidence: float,  # 0-1
        sample_count: int,
        evidence: list[str] = None,
        source: str = "",
        project: str = "",
        created_at: str = "",
        last_updated: str = "",
        status: str = "active",  # active / deprecated / invalidated
    ):
        self.rule_id = rule_id
        self.pattern = pattern
        self.metric = metric
        self.effect = effect
        self.lift_pct = lift_pct
        self.confidence = confidence
        self.sample_count = sample_count
        self.evidence = evidence or []
        self.source = source
        self.project = project
        self.created_at = created_at or datetime.now().isoformat()
        self.last_updated = last_updated or datetime.now().isoformat()
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "pattern": self.pattern,
            "metric": self.metric,
            "effect": self.effect,
            "lift_pct": self.lift_pct,
            "confidence": self.confidence,
            "sample_count": self.sample_count,
            "evidence": self.evidence,
            "source": self.source,
            "project": self.project,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "status": self.status,
        }


class CreativeKnowledgeBase:
    """统一创意知识库

    数据来源:
    1. M3 FeatureAnalyticsEngine 的 top/worst features
    2. M4 WinnerPatternDiscovery 的 patterns
    3. 现有 memory/*.json (gene/winner/loser/family)
    """

    def __init__(self) -> None:
        self._rules: list[dict] = []
        self._load()

    def _load(self) -> None:
        """加载现有知识库"""
        if KB_FILE.exists():
            data = json.loads(KB_FILE.read_text(encoding="utf-8"))
            self._rules = data.get("rules", [])
            print(f"[KnowledgeBase] 加载 {len(self._rules)} 条规则")
        else:
            print(f"[KnowledgeBase] 知识库为空,将从现有memory初始化")
            self._init_from_existing_memory()

    def _init_from_existing_memory(self) -> None:
        """从现有memory文件初始化"""
        # Gene Memory
        gene_file = MEMORY_DIR / "gene_memory.json"
        if gene_file.exists():
            data = json.loads(gene_file.read_text(encoding="utf-8"))
            for gene_type, genes in data.items():
                if isinstance(genes, dict):
                    for gene_value, stats in genes.items():
                        if isinstance(stats, dict) and stats.get("wins", 0) > 0:
                            self._rules.append(KnowledgeRule(
                                rule_id=f"gene_{gene_type}_{gene_value}",
                                pattern=f"gene_{gene_type}={gene_value}",
                                metric="win_rate",
                                effect="positive",
                                lift_pct=0,
                                confidence=min(1.0, stats["wins"] / max(1, stats.get("wins", 0) + stats.get("losses", 0))),
                                sample_count=stats.get("wins", 0) + stats.get("losses", 0),
                                evidence=[f"GeneMemory: {stats.get('wins',0)} wins"],
                                source="gene_memory",
                            ).to_dict())

        # Winner Memory
        winner_file = MEMORY_DIR / "winner_memory.json"
        if winner_file.exists():
            data = json.loads(winner_file.read_text(encoding="utf-8"))
            for entry in data.get("winners", []):
                if isinstance(entry, dict):
                    self._rules.append(KnowledgeRule(
                        rule_id=f"winner_{entry.get('gene_type','')}_{entry.get('gene_value','')}",
                        pattern=f"{entry.get('gene_type','')}={entry.get('gene_value','')}",
                        metric="win_count",
                        effect="positive",
                        lift_pct=0,
                        confidence=0.8,
                        sample_count=entry.get("win_count", 0),
                        evidence=[f"WinnerMemory: {entry.get('win_count',0)} wins"],
                        source="winner_memory",
                    ).to_dict())

        # Loser Memory
        loser_file = MEMORY_DIR / "loser_memory.json"
        if loser_file.exists():
            data = json.loads(loser_file.read_text(encoding="utf-8"))
            for entry in data.get("losers", []):
                if isinstance(entry, dict):
                    self._rules.append(KnowledgeRule(
                        rule_id=f"loser_{entry.get('gene_type','')}_{entry.get('gene_value','')}",
                        pattern=f"{entry.get('gene_type','')}={entry.get('gene_value','')}",
                        metric="loss_count",
                        effect="negative",
                        lift_pct=0,
                        confidence=0.8,
                        sample_count=entry.get("loss_count", 0),
                        evidence=[f"LoserMemory: {entry.get('loss_count',0)} losses"],
                        source="loser_memory",
                    ).to_dict())

        print(f"[KnowledgeBase] 从memory初始化 {len(self._rules)} 条规则")
        self._save()

    def update_from_analytics(self, analytics_report: dict[str, Any]) -> int:
        """从M3 Analytics报告更新知识库"""
        count = 0
        project = analytics_report.get("filters", {}).get("project", "")

        # Top features → positive rules
        for feat in analytics_report.get("top_features", []):
            if feat.get("significant") or feat.get("lift_pct", 0) > 20:
                rule_id = f"analytics_{feat['feature']}_{feat['metric']}_{feat.get('value','')}"
                self._upsert_rule(KnowledgeRule(
                    rule_id=rule_id,
                    pattern=f"{feat['feature']}={feat.get('value', True)}",
                    metric=feat["metric"],
                    effect="positive",
                    lift_pct=feat["lift_pct"],
                    confidence=0.9 if feat.get("significant") else 0.6,
                    sample_count=feat["with_count"],
                    evidence=[f"Analytics: {feat['with_mean']} vs {feat['without_mean']}"],
                    source="analytics",
                    project=project,
                ))
                count += 1

        # Worst features → negative rules
        for feat in analytics_report.get("worst_features", []):
            if feat.get("significant") or feat.get("lift_pct", 0) < -20:
                rule_id = f"analytics_{feat['feature']}_{feat['metric']}_{feat.get('value','')}"
                self._upsert_rule(KnowledgeRule(
                    rule_id=rule_id,
                    pattern=f"{feat['feature']}={feat.get('value', True)}",
                    metric=feat["metric"],
                    effect="negative",
                    lift_pct=feat["lift_pct"],
                    confidence=0.9 if feat.get("significant") else 0.6,
                    sample_count=feat["with_count"],
                    evidence=[f"Analytics: {feat['with_mean']} vs {feat['without_mean']}"],
                    source="analytics",
                    project=project,
                ))
                count += 1

        print(f"[KnowledgeBase] 从Analytics更新 {count} 条规则")
        self._save()
        return count

    def update_from_patterns(self, pattern_report: dict[str, Any]) -> int:
        """从M4 Pattern Discovery报告更新知识库"""
        count = 0
        project = pattern_report.get("filters", {}).get("project", "")

        # Combo patterns
        for combo in pattern_report.get("combo_patterns", []):
            rule_id = f"pattern_{ '_'.join(combo['features']) }"
            self._upsert_rule(KnowledgeRule(
                rule_id=rule_id,
                pattern=combo["pattern"],
                metric="ctr",
                effect="positive" if combo["lift_pct"] > 0 else "negative",
                lift_pct=combo["lift_pct"],
                confidence=min(0.9, combo["sample_count"] / 20),
                sample_count=combo["sample_count"],
                evidence=[f"Combo: {combo['avg_ctr']}% vs {combo['baseline_ctr']}%"],
                source="pattern_discovery",
                project=project,
            ))
            count += 1

        # Single patterns
        for pat in pattern_report.get("single_feature_patterns", []):
            rule_id = f"pattern_single_{pat['feature']}_{pat.get('value','')}"
            self._upsert_rule(KnowledgeRule(
                rule_id=rule_id,
                pattern=pat["pattern"],
                metric="winner_rate",
                effect="positive" if pat["winner_pct"] > pat["loser_pct"] else "negative",
                lift_pct=pat["winner_pct"] - pat["loser_pct"],
                confidence=min(0.9, pat["winner_pct"] / 100),
                sample_count=pattern_report.get("winner_count", 0),
                evidence=[pat["insight"]],
                source="pattern_discovery",
                project=project,
            ))
            count += 1

        print(f"[KnowledgeBase] 从Patterns更新 {count} 条规则")
        self._save()
        return count

    def get_top_rules(
        self,
        project: str | None = None,
        metric: str = "ctr",
        effect: str = "positive",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """获取Top规则"""
        filtered = [
            r for r in self._rules
            if r["status"] == "active"
            and (not project or r["project"] == project or r["project"] == "")
            and r["metric"] in (metric, "win_rate", "winner_rate", "win_count")
            and r["effect"] == effect
        ]
        filtered.sort(key=lambda x: x.get("lift_pct", 0), reverse=True)
        return filtered[:limit]

    def get_avoid_rules(
        self,
        project: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """获取应避免的规则(negative rules)"""
        return self.get_top_rules(project=project, effect="negative", limit=limit)

    def _upsert_rule(self, rule: KnowledgeRule) -> None:
        """插入或更新规则"""
        for i, existing in enumerate(self._rules):
            if existing["rule_id"] == rule.rule_id:
                # 更新,保留created_at
                rule.created_at = existing.get("created_at", rule.created_at)
                self._rules[i] = rule.to_dict()
                return
        self._rules.append(rule.to_dict())

    def _save(self) -> None:
        """保存知识库 + 版本快照"""
        data = {
            "updated_at": datetime.now().isoformat(),
            "total_rules": len(self._rules),
            "active_rules": sum(1 for r in self._rules if r["status"] == "active"),
            "rules": self._rules,
        }
        KB_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        # 版本快照(每天一次)
        version_file = VERSIONS_DIR / f"kb_{datetime.now().strftime('%Y%m%d')}.json"
        if not version_file.exists():
            shutil.copy2(KB_FILE, version_file)

    def get_summary(self) -> dict[str, Any]:
        """知识库摘要"""
        from collections import Counter
        return {
            "total_rules": len(self._rules),
            "active_rules": sum(1 for r in self._rules if r["status"] == "active"),
            "by_source": dict(Counter(r["source"] for r in self._rules)),
            "by_effect": dict(Counter(r["effect"] for r in self._rules)),
            "by_project": dict(Counter(r["project"] for r in self._rules if r["project"])),
            "updated_at": datetime.now().isoformat(),
        }
