"""E13.7.3 Agent Memory — Agent 记忆系统.

Agent 层面记忆，不同于 E13.4 的全局 Memory:
  - 工作记忆 (WorkingMemory): 当前会话的短期记忆
  - 情景记忆 (EpisodicMemory): 过去会话的经验
  - 语义记忆 (SemanticMemory): 从经验中提取的持久知识

连接:
  Agent Memory → E13.4 Memory (ExperienceStore, PatternMemory, StrategyMemory)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .agent_models import Insight, Observation


# ═══════════════════════════════════════════════════════════════
# Working Memory Entry
# ═══════════════════════════════════════════════════════════════


@dataclass
class WorkingMemoryEntry:
    """工作记忆条目 — 当前会话的短期记忆.

    Attributes:
        entry_id: 条目 ID
        content: 内容
        entry_type: 类型
        importance: 重要性 [0, 1]
        timestamp: 时间戳
        ttl_cycles: 存活周期数
        created_at_cycle: 创建时的循环数
    """
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    entry_type: str = "observation"  # observation / insight / decision / action / result
    importance: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_cycles: int = 10
    created_at_cycle: int = 0


# ═══════════════════════════════════════════════════════════════
# Working Memory
# ═══════════════════════════════════════════════════════════════


class WorkingMemory:
    """工作记忆 — 当前会话的短期记忆.

    容量有限，重要信息保留更久，不重要的自动过期。

    用法:
        wm = WorkingMemory(max_entries=50)
        wm.add("发现素材疲劳", importance=0.8)
        wm.get_recent(10)  # 获取最近 10 条
    """

    def __init__(self, max_entries: int = 50):
        self._max_entries = max_entries
        self._entries: list[WorkingMemoryEntry] = []
        self._current_cycle: int = 0

    # ── 读写 ──────────────────────────────────────────────────

    def add(
        self,
        content: str,
        entry_type: str = "observation",
        importance: float = 0.5,
        ttl_cycles: int = 10,
    ) -> WorkingMemoryEntry:
        """添加记忆条目."""
        # 根据重要性调整 TTL
        adjusted_ttl = max(1, int(ttl_cycles * (0.5 + importance)))

        entry = WorkingMemoryEntry(
            content=content,
            entry_type=entry_type,
            importance=importance,
            ttl_cycles=adjusted_ttl,
            created_at_cycle=self._current_cycle,
        )
        self._entries.append(entry)

        # 淘汰过期条目
        self._gc()

        # 容量限制
        while len(self._entries) > self._max_entries:
            self._entries.pop(0)

        return entry

    def add_observation(self, observation: Observation) -> WorkingMemoryEntry:
        """添加观察记忆."""
        return self.add(
            content=observation.summary,
            entry_type="observation",
            importance=observation.significance,
        )

    def add_insight(self, insight: Insight) -> WorkingMemoryEntry:
        """添加洞察记忆."""
        return self.add(
            content=f"{insight.title}: {insight.description}",
            entry_type="insight",
            importance=insight.confidence,
            ttl_cycles=20,
        )

    def get_recent(self, n: int = 10) -> list[WorkingMemoryEntry]:
        """获取最近 N 条记忆."""
        return self._entries[-n:]

    def get_by_type(self, entry_type: str) -> list[WorkingMemoryEntry]:
        """按类型获取."""
        return [e for e in self._entries if e.entry_type == entry_type]

    def get_important(self, threshold: float = 0.7) -> list[WorkingMemoryEntry]:
        """获取重要记忆."""
        return [e for e in self._entries if e.importance >= threshold]

    def get_active(self) -> list[WorkingMemoryEntry]:
        """获取当前活跃的记忆条目."""
        return [
            e for e in self._entries
            if (self._current_cycle - e.created_at_cycle) < e.ttl_cycles
        ]

    def summarize(self) -> str:
        """生成工作记忆摘要."""
        active = self.get_active()
        if not active:
            return "No active memories."

        lines = ["Working Memory Summary:"]
        for e in active[-10:]:
            lines.append(f"  [{e.entry_type}] {e.content[:100]}")
        return "\n".join(lines)

    # ── 内部 ──────────────────────────────────────────────────

    def _gc(self) -> None:
        """垃圾回收 — 淘汰过期条目."""
        self._entries = [
            e for e in self._entries
            if (self._current_cycle - e.created_at_cycle) < e.ttl_cycles
        ]

    def advance_cycle(self) -> None:
        """推进循环."""
        self._current_cycle += 1
        self._gc()

    def clear(self) -> None:
        """清空工作记忆."""
        self._entries.clear()
        self._current_cycle = 0

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def active_count(self) -> int:
        return len(self.get_active())

    @property
    def current_cycle(self) -> int:
        return self._current_cycle


# ═══════════════════════════════════════════════════════════════
# Episodic Memory
# ═══════════════════════════════════════════════════════════════


@dataclass
class Episode:
    """情景记忆 — 一次完整的决策→执行→结果循环.

    Attributes:
        episode_id: 情景 ID
        session_id: 会话 ID
        cycle: 循环编号
        observations: 观察列表
        insights: 洞察列表
        goal: 目标
        plan: 执行计划
        actions: 执行的动作
        results: 执行结果
        outcome: 结果评估
        lessons: 经验教训
        timestamp: 时间戳
    """
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    cycle: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)
    insights: list[dict[str, Any]] = field(default_factory=list)
    goal: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    outcome: str = ""
    lessons: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "session_id": self.session_id,
            "cycle": self.cycle,
            "observations": self.observations,
            "insights": self.insights,
            "goal": self.goal,
            "plan": self.plan,
            "actions": self.actions,
            "results": self.results,
            "outcome": self.outcome,
            "lessons": self.lessons,
            "timestamp": self.timestamp,
        }


class EpisodicMemory:
    """情景记忆 — 存储完整的决策循环记录.

    用法:
        em = EpisodicMemory(max_episodes=100)
        em.record(episode)
        similar = em.find_similar(current_observation)
    """

    def __init__(self, max_episodes: int = 100):
        self._max_episodes = max_episodes
        self._episodes: list[Episode] = []

    def record(self, episode: Episode) -> None:
        """记录情景."""
        self._episodes.append(episode)
        if len(self._episodes) > self._max_episodes:
            self._episodes = self._episodes[-self._max_episodes:]

    def get_recent(self, n: int = 10) -> list[Episode]:
        """获取最近 N 条情景."""
        return self._episodes[-n:]

    def get_successful(self) -> list[Episode]:
        """获取成功的情景."""
        return [e for e in self._episodes if "positive" in e.outcome.lower()]

    def get_failures(self) -> list[Episode]:
        """获取失败的情景."""
        return [e for e in self._episodes if "negative" in e.outcome.lower()]

    def find_similar(self, goal_description: str, n: int = 5) -> list[Episode]:
        """查找相似情景 (基于关键词匹配)."""
        keywords = set(goal_description.lower().split())
        scored = []
        for ep in self._episodes:
            goal_text = ep.goal.get("title", "") + " " + ep.goal.get("description", "")
            score = sum(1 for kw in keywords if kw in goal_text.lower())
            if score > 0:
                scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:n]]

    def get_lessons(self) -> list[str]:
        """获取所有经验教训."""
        lessons = []
        for ep in self._episodes:
            lessons.extend(ep.lessons)
        return lessons

    def get_recent_lessons(self, n: int = 10) -> list[str]:
        """获取最近的经验教训."""
        recent = self._episodes[-n:]
        lessons = []
        for ep in recent:
            lessons.extend(ep.lessons)
        return lessons

    @property
    def size(self) -> int:
        return len(self._episodes)

    def clear(self) -> None:
        self._episodes.clear()


# ═══════════════════════════════════════════════════════════════
# Semantic Memory
# ═══════════════════════════════════════════════════════════════


@dataclass
class KnowledgeNode:
    """知识节点 — 持久化的语义知识.

    Attributes:
        node_id: 节点 ID
        concept: 概念
        description: 描述
        confidence: 置信度
        evidence_count: 支撑证据数量
        created_at: 创建时间
        last_updated: 最后更新时间
    """
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    concept: str = ""
    description: str = ""
    confidence: float = 0.5
    evidence_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SemanticMemory:
    """语义记忆 — 持久化的知识存储.

    存储从经验中提取的持久知识:
      - "Merge 类素材在女性用户中 CTR +32%"
      - "Witch 主题在欧美市场效果最好"
      - "Rescue Hook 提升 payer rate +23%"

    用法:
        sm = SemanticMemory()
        sm.add_knowledge("Merge素材", "女性25-44用户CTR+32%", confidence=0.85)
        knowledge = sm.query("Merge")
    """

    def __init__(self):
        self._knowledge: dict[str, KnowledgeNode] = {}
        self._concept_index: dict[str, list[str]] = {}  # concept → node_ids

    def add_knowledge(
        self,
        concept: str,
        description: str,
        confidence: float = 0.5,
    ) -> KnowledgeNode:
        """添加知识."""
        node = KnowledgeNode(
            concept=concept,
            description=description,
            confidence=confidence,
            evidence_count=1,
        )

        if concept in self._knowledge:
            # 更新已有知识
            existing = self._knowledge[concept]
            existing.description = description
            existing.confidence = max(existing.confidence, confidence)
            existing.evidence_count += 1
            existing.last_updated = datetime.now(timezone.utc).isoformat()
            return existing

        self._knowledge[concept] = node
        return node

    def reinforce(self, concept: str) -> None:
        """增强已有知识的置信度."""
        if concept in self._knowledge:
            node = self._knowledge[concept]
            node.evidence_count += 1
            node.confidence = min(1.0, node.confidence + 0.05)
            node.last_updated = datetime.now(timezone.utc).isoformat()

    def query(self, keyword: str, n: int = 5) -> list[KnowledgeNode]:
        """关键词查询."""
        keyword_lower = keyword.lower()
        results = []
        for concept, node in self._knowledge.items():
            if keyword_lower in concept.lower() or keyword_lower in node.description.lower():
                results.append(node)
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:n]

    def get_high_confidence(self, threshold: float = 0.7) -> list[KnowledgeNode]:
        """获取高置信度知识."""
        return [n for n in self._knowledge.values() if n.confidence >= threshold]

    def get_all(self) -> list[KnowledgeNode]:
        """获取所有知识."""
        return list(self._knowledge.values())

    def summarize(self) -> str:
        """生成知识摘要."""
        high = self.get_high_confidence(0.7)
        if not high:
            return "No high-confidence knowledge."

        lines = [f"Semantic Memory ({len(high)} high-confidence entries):"]
        for node in high[:10]:
            lines.append(f"  [{node.confidence:.0%}] {node.concept}: {node.description[:80]}")
        return "\n".join(lines)

    @property
    def size(self) -> int:
        return len(self._knowledge)

    def clear(self) -> None:
        self._knowledge.clear()