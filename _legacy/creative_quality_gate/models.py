"""Phase 2.1.6 — Creative Production Readiness Gate 数据结构。

定义审核模块内部流转的数据结构，供 critic_agent / scoring / report 复用。
所有分数统一为 0-1 浮点；decision 为 PASS / FAIL / CONDITIONAL。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class DimensionScore:
    """单个审核维度的得分与判定。"""

    name: str
    score: float          # 0-1
    passed: bool          # 是否达到该维度 PASS 阈值
    note: str = ""        # 人类可读说明


@dataclass
class CreativeScore:
    """单张创意的完整审核结果。"""

    creative_id: str
    file: str
    group: str = ""
    mutation_type: str = ""

    # 六维语义评分（0-1）
    hook_strength: float = 0.0
    gameplay_clarity: float = 0.0          # = Gameplay Understanding 的 pattern 分量 (max of 4 模式)
    gameplay_understanding: float = 0.0    # 融合分 = 0.5*pattern + 0.3*action + 0.2*reward
    merge_visibility: float = 0.0          # 兼容展示用（= merge_score）
    reward_visibility: float = 0.0
    visual_quality: float = 0.0
    commercial_readiness: float = 0.0

    # 多模式玩法理解（2.1.6.1 新增）
    gameplay_type: str = ""                # merge / evolution / collection / reward_reveal
    gameplay_confidence: float = 0.0       # = gameplay_clarity（主导模式分）
    action_visibility: float = 0.0
    ad_structure_score: float = 0.0
    merge_score: float = 0.0
    evolution_score: float = 0.0
    collection_score: float = 0.0
    reward_score: float = 0.0

    # 构图校验（2.1.6.2 Composition Validator 新增）
    composition_match: float = 0.0         # 4 项构图子分融合（0-1）
    character_attention: float = 0.0       # 角色抢主体程度（越低越好，<=0.35 通过）
    gameplay_area_ratio: float = 0.0       # 玩法主体占画面比例（>=0.45 通过）
    state_transition_score: float = 0.0    # before/after 转变分（>=0.70 通过）
    diversity: float = 0.0                 # 批次多样性（1 - 与其它创意平均相似度）

    # 生产就绪总分（加权融合）
    production_score: float = 0.0
    # 与真实 winner 的 CLIP 相似度（0-1）
    clip_similarity: float = 0.0

    # AI 伪影检测（0-1，越高越脏）
    ai_artifact_score: float = 0.0

    # 视觉基础检查
    aspect_ratio: float = 0.0
    aspect_ok: bool = True
    reward_area_ratio: float = 0.0

    decision: str = "FAIL"      # PASS / FAIL / CONDITIONAL
    hard_reject_reason: str = ""  # 若触发 Hard Reject，记录原因
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GateResult:
    """整批审核的总结果。"""

    total: int = 0
    approved: int = 0
    rejected: int = 0
    conditional: int = 0
    avg_production_score: float = 0.0
    checks: dict[str, bool] = field(default_factory=dict)  # 9 项验收
    produced_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
