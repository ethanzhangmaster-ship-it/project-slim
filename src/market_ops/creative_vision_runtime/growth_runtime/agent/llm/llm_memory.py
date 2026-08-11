"""E13.7.2 LLM Memory — LLM 经验记忆系统.

LLM 推理过程中产生的经验:
  - 推理模式: 有效的推理路径
  - 成功案例: 验证过的假设
  - 失败教训: 错误的推理
  - 学习笔记: 可复用的知识

设计原则:
  - LLM 记忆独立于 Agent Memory，专注推理经验
  - 自动记录推理过程
  - 支持检索和注入下次推理
  - 经验质量评分

用法:
    memory = LLMExperienceMemory()
    memory.record(experience)
    relevant = memory.retrieve("creative fatigue")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Reasoning Experience
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReasoningExperience:
    """推理经验 — 一次完整推理的经验记录.

    Attributes:
        experience_id: 经验 ID
        insight_type: 洞察类型
        diagnosis: 诊断
        hypothesis: 假设
        confidence: 推理时的置信度
        actions_taken: 实际采取的行动
        outcome: 实际结果
        was_correct: 假设是否正确
        learning: 学到的教训
        evidence: 证据
        timestamp: 时间戳
        metadata: 扩展元数据
    """
    experience_id: str = ""
    insight_type: str = ""
    diagnosis: str = ""
    hypothesis: str = ""
    confidence: float = 0.5
    actions_taken: list[str] = field(default_factory=list)
    outcome: str = ""
    was_correct: bool | None = None
    learning: str = ""
    evidence: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def quality_score(self) -> float:
        """经验质量评分."""
        score = 0.3  # 基础分
        if self.was_correct is True:
            score += 0.4
        elif self.was_correct is False:
            score += 0.2  # 失败经验也有价值
        if self.learning:
            score += 0.1
        if self.evidence:
            score += 0.1
        if self.confidence > 0.7:
            score += 0.1
        return min(1.0, score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "insight_type": self.insight_type,
            "diagnosis": self.diagnosis,
            "hypothesis": self.hypothesis,
            "confidence": self.confidence,
            "actions_taken": self.actions_taken,
            "outcome": self.outcome,
            "was_correct": self.was_correct,
            "learning": self.learning,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "quality_score": self.quality_score,
        }

    def to_prompt_fragment(self) -> str:
        """转换为 Prompt 片段."""
        correctness = "correct" if self.was_correct else "incorrect" if self.was_correct is False else "unverified"
        return (
            f"[{self.insight_type}] {self.diagnosis}\n"
            f"Hypothesis: {self.hypothesis}\n"
            f"Outcome: {self.outcome} ({correctness})\n"
            f"Learning: {self.learning}"
        )


# ═══════════════════════════════════════════════════════════════
# LLM Experience Memory
# ═══════════════════════════════════════════════════════════════


class LLMExperienceMemory:
    """LLM 经验记忆 — 存储和检索推理经验.

    功能:
      - 记录推理经验
      - 按关键词检索
      - 按类型检索
      - 生成 Prompt 注入片段
      - 质量过滤

    用法:
        mem = LLMExperienceMemory(max_size=100)
        mem.record(experience)
        relevant = mem.retrieve("fatigue", top_k=5)
    """

    def __init__(self, max_size: int = 100):
        self._experiences: list[ReasoningExperience] = []
        self._max_size = max_size
        self._counter: int = 0

    @property
    def size(self) -> int:
        return len(self._experiences)

    def record(self, experience: ReasoningExperience) -> None:
        """记录推理经验."""
        if not experience.experience_id:
            self._counter += 1
            experience.experience_id = f"llm_exp_{self._counter}"

        self._experiences.append(experience)

        # 保持最大容量
        if len(self._experiences) > self._max_size:
            # 移除质量最低的经验
            self._experiences.sort(key=lambda e: e.quality_score)
            self._experiences = self._experiences[-self._max_size:]

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_quality: float = 0.0,
    ) -> list[ReasoningExperience]:
        """检索相关经验.

        Args:
            query: 查询关键词
            top_k: 返回数量
            min_quality: 最低质量分

        Returns:
            list[ReasoningExperience]: 相关经验
        """
        query_lower = query.lower()

        scored = []
        for exp in self._experiences:
            if exp.quality_score < min_quality:
                continue

            # 简单关键词匹配评分
            score = 0.0
            text = f"{exp.insight_type} {exp.diagnosis} {exp.hypothesis} {exp.learning}".lower()
            for word in query_lower.split():
                if word in text:
                    score += 1.0
            # 质量加权
            score *= exp.quality_score

            if score > 0:
                scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:top_k]]

    def retrieve_by_type(
        self,
        insight_type: str,
        top_k: int = 5,
        only_correct: bool = False,
    ) -> list[ReasoningExperience]:
        """按类型检索.

        Args:
            insight_type: 洞察类型
            top_k: 返回数量
            only_correct: 仅返回正确经验

        Returns:
            list[ReasoningExperience]: 匹配的经验
        """
        matches = [
            e for e in self._experiences
            if e.insight_type.upper() == insight_type.upper()
        ]

        if only_correct:
            matches = [e for e in matches if e.was_correct is True]

        matches.sort(key=lambda e: e.quality_score, reverse=True)
        return matches[:top_k]

    def get_recent(self, n: int = 10) -> list[ReasoningExperience]:
        """获取最近经验."""
        return self._experiences[-n:]

    def get_best_learnings(self, n: int = 5) -> list[str]:
        """获取最佳学习笔记."""
        scored = [
            (e.quality_score, e.learning)
            for e in self._experiences
            if e.learning and e.was_correct is True
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [l for _, l in scored[:n]]

    def to_prompt_context(self, query: str = "", top_k: int = 5) -> str:
        """生成 Prompt 注入上下文.

        Args:
            query: 查询关键词
            top_k: 返回数量

        Returns:
            str: 可注入 Prompt 的经验上下文
        """
        if query:
            experiences = self.retrieve(query, top_k=top_k, min_quality=0.3)
        else:
            experiences = self.get_recent(top_k)

        if not experiences:
            return "No relevant past experiences."

        lines = ["### Past Reasoning Experiences"]
        for exp in experiences:
            lines.append(exp.to_prompt_fragment())
            lines.append("")

        return "\n".join(lines)

    def clear(self) -> None:
        self._experiences.clear()
        self._counter = 0

    def stats(self) -> dict[str, Any]:
        """统计信息."""
        total = len(self._experiences)
        if total == 0:
            return {"total": 0, "correct": 0, "incorrect": 0, "unverified": 0, "avg_quality": 0}

        correct = sum(1 for e in self._experiences if e.was_correct is True)
        incorrect = sum(1 for e in self._experiences if e.was_correct is False)
        avg_quality = sum(e.quality_score for e in self._experiences) / total

        return {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "unverified": total - correct - incorrect,
            "avg_quality": round(avg_quality, 3),
        }